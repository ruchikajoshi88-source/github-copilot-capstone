from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from apps.sync_service.orchestrator import RunSummary, SyncOrchestrator
from apps.sync_service.persistence.sqlite_store import SqliteSyncState
from apps.sync_service.reliability.dlq import JsonlDlqStore
from apps.sync_service.reliability.retry import RetryConfig
from apps.sync_service.source.scanner import is_markdown_path_in_scope
from shared.config.settings import Settings, load_settings_from_env
from shared.errors.exceptions import ConfigError, PersistenceError, ValidationError


MAX_BODY_BYTES = 1024 * 1024
MAX_CHANGED_PATHS = 100
SIGNATURE_RE = re.compile(r"\At=(\d{1,12}),v1=([0-9a-f]{64})\Z")


def _validate_event(
    payload: Any,
    repository_id: str,
    source_root: str,
    include_patterns: tuple[str, ...],
    exclude_patterns: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
    if not isinstance(payload, dict) or set(payload) != {
        "event_id", "repository_id", "changed_paths"
    }:
        raise ValidationError("Invalid webhook event object or fields")
    event_id = payload["event_id"]
    if (
        not isinstance(event_id, str)
        or not event_id.strip()
        or len(event_id) > 200
        or any(ord(char) < 32 for char in event_id)
    ):
        raise ValidationError("event_id must be a non-empty string of at most 200 characters")
    if payload["repository_id"] != repository_id:
        raise ValidationError("repository_id does not match configured repository")
    paths = payload["changed_paths"]
    if not isinstance(paths, list) or len(paths) > MAX_CHANGED_PATHS:
        raise ValidationError(f"changed_paths must be a list of at most {MAX_CHANGED_PATHS} entries")
    normalized: list[str] = []
    for value in paths:
        if not isinstance(value, str):
            raise ValidationError("changed_paths entries must be strings")
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
            raise ValidationError("changed_paths must contain safe repository-relative Markdown paths")
        if not is_markdown_path_in_scope(path.as_posix(), include_patterns, exclude_patterns):
            raise ValidationError("changed_paths contains a path outside configured sync patterns")
        try:
            Path(source_root).resolve().joinpath(*path.parts).resolve().relative_to(Path(source_root).resolve())
        except (ValueError, OSError, RuntimeError) as exc:
            raise ValidationError("changed_paths contains a path resolving outside source root") from exc
        normalized.append(path.as_posix())
    if len(set(normalized)) != len(normalized):
        raise ValidationError("changed_paths entries must be unique")
    return event_id, tuple(normalized)


def _build_orchestrator(settings: Settings) -> SyncOrchestrator:
    state = SqliteSyncState(settings.database_path)
    dlq = JsonlDlqStore(Path(settings.database_path).parent / "dlq.jsonl")
    return SyncOrchestrator(
        target=state,
        idempotency_store=state,
        event_ledger=state,
        dlq_store=dlq,
        retry_config=RetryConfig(
            max_attempts=settings.retry_policy.max_attempts,
            base_delay_ms=settings.retry_policy.base_delay_ms,
            max_delay_ms=settings.retry_policy.max_delay_ms,
        ),
    )


def _summary_json(summary: RunSummary) -> dict[str, int | str]:
    return {
        "run_id": summary.run_id,
        "trigger_type": summary.trigger_type,
        "discovered": summary.discovered_count,
        "processed": summary.processed_count,
        "succeeded": summary.succeeded_count,
        "skipped": summary.skipped_count,
        "failed": summary.failed_count,
        "retries": summary.retry_count,
        "duration_ms": summary.duration_ms,
        "dlq": summary.dlq_count,
    }


def create_app(
    settings: Settings | None = None,
    webhook_secret: str | None = None,
    orchestrator: SyncOrchestrator | None = None,
) -> FastAPI:
    """Create the provider-agnostic webhook service; secrets are never logged."""
    app = FastAPI(title="Automated Documentation Sync Webhook", version="1")
    effective_settings = settings or load_settings_from_env()
    secret = webhook_secret if webhook_secret is not None else os.getenv("SYNC_WEBHOOK_SECRET")
    if not secret:
        raise ConfigError("SYNC_WEBHOOK_SECRET must be configured")
    worker = orchestrator or _build_orchestrator(effective_settings)

    @app.post("/webhooks/docsync")
    async def receive_event(request: Request) -> dict[str, int | str]:
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_BODY_BYTES:
                raise HTTPException(status_code=413, detail={"code": "body_too_large"})
            chunks.append(chunk)
        raw_body = b"".join(chunks)
        header = request.headers.get("X-DocSync-Signature", "")
        match = SIGNATURE_RE.fullmatch(header)
        if match is None:
            raise HTTPException(status_code=401, detail={"code": "invalid_signature"})
        timestamp = int(match.group(1))
        if abs(int(time.time()) - timestamp) > 300:
            raise HTTPException(status_code=401, detail={"code": "stale_signature"})
        expected = hmac.new(
            secret.encode("utf-8"),
            match.group(1).encode("ascii") + b"." + raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, match.group(2)):
            raise HTTPException(status_code=401, detail={"code": "invalid_signature"})
        try:
            payload = json.loads(raw_body)
            event_id, changed_paths = _validate_event(
                payload,
                effective_settings.repository_id,
                effective_settings.source_root,
                effective_settings.include_patterns,
                effective_settings.exclude_patterns,
            )
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
            raise HTTPException(status_code=400, detail={"code": "invalid_event"}) from exc

        try:
            summary = await run_in_threadpool(
                worker.run,
                repository_id=effective_settings.repository_id,
                source_root=effective_settings.source_root,
                include_patterns=effective_settings.include_patterns,
                exclude_patterns=effective_settings.exclude_patterns,
                trigger_type="webhook",
                event_id=event_id,
                path_scope=changed_paths,
            )
        except (PersistenceError, OSError):
            raise HTTPException(status_code=503, detail={"code": "processing_unavailable"})
        except Exception:
            raise HTTPException(status_code=503, detail={"code": "processing_unavailable"})
        return _summary_json(summary)

    return app
