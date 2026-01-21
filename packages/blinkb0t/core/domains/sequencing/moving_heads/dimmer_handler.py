"""Dimmer handler for intensity control.

Simple wrapper around dimmer library to provide handler interface
compatible with SegmentRenderer.
"""

from __future__ import annotations

import logging
from typing import Any

from blinkb0t.core.config.fixtures import FixtureInstance
from blinkb0t.core.domains.sequencing.libraries.moving_heads import DIMMER_LIBRARY, DimmerID
from blinkb0t.core.domains.sequencing.libraries.moving_heads.base import CategoricalIntensity

logger = logging.getLogger(__name__)


class DimmerHandler:
    """Handler for dimmer/intensity pattern resolution.

    Provides a simple interface for resolving dimmer patterns to either
    static values or dimmer specifications that can be rendered to curves.

    This is a lightweight wrapper around the dimmer library that matches
    the interface needed by SegmentRenderer.

    Usage:
        handler = DimmerHandler()
        dimmer_spec = handler.resolve_dimmer(
            pattern_id="breathe",
            params={"intensity": "SMOOTH"},
            fixture=fixture
        )
    """

    def __init__(self):
        """Initialize dimmer handler."""
        pass

    def resolve_dimmer(
        self,
        pattern_id: str,
        params: dict[str, Any],
        fixture: FixtureInstance,
    ) -> int:
        """Resolve dimmer pattern to static intensity value.

        For Phase 3, we're simplifying to always return static values.
        Dynamic dimmer curves will be added in Phase 4 when the full
        curve pipeline is implemented.

        Args:
            pattern_id: Dimmer pattern ID (e.g., "full", "breathe", "pulse")
            params: Pattern parameters (e.g., {"intensity": "SMOOTH", "base_pct": 80})
            fixture: Fixture instance (for fixture-specific adjustments)

        Returns:
            Static intensity value (0-255)

        Example:
            # Static dimmer
            >>> result = handler.resolve_dimmer("full", {}, fixture)
            >>> assert result == 255

            # Dynamic dimmer (returns average for now)
            >>> result = handler.resolve_dimmer("breathe", {"intensity": "SMOOTH"}, fixture)
            >>> assert isinstance(result, int)
        """
        # Handle static patterns
        if pattern_id in ["full", "hold", "static"]:
            base_pct = params.get("base_pct", 100)
            return int(round((float(base_pct) / 100.0) * 255.0))

        if pattern_id in ["off", "blackout"]:
            return 0

        # Handle dynamic patterns - for Phase 3, return average intensity
        try:
            dimmer_id = DimmerID(pattern_id)
        except ValueError:
            # Unknown pattern - log warning and return full
            logger.warning(f"Unknown dimmer pattern '{pattern_id}', defaulting to full (255)")
            return 255

        # Get pattern from library
        pattern = DIMMER_LIBRARY.get(dimmer_id)
        if not pattern:
            logger.warning(
                f"Dimmer pattern '{pattern_id}' not in library, defaulting to full (255)"
            )
            return 255

        # Resolve categorical intensity if provided
        categorical_params = self._resolve_categorical_params(pattern_id, params)

        # For Phase 3, return the average intensity
        # Phase 4 will add proper curve generation
        min_intensity = categorical_params.get("min_intensity", 0)
        max_intensity = categorical_params.get("max_intensity", 255)
        average_intensity = int((min_intensity + max_intensity) / 2)

        logger.debug(
            f"Dimmer pattern '{pattern_id}' resolved to average intensity {average_intensity} "
            f"(range {min_intensity}-{max_intensity})"
        )

        return average_intensity

    def _resolve_categorical_params(
        self,
        pattern_id: str,
        params: dict[str, Any],
    ) -> dict[str, int | float]:
        """Resolve categorical parameters to numeric values.

        Args:
            pattern_id: Pattern ID
            params: Parameters dict (may contain "intensity" categorical param)

        Returns:
            Dict with numeric parameters (min_intensity, max_intensity, period)
        """
        # If already numeric params, return them
        if "min_intensity" in params and "max_intensity" in params:
            return {
                "min_intensity": int(params["min_intensity"]),
                "max_intensity": int(params["max_intensity"]),
                "period": float(params.get("period", 4.0)),
            }

        # Get categorical intensity
        intensity_val = params.get("intensity")
        if not intensity_val:
            # No categorical params, return defaults
            return {"min_intensity": 0, "max_intensity": 255, "period": 4.0}

        # Handle numeric intensity (from LLM)
        if isinstance(intensity_val, (int, float)):
            return {
                "min_intensity": 0,
                "max_intensity": int(intensity_val),
                "period": 4.0,
            }

        # Try to parse as numeric string
        if isinstance(intensity_val, str):
            try:
                numeric_intensity = float(intensity_val)
                return {
                    "min_intensity": 0,
                    "max_intensity": int(numeric_intensity),
                    "period": 4.0,
                }
            except ValueError:
                pass  # Not numeric, try categorical

        # Must be categorical string
        intensity_str = str(intensity_val).upper()

        # Get pattern from library
        try:
            dimmer_id = DimmerID(pattern_id)
            pattern = DIMMER_LIBRARY.get(dimmer_id)
            if pattern and pattern.categorical_params:
                try:
                    intensity_enum = CategoricalIntensity(intensity_str)
                    categorical = pattern.categorical_params.get(intensity_enum)
                    if categorical:
                        return {
                            "min_intensity": categorical.min_intensity,
                            "max_intensity": categorical.max_intensity,
                            "period": categorical.period,
                        }
                except ValueError:
                    pass  # Invalid intensity value
        except (ValueError, KeyError):
            pass

        # Fallback to defaults
        logger.debug(
            f"Could not resolve categorical params for dimmer pattern '{pattern_id}', "
            f"intensity '{intensity_str}' - using defaults"
        )
        return {"min_intensity": 0, "max_intensity": 128, "period": 4.0}
