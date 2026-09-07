from pathlib import Path

import pytest

from apps.sync_service.parser.frontmatter import parse_markdown_with_frontmatter
from shared.errors.exceptions import ValidationError


def test_parse_frontmatter_with_valid_yaml(tmp_path: Path) -> None:
    file_path = tmp_path / "doc.md"
    file_path.write_text(
        "---\ntitle: Sample\nversion: v1\n---\n# Body\ntext\n",
        encoding="utf-8",
    )

    parsed = parse_markdown_with_frontmatter(file_path)

    assert parsed.has_frontmatter is True
    assert parsed.metadata["title"] == "Sample"
    assert "# Body" in parsed.body


def test_parse_frontmatter_missing_frontmatter(tmp_path: Path) -> None:
    file_path = tmp_path / "doc.md"
    file_path.write_text("# Body only\n", encoding="utf-8")

    parsed = parse_markdown_with_frontmatter(file_path)

    assert parsed.has_frontmatter is False
    assert parsed.metadata == {}
    assert parsed.body == "# Body only\n"


def test_parse_frontmatter_malformed_yaml(tmp_path: Path) -> None:
    file_path = tmp_path / "bad.md"
    file_path.write_text("---\ntitle: [broken\n---\nbody\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        parse_markdown_with_frontmatter(file_path)


def test_parse_frontmatter_requires_mapping(tmp_path: Path) -> None:
    file_path = tmp_path / "bad.md"
    file_path.write_text("---\n- item\n- item2\n---\nbody\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        parse_markdown_with_frontmatter(file_path)
