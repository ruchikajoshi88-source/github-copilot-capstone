from __future__ import annotations

from typing import Any, Dict


class MarkdownConnector:
    def sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not payload.get("job_id") or not payload.get("event") or payload.get("target") != "markdown":
            return {"status": "invalid", "error": "invalid payload"}

        event = payload.get("event") or {}
        if not event.get("repository"):
            return {"status": "invalid", "error": "missing repository"}

        if not event.get("changed_files"):
            return {"status": "no_change"}

        return {"status": "updated", "target": "markdown"}

    execute = sync
    publish = sync
