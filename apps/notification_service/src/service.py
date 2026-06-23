from __future__ import annotations

from typing import Any, Dict


class NotificationClient:
    def send(self, _payload: Dict[str, Any]) -> bool:
        return True


class NotificationService:
    def __init__(self) -> None:
        self.client = NotificationClient()
        self._dedup_keys: set[str] = set()

    def dispatch(self, payload: Dict[str, Any]) -> bool:
        return self.client.send(payload)

    def send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        required = ("job_id", "severity", "message", "channel")
        if any(not payload.get(field) for field in required):
            return {"status": "invalid", "error": "missing required fields"}

        channel = str(payload.get("channel")).lower()
        if channel not in {"slack", "email", "jira"}:
            return {"status": "invalid", "error": "unknown channel"}

        dedup_key = f"{payload['job_id']}:{channel}:{payload['message']}"
        if dedup_key in self._dedup_keys:
            return {"status": "deduped", "channel": channel}

        try:
            self.dispatch(payload)
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

        self._dedup_keys.add(dedup_key)
        return {"status": "sent", "channel": channel}

    notify = send
    send_failure = send
