from __future__ import annotations


class IdempotencyStore:
    def __init__(self) -> None:
        self._keys: set[str] = set()

    def _write(self, key: str) -> None:
        self._keys.add(key)

    def mark_processed(self, key: str | None) -> bool:
        if not key:
            return False
        self._write(key)
        return True

    def is_processed(self, key: str | None) -> bool:
        if not key:
            return False
        return key in self._keys

    store_key = mark_processed
    put = mark_processed
    contains = is_processed
    exists = is_processed
