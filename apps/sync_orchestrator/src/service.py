from __future__ import annotations

from typing import Any, Dict

from apps.sync_orchestrator.src.store import IdempotencyStore


class InMemoryQueueClient:
    def __init__(self) -> None:
        self.published_jobs: list[Dict[str, Any]] = []

    def publish(self, job: Dict[str, Any]) -> None:
        self.published_jobs.append(job)


class SyncOrchestrator:
    def __init__(self) -> None:
        self.queue_client = InMemoryQueueClient()
        self._store = IdempotencyStore()

    def _key(self, event: Dict[str, Any]) -> str:
        return f"{event.get('repository')}:{event.get('branch')}:{event.get('merge_sha')}"

    def publish_job(self, job: Dict[str, Any]) -> None:
        self.queue_client.publish(job)

    def create_job(self, event: Dict[str, Any]) -> Dict[str, Any]:
        required = ("repository", "branch", "merge_sha")
        if any(not event.get(field) for field in required):
            return {"status": "invalid", "error": "missing required event fields"}

        if event.get("event_type") not in {None, "merge_completed"}:
            return {"status": "invalid", "error": "unsupported event type"}

        if event.get("branch") != "main":
            return {"status": "ignored", "reason": "branch not configured"}

        key = self._key(event)
        if self._store.is_processed(key):
            return {"status": "duplicate", "job_id": f"dup-{event.get('merge_sha')}"}

        job = {
            "job_id": f"job-{event.get('merge_sha')}",
            "event": event,
            "targets": ["markdown", "confluence", "generated_docs"],
            "attempt": 1,
        }

        try:
            self.publish_job(job)
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

        self._store.mark_processed(key)
        return {"status": "queued", "job": job, "job_id": job["job_id"]}

    orchestrate = create_job
    handle_merge_event = create_job
