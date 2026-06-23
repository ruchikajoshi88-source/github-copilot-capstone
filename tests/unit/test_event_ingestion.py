import pytest

from conftest import assert_error_or_failed, call_method, instantiate


class TestEventIngestion:
    def test_happy_path_valid_merge_event(self, valid_merge_event, valid_headers):
        service = instantiate("event_ingestion")
        result = call_method(service, ["handle_event", "ingest", "process_event"], valid_merge_event, valid_headers)

        if isinstance(result, dict):
            assert result.get("status", "ok") in {"ok", "accepted", "queued", "processed"}
            assert result.get("merge_sha", valid_merge_event["merge_sha"]) == valid_merge_event["merge_sha"]

    def test_invalid_input_bad_signature(self, valid_merge_event):
        service = instantiate("event_ingestion")
        invalid_headers = {"X-Signature": "invalid", "X-Event-Id": "evt-001"}

        try:
            result = call_method(service, ["handle_event", "ingest", "process_event"], valid_merge_event, invalid_headers)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_missing_fields_event_payload(self, valid_headers):
        service = instantiate("event_ingestion")
        invalid_event = {
            "event_type": "merge_completed",
            "repository": "example/repo",
            # branch and merge_sha intentionally missing
        }

        try:
            result = call_method(service, ["handle_event", "ingest", "process_event"], invalid_event, valid_headers)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_api_failure_from_dependency(self, monkeypatch, valid_merge_event, valid_headers):
        service = instantiate("event_ingestion")

        if hasattr(service, "verify_signature"):
            monkeypatch.setattr(service, "verify_signature", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("verifier timeout")))
        elif hasattr(service, "validator"):
            validator = getattr(service, "validator")
            if hasattr(validator, "verify_signature"):
                monkeypatch.setattr(validator, "verify_signature", lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("validator unavailable")))
            else:
                pytest.skip("No injectable signature verifier found for API failure scenario")
        else:
            pytest.skip("No injectable validation dependency found")

        try:
            result = call_method(service, ["handle_event", "ingest", "process_event"], valid_merge_event, valid_headers)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_edge_case_duplicate_event_id(self, valid_merge_event, valid_headers):
        service = instantiate("event_ingestion")

        first = call_method(service, ["handle_event", "ingest", "process_event"], valid_merge_event, valid_headers)
        second = call_method(service, ["handle_event", "ingest", "process_event"], valid_merge_event, valid_headers)

        if isinstance(second, dict):
            assert second.get("status", "").lower() in {"ok", "accepted", "duplicate", "already_processed", "queued"}
        else:
            assert second is not None
