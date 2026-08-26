"""Palette deduplication registry.

Tracks unique ColorPalette strings and returns indices. Avoids
bloating the .xsq file with duplicate palette entries.
"""

from __future__ import annotations

from twinklr.core.formats.xlights.sequence.registry import PositionalRegistry


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

    def __init__(self, *, initial_entries: list[str] | None = None) -> None:
        self._registry = PositionalRegistry(initial_entries)

    def register(self, palette_string: str) -> int:
        """Register a palette string, returning its index.

        If the identical string already exists, returns the existing index.

        Args:
            palette_string: xLights ColorPalette settings string.

        Returns:
            0-based index into the palette list.
        """
        return self._registry.register(palette_string)

    def get_entries(self) -> list[str]:
        """Return all registered palette strings in order.

        Returns:
            Ordered list of palette strings.
        """
        return self._registry.get_entries()

    def __len__(self) -> int:
        return len(self._registry)


__all__ = [
    "PaletteDBRegistry",
]
