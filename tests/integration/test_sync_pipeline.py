from __future__ import annotations

import pytest


@pytest.mark.integration
def test_sync_pipeline_happy_path(integration_services: dict, integration_event: dict, integration_headers: dict) -> None:
    ingestion = integration_services["ingestion"]
    orchestrator = integration_services["orchestrator"]
    worker = integration_services["worker"]

    ingest_result = ingestion.handle_event(integration_event, integration_headers)
    assert ingest_result["status"] in {"accepted", "queued", "ok", "processed"}

    orchestration_result = orchestrator.create_job(integration_event)
    assert orchestration_result["status"] in {"queued", "accepted", "ok", "created"}

    job = orchestration_result["job"]
    worker_result = worker.process_job(job)
    assert worker_result["status"] in {"completed", "success", "ok", "partial"}


@pytest.mark.integration
def test_sync_pipeline_rejects_invalid_event(integration_services: dict, integration_headers: dict) -> None:
    ingestion = integration_services["ingestion"]
    invalid_event = {
        "event_type": "merge_completed",
        "repository": "",
        "branch": "main",
        "merge_sha": "integration-sha-002",
        "changed_files": [],
    }

    result = ingestion.handle_event(invalid_event, integration_headers)
    assert result["status"] in {"error", "failed", "invalid"}
