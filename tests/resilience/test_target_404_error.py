from pathlib import Path

from apps.sync_service.idempotency.store import InMemoryEventLedger, InMemoryIdempotencyStore
from apps.sync_service.orchestrator import SyncOrchestrator
from apps.sync_service.reliability.dlq import JsonlDlqStore
from apps.sync_service.reliability.retry import RetryConfig
from apps.sync_service.target.mock_registry import MockRegistryTarget
from shared.errors.codes import ErrorCode
from shared.errors.exceptions import SyncError


class NotFoundTarget(MockRegistryTarget):
    def upsert(self, document):
        raise SyncError(ErrorCode.UNEXPECTED_ERROR, "target returned 404 not found")


def test_target_404_is_captured_in_dlq_without_retry(tmp_path: Path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text(
        "---\n"
        "title: A\n"
        "source_path: a.md\n"
        "version: v1\n"
        "last_updated: 2026-09-07\n"
        "---\n"
        "# body\n",
        encoding="utf-8",
    )

    sleep_calls = {"count": 0}

    def fake_sleep(_: float) -> None:
        sleep_calls["count"] += 1

    monkeypatch.setattr("apps.sync_service.reliability.retry.time.sleep", fake_sleep)

    dlq_path = tmp_path / "dlq.jsonl"
    orchestrator = SyncOrchestrator(
        target=NotFoundTarget(),
        idempotency_store=InMemoryIdempotencyStore(),
        event_ledger=InMemoryEventLedger(),
        dlq_store=JsonlDlqStore(dlq_path),
        retry_config=RetryConfig(max_attempts=3, base_delay_ms=1, max_delay_ms=2),
    )

    summary = orchestrator.run("repo", str(docs), ("**/*.md",), (), trigger_type="cli")

    assert summary.failed_count == 1
    assert summary.retry_count == 0
    assert sleep_calls["count"] == 0
    assert dlq_path.exists()
