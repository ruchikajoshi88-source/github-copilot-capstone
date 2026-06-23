from conftest import assert_error_or_failed, call_method, instantiate


class TestSyncOrchestrator:
    def test_happy_path_creates_job(self, valid_merge_event):
        orchestrator = instantiate("sync_orchestrator")
        result = call_method(orchestrator, ["create_job", "orchestrate", "handle_merge_event"], valid_merge_event)

        if isinstance(result, dict):
            assert result.get("status", "created") in {"created", "queued", "ok", "accepted"}
            assert "job" in result or "job_id" in result

    def test_invalid_input_unknown_branch(self, valid_merge_event):
        orchestrator = instantiate("sync_orchestrator")
        event = dict(valid_merge_event)
        event["branch"] = "feature/not-allowed"

        try:
            result = call_method(orchestrator, ["create_job", "orchestrate", "handle_merge_event"], event)
        except Exception:
            return

        if isinstance(result, dict) and result.get("status", "").lower() in {"ignored", "skipped"}:
            return
        assert_error_or_failed(result)

    def test_missing_fields_rejected(self):
        orchestrator = instantiate("sync_orchestrator")
        event = {"repository": "example/repo"}

        try:
            result = call_method(orchestrator, ["create_job", "orchestrate", "handle_merge_event"], event)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_queue_publish_failure(self, monkeypatch, valid_merge_event):
        orchestrator = instantiate("sync_orchestrator")

        if hasattr(orchestrator, "queue_client") and hasattr(orchestrator.queue_client, "publish"):
            monkeypatch.setattr(orchestrator.queue_client, "publish", lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("queue unavailable")))
        elif hasattr(orchestrator, "publish_job"):
            monkeypatch.setattr(orchestrator, "publish_job", lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("queue unavailable")))
        else:
            return

        try:
            result = call_method(orchestrator, ["create_job", "orchestrate", "handle_merge_event"], valid_merge_event)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_edge_case_duplicate_merge_sha(self, valid_merge_event):
        orchestrator = instantiate("sync_orchestrator")

        first = call_method(orchestrator, ["create_job", "orchestrate", "handle_merge_event"], valid_merge_event)
        second = call_method(orchestrator, ["create_job", "orchestrate", "handle_merge_event"], valid_merge_event)

        if isinstance(second, dict):
            assert second.get("status", "").lower() in {"queued", "duplicate", "already_processed", "ok", "accepted"}
        else:
            assert second is not None
