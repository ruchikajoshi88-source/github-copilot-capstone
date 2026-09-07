from pathlib import Path

from apps.sync_service.idempotency.store import InMemoryEventLedger, InMemoryIdempotencyStore
from apps.sync_service.orchestrator import SyncOrchestrator
from apps.sync_service.reliability.dlq import JsonlDlqStore
from apps.sync_service.reliability.retry import RetryConfig
from apps.sync_service.target.mock_registry import MockRegistryTarget


def _write_doc(path: Path, title: str, version: str = "v1") -> None:
    path.write_text(
        "---\n"
        f"title: {title}\n"
        f"source_path: {path.name}\n"
        f"version: {version}\n"
        "last_updated: 2026-09-07\n"
        "---\n"
        "# body\n",
        encoding="utf-8",
    )


def _build_orchestrator(tmp_path: Path) -> tuple[SyncOrchestrator, MockRegistryTarget]:
    target = MockRegistryTarget()
    orchestrator = SyncOrchestrator(
        target=target,
        idempotency_store=InMemoryIdempotencyStore(),
        event_ledger=InMemoryEventLedger(),
        dlq_store=JsonlDlqStore(tmp_path / "dlq.jsonl"),
        retry_config=RetryConfig(max_attempts=3, base_delay_ms=1, max_delay_ms=2),
    )
    return orchestrator, target


def test_orchestrator_sync_and_idempotent_skip(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_doc(docs / "a.md", "Doc A")

    orchestrator, target = _build_orchestrator(tmp_path)

    first = orchestrator.run("repo", str(docs), ("**/*.md",), (), trigger_type="cli")
    second = orchestrator.run("repo", str(docs), ("**/*.md",), (), trigger_type="cli")

    assert first.succeeded_count == 1
    assert second.skipped_count == 1
    assert len(target.all_documents()) == 1


def test_orchestrator_path_scope(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_doc(docs / "a.md", "Doc A")
    _write_doc(docs / "b.md", "Doc B")

    orchestrator, target = _build_orchestrator(tmp_path)

    summary = orchestrator.run(
        "repo",
        str(docs),
        ("**/*.md",),
        (),
        trigger_type="cli",
        path_scope=("b.md",),
    )

    assert summary.discovered_count == 1
    assert summary.succeeded_count == 1
    assert target.all_documents()[0].source_path == "b.md"


def test_orchestrator_event_dedup(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_doc(docs / "a.md", "Doc A")

    orchestrator, _target = _build_orchestrator(tmp_path)

    first = orchestrator.run("repo", str(docs), ("**/*.md",), (), trigger_type="event", event_id="evt-1")
    second = orchestrator.run("repo", str(docs), ("**/*.md",), (), trigger_type="event", event_id="evt-1")

    assert first.processed_count == 1
    assert second.processed_count == 0
