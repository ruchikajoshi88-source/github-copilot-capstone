from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InMemoryIdempotencyStore:
    """Tracks last successful checksum per document key."""

    _checksums: dict[str, str] = field(default_factory=dict)

    def should_write(self, key: str, checksum: str) -> bool:
        return self._checksums.get(key) != checksum

    def mark_success(self, key: str, checksum: str) -> None:
        self._checksums[key] = checksum


@dataclass
class InMemoryEventLedger:
    """Tracks processed event ids to prevent duplicate event processing."""

    _processed: set[str] = field(default_factory=set)

    def seen(self, event_id: str | None) -> bool:
        if not event_id:
            return False
        return event_id in self._processed

    def mark_processed(self, event_id: str | None) -> None:
        if event_id:
            self._processed.add(event_id)
