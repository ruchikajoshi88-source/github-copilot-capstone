from __future__ import annotations

from typing import Any, Dict


class ConfluenceClient:
    def update(self, _payload: Dict[str, Any]) -> bool:
        return True


class ConfluenceConnector:
    def __init__(self) -> None:
        self.client = ConfluenceClient()

    def _update_remote(self, payload: Dict[str, Any]) -> bool:
        return self.client.update(payload)

    def sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not payload.get("job_id") or not payload.get("event") or payload.get("target") != "confluence":
            return {"status": "invalid", "error": "invalid payload"}

        event = payload.get("event") or {}
        if not event.get("repository"):
            return {"status": "invalid", "error": "missing repository"}

        if not event.get("changed_files"):
            return {"status": "skipped"}

        try:
            self._update_remote(payload)
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

        return {"status": "updated", "target": "confluence"}

    execute = sync
    publish = sync
