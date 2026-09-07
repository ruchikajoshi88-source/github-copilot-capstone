from __future__ import annotations

from hashlib import sha256
import json
from pathlib import PurePosixPath
from typing import Any

from shared.contracts.document import CanonicalDocument


def _normalize_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    # PyYAML may produce date/datetime objects; stringify unknown objects deterministically.
    return str(value)


def _normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _normalize_value(value) for key, value in metadata.items()}


def normalize_source_path(source_path: str) -> str:
    return PurePosixPath(source_path).as_posix()


def build_document_key(repository_id: str, source_path: str) -> str:
    raw = f"{repository_id}:{normalize_source_path(source_path)}"
    return sha256(raw.encode("utf-8")).hexdigest()


def build_checksum(content_markdown: str, metadata: dict[str, Any]) -> str:
    normalized_metadata = _normalize_metadata(metadata)
    canonical = json.dumps(
        {
            "content_markdown": content_markdown.replace("\r\n", "\n"),
            "metadata": normalized_metadata,
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def build_canonical_document(
    repository_id: str,
    source_path: str,
    metadata: dict[str, Any],
    content_markdown: str,
) -> CanonicalDocument:
    normalized_path = normalize_source_path(source_path)
    normalized_metadata = _normalize_metadata(metadata)
    key = build_document_key(repository_id, normalized_path)
    checksum = build_checksum(content_markdown, normalized_metadata)

    version = str(normalized_metadata.get("version", "unknown"))
    return CanonicalDocument(
        key=key,
        repository_id=repository_id,
        source_path=normalized_path,
        metadata=normalized_metadata,
        content_markdown=content_markdown,
        checksum=checksum,
        version=version,
    )
