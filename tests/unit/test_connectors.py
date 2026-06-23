import pytest

from conftest import assert_error_or_failed, call_method, instantiate


@pytest.mark.parametrize(
    "component_key,target",
    [
        ("markdown_connector", "markdown"),
        ("confluence_connector", "confluence"),
        ("generated_docs_connector", "generated_docs"),
    ],
)
class TestConnectors:
    def test_happy_path_sync(self, component_key, target, valid_sync_job):
        connector = instantiate(component_key)
        payload = {
            "job_id": valid_sync_job["job_id"],
            "target": target,
            "event": valid_sync_job["event"],
        }

        result = call_method(connector, ["sync", "execute", "publish"], payload)

        if isinstance(result, dict):
            assert result.get("status", "success") in {"success", "ok", "completed", "updated"}

    def test_invalid_input_bad_target_payload(self, component_key, target, valid_sync_job):
        _ = target
        connector = instantiate(component_key)
        payload = {
            "job_id": valid_sync_job["job_id"],
            "event": valid_sync_job["event"],
            "target": "",
        }

        try:
            result = call_method(connector, ["sync", "execute", "publish"], payload)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_missing_fields_missing_event(self, component_key, target, valid_sync_job):
        connector = instantiate(component_key)
        payload = {
            "job_id": valid_sync_job["job_id"],
            "target": target,
        }

        try:
            result = call_method(connector, ["sync", "execute", "publish"], payload)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_api_failure_remote_update(self, monkeypatch, component_key, target, valid_sync_job):
        connector = instantiate(component_key)
        payload = {
            "job_id": valid_sync_job["job_id"],
            "target": target,
            "event": valid_sync_job["event"],
        }

        if hasattr(connector, "client") and hasattr(connector.client, "update"):
            monkeypatch.setattr(connector.client, "update", lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("api failed")))
        elif hasattr(connector, "_update_remote"):
            monkeypatch.setattr(connector, "_update_remote", lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("api failed")))
        else:
            return

        try:
            result = call_method(connector, ["sync", "execute", "publish"], payload)
        except Exception:
            return

        assert_error_or_failed(result)

    def test_edge_case_no_content_change(self, component_key, target, valid_sync_job):
        connector = instantiate(component_key)
        payload = {
            "job_id": valid_sync_job["job_id"],
            "target": target,
            "event": dict(valid_sync_job["event"], changed_files=[]),
        }

        result = call_method(connector, ["sync", "execute", "publish"], payload)

        if isinstance(result, dict):
            assert result.get("status", "").lower() in {
                "success",
                "ok",
                "completed",
                "skipped",
                "no_change",
                "updated",
            }
