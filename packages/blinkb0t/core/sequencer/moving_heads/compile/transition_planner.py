"""Transition planning for the moving head sequencer.

This module provides functionality to plan transitions between segments,
calculating overlap timing and determining per-channel strategies.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.config.models import TransitionConfig
from blinkb0t.core.sequencer.models.enum import ChannelName, TransitionMode
from blinkb0t.core.sequencer.models.transition import (
    Boundary,
    TransitionHint,
    TransitionPlan,
    TransitionStrategy,
)
from blinkb0t.core.sequencer.timing.beat_grid import BeatGrid

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TransitionPlanner:
    """Plans transitions by calculating timing and channel strategies.

    Responsibilities:
    - Calculate overlap regions (start/end times)
    - Determine per-channel transition strategies
    - Apply configuration defaults
    - Validate transition feasibility
    """

    def __init__(self, config: TransitionConfig, beat_grid: BeatGrid):
        """Initialize transition planner.

        Args:
            config: Global transition configuration.
            beat_grid: Beat grid for timing calculations.
        """
        self.config = config
        self.beat_grid = beat_grid

    def plan_transition(
        self,
        boundary: Boundary,
        hint: TransitionHint | None,
        fixtures: list[str],
        transition_id: str | None = None,
    ) -> TransitionPlan:
        """Plan a single transition at a boundary.

        Args:
            boundary: The boundary where transition occurs.
            hint: Optional transition hint (from agent or template).
            fixtures: List of fixture IDs involved.
            transition_id: Optional explicit transition ID.

        Returns:
            Complete transition plan with timing and strategies.

        Example:
            >>> planner = TransitionPlanner(config, beat_grid)
            >>> plan = planner.plan_transition(
            ...     boundary=boundary,
            ...     hint=TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=1.0),
            ...     fixtures=["fixture_1", "fixture_2"]
            ... )
        """
        # Use hint or create default
        effective_hint = hint or self._create_default_hint()

        # Generate transition ID if not provided
        if transition_id is None:
            transition_id = f"trans_{boundary.source_id}_to_{boundary.target_id}"

        # Calculate overlap timing
        overlap_start_ms, overlap_end_ms, overlap_duration_ms = self._calculate_overlap(
            boundary, effective_hint
        )

        # Determine per-channel strategies
        channel_strategies = self._determine_channel_strategies(effective_hint)

        # Build transition plan
        plan = TransitionPlan(
            transition_id=transition_id,
            boundary=boundary,
            hint=effective_hint,
            overlap_start_ms=overlap_start_ms,
            overlap_end_ms=overlap_end_ms,
            overlap_duration_ms=overlap_duration_ms,
            channel_strategies=channel_strategies,
            fixtures=fixtures,
            metadata={
                "planned_by": "TransitionPlanner",
                "mode": effective_hint.mode.value,
            },
        )

        logger.debug(
            f"Planned transition {transition_id}: {boundary.source_id} → {boundary.target_id}, "
            f"duration={overlap_duration_ms}ms, mode={effective_hint.mode.value}"
        )

        return plan

    def _create_default_hint(self) -> TransitionHint:
        """Create default transition hint from configuration.

        Returns:
            Default transition hint.
        """
        return TransitionHint(
            mode=self.config.default_mode,
            duration_bars=self.config.default_duration_bars,
            curve=self.config.default_curve,
        )

    def _calculate_overlap(self, boundary: Boundary, hint: TransitionHint) -> tuple[int, int, int]:
        """Calculate overlap timing for a transition.

        The overlap region is centered on the boundary, extending before and after.
        For crossfades, the fade_out_ratio determines asymmetry.

        Args:
            boundary: Boundary where transition occurs.
            hint: Transition hint with duration and mode.

        Returns:
            Tuple of (overlap_start_ms, overlap_end_ms, overlap_duration_ms).

        Algorithm:
            - SNAP: Zero duration (overlap_start = overlap_end = boundary_time)
            - CROSSFADE with fade_out_ratio:
                - fade_out portion extends BEFORE boundary
                - fade_in portion extends AFTER boundary
            - Other modes: Symmetric split around boundary

        Example:
            Boundary at 40000ms, duration=1.0 bars (2000ms), fade_out_ratio=0.5:
            - overlap_start = 40000 - (2000 * 0.5) = 39000ms
            - overlap_end = 40000 + (2000 * 0.5) = 41000ms
        """
        if hint.is_snap:
            # Instant transition - no overlap
            return (boundary.time_ms, boundary.time_ms, 0)

        # Convert duration from bars to milliseconds
        duration_ms = int(hint.duration_bars * self.beat_grid.ms_per_bar)

        if hint.mode == TransitionMode.CROSSFADE:
            # Asymmetric split based on fade_out_ratio
            fade_out_duration_ms = int(duration_ms * hint.fade_out_ratio)
            fade_in_duration_ms = duration_ms - fade_out_duration_ms

            overlap_start_ms = boundary.time_ms - fade_out_duration_ms
            overlap_end_ms = boundary.time_ms + fade_in_duration_ms
        else:
            # Symmetric split for other modes (MORPH, FADE_VIA_BLACK, etc.)
            half_duration_ms = duration_ms // 2

            overlap_start_ms = boundary.time_ms - half_duration_ms
            overlap_end_ms = boundary.time_ms + half_duration_ms

        # Ensure non-negative start time
        overlap_start_ms = max(0, overlap_start_ms)

        # Recalculate actual duration (may differ if we clamped start)
        overlap_duration_ms = overlap_end_ms - overlap_start_ms

        logger.debug(
            f"Calculated overlap: start={overlap_start_ms}ms, end={overlap_end_ms}ms, "
            f"duration={overlap_duration_ms}ms (requested={duration_ms}ms)"
        )

        return (overlap_start_ms, overlap_end_ms, overlap_duration_ms)

    def _determine_channel_strategies(
        self, hint: TransitionHint
    ) -> dict[ChannelName, TransitionStrategy]:
        """Determine per-channel transition strategies.

        Uses hint overrides if provided, otherwise falls back to config defaults.

        Args:
            hint: Transition hint with optional per-channel overrides.

        Returns:
            Dictionary mapping channel names to strategies.

        Example:
            Config defaults: {pan: SMOOTH, tilt: SMOOTH, dimmer: CROSSFADE}
            Hint overrides: {dimmer: FADE_VIA_BLACK}
            Result: {pan: SMOOTH, tilt: SMOOTH, dimmer: FADE_VIA_BLACK}
        """
        strategies: dict[ChannelName, TransitionStrategy] = {}

        # Start with config defaults
        for channel_name_str, strategy_str in self.config.per_channel_defaults.items():
            try:
                channel_name = ChannelName(channel_name_str)
                strategy = TransitionStrategy(strategy_str)
                strategies[channel_name] = strategy
            except ValueError as e:
                logger.warning(
                    f"Invalid config default: channel={channel_name_str}, "
                    f"strategy={strategy_str}, error={e}"
                )

        # Apply hint overrides
        if hint.per_channel_overrides:
            for channel_name_str, strategy_str in hint.per_channel_overrides.items():
                try:
                    channel_name = ChannelName(channel_name_str)
                    strategy = TransitionStrategy(strategy_str)
                    strategies[channel_name] = strategy
                    logger.debug(f"Applied override: {channel_name.value} → {strategy.value}")
                except ValueError as e:
                    logger.warning(
                        f"Invalid hint override: channel={channel_name_str}, "
                        f"strategy={strategy_str}, error={e}"
                    )

        # If hint is SNAP, override all channels to SNAP
        if hint.is_snap:
            for channel_name in strategies:
                strategies[channel_name] = TransitionStrategy.SNAP
            logger.debug("SNAP mode: overriding all channels to SNAP strategy")

        return strategies

    def validate_transition_feasibility(
        self, plan: TransitionPlan, source_duration_ms: int, target_duration_ms: int
    ) -> tuple[bool, list[str]]:
        """Validate that a transition plan is feasible.

        Checks:
        - Overlap doesn't exceed source/target durations
        - Minimum section duration requirements met
        - Timing is sensible (overlap_start < overlap_end)

        Args:
            plan: Transition plan to validate.
            source_duration_ms: Duration of source segment in ms.
            target_duration_ms: Duration of target segment in ms.

        Returns:
            Tuple of (is_valid, list_of_warnings).
        """
        warnings: list[str] = []

        # Check timing sanity
        if plan.overlap_start_ms >= plan.overlap_end_ms:
            warnings.append(
                f"Invalid timing: overlap_start ({plan.overlap_start_ms}ms) >= "
                f"overlap_end ({plan.overlap_end_ms}ms)"
            )

        # Calculate how much overlap extends into source/target
        fade_out_duration_ms = plan.boundary.time_ms - plan.overlap_start_ms
        fade_in_duration_ms = plan.overlap_end_ms - plan.boundary.time_ms

        # Check source segment has enough duration for fade out
        if fade_out_duration_ms > source_duration_ms:
            warnings.append(
                f"Fade-out duration ({fade_out_duration_ms}ms) exceeds source duration "
                f"({source_duration_ms}ms)"
            )

        # Check target segment has enough duration for fade in
        if fade_in_duration_ms > target_duration_ms:
            warnings.append(
                f"Fade-in duration ({fade_in_duration_ms}ms) exceeds target duration "
                f"({target_duration_ms}ms)"
            )

        # Check minimum section duration (convert to ms)
        min_duration_ms = int(self.config.min_section_duration_bars * self.beat_grid.ms_per_bar)
        if source_duration_ms < min_duration_ms:
            warnings.append(
                f"Source duration ({source_duration_ms}ms) below minimum "
                f"({min_duration_ms}ms, {self.config.min_section_duration_bars} bars)"
            )
        if target_duration_ms < min_duration_ms:
            warnings.append(
                f"Target duration ({target_duration_ms}ms) below minimum "
                f"({min_duration_ms}ms, {self.config.min_section_duration_bars} bars)"
            )

        is_valid = len(warnings) == 0

        if warnings:
            logger.warning(
                f"Transition {plan.transition_id} feasibility issues: {'; '.join(warnings)}"
            )

        return (is_valid, warnings)

    def adjust_section_timing(
        self, plan: TransitionPlan, source_end_ms: int, target_start_ms: int
    ) -> tuple[int, int]:
        """Adjust section timing to accommodate transition overlap.

        When transitions overlap, source sections need to be shortened (end earlier)
        and target sections need to start earlier to create the blend region.

        Args:
            plan: Transition plan with overlap timing.
            source_end_ms: Original end time of source section.
            target_start_ms: Original start time of target section.

        Returns:
            Tuple of (adjusted_source_end_ms, adjusted_target_start_ms).

        Algorithm:
            - Source ends at overlap_start (beginning of transition)
            - Target starts at overlap_start (beginning of transition)
            - Both sections render into the overlap region

        Example:
            Original: source=[0, 40000], target=[40000, 80000]
            Transition: overlap=[39000, 41000]
            Adjusted: source=[0, 39000], target=[39000, 80000]
            (Both render overlap region [39000, 41000])
        """
        if plan.hint.is_snap:
            # No adjustment needed for snap transitions
            return (source_end_ms, target_start_ms)

        if not self.config.allow_overlaps:
            # Overlaps disabled - no adjustment
            logger.debug("Overlaps disabled in config, skipping timing adjustment")
            return (source_end_ms, target_start_ms)

        # Adjust source to end at overlap start
        adjusted_source_end_ms = plan.overlap_start_ms

        # Adjust target to start at overlap start
        adjusted_target_start_ms = plan.overlap_start_ms

        logger.debug(
            f"Adjusted timing: source_end {source_end_ms} → {adjusted_source_end_ms}, "
            f"target_start {target_start_ms} → {adjusted_target_start_ms}"
        )

        return (adjusted_source_end_ms, adjusted_target_start_ms)
