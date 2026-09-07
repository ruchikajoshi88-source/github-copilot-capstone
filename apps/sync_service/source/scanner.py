from __future__ import annotations

from dataclasses import dataclass
import fnmatch
from pathlib import Path, PurePosixPath

from shared.errors.exceptions import SourceAccessError


@dataclass(frozen=True)
class SourceFile:
    """Represents a markdown source file selected for synchronization."""

    absolute_path: Path
    relative_path: str
    size_bytes: int


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    posix_path = PurePosixPath(path)
    for pattern in patterns:
        if posix_path.match(pattern) or fnmatch.fnmatch(path, pattern):
            return True
        if pattern.startswith("**/") and fnmatch.fnmatch(path, pattern[3:]):
            return True
    return False


def discover_markdown_files(
    source_root: str,
    include_patterns: tuple[str, ...] = ("**/*.md",),
    exclude_patterns: tuple[str, ...] = (),
) -> list[SourceFile]:
    """Discover markdown files under source_root with include/exclude filtering."""
    root = Path(source_root)
    if not root.exists() or not root.is_dir():
        raise SourceAccessError("Source root does not exist or is not a directory", {"source_root": source_root})

    results: list[SourceFile] = []
    for candidate in root.rglob("*.md"):
        relative = candidate.relative_to(root).as_posix()

        if include_patterns and not _matches_any(relative, include_patterns):
            continue
        if exclude_patterns and _matches_any(relative, exclude_patterns):
            continue

        try:
            size_bytes = candidate.stat().st_size
        except OSError as exc:
            raise SourceAccessError(
                "Unable to stat source file",
                {"source_path": relative, "cause": str(exc)},
            ) from exc

        results.append(SourceFile(candidate, relative, size_bytes))

    return sorted(results, key=lambda item: item.relative_path)


def load_markdown_file(path: Path) -> str:
    """Read markdown file as UTF-8 text."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SourceAccessError("Unable to read source file", {"source_path": str(path), "cause": str(exc)}) from exc
