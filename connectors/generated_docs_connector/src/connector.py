from __future__ import annotations

from typing import Any, Dict


class GeneratedDocsConnector:
    def sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not payload.get("job_id") or not payload.get("event") or payload.get("target") != "generated_docs":
            return {"status": "invalid", "error": "invalid payload"}

        event = payload.get("event") or {}
        if not event.get("repository"):
            return {"status": "invalid", "error": "missing repository"}

        if not event.get("changed_files"):
            return {"status": "skipped"}

        return {"status": "updated", "target": "generated_docs"}

    execute = sync
    publish = sync
