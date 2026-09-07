from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SyncStatus(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    NO_CHANGE = "no_change"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class CanonicalDocument:
    """Normalized document contract used by source and target connectors."""

    key: str
    repository_id: str
    source_path: str
    metadata: dict[str, object]
    content_markdown: str
    checksum: str
    version: str
