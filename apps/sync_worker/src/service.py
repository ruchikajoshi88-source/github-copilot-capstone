from __future__ import annotations

from typing import Any, Dict

from connectors.confluence_connector.src.connector import ConfluenceConnector
from connectors.generated_docs_connector.src.connector import GeneratedDocsConnector
from connectors.markdown_connector.src.connector import MarkdownConnector


class ConnectorManager:
    def __init__(self) -> None:
        self._connectors = {
            "markdown": MarkdownConnector(),
            "confluence": ConfluenceConnector(),
            "generated_docs": GeneratedDocsConnector(),
        }

    def execute(self, target: str, job: Dict[str, Any]) -> Dict[str, Any]:
        connector = self._connectors.get(target)
        if connector is None:
            return {"status": "failed", "error": f"unknown target {target}"}

        payload = {
            "job_id": job.get("job_id"),
            "target": target,
            "event": job.get("event"),
        }
        return connector.sync(payload)


class SyncWorker:
    def __init__(self) -> None:
        self.connector_manager = ConnectorManager()

    def invoke_connector(self, target: str, job: Dict[str, Any]) -> Dict[str, Any]:
        return self.connector_manager.execute(target, job)

    def process_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        if not job.get("job_id") or not job.get("event") or not job.get("targets"):
            return {"status": "invalid", "error": "job requires job_id, event, and targets"}

        statuses: list[str] = []
        try:
            for target in job["targets"]:
                result = self.invoke_connector(target, job)
                statuses.append(str(result.get("status", "failed")).lower())
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

        if all(s in {"success", "updated", "completed", "ok"} for s in statuses):
            return {"status": "completed", "targets": statuses}

        if any(s in {"success", "updated", "completed", "ok"} for s in statuses):
            return {"status": "partial", "targets": statuses}

        if all(s in {"skipped", "no_change"} for s in statuses):
            return {"status": "completed", "targets": statuses}

        return {"status": "failed", "targets": statuses}

    handle_job = process_job
    run_job = process_job
