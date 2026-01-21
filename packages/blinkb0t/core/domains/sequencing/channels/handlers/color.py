"""Color channel handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.libraries.channels.color import ColorLibrary
from blinkb0t.core.domains.sequencing.models.channels import ChannelEffect

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureGroup, FixtureInstance
    from blinkb0t.core.domains.sequencing.libraries.channels.color import ColorPresetDefinition

logger = logging.getLogger(__name__)


class ColorHandler:
    """Handler for color channel.

    Responsibilities:
    - Look up color preset from library
    - Generate DMX values for color wheel channel (using fixture-specific mappings)
    - Handle fixture-specific color wheel mappings

    Note: Uses fixture-specific color_map for DMX values, not generic library defaults.
    This ensures correct DMX values for different fixture models.
    """

    def __init__(self, library: ColorLibrary):
        """Initialize color handler.

        Args:
            library: Color library for preset definitions
        """
        self._library = library

    def resolve(
        self,
        preset_id: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> tuple[int, int, int] | int:
        """Resolve color preset to RGB tuple or DMX value.

        Simple resolution for channel overlays (Phase 5B).
        Returns default RGB/DMX values for common presets.
        Full fixture-specific resolution happens in render().

        Args:
            preset_id: Color preset ID (e.g., "white", "red", "blue")
            start_ms: Start time (unused, for interface compatibility)
            end_ms: End time (unused, for interface compatibility)

        Returns:
            RGB tuple (for RGB fixtures) or DMX value (for color wheel fixtures)
        """
        # Simple default mapping (generic, not fixture-specific)
        default_colors = {
            "white": (255, 255, 255),
            "red": (255, 0, 0),
            "green": (0, 255, 0),
            "blue": (0, 0, 255),
            "yellow": (255, 255, 0),
            "cyan": (0, 255, 255),
            "magenta": (255, 0, 255),
            "orange": (255, 128, 0),
        }
        return default_colors.get(preset_id, (255, 255, 255))  # Default to white

    def render(
        self,
        channel_value: str,
        fixtures: FixtureGroup,
        start_time_ms: int,
        end_time_ms: int,
        beat_times_ms: list[int] | None = None,
    ) -> list[ChannelEffect]:
        """Render color effects.

        Args:
            channel_value: Color preset ID (e.g., "blue", "red")
            fixtures: Fixtures to render for
            start_time_ms: Start time
            end_time_ms: End time
            beat_times_ms: Optional beat times (not used for static color)

        Returns:
            List of ChannelEffect objects
        """
        # Look up preset
        preset = self._library.get_preset(channel_value)

        logger.debug(f"Rendering color: {preset.name} for {len(fixtures.fixtures)} fixtures")

        effects = []

        # Expand fixtures to ensure we have full FixtureInstance objects
        # (unless it's a Mock for testing)
        expanded_fixtures: list[FixtureInstance]
        try:
            expanded_fixtures = fixtures.expand_fixtures()
        except (AttributeError, TypeError):
            # Mock object or already a list
            expanded_fixtures = fixtures.fixtures if hasattr(fixtures, "fixtures") else fixtures  # type: ignore[assignment]

        for fixture in expanded_fixtures:
            # Check if fixture has color channel
            if not self._has_color_channel(fixture):
                logger.warning(f"Fixture {fixture.fixture_id} has no color channel, skipping")
                continue

            # Get fixture-specific DMX value
            dmx_value = self._get_fixture_color_value(fixture, preset)

            # Create effect (constant color, no curve)
            effect = ChannelEffect(
                fixture_id=fixture.fixture_id,
                channel_name="color",
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                dmx_values=[dmx_value],
                value_curve=None,  # Constant value
            )
            effects.append(effect)

        return effects

    def _has_color_channel(self, fixture: FixtureInstance) -> bool:
        """Check if fixture has color channel.

        Args:
            fixture: Fixture instance

        Returns:
            True if fixture has color channel configured
        """
        # Use the property that returns channel number or None
        return fixture.config.dmx_mapping.color is not None

    def _get_fixture_color_value(
        self, fixture: FixtureInstance, preset: ColorPresetDefinition
    ) -> int:
        """Get fixture-specific DMX value for color.

        Different fixtures have different color wheel layouts.
        Uses the fixture's color_map to get the correct DMX value.

        Args:
            fixture: Fixture instance
            preset: Color preset definition

        Returns:
            DMX value for color from fixture's color_map.
            Returns 0 (off) if color not supported by fixture.
        """
        color_map = fixture.config.dmx_mapping.color_map
        color_id = preset.color_id

        # Look up color in fixture's map
        if color_id not in color_map:
            # Fallback to DMX 0 (off) with warning
            # Better to be safe than send incorrect color
            logger.warning(
                f"Color '{color_id}' not found in fixture {fixture.fixture_id} color_map. "
                f"Supported colors: {sorted(color_map.keys())}. Falling back to DMX 0 (off)."
            )
            return 0

        return color_map[color_id]
