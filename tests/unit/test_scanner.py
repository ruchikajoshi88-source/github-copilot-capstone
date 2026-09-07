from pathlib import Path

import pytest

from apps.sync_service.source.scanner import discover_markdown_files, load_markdown_file
from shared.errors.exceptions import SourceAccessError


def test_discover_markdown_files_filters_include_exclude(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A", encoding="utf-8")
    (docs / "b.txt").write_text("skip", encoding="utf-8")
    nested = docs / "nested"
    nested.mkdir()
    (nested / "keep.md").write_text("# Keep", encoding="utf-8")
    (nested / "skip.md").write_text("# Skip", encoding="utf-8")

    results = discover_markdown_files(
        source_root=str(docs),
        include_patterns=("**/*.md",),
        exclude_patterns=("nested/skip.md",),
    )

    assert [item.relative_path for item in results] == ["a.md", "nested/keep.md"]


def test_discover_markdown_files_raises_for_missing_root(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(SourceAccessError):
        discover_markdown_files(str(missing))


def test_load_markdown_file_reads_utf8(tmp_path: Path) -> None:
    file_path = tmp_path / "doc.md"
    file_path.write_text("hello", encoding="utf-8")

    assert load_markdown_file(file_path) == "hello"
