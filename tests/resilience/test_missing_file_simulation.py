from pathlib import Path

from apps.sync_service.idempotency.store import InMemoryEventLedger, InMemoryIdempotencyStore
from apps.sync_service.orchestrator import SyncOrchestrator
from apps.sync_service.reliability.dlq import JsonlDlqStore
from apps.sync_service.reliability.retry import RetryConfig
from apps.sync_service.target.mock_registry import MockRegistryTarget
from shared.errors.exceptions import SourceAccessError


def test_missing_file_is_recorded_and_run_continues(tmp_path: Path, monkeypatch) -> None:
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

    def raise_missing(_path: Path):
        raise SourceAccessError("Unable to read source file", {"source_path": "a.md", "cause": "file not found"})

    monkeypatch.setattr("apps.sync_service.orchestrator.parse_markdown_with_frontmatter", raise_missing)

    dlq_path = tmp_path / "dlq.jsonl"
    orchestrator = SyncOrchestrator(
        target=MockRegistryTarget(),
        idempotency_store=InMemoryIdempotencyStore(),
        event_ledger=InMemoryEventLedger(),
        dlq_store=JsonlDlqStore(dlq_path),
        retry_config=RetryConfig(max_attempts=2, base_delay_ms=1, max_delay_ms=2),
    )

    summary = orchestrator.run("repo", str(docs), ("**/*.md",), (), trigger_type="cli")

    assert summary.failed_count == 1
    assert summary.succeeded_count == 0
    assert dlq_path.exists()
