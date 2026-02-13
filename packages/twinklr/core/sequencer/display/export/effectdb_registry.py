"""EffectDB deduplication registry.

Tracks unique EffectDB settings strings and returns indices.
Avoids bloating the .xsq file with duplicate effect entries.
"""

from __future__ import annotations


class EffectDBRegistry:
    """Registry that deduplicates EffectDB settings strings.

    xLights stores effect settings in an ordered list (<EffectDB>). Each
    effect placement references settings by a 0-based index (the 'ref'
    attribute). This registry ensures identical settings share the same index.

    Note: Index 0 is conventionally empty in xLights (used for default On/Off).

    Example:
        >>> reg = EffectDBRegistry()
        >>> idx1 = reg.register("E_SLIDER_Speed=50,E_CHECKBOX_Mirror=0")
        >>> idx2 = reg.register("E_SLIDER_Speed=50,E_CHECKBOX_Mirror=0")
        >>> idx1 == idx2
        True
    """

    def __init__(self, *, reserve_zero: bool = True) -> None:
        """Initialize the registry.

        Args:
            reserve_zero: If True, index 0 is reserved with an empty string
                (matching xLights convention).
        """
        self._entries: list[str] = []
        self._index: dict[str, int] = {}

        if reserve_zero:
            self._entries.append("")
            self._index[""] = 0

    def register(self, settings_string: str) -> int:
        """Register a settings string, returning its index.

        If the identical string already exists, returns the existing index.

        Args:
            settings_string: xLights EffectDB settings string.

        Returns:
            0-based index into the EffectDB.
        """
        if settings_string in self._index:
            return self._index[settings_string]

        idx = len(self._entries)
        self._entries.append(settings_string)
        self._index[settings_string] = idx
        return idx

    def get_entries(self) -> list[str]:
        """Return all registered settings strings in order.

        Returns:
            Ordered list of settings strings.
        """
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


__all__ = [
    "EffectDBRegistry",
]
