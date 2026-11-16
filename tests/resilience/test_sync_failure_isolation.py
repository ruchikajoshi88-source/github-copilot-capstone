import json
from pathlib import Path

from apps.sync_service.idempotency.store import InMemoryEventLedger, InMemoryIdempotencyStore
from apps.sync_service.orchestrator import SyncOrchestrator
from apps.sync_service.reliability.dlq import JsonlDlqStore
from apps.sync_service.reliability.retry import RetryConfig
from apps.sync_service.target.mock_registry import MockRegistryTarget
from shared.errors.exceptions import ConnectorTransientError


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_missing_paths_and_missing_frontmatter_fail_but_other_paths_continue(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    _write(docs / "missing-metadata.md", "# no metadata\n")
    _write(
        docs / "valid.md",
        "---\ntitle: Valid\nsource_path: valid.md\nversion: v1\nlast_updated: 2026-09-07\n---\n# valid\n",
    )
    dlq = tmp_path / "dlq.jsonl"
    orchestrator = SyncOrchestrator(
        target=MockRegistryTarget(),
        idempotency_store=InMemoryIdempotencyStore(),
        event_ledger=InMemoryEventLedger(),
        dlq_store=JsonlDlqStore(dlq),
        retry_config=RetryConfig(max_attempts=1, base_delay_ms=0, max_delay_ms=0),
    )

    summary = orchestrator.run(
        "repo",
        str(docs),
        ("**/*.md",),
        (),
        trigger_type="event",
        event_id="evt-isolation",
        path_scope=("missing.md", "missing-metadata.md", "valid.md"),
    )

    assert summary.discovered_count == 3
    assert summary.processed_count == 3
    assert summary.succeeded_count == 1
    assert summary.failed_count == 2
    records = [json.loads(line) for line in dlq.read_text(encoding="utf-8").splitlines()]
    assert {record["source_path"] for record in records} == {"missing.md", "missing-metadata.md"}
    assert all(record["run_id"] == summary.run_id for record in records)


def test_diagnostics_redact_secret_values_before_dlq_write(tmp_path, monkeypatch):
    monkeypatch.setenv("VENDOR_ACCESS_TOKEN", "local-test-secret-value")
    docs = tmp_path / "docs"
    docs.mkdir()
    _write(
        docs / "valid.md",
        "---\ntitle: Valid\nsource_path: valid.md\nversion: v1\nlast_updated: 2026-09-07\n---\n# valid\n",
    )
    dlq = tmp_path / "dlq.jsonl"

    class SecretBearingTarget(MockRegistryTarget):
        def upsert(self, _document):
            raise ConnectorTransientError("request failed Authorization: Bearer local-test-secret-value")

    orchestrator = SyncOrchestrator(
        target=SecretBearingTarget(),
        idempotency_store=InMemoryIdempotencyStore(),
        event_ledger=InMemoryEventLedger(),
        dlq_store=JsonlDlqStore(dlq),
        retry_config=RetryConfig(max_attempts=1, base_delay_ms=0, max_delay_ms=0),
    )
    orchestrator.run("repo", str(docs), ("**/*.md",), (), trigger_type="cli")
    record = json.loads(dlq.read_text(encoding="utf-8").strip())
    assert "local-test-secret-value" not in record["error_message"]
    assert "<redacted>" in record["error_message"]
