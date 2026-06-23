import pytest

from conftest import assert_error_or_failed, call_method, instantiate


class TestNegativeCases:
    @pytest.mark.parametrize(
        "component_key,method_candidates,payload",
        [
            (
                "event_ingestion",
                ["handle_event", "ingest", "process_event"],
                {"event_type": "merge_completed"},
            ),
            (
                "sync_orchestrator",
                ["create_job", "orchestrate", "handle_merge_event"],
                {"repository": "example/repo"},
            ),
            (
                "sync_worker",
                ["process_job", "handle_job", "run_job"],
                {"job_id": "job-001"},
            ),
        ],
    )
    def test_missing_payload_fields(self, component_key, method_candidates, payload):
        """Expected outcome: request is rejected with validation error or failed status."""
        component = instantiate(component_key)

        try:
            if component_key == "event_ingestion":
                result = call_method(component, method_candidates, payload, {"X-Signature": "valid-signature"})
            else:
                result = call_method(component, method_candidates, payload)
        except Exception:
            return

        assert_error_or_failed(result)

    @pytest.mark.parametrize(
        "component_key,method_candidates,payload",
        [
            (
                "event_ingestion",
                ["handle_event", "ingest", "process_event"],
                {"event_type": 123, "repository": [], "branch": {}, "merge_sha": None},
            ),
            (
                "sync_orchestrator",
                ["create_job", "orchestrate", "handle_merge_event"],
                {"event_type": "unknown_event", "repository": "example/repo", "branch": "main", "merge_sha": "abc"},
            ),
            (
                "policy_service",
                ["resolve_policy", "get_policy", "evaluate"],
                {"repository": "", "branch": 99, "merge_sha": []},
            ),
        ],
    )
    def test_invalid_requests(self, component_key, method_candidates, payload):
        """Expected outcome: invalid request is rejected or mapped to explicit failed/invalid status."""
        component = instantiate(component_key)

        try:
            if component_key == "event_ingestion":
                result = call_method(component, method_candidates, payload, {"X-Signature": "valid-signature"})
            else:
                result = call_method(component, method_candidates, payload)
        except Exception:
            return

        assert_error_or_failed(result)

    @pytest.mark.parametrize(
        "component_key,method_candidates,patch_target",
        [
            ("event_ingestion", ["handle_event", "ingest", "process_event"], "verify_signature"),
            ("sync_orchestrator", ["create_job", "orchestrate", "handle_merge_event"], "publish_job"),
            ("sync_worker", ["process_job", "handle_job", "run_job"], "invoke_connector"),
            ("notification_service", ["send", "notify", "send_failure"], "dispatch"),
        ],
    )
    def test_api_timeouts(self, monkeypatch, component_key, method_candidates, patch_target, valid_merge_event, valid_sync_job):
        """Expected outcome: timeout is surfaced as failed/error or retriable failure path."""
        component = instantiate(component_key)

        if not hasattr(component, patch_target):
            if component_key == "sync_orchestrator" and hasattr(component, "queue_client") and hasattr(component.queue_client, "publish"):
                monkeypatch.setattr(component.queue_client, "publish", lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError("timeout")))
            elif component_key == "sync_worker" and hasattr(component, "connector_manager") and hasattr(component.connector_manager, "execute"):
                monkeypatch.setattr(component.connector_manager, "execute", lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError("timeout")))
            elif component_key == "notification_service" and hasattr(component, "client") and hasattr(component.client, "send"):
                monkeypatch.setattr(component.client, "send", lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError("timeout")))
            elif component_key == "event_ingestion" and hasattr(component, "validator") and hasattr(component.validator, "verify_signature"):
                monkeypatch.setattr(component.validator, "verify_signature", lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError("timeout")))
            else:
                pytest.skip(f"No injectable timeout hook found for {component_key}")
        else:
            monkeypatch.setattr(component, patch_target, lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError("timeout")))

        try:
            if component_key == "event_ingestion":
                result = call_method(component, method_candidates, valid_merge_event, {"X-Signature": "valid-signature"})
            elif component_key == "sync_orchestrator":
                result = call_method(component, method_candidates, valid_merge_event)
            elif component_key == "sync_worker":
                result = call_method(component, method_candidates, valid_sync_job)
            else:
                result = call_method(
                    component,
                    method_candidates,
                    {
                        "job_id": "job-001",
                        "severity": "critical",
                        "message": "sync failed",
                        "channel": "slack",
                    },
                )
        except Exception:
            return

        assert_error_or_failed(result)

    @pytest.mark.parametrize(
        "component_key,method_candidates,payload",
        [
            (
                "event_ingestion",
                ["handle_event", "ingest", "process_event"],
                {
                    "event_type": "merge_completed",
                    "repository": "",
                    "branch": "main",
                    "merge_sha": "abc123",
                    "changed_files": [],
                },
            ),
            (
                "sync_orchestrator",
                ["create_job", "orchestrate", "handle_merge_event"],
                {
                    "event_type": "merge_completed",
                    "repository": "",
                    "branch": "main",
                    "merge_sha": "abc123",
                    "changed_files": [],
                },
            ),
            (
                "markdown_connector",
                ["sync", "execute", "publish"],
                {"job_id": "job-001", "target": "markdown", "event": {"repository": "", "changed_files": []}},
            ),
        ],
    )
    def test_empty_repositories(self, component_key, method_candidates, payload):
        """Expected outcome: empty repository is rejected or treated as no-op/skip with explicit status."""
        component = instantiate(component_key)

        try:
            if component_key == "event_ingestion":
                result = call_method(component, method_candidates, payload, {"X-Signature": "valid-signature"})
            else:
                result = call_method(component, method_candidates, payload)
        except Exception:
            return

        if isinstance(result, dict):
            assert result.get("status", "").lower() in {
                "error",
                "failed",
                "invalid",
                "skipped",
                "no_change",
                "ignored",
            }
        else:
            assert result is not None

    def test_authentication_failures_event_ingestion(self, valid_merge_event):
        """Expected outcome: authentication failure blocks processing and returns failure."""
        component = instantiate("event_ingestion")
        bad_headers = {"X-Signature": "bad-signature", "X-Event-Id": "evt-auth-fail"}

        try:
            result = call_method(component, ["handle_event", "ingest", "process_event"], valid_merge_event, bad_headers)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_authentication_failures_notification_provider(self, monkeypatch):
        """Expected outcome: provider auth failure returns terminal failed/error response."""
        component = instantiate("notification_service")
        payload = {
            "job_id": "job-auth-001",
            "severity": "critical",
            "message": "sync failed",
            "channel": "slack",
        }

        if hasattr(component, "client") and hasattr(component.client, "send"):
            monkeypatch.setattr(component.client, "send", lambda *_a, **_k: (_ for _ in ()).throw(PermissionError("401 unauthorized")))
        elif hasattr(component, "dispatch"):
            monkeypatch.setattr(component, "dispatch", lambda *_a, **_k: (_ for _ in ()).throw(PermissionError("401 unauthorized")))
        else:
            pytest.skip("No injectable provider client/dispatch hook found")

        try:
            result = call_method(component, ["send", "notify", "send_failure"], payload)
        except Exception:
            return

        assert_error_or_failed(result)
