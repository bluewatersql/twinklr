"""Transition segment compiler for generating blended FixtureSegments.

This module compiles transition plans into FixtureSegments with blended
channel values, creating smooth transitions between choreography sections.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.sequencer.models.enum import ChannelName
from blinkb0t.core.sequencer.models.transition import TransitionPlan
from blinkb0t.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from blinkb0t.core.sequencer.moving_heads.compile.channel_blender import ChannelBlender

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TransitionSegmentCompiler:
    """Compiles transition plans into FixtureSegments with blended channels.

    Responsibilities:
    - Generate FixtureSegments for transition overlap regions
    - Blend channel values from source to target states
    - Handle per-fixture, per-channel blending strategies
    - Maintain timing alignment with TransitionPlan
    """

    def __init__(self, blender: ChannelBlender):
        """Initialize transition segment compiler.

        Args:
            blender: ChannelBlender for generating interpolated curves.
        """
        self.blender = blender

    def compile_transition(
        self,
        transition_plan: TransitionPlan,
        source_segments: list[FixtureSegment],
        target_segments: list[FixtureSegment],
    ) -> list[FixtureSegment]:
        """Compile transition plan into fixture segments.

        Args:
            transition_plan: Transition plan with timing and strategies.
            source_segments: Segments from source section (at boundary).
            target_segments: Segments from target section (at boundary).

        Returns:
            List of FixtureSegments for the transition region.

        Example:
            >>> compiler = TransitionSegmentCompiler(blender)
            >>> transition_segments = compiler.compile_transition(
            ...     transition_plan,
            ...     verse_segments,
            ...     chorus_segments
            ... )
        """
        transition_segments = []

        # Group segments by fixture
        source_by_fixture = {seg.fixture_id: seg for seg in source_segments}
        target_by_fixture = {seg.fixture_id: seg for seg in target_segments}

        # Get all fixtures involved (from plan or segments)
        if transition_plan.fixtures:
            fixture_ids = transition_plan.fixtures
        else:
            # Use all fixtures from source and target
            fixture_ids = list(set(source_by_fixture.keys()) | set(target_by_fixture.keys()))

        logger.debug(
            f"Compiling transition {transition_plan.transition_id} for {len(fixture_ids)} fixtures"
        )

        # Compile transition segment for each fixture
        for fixture_id in fixture_ids:
            source_seg = source_by_fixture.get(fixture_id)
            target_seg = target_by_fixture.get(fixture_id)

            # Get source and target channel states
            source_state = self._extract_channel_state(source_seg) if source_seg else {}
            target_state = self._extract_channel_state(target_seg) if target_seg else {}

            # Compile segment for this fixture
            transition_segment = self._compile_fixture_transition(
                fixture_id, transition_plan, source_state, target_state
            )

            transition_segments.append(transition_segment)

        logger.debug(f"Generated {len(transition_segments)} transition segments")
        return transition_segments

    def _compile_fixture_transition(
        self,
        fixture_id: str,
        transition_plan: TransitionPlan,
        source_state: dict[ChannelName, ChannelValue],
        target_state: dict[ChannelName, ChannelValue],
    ) -> FixtureSegment:
        """Compile transition segment for a single fixture.

        Args:
            fixture_id: Fixture ID.
            transition_plan: Transition plan.
            source_state: Source channel states.
            target_state: Target channel states.

        Returns:
            FixtureSegment for this fixture's transition.
        """
        # Get all channels that need blending
        all_channels = set(source_state.keys()) | set(target_state.keys())

        blended_channels: dict[ChannelName, ChannelValue] = {}

        # Blend each channel
        for channel_name in all_channels:
            source_value = source_state.get(channel_name)
            target_value = target_state.get(channel_name)

            # Blend channel
            blended_channel = self._blend_channel_for_segment(
                channel_name,
                source_value,
                target_value,
                transition_plan,
            )

            if blended_channel:
                blended_channels[channel_name] = blended_channel

        # Create transition segment
        return self._create_transition_segment(fixture_id, transition_plan, blended_channels)

    def _blend_channel_for_segment(
        self,
        channel_name: ChannelName,
        source_value: ChannelValue | None,
        target_value: ChannelValue | None,
        transition_plan: TransitionPlan,
    ) -> ChannelValue | None:
        """Blend a single channel for the full transition duration.

        Args:
            channel_name: Channel to blend.
            source_value: Source channel state (may be None).
            target_value: Target channel state (may be None).
            transition_plan: Transition plan with strategies.

        Returns:
            Blended ChannelValue, or None if both source and target are None.
        """
        # If both are None, skip this channel
        if source_value is None and target_value is None:
            return None

        # Extract DMX values at boundary
        source_dmx = self._extract_dmx_value(source_value) if source_value else 0
        target_dmx = self._extract_dmx_value(target_value) if target_value else 0

        # Number of samples for the transition curve
        duration_ms = transition_plan.overlap_duration_ms
        n_samples = max(10, duration_ms // 50)  # At least 10 samples, ~50ms per sample

        # Generate constant curves for source and target
        source_curve = [source_dmx] * n_samples
        target_curve = [target_dmx] * n_samples

        # Blend the curves
        blended_curve = self.blender.blend_channel_curve(
            channel_name,
            source_curve,
            target_curve,
            transition_plan,
            n_samples=n_samples,
        )

        # Create ChannelValue from blended curve
        return self.blender.create_blended_channel_value(
            channel_name,
            blended_curve,
            clamp_min=0,
            clamp_max=255,
        )

    def _extract_channel_state(self, segment: FixtureSegment) -> dict[ChannelName, ChannelValue]:
        """Extract channel state from a fixture segment.

        Args:
            segment: FixtureSegment with channel values.

        Returns:
            Dict mapping channel names to their ChannelValue specifications.
        """
        return segment.channels.copy()

    def _extract_dmx_value(self, channel_value: ChannelValue) -> int:
        """Extract a representative DMX value from a ChannelValue.

        For static values, returns the static_dmx.
        For curve values, returns the midpoint value (approximation).

        Args:
            channel_value: ChannelValue specification.

        Returns:
            DMX value (0-255).
        """
        if channel_value.static_dmx is not None:
            return channel_value.static_dmx

        # For curves, use midpoint value as approximation
        if channel_value.curve and hasattr(channel_value.curve, "points"):
            points = channel_value.curve.points
            if points:
                mid_idx = len(points) // 2
                # Denormalize from [0, 1] to [clamp_min, clamp_max]
                normalized_value = points[mid_idx].v
                return int(
                    channel_value.clamp_min
                    + normalized_value * (channel_value.clamp_max - channel_value.clamp_min)
                )

        # Default to middle DMX value
        return 128

    def _create_transition_segment(
        self,
        fixture_id: str,
        transition_plan: TransitionPlan,
        blended_channels: dict[ChannelName, ChannelValue],
    ) -> FixtureSegment:
        """Create a FixtureSegment for a transition.

        Args:
            fixture_id: Fixture ID.
            transition_plan: Transition plan with timing.
            blended_channels: Blended channel values.

        Returns:
            FixtureSegment representing the transition.
        """
        # Build segment metadata
        metadata = {
            "is_transition": "true",
            "transition_id": transition_plan.transition_id,
            "boundary_type": transition_plan.boundary.type.value,
            "source_id": transition_plan.boundary.source_id,
            "target_id": transition_plan.boundary.target_id,
            "transition_mode": transition_plan.hint.mode.value,
        }

        # Create segment
        return FixtureSegment(
            section_id=f"transition_{transition_plan.boundary.source_id}_to_{transition_plan.boundary.target_id}",
            segment_id=transition_plan.transition_id,
            step_id="transition",
            template_id="transition",
            preset_id=None,
            fixture_id=fixture_id,
            t0_ms=transition_plan.overlap_start_ms,
            t1_ms=transition_plan.overlap_end_ms,
            channels=blended_channels,
            metadata=metadata,
            allow_grouping=False,  # Transitions are per-fixture
        )
