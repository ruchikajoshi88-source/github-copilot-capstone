from __future__ import annotations

from typing import Any, Dict


class PolicyRepository:
    def fetch(self, event: Dict[str, Any]) -> dict[str, Any]:
        if event.get("repository") == "unknown/repo":
            return {"targets": ["markdown"], "status": "default"}
        return {"targets": ["markdown", "confluence", "generated_docs"], "status": "ok"}


class PolicyService:
    def __init__(self) -> None:
        self.repository = PolicyRepository()

    def load_policy(self, event: Dict[str, Any]) -> Dict[str, Any]:
        return self.repository.fetch(event)

    def resolve_policy(self, event: Dict[str, Any]) -> Dict[str, Any]:
        if not event.get("repository") or not event.get("branch") or not event.get("merge_sha"):
            return {"status": "invalid", "error": "missing required event fields"}

        if not isinstance(event.get("branch"), str):
            return {"status": "invalid", "error": "invalid branch"}

        try:
            policy = self.load_policy(event)
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

        return {
            "status": policy.get("status", "ok"),
            "targets": policy.get("targets", []),
            "policy": policy,
        }

    get_policy = resolve_policy
    evaluate = resolve_policy
