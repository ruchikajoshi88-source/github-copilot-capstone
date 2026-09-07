from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import uuid

from apps.sync_service.canonicalize import build_canonical_document
from apps.sync_service.idempotency.store import InMemoryEventLedger, InMemoryIdempotencyStore
from apps.sync_service.parser.frontmatter import parse_markdown_with_frontmatter
from apps.sync_service.reliability.dlq import DlqRecord, JsonlDlqStore
from apps.sync_service.reliability.retry import RetryConfig, with_retry
from apps.sync_service.source.scanner import discover_markdown_files
from apps.sync_service.target.mock_registry import MockRegistryTarget
from shared.contracts.document import SyncStatus
from shared.errors.exceptions import SyncError, ValidationError


REQUIRED_FRONTMATTER_FIELDS = ("title", "source_path", "version", "last_updated")


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


def _validate_required_metadata(metadata: dict[str, object], source_path: str) -> None:
    missing = [field for field in REQUIRED_FRONTMATTER_FIELDS if not metadata.get(field)]
    if missing:
        raise ValidationError(
            "Missing required frontmatter fields",
            {"source_path": source_path, "missing": ",".join(missing)},
        )


class SyncOrchestrator:
    """Coordinates source discovery, parsing, idempotency, and target writes."""

    def __init__(
        self,
        target: MockRegistryTarget,
        idempotency_store: InMemoryIdempotencyStore,
        event_ledger: InMemoryEventLedger,
        dlq_store: JsonlDlqStore,
        retry_config: RetryConfig,
    ) -> None:
        self._target = target
        self._idempotency_store = idempotency_store
        self._event_ledger = event_ledger
        self._dlq_store = dlq_store
        self._retry_config = retry_config

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
        run_id = str(uuid.uuid4())

        if self._event_ledger.seen(event_id):
            return RunSummary(run_id, trigger_type, 0, 0, 0, 0, 0, 0)

        discovered = discover_markdown_files(source_root, include_patterns, exclude_patterns)
        if path_scope:
            discovered = [item for item in discovered if item.relative_path in set(path_scope)]

        processed = 0
        succeeded = 0
        skipped = 0
        failed = 0
        retries = 0

        for source_file in discovered:
            processed += 1
            try:
                parsed = parse_markdown_with_frontmatter(source_file.absolute_path)
                _validate_required_metadata(parsed.metadata, source_file.relative_path)

                canonical = build_canonical_document(
                    repository_id=repository_id,
                    source_path=source_file.relative_path,
                    metadata=parsed.metadata,
                    content_markdown=parsed.body,
                )

                if not self._idempotency_store.should_write(canonical.key, canonical.checksum):
                    skipped += 1
                    continue

                def write_operation() -> SyncStatus:
                    return self._target.upsert(canonical)

                _status, write_retries = with_retry(write_operation, self._retry_config)
                retries += write_retries
                self._idempotency_store.mark_success(canonical.key, canonical.checksum)
                succeeded += 1
            except SyncError as exc:
                failed += 1
                self._dlq_store.push(
                    DlqRecord(
                        run_id=run_id,
                        trigger_type=trigger_type,
                        event_id=event_id,
                        source_path=source_file.relative_path,
                        error_class=exc.code.value,
                        error_message=exc.message,
                    )
                )
            except Exception as exc:  # defensive catch for unexpected runtime errors
                failed += 1
                self._dlq_store.push(
                    DlqRecord(
                        run_id=run_id,
                        trigger_type=trigger_type,
                        event_id=event_id,
                        source_path=source_file.relative_path,
                        error_class="unexpected_error",
                        error_message=str(exc),
                    )
                )

        self._event_ledger.mark_processed(event_id)
        return RunSummary(
            run_id=run_id,
            trigger_type=trigger_type,
            discovered_count=len(discovered),
            processed_count=processed,
            succeeded_count=succeeded,
            skipped_count=skipped,
            failed_count=failed,
            retry_count=retries,
        )
