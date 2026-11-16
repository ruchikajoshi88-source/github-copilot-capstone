from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path, PurePosixPath
import re
import time
import uuid

from apps.sync_service.canonicalize import build_canonical_document
from apps.sync_service.idempotency.store import InMemoryEventLedger, InMemoryIdempotencyStore
from apps.sync_service.parser.frontmatter import parse_markdown_with_frontmatter
from apps.sync_service.persistence.sqlite_store import SqliteSyncState
from apps.sync_service.reliability.dlq import DlqRecord, JsonlDlqStore
from apps.sync_service.reliability.retry import RetryConfig, is_retryable, with_retry
from apps.sync_service.source.scanner import (
    SourceFile,
    discover_markdown_files,
    is_markdown_path_in_scope,
)
from apps.sync_service.target.mock_registry import MockRegistryTarget
from shared.contracts.document import SyncStatus
from shared.errors.codes import ErrorCode
from shared.errors.exceptions import PersistenceError, SourceAccessError, SyncError, ValidationError


logger = logging.getLogger(__name__)
REQUIRED_FRONTMATTER_FIELDS = ("title", "source_path", "version", "last_updated")
_SENSITIVE_VALUE_RE = re.compile(
    r"(?i)\b(token|secret|password|authorization|api[_-]?key)\b(\s*[:=]\s*)(?:bearer\s+)?([^\s,;]+)"
)


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    trigger_type: str
    discovered_count: int
    processed_count: int
    succeeded_count: int
    skipped_count: int
    failed_count: int
    retry_count: int
    duration_ms: int = 0
    dlq_count: int = 0


def redact_diagnostic(message: str) -> str:
    """Redact common inline secrets and values of secret-like environment variables."""
    sanitized = _SENSITIVE_VALUE_RE.sub(r"\1\2<redacted>", message)
    import os

    for name, value in os.environ.items():
        if any(part in name.lower() for part in ("token", "secret", "password", "api_key")) and value:
            sanitized = sanitized.replace(value, "<redacted>")
    return sanitized[:2000]


def _validate_required_metadata(metadata: dict[str, object], source_path: str) -> None:
    missing = [field for field in REQUIRED_FRONTMATTER_FIELDS if not metadata.get(field)]
    if missing:
        raise ValidationError(
            "Missing required frontmatter fields",
            {"source_path": source_path, "missing": ",".join(missing)},
        )


def _safe_scope_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or ":" in value
        or any(ord(char) < 32 for char in value)
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in value.split("/"))
        or path.suffix != ".md"
    ):
        raise ValidationError("Invalid repository-relative Markdown path", {"source_path": value[:200]})
    return path.as_posix()


class SyncOrchestrator:
    """Coordinates source discovery, parsing, idempotency, and target writes."""

    def __init__(
        self,
        target: MockRegistryTarget | SqliteSyncState,
        idempotency_store: InMemoryIdempotencyStore | SqliteSyncState,
        event_ledger: InMemoryEventLedger | SqliteSyncState,
        dlq_store: JsonlDlqStore,
        retry_config: RetryConfig,
    ) -> None:
        self._target = target
        self._idempotency_store = idempotency_store
        self._event_ledger = event_ledger
        self._dlq_store = dlq_store
        self._retry_config = retry_config

    def _record_failure(
        self,
        *,
        run_id: str,
        trigger_type: str,
        event_id: str | None,
        source_path: str,
        error_class: str,
        error_code: str,
        error_message: str,
        document_key: str | None = None,
        attempt_count: int = 0,
    ) -> None:
        record = DlqRecord(
            run_id=run_id,
            trigger_type=trigger_type,
            event_id=event_id,
            source_path=source_path,
            document_key=document_key,
            error_class=error_class,
            error_code=error_code,
            error_message=redact_diagnostic(error_message),
            attempt_count=attempt_count,
        )
        try:
            self._dlq_store.push(record)
        except Exception as exc:
            raise PersistenceError("Unable to durably record per-file failure") from exc

    def _scoped_files(
        self,
        discovered: list[SourceFile],
        source_root: str,
        path_scope: tuple[str, ...] | None,
        include_patterns: tuple[str, ...],
        exclude_patterns: tuple[str, ...],
    ) -> list[SourceFile]:
        if path_scope is None:
            return discovered
        by_path = {item.relative_path: item for item in discovered}
        root = Path(source_root).resolve()
        selected: dict[str, SourceFile] = {}
        for requested in path_scope:
            relative = _safe_scope_path(requested)
            if not is_markdown_path_in_scope(relative, include_patterns, exclude_patterns):
                raise ValidationError(
                    "Requested source path is outside configured include/exclude scope",
                    {"source_path": relative},
                )
            existing = by_path.get(relative)
            if existing is not None:
                try:
                    existing.absolute_path.resolve().relative_to(root)
                except ValueError as exc:
                    raise ValidationError("Source path resolves outside source root") from exc
                selected[relative] = existing
            else:
                candidate = root / relative
                try:
                    candidate.resolve().relative_to(root)
                except ValueError as exc:
                    raise ValidationError("Requested source path resolves outside source root") from exc
                selected[relative] = SourceFile(candidate, relative, 0)
        return [selected[key] for key in sorted(selected)]

    def run(
        self,
        repository_id: str,
        source_root: str,
        include_patterns: tuple[str, ...],
        exclude_patterns: tuple[str, ...],
        trigger_type: str,
        event_id: str | None = None,
        path_scope: tuple[str, ...] | None = None,
    ) -> RunSummary:
        started = time.monotonic()
        run_id = str(uuid.uuid4())
        if event_id and hasattr(self._event_ledger, "claim_event"):
            if not self._event_ledger.claim_event(event_id):
                return RunSummary(run_id, trigger_type, 0, 0, 0, 0, 0, 0)
        elif self._event_ledger.seen(event_id):
            return RunSummary(run_id, trigger_type, 0, 0, 0, 0, 0, 0)

        try:
            discovered = discover_markdown_files(source_root, include_patterns, exclude_patterns)
            selected = self._scoped_files(
                discovered,
                source_root,
                path_scope,
                include_patterns,
                exclude_patterns,
            )

            processed = succeeded = skipped = failed = retries = dlq_count = 0
            for source_file in selected:
                if event_id and hasattr(self._event_ledger, "touch_event"):
                    self._event_ledger.touch_event(event_id)
                processed += 1
                document_key: str | None = None
                attempt_count = 0
                try:
                    if source_file.discovery_error:
                        raise SourceAccessError(
                            source_file.discovery_error,
                            {"source_path": source_file.relative_path},
                        )
                    parsed = parse_markdown_with_frontmatter(source_file.absolute_path)
                    _validate_required_metadata(parsed.metadata, source_file.relative_path)
                    canonical = build_canonical_document(
                        repository_id=repository_id,
                        source_path=source_file.relative_path,
                        metadata=parsed.metadata,
                        content_markdown=parsed.body,
                    )
                    document_key = canonical.key
                    if hasattr(self._target, "upsert_if_changed"):
                        status = self._target.upsert_if_changed(canonical)
                        if status == SyncStatus.NO_CHANGE:
                            skipped += 1
                            logger.info(json.dumps({
                                "event": "document_skipped",
                                "run_id": run_id,
                                "document_key": document_key,
                                "source_path": source_file.relative_path,
                                "error_class": None,
                                "retry_count": 0,
                            }))
                            continue
                        succeeded += 1
                    else:
                        if not self._idempotency_store.should_write(canonical.key, canonical.checksum):
                            skipped += 1
                            continue

                        def write_operation() -> SyncStatus:
                            nonlocal attempt_count
                            attempt_count += 1
                            return self._target.upsert(canonical)

                        _status, write_retries = with_retry(write_operation, self._retry_config)
                        retries += write_retries
                        self._idempotency_store.mark_success(canonical.key, canonical.checksum)
                        succeeded += 1
                    logger.info(json.dumps({
                        "event": "document_synchronized",
                        "run_id": run_id,
                        "document_key": document_key,
                        "source_path": source_file.relative_path,
                        "error_class": None,
                        "retry_count": max(0, attempt_count - 1),
                    }))
                    if event_id and hasattr(self._event_ledger, "touch_event"):
                        self._event_ledger.touch_event(event_id)
                except SyncError as exc:
                    if isinstance(exc, PersistenceError):
                        raise
                    failed += 1
                    if attempt_count:
                        retries += max(0, attempt_count - 1)
                    exhausted = attempt_count >= self._retry_config.max_attempts and is_retryable(exc)
                    error_class = "retry_exhausted" if exhausted else exc.code.value
                    error_message = (
                        f"Retry budget exhausted after {attempt_count} attempts: {exc.message}"
                        if exhausted
                        else exc.message
                    )
                    self._record_failure(
                        run_id=run_id,
                        trigger_type=trigger_type,
                        event_id=event_id,
                        source_path=source_file.relative_path,
                        document_key=document_key,
                        error_class=error_class,
                        error_code=ErrorCode.RETRY_EXHAUSTED.value if exhausted else exc.code.value,
                        error_message=error_message,
                        attempt_count=attempt_count,
                    )
                    dlq_count += 1
                    logger.error(json.dumps({
                        "event": "document_failed",
                        "run_id": run_id,
                        "document_key": document_key,
                        "source_path": source_file.relative_path,
                        "error_class": error_class,
                        "reason": redact_diagnostic(error_message),
                        "retry_count": max(0, attempt_count - 1),
                    }))
                    if event_id and hasattr(self._event_ledger, "touch_event"):
                        self._event_ledger.touch_event(event_id)
                except Exception as exc:  # defensive catch for unexpected document-level errors
                    failed += 1
                    message = redact_diagnostic(str(exc))
                    self._record_failure(
                        run_id=run_id,
                        trigger_type=trigger_type,
                        event_id=event_id,
                        source_path=source_file.relative_path,
                        document_key=document_key,
                        error_class="unexpected_error",
                        error_code="unexpected_error",
                        error_message=message,
                        attempt_count=attempt_count,
                    )
                    dlq_count += 1
                    logger.error(json.dumps({
                        "event": "document_failed",
                        "run_id": run_id,
                        "document_key": document_key,
                        "source_path": source_file.relative_path,
                        "error_class": "unexpected_error",
                        "reason": message,
                        "retry_count": max(0, attempt_count - 1),
                    }))
                    if event_id and hasattr(self._event_ledger, "touch_event"):
                        self._event_ledger.touch_event(event_id)

            if event_id:
                self._event_ledger.mark_processed(event_id)
        except Exception:
            if event_id and hasattr(self._event_ledger, "mark_retryable"):
                self._event_ledger.mark_retryable(event_id)
            raise

        duration_ms = int((time.monotonic() - started) * 1000)
        summary = RunSummary(
            run_id=run_id,
            trigger_type=trigger_type,
            discovered_count=len(selected),
            processed_count=processed,
            succeeded_count=succeeded,
            skipped_count=skipped,
            failed_count=failed,
            retry_count=retries,
            duration_ms=duration_ms,
            dlq_count=dlq_count,
        )
        logger.info(json.dumps({
            "event": "sync_run_completed",
            "run_id": run_id,
            "trigger_type": trigger_type,
            "processed": processed,
            "succeeded": succeeded,
            "skipped": skipped,
            "failed": failed,
            "retries": retries,
            "duration_ms": duration_ms,
        }))
        return summary
