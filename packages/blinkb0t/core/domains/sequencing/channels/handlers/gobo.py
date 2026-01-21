"""Gobo channel handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.libraries.channels.gobo import GoboLibrary
from blinkb0t.core.domains.sequencing.models.channels import ChannelEffect

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureGroup, FixtureInstance
    from blinkb0t.core.domains.sequencing.libraries.channels.gobo import GoboPatternDefinition

logger = logging.getLogger(__name__)


class GoboHandler:
    """Handler for gobo channel.

    Responsibilities:
    - Look up gobo pattern from library
    - Generate DMX values for gobo wheel channel (using fixture-specific mappings)
    - Handle fixture-specific gobo wheel mappings

    Note: Uses fixture-specific gobo_map for DMX values, not generic library defaults.
    This ensures correct DMX values for different fixture models.
    """

    def __init__(self, library: GoboLibrary):
        """Initialize gobo handler.

        Args:
            library: Gobo library for pattern definitions
        """
        self._library = library

    def resolve(
        self,
        pattern_id: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> int:
        """Resolve gobo pattern to static DMX value.

        Simple resolution for channel overlays (Phase 5B).
        Returns default DMX value for common patterns.
        Full fixture-specific resolution happens in render().

        Args:
            pattern_id: Gobo pattern ID (e.g., "open", "stars", "dots")
            start_ms: Start time (unused, for interface compatibility)
            end_ms: End time (unused, for interface compatibility)

        Returns:
            DMX value for the pattern (generic, not fixture-specific)
        """
        # Simple default mapping (generic, not fixture-specific)
        # Full resolution with fixture-specific DMX values happens in render()
        default_values = {
            "open": 0,
            "stars": 1,
            "dots": 2,
            "spiral": 3,
            "rings": 4,
        }
        return default_values.get(pattern_id, 0)  # Default to open

    def render(
        self,
        channel_value: str,
        fixtures: FixtureGroup,
        start_time_ms: int,
        end_time_ms: int,
        beat_times_ms: list[int] | None = None,
    ) -> list[ChannelEffect]:
        """Render gobo effects.

        Args:
            channel_value: Gobo pattern ID (e.g., "stars", "clouds")
            fixtures: Fixtures to render for
            start_time_ms: Start time
            end_time_ms: End time
            beat_times_ms: Optional beat times (not used for static gobo)

        Returns:
            List of ChannelEffect objects
        """
        # Look up pattern
        pattern = self._library.get_pattern(channel_value)

        logger.debug(f"Rendering gobo: {pattern.name} for {len(fixtures.fixtures)} fixtures")

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
            # Check if fixture has gobo channel
            if not self._has_gobo_channel(fixture):
                logger.warning(f"Fixture {fixture.fixture_id} has no gobo channel, skipping")
                continue

            # Get fixture-specific DMX value
            dmx_value = self._get_fixture_gobo_value(fixture, pattern)

            # Create effect (static gobo, no curve)
            effect = ChannelEffect(
                fixture_id=fixture.fixture_id,
                channel_name="gobo",
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                dmx_values=[dmx_value],
                value_curve=None,  # Constant value
            )
            effects.append(effect)

        return effects

    def _has_gobo_channel(self, fixture: FixtureInstance) -> bool:
        """Check if fixture has gobo channel.

        Args:
            fixture: Fixture instance

        Returns:
            True if fixture has gobo channel configured
        """
        # Use the property that returns channel number or None
        return fixture.config.dmx_mapping.gobo is not None

    def _get_fixture_gobo_value(
        self, fixture: FixtureInstance, pattern: GoboPatternDefinition
    ) -> int:
        """Get fixture-specific DMX value for gobo.

        Different fixtures have different gobo wheels.
        Uses the fixture's gobo_map to get the correct DMX value.

        Args:
            fixture: Fixture instance
            pattern: Gobo pattern definition

        Returns:
            DMX value for gobo from fixture's gobo_map.
            Returns 0 (off/open) if gobo not supported by fixture.
        """
        gobo_map = fixture.config.dmx_mapping.gobo_map
        gobo_id = pattern.gobo_id

        # Look up gobo in fixture's map
        if gobo_id not in gobo_map:
            # Fallback to DMX 0 (open/off) with warning
            # Better to be safe than send incorrect gobo
            logger.warning(
                f"Gobo '{gobo_id}' not found in fixture {fixture.fixture_id} gobo_map. "
                f"Supported gobos: {sorted(gobo_map.keys())}. Falling back to DMX 0 (open)."
            )
            return 0

        return gobo_map[gobo_id]
