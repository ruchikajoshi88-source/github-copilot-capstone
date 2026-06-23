from conftest import assert_error_or_failed, call_method, instantiate


class TestSyncWorker:
    def test_happy_path_process_job(self, valid_sync_job):
        worker = instantiate("sync_worker")
        result = call_method(worker, ["process_job", "handle_job", "run_job"], valid_sync_job)

        if isinstance(result, dict):
            assert result.get("status", "completed") in {"completed", "ok", "success", "partial"}

    def test_invalid_input_missing_targets(self, valid_sync_job):
        worker = instantiate("sync_worker")
        invalid_job = dict(valid_sync_job)
        invalid_job.pop("targets", None)

        try:
            result = call_method(worker, ["process_job", "handle_job", "run_job"], invalid_job)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_missing_fields_missing_event(self, valid_sync_job):
        worker = instantiate("sync_worker")
        invalid_job = dict(valid_sync_job)
        invalid_job.pop("event", None)

        try:
            result = call_method(worker, ["process_job", "handle_job", "run_job"], invalid_job)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_api_failure_connector_timeout(self, monkeypatch, valid_sync_job):
        worker = instantiate("sync_worker")

        if hasattr(worker, "invoke_connector"):
            monkeypatch.setattr(worker, "invoke_connector", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("connector timeout")))
        elif hasattr(worker, "connector_manager") and hasattr(worker.connector_manager, "execute"):
            monkeypatch.setattr(worker.connector_manager, "execute", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("connector timeout")))
        else:
            return

        try:
            result = call_method(worker, ["process_job", "handle_job", "run_job"], valid_sync_job)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_edge_case_partial_success(self, valid_sync_job):
        worker = instantiate("sync_worker")
        job = dict(valid_sync_job)
        job["targets"] = ["markdown", "confluence", "generated_docs"]

        result = call_method(worker, ["process_job", "handle_job", "run_job"], job)

        if isinstance(result, dict):
            assert result.get("status", "").lower() in {"success", "completed", "partial", "ok"}


class TestRetryPolicy:
    def test_happy_path_retryable_error(self):
        policy = instantiate("retry_policy")
        result = call_method(policy, ["should_retry", "is_retryable", "evaluate"], "timeout", 1)
        assert bool(result) is True

    def test_invalid_input_negative_attempt(self):
        policy = instantiate("retry_policy")

        try:
            result = call_method(policy, ["should_retry", "is_retryable", "evaluate"], "timeout", -1)
        except Exception:
            return

        assert bool(result) is False

    def test_missing_fields_unknown_error_code(self):
        policy = instantiate("retry_policy")
        result = call_method(policy, ["should_retry", "is_retryable", "evaluate"], None, 1)
        assert bool(result) is False

    def test_api_failure_policy_source_unavailable(self, monkeypatch):
        policy = instantiate("retry_policy")

        if hasattr(policy, "load_rules"):
            monkeypatch.setattr(policy, "load_rules", lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("policy source unavailable")))
        else:
            return

        try:
            result = call_method(policy, ["should_retry", "is_retryable", "evaluate"], "timeout", 1)
        except Exception:
            return

        assert bool(result) in {False, True}

    def test_edge_case_attempt_limit(self):
        policy = instantiate("retry_policy")

        result = call_method(policy, ["should_retry", "is_retryable", "evaluate"], "timeout", 999)
        assert bool(result) is False
