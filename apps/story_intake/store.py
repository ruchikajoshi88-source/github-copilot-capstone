from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator

from shared.contracts.story import NormalizedStory
from shared.errors.exceptions import PersistenceError


class StoryRecordStore:
    """Separate local SQLite store; records persist until an explicit delete."""

    def __init__(self, path: str | Path = ".story-intake/records.sqlite3") -> None:
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection() as connection:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS stories (
                        record_id TEXT PRIMARY KEY,
                        source_reference TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        record_json TEXT NOT NULL
                    )"""
                )
            if os.name != "nt":
                self.path.chmod(0o600)
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("Unable to initialize story record store") from exc

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def add(self, story: NormalizedStory) -> None:
        try:
            with self._connection() as connection:
                connection.execute(
                    "INSERT INTO stories(record_id, source_reference, created_at, record_json) VALUES (?, ?, ?, ?)",
                    (
                        story.record_id,
                        story.source_reference,
                        story.created_at,
                        json.dumps(story.to_dict(), ensure_ascii=False, sort_keys=True),
                    ),
                )
        except sqlite3.Error as exc:
            raise PersistenceError("Unable to store normalized story") from exc

    def list_records(self) -> list[dict[str, object]]:
        try:
            with self._connection() as connection:
                rows = connection.execute("SELECT record_json FROM stories ORDER BY created_at, record_id").fetchall()
            return [json.loads(row[0]) for row in rows]
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise PersistenceError("Unable to read normalized story records") from exc

    def delete(self, record_id: str) -> bool:
        try:
            with self._connection() as connection:
                result = connection.execute("DELETE FROM stories WHERE record_id = ?", (record_id,))
                return result.rowcount == 1
        except sqlite3.Error as exc:
            raise PersistenceError("Unable to delete normalized story record") from exc
