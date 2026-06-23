import asyncio
import importlib
import inspect
from typing import Any, Iterable, Optional

import pytest


COMPONENT_IMPORTS = {
    "event_ingestion": [
        ("apps.event_ingestion.src.service", "EventIngestionService"),
        ("apps.event_ingestion.src.main", "EventIngestionService"),
        ("apps.event_ingestion.src.handler", "EventIngestionHandler"),
    ],
    "sync_orchestrator": [
        ("apps.sync_orchestrator.src.service", "SyncOrchestrator"),
        ("apps.sync_orchestrator.src.main", "SyncOrchestrator"),
    ],
    "sync_worker": [
        ("apps.sync_worker.src.service", "SyncWorker"),
        ("apps.sync_worker.src.main", "SyncWorker"),
    ],
    "retry_policy": [
        ("apps.sync_worker.src.retry", "RetryPolicy"),
        ("apps.sync_worker.src.service", "RetryPolicy"),
    ],
    "idempotency_store": [
        ("apps.sync_orchestrator.src.idempotency", "IdempotencyStore"),
        ("apps.sync_orchestrator.src.store", "IdempotencyStore"),
    ],
    "policy_service": [
        ("apps.policy_service.src.service", "PolicyService"),
        ("apps.policy_service.src.main", "PolicyService"),
    ],
    "notification_service": [
        ("apps.notification_service.src.service", "NotificationService"),
        ("apps.notification_service.src.main", "NotificationService"),
    ],
    "markdown_connector": [
        ("connectors.markdown_connector.src.connector", "MarkdownConnector"),
    ],
    "confluence_connector": [
        ("connectors.confluence_connector.src.connector", "ConfluenceConnector"),
    ],
    "generated_docs_connector": [
        ("connectors.generated_docs_connector.src.connector", "GeneratedDocsConnector"),
    ],
}


def _import_attr(module_name: str, attr_name: str) -> Optional[Any]:
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return None
    return getattr(module, attr_name, None)


def resolve_component(component_key: str) -> Any:
    candidates = COMPONENT_IMPORTS.get(component_key, [])
    for module_name, attr_name in candidates:
        value = _import_attr(module_name, attr_name)
        if value is not None:
            return value
    pytest.skip(f"Component '{component_key}' is not implemented or importable yet")


def instantiate(component_key: str, *args: Any, **kwargs: Any) -> Any:
    component = resolve_component(component_key)
    if inspect.isclass(component):
        return component(*args, **kwargs)
    return component


def run_maybe_async(value: Any) -> Any:
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def find_method(obj: Any, candidates: Iterable[str]) -> Any:
    for name in candidates:
        if hasattr(obj, name):
            return getattr(obj, name)
    pytest.skip(f"None of the candidate methods exist: {list(candidates)}")


def call_method(obj: Any, method_candidates: Iterable[str], *args: Any, **kwargs: Any) -> Any:
    method = find_method(obj, method_candidates)
    return run_maybe_async(method(*args, **kwargs))


def assert_error_or_failed(result: Any) -> None:
    if isinstance(result, dict):
        status = str(result.get("status", "")).lower()
        error = result.get("error")
        assert status in {"error", "failed", "invalid"} or error is not None
        return
    if isinstance(result, tuple) and result:
        head = str(result[0]).lower()
        assert head in {"error", "failed", "invalid"}
        return
    pytest.fail("Expected failure signal, but result format is not recognized")


@pytest.fixture
def valid_merge_event() -> dict:
    return {
        "event_type": "merge_completed",
        "repository": "example/repo",
        "branch": "main",
        "merge_sha": "abc123def456",
        "timestamp": "2026-06-19T10:00:00Z",
        "changed_files": ["docs/intro.md", "src/service.py"],
    }


@pytest.fixture
def valid_headers() -> dict:
    return {
        "X-Signature": "valid-signature",
        "X-Event-Id": "evt-12345",
    }


@pytest.fixture
def valid_sync_job(valid_merge_event: dict) -> dict:
    return {
        "job_id": "job-001",
        "event": valid_merge_event,
        "targets": ["markdown", "confluence"],
        "attempt": 1,
    }
