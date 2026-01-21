"""Channel integration pipeline orchestrator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.channels.pipeline.boundary_detector import (
    BoundaryDetector,
)
from blinkb0t.core.domains.sequencing.channels.pipeline.channel_state_filler import (
    ChannelStateFiller,
)
from blinkb0t.core.domains.sequencing.channels.pipeline.effect_splitter import EffectSplitter
from blinkb0t.core.domains.sequencing.channels.pipeline.gap_detector import GapDetector
from blinkb0t.core.domains.sequencing.channels.pipeline.gap_filler import GapFiller
from blinkb0t.core.domains.sequencing.channels.state import ChannelState
from blinkb0t.core.domains.sequencing.models.channels import DmxEffect, SequencedEffect

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureGroup, FixtureInstance
    from blinkb0t.core.domains.sequencing.models.channels import ChannelEffect

logger = logging.getLogger(__name__)


class ChannelIntegrationPipeline:
    """Integrate movement and channel effects into discrete DMX effects.

    Coordinates the entire pipeline:
    1. Convert channel effects to SequencedEffect
    2. Group effects by fixture
    3. Detect boundaries
    4. Split at boundaries
    5. Fill all channels
    6. Detect and fill gaps

    Example:
        >>> pipeline = ChannelIntegrationPipeline()
        >>> dmx_effects = pipeline.process_section(
        ...     movement_effects=[...],
        ...     channel_effects=[...],
        ...     fixtures=fixture_group,
        ...     section_start_ms=0,
        ...     section_end_ms=8000
        ... )
    """

    def __init__(self):
        """Initialize pipeline components."""
        self.boundary_detector = BoundaryDetector()
        self.effect_splitter = EffectSplitter()
        self.channel_filler = ChannelStateFiller()
        self.gap_detector = GapDetector()
        self.gap_filler = GapFiller()

    def process_section(
        self,
        movement_effects: list[SequencedEffect],
        channel_effects: list[ChannelEffect],
        fixtures: FixtureGroup,
        section_start_ms: int,
        section_end_ms: int,
    ) -> list[DmxEffect]:
        """Process section effects into DMX effects.

        Args:
            movement_effects: Movement handler outputs
            channel_effects: Channel handler outputs
            fixtures: Fixture group (already resolved from semantic groups)
            section_start_ms: Section start time
            section_end_ms: Section end time

        Returns:
            List of DmxEffect objects ready for XSQ conversion

        Example:
            >>> pipeline = ChannelIntegrationPipeline()
            >>> dmx_effects = pipeline.process_section(
            ...     movement_effects=[...],
            ...     channel_effects=[...],
            ...     fixtures=fixture_group,
            ...     section_start_ms=0,
            ...     section_end_ms=8000
            ... )
        """
        logger.info(
            f"Processing section: {section_start_ms}-{section_end_ms}ms, "
            f"{len(movement_effects)} movement effects, "
            f"{len(channel_effects)} channel effects, "
            f"{len(fixtures.fixtures)} fixtures"
        )

        # 1. Convert channel effects to SequencedEffect
        channel_sequenced = self._convert_channel_effects(channel_effects)
        all_effects = movement_effects + channel_sequenced

        logger.debug(f"Total effects after conversion: {len(all_effects)}")

        # 2. Group effects by fixture and process each
        all_dmx_effects = []

        # Expand fixtures to ensure we have full FixtureInstance objects
        expanded_fixtures = fixtures.expand_fixtures()

        for fixture in expanded_fixtures:
            # Get effects targeting this fixture
            fixture_effects = self._filter_effects_for_fixture(
                all_effects, fixture.fixture_id, fixtures.group_id, fixture.xlights_model_name
            )

            # Process this fixture's effects
            dmx_effects = self._process_fixture(
                fixture_effects, fixture, section_start_ms, section_end_ms
            )

            all_dmx_effects.extend(dmx_effects)

        logger.info(f"Generated {len(all_dmx_effects)} DMX effects")

        return all_dmx_effects

    def _convert_channel_effects(
        self, channel_effects: list[ChannelEffect]
    ) -> list[SequencedEffect]:
        """Convert ChannelEffect to SequencedEffect.

        Args:
            channel_effects: List of channel effects

        Returns:
            List of SequencedEffect
        """
        sequenced = []

        for ce in channel_effects:
            # Create ChannelState for this channel
            # Note: We need a fixture instance, but we only have fixture_id
            # This will be resolved during filtering
            # For now, create a minimal representation
            sequenced.append(
                SequencedEffect(
                    targets=[ce.fixture_id],  # Direct fixture targeting
                    channels={ce.channel_name: self._create_channel_state_from_effect(ce)},
                    start_ms=ce.start_time_ms,
                    end_ms=ce.end_time_ms,
                    metadata={"source": "channel_handler", "channel": ce.channel_name},
                )
            )

        return sequenced

    def _create_channel_state_from_effect(self, effect: ChannelEffect) -> ChannelState:
        """Create ChannelState from ChannelEffect.

        Note: This is a simplified implementation. In production, we'd need
        to properly handle value curves and interpolation.

        Args:
            effect: Channel effect

        Returns:
            ChannelState with channel values
        """
        # This is a placeholder - in real implementation, we'd need the fixture
        # For now, we'll rely on the fact that ChannelState will be properly
        # created during fixture-specific processing
        from unittest.mock import Mock

        # Create a mock fixture for the ChannelState
        mock_fixture = Mock()
        mock_fixture.fixture_id = effect.fixture_id
        mock_fixture.config = Mock()
        mock_fixture.config.dmx_mapping = Mock()
        # Set channel numbers based on channel name
        channel_map = {
            "pan": 1,
            "tilt": 2,
            "dimmer": 3,
            "shutter": 4,
            "color": 5,
            "gobo": 6,
        }
        for ch_name, ch_num in channel_map.items():
            setattr(
                mock_fixture.config.dmx_mapping,
                ch_name,
                ch_num if ch_name != effect.channel_name else ch_num,
            )

        state = ChannelState(fixture=mock_fixture)
        state.set_channel(effect.channel_name, effect.dmx_values[0])
        return state

    def _filter_effects_for_fixture(
        self,
        effects: list[SequencedEffect],
        fixture_id: str,
        group_name: str,
        xlights_model_name: str,
    ) -> list[SequencedEffect]:
        """Filter effects that target this fixture.

        Args:
            effects: All effects
            fixture_id: Fixture ID to filter for (e.g., "MH3")
            group_name: Group name (for matching "ALL" targets)
            xlights_model_name: xLights model name (e.g., "Dmx MH3")

        Returns:
            Effects targeting this fixture
        """
        filtered = []

        for effect in effects:
            # Check if this effect targets the fixture
            # Targets can be: fixture_id, xlights_model_name, group_name, "ALL"
            if (
                fixture_id in effect.targets
                or xlights_model_name in effect.targets  # CRITICAL: Match xLights model names
                or group_name in effect.targets
                or "ALL" in effect.targets
            ):
                filtered.append(effect)

        logger.debug(f"Filtered to {len(filtered)} effects for {fixture_id}")
        return filtered

    def _process_fixture(
        self,
        effects: list[SequencedEffect],
        fixture: FixtureInstance,
        section_start_ms: int,
        section_end_ms: int,
    ) -> list[DmxEffect]:
        """Process effects for a single fixture.

        Args:
            effects: Effects targeting this fixture
            fixture: Fixture instance
            section_start_ms: Section start time
            section_end_ms: Section end time

        Returns:
            List of DmxEffect for this fixture
        """
        if not effects:
            # No effects - fill entire section with gap
            gaps = [self.gap_detector.detect([], section_start_ms, section_end_ms)[0]]
            return self.gap_filler.fill(gaps, fixture)

        # Detect boundaries
        boundaries = self.boundary_detector.detect(effects)

        # Split effects at boundaries
        segments = self.effect_splitter.split(effects, boundaries)

        # Fill all channels
        filled_effects = self.channel_filler.fill(segments, fixture)

        # Detect gaps
        gaps = self.gap_detector.detect(filled_effects, section_start_ms, section_end_ms)

        # Fill gaps
        gap_effects = self.gap_filler.fill(gaps, fixture)

        # Merge and sort by time
        all_effects = filled_effects + gap_effects
        all_effects.sort(key=lambda e: e.start_ms)

        return all_effects
