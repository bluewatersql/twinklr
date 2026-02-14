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

        Performs a catalog lookup by ``palette_id``, then applies the
        optional ``intensity`` scaler (0.0-1.0) as palette brightness.

        .. note::
           ``PaletteRef.role`` and ``PaletteRef.variant`` are available
           for future use (e.g., color subset selection, palette variant
           lookup) but are not currently consumed.

        Args:
            palette_ref: Palette reference from the plan, or None for default.

        Returns:
            ResolvedPalette with hex colors and active slot indices.
        """
        if palette_ref is None:
            return self._default

        palette_id = palette_ref.palette_id

        # Cache lookup on palette_id (base colors only)
        if palette_id in self._cache:
            base = self._cache[palette_id]
        else:
            try:
                definition = self._catalog.get(palette_id)
            except (ItemNotFoundError, KeyError):
                logger.warning(
                    "Palette '%s' not found in catalog, using default",
                    palette_id,
                )
                return self._default

            base = self._definition_to_palette(definition)
            self._cache[palette_id] = base

            logger.debug(
                "Resolved palette '%s': %d colors %s",
                palette_id,
                len(base.colors),
                base.colors,
            )

        # Apply palette-level intensity scaler
        return self._apply_palette_intensity(base, palette_ref.intensity)

    @staticmethod
    def _apply_palette_intensity(
        palette: ResolvedPalette,
        intensity: float | None,
    ) -> ResolvedPalette:
        """Apply a PaletteRef intensity scaler to the resolved palette.

        Maps ``intensity`` (0.0-1.0) to ``C_SLIDER_Brightness`` (0-100).
        Composes with any existing brightness on the palette.

        Args:
            palette: Base resolved palette.
            intensity: Optional intensity scaler (0.0-1.0). None or 1.0
                means no adjustment.

        Returns:
            Palette with brightness applied, or unchanged if not needed.
        """
        if intensity is None or intensity >= 1.0:
            return palette

        base_brightness = palette.brightness if palette.brightness is not None else 100
        effective = max(0, min(100, int(base_brightness * intensity)))
        return palette.model_copy(update={"brightness": effective})

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
