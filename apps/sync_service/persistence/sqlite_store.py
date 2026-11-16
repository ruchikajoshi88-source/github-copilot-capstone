from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import time
from contextlib import contextmanager
from collections.abc import Iterator

from shared.contracts.document import CanonicalDocument, SyncStatus
from shared.errors.exceptions import EventInProgressError, PersistenceError


EVENT_LEASE_SECONDS = 300


class SqliteSyncState:
    """Local mock target, checksum ledger, and event ledger in one SQLite file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize()
            if os.name != "nt":
                self.path.chmod(0o600)
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("Unable to initialize sync state database") from exc

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    key TEXT PRIMARY KEY,
                    repository_id TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    content_markdown TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    version TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    claimed_at REAL NOT NULL
                );
                """
            )

    @staticmethod
    def _document(row: sqlite3.Row | None) -> CanonicalDocument | None:
        if row is None:
            return None
        return CanonicalDocument(
            key=row["key"],
            repository_id=row["repository_id"],
            source_path=row["source_path"],
            metadata=json.loads(row["metadata_json"]),
            content_markdown=row["content_markdown"],
            checksum=row["checksum"],
            version=row["version"],
        )

    def get(self, key: str) -> CanonicalDocument | None:
        try:
            with self._connection() as connection:
                row = connection.execute("SELECT * FROM documents WHERE key = ?", (key,)).fetchone()
                return self._document(row)
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise PersistenceError("Unable to read sync target state") from exc

    def all_documents(self) -> list[CanonicalDocument]:
        try:
            with self._connection() as connection:
                rows = connection.execute("SELECT * FROM documents ORDER BY key").fetchall()
                return [self._document(row) for row in rows if row is not None]
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise PersistenceError("Unable to read sync target state") from exc

    @staticmethod
    def _upsert(connection: sqlite3.Connection, document: CanonicalDocument) -> None:
        connection.execute(
            """
            INSERT INTO documents
                (key, repository_id, source_path, metadata_json, content_markdown, checksum, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                repository_id = excluded.repository_id,
                source_path = excluded.source_path,
                metadata_json = excluded.metadata_json,
                content_markdown = excluded.content_markdown,
                checksum = excluded.checksum,
                version = excluded.version
            """,
            (
                document.key,
                document.repository_id,
                document.source_path,
                json.dumps(document.metadata, ensure_ascii=False, sort_keys=True),
                document.content_markdown,
                document.checksum,
                document.version,
            ),
        )

    def upsert_if_changed(self, document: CanonicalDocument) -> SyncStatus:
        """Atomically compare checksum and persist both target and checksum state."""
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                prior = connection.execute(
                    "SELECT checksum FROM documents WHERE key = ?", (document.key,)
                ).fetchone()
                if prior is not None and prior["checksum"] == document.checksum:
                    return SyncStatus.NO_CHANGE
                self._upsert(connection, document)
                return SyncStatus.CREATED if prior is None else SyncStatus.UPDATED
        except sqlite3.Error as exc:
            raise PersistenceError("Unable to atomically update sync target state") from exc

    def upsert(self, document: CanonicalDocument) -> SyncStatus:
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                prior = connection.execute(
                    "SELECT 1 FROM documents WHERE key = ?", (document.key,)
                ).fetchone()
                self._upsert(connection, document)
                return SyncStatus.CREATED if prior is None else SyncStatus.UPDATED
        except sqlite3.Error as exc:
            raise PersistenceError("Unable to update sync target state") from exc

    def should_write(self, key: str, checksum: str) -> bool:
        current = self.get(key)
        return current is None or current.checksum != checksum

    def mark_success(self, key: str, checksum: str) -> None:
        """Compatibility method; durable checksums are committed by upsert_if_changed."""
        current = self.get(key)
        if current is None or current.checksum != checksum:
            raise PersistenceError("Checksum cannot be advanced without an atomic target write")

    def seen(self, event_id: str | None) -> bool:
        if not event_id:
            return False
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT status FROM events WHERE event_id = ?", (event_id,)
                ).fetchone()
                return row is not None and row["status"] == "completed"
        except sqlite3.Error as exc:
            raise PersistenceError("Unable to read webhook event state") from exc

    def claim_event(self, event_id: str) -> bool:
        """Claim a retryable event; return False for completed duplicates."""
        now = time.time()
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT status, claimed_at FROM events WHERE event_id = ?", (event_id,)
                ).fetchone()
                if row is not None and row["status"] == "completed":
                    return False
                if (
                    row is not None
                    and row["status"] == "processing"
                    and now - row["claimed_at"] < EVENT_LEASE_SECONDS
                ):
                    raise EventInProgressError("Webhook event is already being processed")
                connection.execute(
                    """
                    INSERT INTO events(event_id, status, claimed_at) VALUES (?, 'processing', ?)
                    ON CONFLICT(event_id) DO UPDATE SET status = 'processing', claimed_at = excluded.claimed_at
                    """,
                    (event_id, now),
                )
                return True
        except EventInProgressError:
            raise
        except sqlite3.Error as exc:
            raise PersistenceError("Unable to claim webhook event") from exc

    def mark_processed(self, event_id: str | None) -> None:
        if not event_id:
            return
        try:
            with self._connection() as connection:
                result = connection.execute(
                    "UPDATE events SET status = 'completed', claimed_at = ? WHERE event_id = ?",
                    (time.time(), event_id),
                )
                if result.rowcount != 1:
                    raise PersistenceError("Webhook event was not claimed")
        except PersistenceError:
            raise
        except sqlite3.Error as exc:
            raise PersistenceError("Unable to complete webhook event") from exc

    def touch_event(self, event_id: str | None) -> None:
        if not event_id:
            return
        try:
            with self._connection() as connection:
                result = connection.execute(
                    "UPDATE events SET claimed_at = ? WHERE event_id = ? AND status = 'processing'",
                    (time.time(), event_id),
                )
                if result.rowcount != 1:
                    raise PersistenceError("Webhook event processing lease was lost")
        except PersistenceError:
            raise
        except sqlite3.Error as exc:
            raise PersistenceError("Unable to renew webhook event lease") from exc

    def mark_retryable(self, event_id: str | None) -> None:
        if not event_id:
            return
        try:
            with self._connection() as connection:
                connection.execute("DELETE FROM events WHERE event_id = ? AND status = 'processing'", (event_id,))
        except sqlite3.Error as exc:
            raise PersistenceError("Unable to release webhook event for retry") from exc
