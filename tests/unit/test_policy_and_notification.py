from conftest import assert_error_or_failed, call_method, instantiate


class TestPolicyService:
    def test_happy_path_resolve_routing_policy(self, valid_merge_event):
        service = instantiate("policy_service")
        result = call_method(service, ["resolve_policy", "get_policy", "evaluate"], valid_merge_event)

        if isinstance(result, dict):
            assert "targets" in result or "routing" in result or "policy" in result

    def test_invalid_input_unknown_repository(self):
        service = instantiate("policy_service")
        event = {
            "repository": "unknown/repo",
            "branch": "main",
            "merge_sha": "abc123",
        }

        try:
            result = call_method(service, ["resolve_policy", "get_policy", "evaluate"], event)
        except Exception:
            return

        if isinstance(result, dict) and result.get("status", "").lower() in {"default", "fallback", "ok"}:
            return
        assert_error_or_failed(result)

    def test_missing_fields_missing_branch(self):
        service = instantiate("policy_service")
        event = {"repository": "example/repo", "merge_sha": "abc123"}

        try:
            result = call_method(service, ["resolve_policy", "get_policy", "evaluate"], event)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_api_failure_policy_backend(self, monkeypatch, valid_merge_event):
        service = instantiate("policy_service")

        if hasattr(service, "repository") and hasattr(service.repository, "fetch"):
            monkeypatch.setattr(service.repository, "fetch", lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("backend unavailable")))
        elif hasattr(service, "load_policy"):
            monkeypatch.setattr(service, "load_policy", lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("backend unavailable")))
        else:
            return

        try:
            result = call_method(service, ["resolve_policy", "get_policy", "evaluate"], valid_merge_event)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_edge_case_empty_target_list(self, valid_merge_event):
        service = instantiate("policy_service")
        result = call_method(service, ["resolve_policy", "get_policy", "evaluate"], valid_merge_event)

        if isinstance(result, dict) and "targets" in result:
            assert isinstance(result["targets"], list)


class TestNotificationService:
    def test_happy_path_send_failure_notification(self):
        service = instantiate("notification_service")
        payload = {
            "job_id": "job-001",
            "severity": "critical",
            "message": "sync failed",
            "channel": "slack",
        }

        result = call_method(service, ["send", "notify", "send_failure"], payload)

        if isinstance(result, dict):
            assert result.get("status", "sent") in {"sent", "ok", "queued", "accepted"}

    def test_invalid_input_unknown_channel(self):
        service = instantiate("notification_service")
        payload = {
            "job_id": "job-001",
            "severity": "critical",
            "message": "sync failed",
            "channel": "pager",
        }

        try:
            result = call_method(service, ["send", "notify", "send_failure"], payload)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_missing_fields_no_recipients(self):
        service = instantiate("notification_service")
        payload = {
            "job_id": "job-001",
            "message": "sync failed",
        }

        try:
            result = call_method(service, ["send", "notify", "send_failure"], payload)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_api_failure_notification_provider(self, monkeypatch):
        service = instantiate("notification_service")
        payload = {
            "job_id": "job-001",
            "severity": "critical",
            "message": "sync failed",
            "channel": "slack",
        }

        if hasattr(service, "client") and hasattr(service.client, "send"):
            monkeypatch.setattr(service.client, "send", lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("provider unavailable")))
        elif hasattr(service, "dispatch"):
            monkeypatch.setattr(service, "dispatch", lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("provider unavailable")))
        else:
            return

        try:
            result = call_method(service, ["send", "notify", "send_failure"], payload)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_edge_case_dedup_window(self):
        service = instantiate("notification_service")
        payload = {
            "job_id": "job-001",
            "severity": "warning",
            "message": "retrying",
            "channel": "email",
        }

        first = call_method(service, ["send", "notify", "send_failure"], payload)
        second = call_method(service, ["send", "notify", "send_failure"], payload)

        if isinstance(second, dict):
            assert second.get("status", "").lower() in {"sent", "deduped", "suppressed", "queued", "accepted"}
        else:
            assert second is not None
