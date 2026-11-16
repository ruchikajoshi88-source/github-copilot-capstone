import asyncio
from dataclasses import replace
import hashlib
import hmac
import json
import time

import httpx

from apps.sync_service.orchestrator import SyncOrchestrator
from apps.sync_service.persistence.sqlite_store import SqliteSyncState
from apps.sync_service.reliability.dlq import JsonlDlqStore
from apps.sync_service.reliability.retry import RetryConfig
from apps.sync_service.webhook import MAX_BODY_BYTES, create_app
from shared.config.settings import RetryPolicy, Settings


SECRET = "test-webhook-secret"


class SyncASGIClient:
    def __init__(self, app):
        self._app = app

    def post(self, path, **kwargs):
        async def send():
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.post(path, **kwargs)

        return asyncio.run(send())


def _settings(tmp_path, source_root):
    return Settings(
        repository_id="repo-1",
        source_root=str(source_root),
        database_path=str(tmp_path / "state.sqlite3"),
        include_patterns=("**/*.md",),
        exclude_patterns=(),
        retry_policy=RetryPolicy(max_attempts=1, base_delay_ms=0, max_delay_ms=0),
    )


def _signed_request(client, payload, timestamp=None, secret=SECRET):
    timestamp = int(time.time()) if timestamp is None else timestamp
    body = json.dumps(payload, separators=(",", ":")).encode()
    digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhooks/docsync",
        content=body,
        headers={"X-DocSync-Signature": f"t={timestamp},v1={digest}", "Content-Type": "application/json"},
    )


def _event(event_id="evt-1", paths=None):
    return {
        "event_id": event_id,
        "repository_id": "repo-1",
        "changed_paths": paths if paths is not None else ["a.md"],
    }


def _build_client(tmp_path, docs, dlq=None, state=None, settings=None):
    settings = settings or _settings(tmp_path, docs)
    state = state or SqliteSyncState(settings.database_path)
    worker = SyncOrchestrator(
        target=state,
        idempotency_store=state,
        event_ledger=state,
        dlq_store=dlq or JsonlDlqStore(tmp_path / "dlq.jsonl"),
        retry_config=RetryConfig(max_attempts=1, base_delay_ms=0, max_delay_ms=0),
    )
    return SyncASGIClient(create_app(settings, SECRET, worker)), state


def _write_doc(path):
    path.write_text(
        "---\ntitle: A\nsource_path: a.md\nversion: v1\nlast_updated: 2026-09-07\n---\n# body\n",
        encoding="utf-8",
    )


def test_signed_event_scopes_work_and_duplicate_is_acknowledged(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_doc(docs / "a.md")
    client, state = _build_client(tmp_path, docs)

    response = _signed_request(client, _event(paths=["a.md", "gone.md"]))
    assert response.status_code == 200
    assert response.json()["succeeded"] == 1
    assert response.json()["failed"] == 1
    assert len(state.all_documents()) == 1
    dlq = tmp_path / "dlq.jsonl"
    assert len(dlq.read_text(encoding="utf-8").splitlines()) == 1

    duplicate = _signed_request(client, _event(paths=["a.md", "gone.md"]))
    assert duplicate.status_code == 200
    assert duplicate.json()["processed"] == 0
    assert len(dlq.read_text(encoding="utf-8").splitlines()) == 1


def test_webhook_rejects_bad_signature_stale_timestamp_and_unsafe_paths(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    client, state = _build_client(tmp_path, docs)

    assert _signed_request(client, _event(), secret="wrong").status_code == 401
    assert _signed_request(client, _event("stale"), timestamp=int(time.time()) - 301).status_code == 401
    assert _signed_request(client, _event("unsafe", ["../outside.md"])).status_code == 400
    assert _signed_request(client, _event("drive", ["C:/outside.md"])).status_code == 400
    assert state.seen("evt-1") is False


def test_webhook_enforces_body_and_path_count_limits(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    client, _state = _build_client(tmp_path, docs)

    oversized = b"x" * (MAX_BODY_BYTES + 1)
    assert client.post("/webhooks/docsync", content=oversized).status_code == 413
    assert _signed_request(client, _event("many", [f"{i}.md" for i in range(101)])).status_code == 400
    assert _signed_request(client, _event("wrong-repo") | {"repository_id": "other"}).status_code == 400


def test_webhook_rejects_paths_excluded_from_sync_scope(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    settings = replace(_settings(tmp_path, docs), exclude_patterns=("private/**",))
    client, _state = _build_client(tmp_path, docs, settings=settings)

    assert _signed_request(client, _event("excluded", ["private/notes.md"])).status_code == 400


def test_dlq_persistence_failure_returns_retryable_server_error(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()

    class BrokenDlq:
        def push(self, _record):
            raise OSError("disk unavailable")

    client, state = _build_client(tmp_path, docs, dlq=BrokenDlq())
    response = _signed_request(client, _event(paths=["missing.md"]))

    assert response.status_code == 503
    assert state.seen("evt-1") is False
    assert state.claim_event("evt-1") is True
