from conftest import call_method, instantiate


class TestIdempotencyStore:
    def test_happy_path_store_and_check_key(self):
        store = instantiate("idempotency_store")
        key = "repo-main-abc123-markdown"

        call_method(store, ["mark_processed", "store_key", "put"], key)
        result = call_method(store, ["is_processed", "contains", "exists"], key)

        assert bool(result) is True

    def test_invalid_input_empty_key(self):
        store = instantiate("idempotency_store")

        try:
            call_method(store, ["mark_processed", "store_key", "put"], "")
        except Exception:
            return

        result = call_method(store, ["is_processed", "contains", "exists"], "")
        assert bool(result) is False

    def test_missing_fields_none_key(self):
        store = instantiate("idempotency_store")

        try:
            call_method(store, ["mark_processed", "store_key", "put"], None)
        except Exception:
            return

        result = call_method(store, ["is_processed", "contains", "exists"], None)
        assert bool(result) is False

    def test_storage_failure(self, monkeypatch):
        store = instantiate("idempotency_store")
        key = "repo-main-abc123-confluence"

        if hasattr(store, "_write"):
            monkeypatch.setattr(store, "_write", lambda *_args, **_kwargs: (_ for _ in ()).throw(IOError("storage down")))
        elif hasattr(store, "db") and hasattr(store.db, "save"):
            monkeypatch.setattr(store.db, "save", lambda *_args, **_kwargs: (_ for _ in ()).throw(IOError("storage down")))
        else:
            return

        try:
            call_method(store, ["mark_processed", "store_key", "put"], key)
        except Exception:
            return

        result = call_method(store, ["is_processed", "contains", "exists"], key)
        assert bool(result) is False

    def test_edge_case_idempotent_reinsert(self):
        store = instantiate("idempotency_store")
        key = "repo-main-abc123-generated"

        call_method(store, ["mark_processed", "store_key", "put"], key)
        call_method(store, ["mark_processed", "store_key", "put"], key)

        result = call_method(store, ["is_processed", "contains", "exists"], key)
        assert bool(result) is True
