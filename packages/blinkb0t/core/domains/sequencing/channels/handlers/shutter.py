"""Shutter channel handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.libraries.channels.shutter import ShutterLibrary
from blinkb0t.core.domains.sequencing.models.channels import ChannelEffect

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureGroup, FixtureInstance
    from blinkb0t.core.domains.sequencing.libraries.channels.shutter import (
        ShutterPatternDefinition,
    )

logger = logging.getLogger(__name__)


class ShutterHandler:
    """Handler for shutter/strobe channel.

    Responsibilities:
    - Look up shutter pattern from library
    - Generate DMX values for shutter channel (using fixture-specific mappings)
    - Handle beat-synchronized effects (pulse)

    Note: Uses fixture-specific shutter_map for DMX values, not generic library defaults.
    This ensures correct DMX values for different fixture models.
    """

    def __init__(self, library: ShutterLibrary):
        """Initialize shutter handler.

        Args:
            library: Shutter library for pattern definitions
        """
        self._library = library

    def resolve(
        self,
        pattern_id: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> int:
        """Resolve shutter pattern to static DMX value.

        Simple resolution for channel overlays (Phase 5B).
        Returns default DMX value for common patterns.
        Full fixture-specific resolution happens in render().

        Args:
            pattern_id: Shutter pattern ID (e.g., "open", "closed", "strobe_fast")
            start_ms: Start time (unused, for interface compatibility)
            end_ms: End time (unused, for interface compatibility)

        Returns:
            DMX value for the pattern (generic, not fixture-specific)
        """
        # Simple default mapping (generic, not fixture-specific)
        # Full resolution with fixture-specific DMX values happens in render()
        default_values = {
            "open": 255,
            "closed": 0,
            "strobe_slow": 100,
            "strobe_medium": 150,
            "strobe_fast": 200,
        }
        return default_values.get(pattern_id, 255)  # Default to open

    def render(
        self,
        channel_value: str,
        fixtures: FixtureGroup,
        start_time_ms: int,
        end_time_ms: int,
        beat_times_ms: list[int] | None = None,
    ) -> list[ChannelEffect]:
        """Render shutter effects.

        Args:
            channel_value: Shutter pattern ID (e.g., "strobe_fast", "open")
            fixtures: Fixtures to render for
            start_time_ms: Start time
            end_time_ms: End time
            beat_times_ms: Optional beat times for pulse sync

        Returns:
            List of ChannelEffect objects
        """
        # Look up pattern
        pattern = self._library.get_pattern(channel_value)

        logger.debug(
            f"Rendering shutter: {pattern.name} for {len(fixtures.fixtures)} fixtures "
            f"({start_time_ms}ms - {end_time_ms}ms)"
        )

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
            # Check if fixture has shutter channel
            if not self._has_shutter_channel(fixture):
                logger.warning(f"Fixture {fixture.fixture_id} has no shutter channel, skipping")
                continue

            # Generate DMX values using fixture-specific mapping
            if pattern.is_dynamic:
                # Dynamic pattern (e.g., pulse) - use value curve for STEP interpolation
                dmx_values = self._render_dynamic_pattern(
                    fixture, pattern, start_time_ms, end_time_ms, beat_times_ms
                )
                # For dynamic patterns, value_curve can be added if needed
                # For now, pulse uses discrete DMX values (no curve needed)
                value_curve = None
            else:
                # Static pattern (constant DMX value from fixture's shutter_map)
                dmx_value = self._get_fixture_shutter_value(fixture, pattern.pattern_id)
                dmx_values = [dmx_value]
                value_curve = None  # Constant value (no curve)

            # Create effect
            effect = ChannelEffect(
                fixture_id=fixture.fixture_id,
                channel_name="shutter",
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                dmx_values=dmx_values,
                value_curve=value_curve,
            )
            effects.append(effect)

        return effects

    def _has_shutter_channel(self, fixture: FixtureInstance) -> bool:
        """Check if fixture has shutter channel.

        Args:
            fixture: Fixture instance

        Returns:
            True if fixture has shutter channel configured
        """
        # Use the property that returns channel number or None
        return fixture.config.dmx_mapping.shutter is not None

    def _get_fixture_shutter_value(self, fixture: FixtureInstance, pattern_id: str) -> int:
        """Get fixture-specific DMX value for shutter pattern.

        Uses the fixture's shutter_map to get the correct DMX value for this fixture model.

        Args:
            fixture: Fixture instance
            pattern_id: Shutter pattern ID (open, closed, strobe_fast, etc.)

        Returns:
            DMX value for the pattern

        Raises:
            ValueError: If pattern_id is not supported
        """
        shutter_map = fixture.config.dmx_mapping.shutter_map

        # Map pattern IDs to shutter_map attributes
        pattern_mapping = {
            "open": shutter_map.open,
            "closed": shutter_map.closed,
            "strobe_slow": shutter_map.strobe_slow,
            "strobe_medium": shutter_map.strobe_medium,
            "strobe_fast": shutter_map.strobe_fast,
        }

        dmx_value = pattern_mapping.get(pattern_id)
        if dmx_value is None:
            raise ValueError(
                f"Unsupported shutter pattern '{pattern_id}' for fixture {fixture.fixture_id}"
            )

        return dmx_value

    def _render_dynamic_pattern(
        self,
        fixture: FixtureInstance,
        pattern: ShutterPatternDefinition,
        start_time_ms: int,
        end_time_ms: int,
        beat_times_ms: list[int] | None,
    ) -> list[int]:
        """Render dynamic pattern (e.g., pulse).

        For pulse: alternate open/closed on beats using fixture-specific DMX values.

        Args:
            fixture: Fixture instance (for shutter_map)
            pattern: Pattern definition
            start_time_ms: Start time
            end_time_ms: End time
            beat_times_ms: Beat times in milliseconds

        Returns:
            List of DMX values using fixture's shutter_map
        """
        # Get fixture-specific DMX values
        shutter_map = fixture.config.dmx_mapping.shutter_map

        if pattern.pattern_id == "pulse":
            if not beat_times_ms:
                # No beat times, fall back to open
                logger.warning(
                    f"Pulse pattern requires beat times for {fixture.fixture_id}, "
                    "falling back to open"
                )
                return [shutter_map.open]

            # Generate open/closed pattern on beats using fixture-specific values
            dmx_values = []
            is_open = True

            for beat_time in beat_times_ms:
                if start_time_ms <= beat_time <= end_time_ms:
                    dmx_values.append(shutter_map.open if is_open else shutter_map.closed)
                    is_open = not is_open

            # If no beats within range, default to open
            return dmx_values if dmx_values else [shutter_map.open]

        # Unknown dynamic pattern - fallback to open
        logger.warning(
            f"Unknown dynamic pattern '{pattern.pattern_id}' for {fixture.fixture_id}, "
            "falling back to open"
        )
        return [shutter_map.open]
