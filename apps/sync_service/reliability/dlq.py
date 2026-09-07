from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DlqRecord:
    run_id: str
    trigger_type: str
    source_path: str
    error_class: str
    error_message: str
    document_key: str | None = None
    event_id: str | None = None
    attempt_count: int = 0


class JsonlDlqStore:
    """Append-only JSONL dead-letter store for unrecoverable per-file failures."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def push(self, record: DlqRecord) -> None:
        payload: dict[str, Any] = {
            "run_id": record.run_id,
            "trigger_type": record.trigger_type,
            "source_path": record.source_path,
            "error_class": record.error_class,
            "error_message": record.error_message,
            "document_key": record.document_key,
            "event_id": record.event_id,
            "attempt_count": record.attempt_count,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True))
            fh.write("\n")
