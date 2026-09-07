from pathlib import Path

from apps.sync_service.idempotency.store import InMemoryEventLedger, InMemoryIdempotencyStore
from apps.sync_service.orchestrator import SyncOrchestrator
from apps.sync_service.reliability.dlq import JsonlDlqStore
from apps.sync_service.reliability.retry import RetryConfig
from apps.sync_service.target.mock_registry import MockRegistryTarget
from shared.errors.exceptions import RateLimitedError


class AlwaysRateLimitedTarget(MockRegistryTarget):
    def upsert(self, document):
        raise RateLimitedError("throttled")


def test_retry_exhaustion_writes_dlq(tmp_path: Path, monkeypatch) -> None:
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

    monkeypatch.setattr("apps.sync_service.reliability.retry.time.sleep", lambda _: None)

    dlq_path = tmp_path / "dlq.jsonl"
    orchestrator = SyncOrchestrator(
        target=AlwaysRateLimitedTarget(),
        idempotency_store=InMemoryIdempotencyStore(),
        event_ledger=InMemoryEventLedger(),
        dlq_store=JsonlDlqStore(dlq_path),
        retry_config=RetryConfig(max_attempts=2, base_delay_ms=1, max_delay_ms=2),
    )

    summary = orchestrator.run("repo", str(docs), ("**/*.md",), (), trigger_type="cli")

    assert summary.failed_count == 1
    assert dlq_path.exists()
    lines = dlq_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
