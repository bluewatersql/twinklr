"""Seeded positional string registries for xLights sequence emission."""

from __future__ import annotations


class PositionalRegistry:
    """Preserve existing indices while deduplicating every newly registered value."""

    def __init__(
        self, entries: list[str] | None = None, *, reserve_empty_zero: bool = False
    ) -> None:
        self._entries = list(entries or [])
        if reserve_empty_zero and not self._entries:
            self._entries.append("")
        self._index: dict[str, int] = {}
        for index, entry in enumerate(self._entries):
            self._index.setdefault(entry, index)

    def register(self, value: str) -> int:
        if value in self._index:
            return self._index[value]
        index = len(self._entries)
        self._entries.append(value)
        self._index[value] = index
        return index

    def get_entries(self) -> list[str]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


__all__ = ["PositionalRegistry"]
