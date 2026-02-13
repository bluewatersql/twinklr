"""Palette deduplication registry.

Tracks unique ColorPalette strings and returns indices. Avoids
bloating the .xsq file with duplicate palette entries.
"""

from __future__ import annotations


class PaletteDBRegistry:
    """Registry that deduplicates palette strings and assigns indices.

    xLights stores palettes in an ordered list (<ColorPalettes>). Each
    effect references a palette by its 0-based index. This registry
    ensures identical palettes share the same index.

    Example:
        >>> reg = PaletteDBRegistry()
        >>> idx1 = reg.register("C_BUTTON_Palette1=#FF0000,...")
        >>> idx2 = reg.register("C_BUTTON_Palette1=#FF0000,...")
        >>> idx1 == idx2
        True
    """

    def __init__(self) -> None:
        self._entries: list[str] = []
        self._index: dict[str, int] = {}

    def register(self, palette_string: str) -> int:
        """Register a palette string, returning its index.

        If the identical string already exists, returns the existing index.

        Args:
            palette_string: xLights ColorPalette settings string.

        Returns:
            0-based index into the palette list.
        """
        if palette_string in self._index:
            return self._index[palette_string]

        idx = len(self._entries)
        self._entries.append(palette_string)
        self._index[palette_string] = idx
        return idx

    def get_entries(self) -> list[str]:
        """Return all registered palette strings in order.

        Returns:
            Ordered list of palette strings.
        """
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


__all__ = [
    "PaletteDBRegistry",
]
