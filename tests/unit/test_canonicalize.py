from apps.sync_service.canonicalize import build_canonical_document, build_checksum, build_document_key


def test_build_document_key_deterministic() -> None:
    key1 = build_document_key("repo", "docs/a.md")
    key2 = build_document_key("repo", "docs/a.md")
    assert key1 == key2


def test_checksum_changes_with_content() -> None:
    checksum1 = build_checksum("hello", {"title": "A"})
    checksum2 = build_checksum("hello2", {"title": "A"})
    assert checksum1 != checksum2


def test_build_canonical_document_sets_version() -> None:
    doc = build_canonical_document("repo", "docs/a.md", {"version": "v1"}, "# body")
    assert doc.version == "v1"
