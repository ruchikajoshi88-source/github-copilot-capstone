from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml

from shared.errors.exceptions import SourceAccessError, ValidationError


FRONTMATTER_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*\r?\n?", re.DOTALL)


@dataclass(frozen=True)
class ParsedMarkdown:
    """Parsed markdown result with metadata extracted from YAML frontmatter."""

    metadata: dict[str, Any]
    body: str
    has_frontmatter: bool


def parse_markdown_with_frontmatter(path: Path) -> ParsedMarkdown:
    """Parse a markdown file, extracting YAML frontmatter if present."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SourceAccessError("Unable to read source file", {"source_path": str(path), "cause": str(exc)}) from exc

    match = FRONTMATTER_RE.match(content)
    if not match:
        return ParsedMarkdown(metadata={}, body=content, has_frontmatter=False)

    raw_frontmatter = match.group(1)
    body = content[match.end() :]

    try:
        parsed = yaml.safe_load(raw_frontmatter)
    except yaml.YAMLError as exc:
        raise ValidationError(
            "Malformed YAML frontmatter",
            {"source_path": str(path), "cause": str(exc)},
        ) from exc

    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        raise ValidationError(
            "Frontmatter must parse to a key/value mapping",
            {"source_path": str(path)},
        )

    return ParsedMarkdown(metadata=parsed, body=body, has_frontmatter=True)
