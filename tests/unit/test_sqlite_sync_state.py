import sqlite3

import pytest

from apps.sync_service.persistence.sqlite_store import SqliteSyncState
from shared.contracts.document import CanonicalDocument, SyncStatus
from shared.errors.exceptions import EventInProgressError, PersistenceError


def _document(content: str = "body") -> CanonicalDocument:
    return CanonicalDocument(
        key="repo:docs/a.md",
        repository_id="repo",
        source_path="docs/a.md",
        metadata={"title": "A"},
        content_markdown=content,
        checksum=f"sha-{content}",
        version="v1",
    )


def test_target_and_checksum_survive_database_reopen(tmp_path):
    database = tmp_path / "state.sqlite3"
    first = SqliteSyncState(database)
    assert first.upsert_if_changed(_document()) == SyncStatus.CREATED

    reopened = SqliteSyncState(database)
    assert reopened.should_write("repo:docs/a.md", "sha-body") is False
    assert reopened.upsert_if_changed(_document()) == SyncStatus.NO_CHANGE
    assert reopened.upsert_if_changed(_document("changed")) == SyncStatus.UPDATED
    assert reopened.get("repo:docs/a.md").content_markdown == "changed"


def test_target_failure_does_not_advance_checksum_or_document(tmp_path, monkeypatch):
    state = SqliteSyncState(tmp_path / "state.sqlite3")

    def fail(_connection, _document):
        raise sqlite3.OperationalError("simulated write failure")

    monkeypatch.setattr(SqliteSyncState, "_upsert", staticmethod(fail))
    with pytest.raises(PersistenceError, match="atomically update"):
        state.upsert_if_changed(_document())

    reopened = SqliteSyncState(tmp_path / "state.sqlite3")
    assert reopened.get("repo:docs/a.md") is None
    assert reopened.should_write("repo:docs/a.md", "sha-body") is True


def test_event_ledger_rejects_active_duplicate_and_releases_retry(tmp_path):
    state = SqliteSyncState(tmp_path / "state.sqlite3")
    assert state.claim_event("evt-1") is True
    with pytest.raises(EventInProgressError):
        state.claim_event("evt-1")

    state.mark_retryable("evt-1")
    assert state.claim_event("evt-1") is True
    state.mark_processed("evt-1")
    assert state.seen("evt-1") is True
    assert state.claim_event("evt-1") is False
