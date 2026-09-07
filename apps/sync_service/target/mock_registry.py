from __future__ import annotations

from dataclasses import dataclass, field

from shared.contracts.document import CanonicalDocument, SyncStatus


@dataclass
class MockRegistryTarget:
    """In-memory target registry adapter for phase-1 synchronization."""

    _documents: dict[str, CanonicalDocument] = field(default_factory=dict)

    def get(self, key: str) -> CanonicalDocument | None:
        return self._documents.get(key)

    def upsert(self, document: CanonicalDocument) -> SyncStatus:
        existing = self._documents.get(document.key)
        if existing is None:
            self._documents[document.key] = document
            return SyncStatus.CREATED

        self._documents[document.key] = document
        return SyncStatus.UPDATED

    def all_documents(self) -> list[CanonicalDocument]:
        return list(self._documents.values())
