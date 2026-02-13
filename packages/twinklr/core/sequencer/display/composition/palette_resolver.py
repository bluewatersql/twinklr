"""Palette resolver: converts PaletteRef to ResolvedPalette via theming catalog.

Bridges the planning domain (PaletteRef with a palette_id string) to the
rendering domain (ResolvedPalette with concrete hex colors and slot info)
by looking up PaletteDefinition from the theming PaletteCatalog.

This replaces the hardcoded _PALETTE_MAP that was in the composition engine.
"""

from __future__ import annotations

import logging

from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.theming.catalog import (
    ItemNotFoundError,
    PaletteCatalog,
)
from twinklr.core.sequencer.theming.models import PaletteDefinition

logger = logging.getLogger(__name__)

# xLights supports up to 8 palette color slots
_MAX_PALETTE_SLOTS = 8


class PaletteResolver:
    """Resolves PaletteRef → ResolvedPalette via a PaletteCatalog.

    Extracts hex colors from PaletteDefinition color stops and builds
    a ResolvedPalette with sequential active slots. Falls back to a
    configurable default when the palette_id is not found.

    Args:
        catalog: PaletteCatalog to look up palette definitions.
        default: Fallback ResolvedPalette when lookup fails or ref is None.
    """

    def __init__(
        self,
        catalog: PaletteCatalog,
        default: ResolvedPalette,
    ) -> None:
        self._catalog = catalog
        self._default = default
        # Cache to avoid repeated conversions for the same palette_id
        self._cache: dict[str, ResolvedPalette] = {}

    def resolve(self, palette_ref: PaletteRef | None) -> ResolvedPalette:
        """Resolve a PaletteRef to a concrete ResolvedPalette.

        Args:
            palette_ref: Palette reference from the plan, or None for default.

        Returns:
            ResolvedPalette with hex colors and active slot indices.
        """
        if palette_ref is None:
            return self._default

        palette_id = palette_ref.palette_id

        # Check cache first
        if palette_id in self._cache:
            return self._cache[palette_id]

        # Look up in catalog
        try:
            definition = self._catalog.get(palette_id)
        except (ItemNotFoundError, KeyError):
            logger.warning(
                "Palette '%s' not found in catalog, using default",
                palette_id,
            )
            return self._default

        resolved = self._definition_to_palette(definition)
        self._cache[palette_id] = resolved

        logger.debug(
            "Resolved palette '%s': %d colors %s",
            palette_id,
            len(resolved.colors),
            resolved.colors,
        )

        return resolved

    @staticmethod
    def _definition_to_palette(definition: PaletteDefinition) -> ResolvedPalette:
        """Convert a PaletteDefinition to a ResolvedPalette.

        Extracts hex colors from all stops (up to 8, the xLights max),
        preserving stop order. All included colors get active slots.

        Args:
            definition: Palette definition with color stops.

        Returns:
            ResolvedPalette with colors and sequential active slots.
        """
        colors: list[str] = []
        for stop in definition.stops:
            if len(colors) >= _MAX_PALETTE_SLOTS:
                break
            colors.append(stop.hex)

        active_slots = list(range(1, len(colors) + 1))

        return ResolvedPalette(
            colors=colors,
            active_slots=active_slots,
        )


__all__ = [
    "PaletteResolver",
]
