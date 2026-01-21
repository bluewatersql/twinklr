"""Gap renderer for inter-section gaps.

GapRenderer handles the rendering of timeline gaps where fixtures should
hold at SOFT_HOME position with dimmer off. This creates smooth transitions
between sections and prevents fixtures from jumping unexpectedly.
"""

import logging

from blinkb0t.core.config.fixtures import FixtureGroup, Pose
from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec
from blinkb0t.core.domains.sequencing.models.poses import PoseID
from blinkb0t.core.domains.sequencing.models.timeline import GapSegment
from blinkb0t.core.domains.sequencing.poses.standards import STANDARD_POSES
from blinkb0t.core.domains.sequencing.rendering.models import (
    BoundaryInfo,
    ChannelOverlay,
    ChannelSpecs,
    SequencedEffect,
)

logger = logging.getLogger(__name__)


class GapRenderer:
    """Render gap segments to per-fixture SequencedEffects.

    Gaps are inter-section gaps (between sections) or end-of-song gaps.
    Strategy: Hold at SOFT_HOME position with dimmer off.

    This creates smooth, predictable behavior during timeline gaps:
    - Fixtures return to neutral position (SOFT_HOME)
    - Dimmer is turned off (no light output)
    - Appearance channels can still be controlled via overlays
    """

    def __init__(self):
        """Initialize GapRenderer."""
        logger.debug("GapRenderer initialized")

    def detect_and_render_gaps_per_fixture(
        self,
        segment_effects: list[SequencedEffect],
        fixture_group: FixtureGroup,
        channel_overlays: dict[str, ChannelOverlay],
        total_duration_ms: float,
    ) -> list[SequencedEffect]:
        """Detect and render gaps per-fixture from segment effects.

        This is the correct way to detect gaps - analyze each fixture's timeline
        independently, not globally. Handles cases where different groups/targets
        have different active periods.

        Args:
            segment_effects: All rendered segment effects (per-fixture)
            fixture_group: All fixtures in the show
            channel_overlays: Channel overlays per section
            total_duration_ms: Total song duration

        Returns:
            List of gap SequencedEffects (one per gap per fixture)

        Example:
            - RIGHT group ends at 57751, next at 77002 → gap 57751-77002
            - LEFT group ends at 64168, next at 77002 → gap 64168-77002
            Different gaps for different fixtures based on their actual timelines.
        """
        gap_effects = []

        # Expand fixtures to ensure we have FixtureInstance objects
        expanded_fixtures = fixture_group.expand_fixtures()

        # Group segment effects by fixture_id
        effects_by_fixture: dict[str, list[SequencedEffect]] = {}
        for effect in segment_effects:
            fixture_id = effect.fixture_id
            if fixture_id not in effects_by_fixture:
                effects_by_fixture[fixture_id] = []
            effects_by_fixture[fixture_id].append(effect)

        logger.info(f"Detecting gaps for {len(expanded_fixtures)} fixtures")

        # Detect gaps for each fixture independently
        for fixture in expanded_fixtures:
            fixture_id = fixture.fixture_id
            fixture_effects = effects_by_fixture.get(fixture_id, [])

            # Sort effects by start time
            fixture_effects.sort(key=lambda e: e.start_ms)

            # Detect gaps for this fixture
            fixture_gaps = self._detect_gaps_for_fixture(
                fixture_effects=fixture_effects,
                fixture_id=fixture_id,
                total_duration_ms=total_duration_ms,
            )

            logger.debug(
                f"Fixture {fixture_id}: {len(fixture_effects)} effects, {len(fixture_gaps)} gaps detected"
            )

            # Render gap effects for this fixture
            for gap_start, gap_end, section_id in fixture_gaps:
                # Get appropriate channel overlay
                section_overlay = None
                if section_id and section_id in channel_overlays:
                    section_overlay = channel_overlays[section_id]
                elif channel_overlays:
                    section_overlay = next(iter(channel_overlays.values()))

                # Create gap segment for this fixture
                gap = GapSegment(
                    start_ms=gap_start,
                    end_ms=gap_end,
                    section_id=section_id,
                    gap_type="inter_section",
                )

                effect = self._render_gap_for_fixture(
                    gap=gap,
                    fixture=fixture,
                    channel_overlay=section_overlay,
                )
                gap_effects.append(effect)

        logger.info(f"Created {len(gap_effects)} gap effects across all fixtures")
        return gap_effects

    def _detect_gaps_for_fixture(
        self,
        fixture_effects: list[SequencedEffect],
        fixture_id: str,
        total_duration_ms: float,
    ) -> list[tuple[float, float, str | None]]:
        """Detect gaps in a single fixture's timeline.

        Args:
            fixture_effects: Effects for this fixture (sorted by start time)
            fixture_id: Fixture identifier
            total_duration_ms: Total song duration

        Returns:
            List of (start_ms, end_ms, section_id) tuples for each gap
        """
        gaps: list[tuple[float, float, str | None]] = []

        if not fixture_effects:
            # Entire timeline is a gap
            if total_duration_ms > 0:
                gaps.append((0.0, total_duration_ms, None))
            return gaps

        # Gap at start (0 → first effect)
        first_effect = fixture_effects[0]
        if first_effect.start_ms > 0:
            gaps.append((0.0, first_effect.start_ms, None))

        # Gaps between effects
        for i in range(len(fixture_effects) - 1):
            curr = fixture_effects[i]
            next_effect = fixture_effects[i + 1]

            if curr.end_ms < next_effect.start_ms:
                gap_size = next_effect.start_ms - curr.end_ms
                # Skip tiny gaps (likely precision artifacts)
                if gap_size >= 1.0:  # At least 1ms
                    # Use section_id from next effect for context
                    section_id = (
                        next_effect.metadata.get("section_id") if next_effect.metadata else None
                    )
                    gaps.append((curr.end_ms, next_effect.start_ms, section_id))

        # Gap at end (last effect → total duration)
        last_effect = fixture_effects[-1]
        if last_effect.end_ms < total_duration_ms:
            gaps.append((last_effect.end_ms, total_duration_ms, None))

        return gaps

    def render_gaps(
        self,
        gaps: list[GapSegment],
        fixture_group: FixtureGroup,
        channel_overlays: dict[str, ChannelOverlay],
        segment_effects: list[SequencedEffect] | None = None,
    ) -> list[SequencedEffect]:
        """Render gaps to per-fixture effects.

        Only creates gap effects for fixtures that are actually idle during the gap.
        This prevents filling gaps for fixtures that are active in other groups.

        Args:
            gaps: Gap segments from ExplodedTimeline
            fixture_group: All fixtures in the show
            channel_overlays: Channel overlays per section
            segment_effects: Optional list of segment effects to determine which fixtures are active

        Returns:
            List of SequencedEffect (one per idle fixture per gap)

        Example:
            >>> renderer = GapRenderer()
            >>> effects = renderer.render_gaps(
            ...     gaps=[GapSegment(start_ms=1000, end_ms=2000, gap_type="inter_section")],
            ...     fixture_group=fixture_group,
            ...     channel_overlays={},
            ...     segment_effects=segment_effects
            ... )
        """
        gap_effects = []

        logger.info(f"Rendering {len(gaps)} gaps")

        # Expand fixtures to ensure we have FixtureInstance objects
        expanded_fixtures = fixture_group.expand_fixtures()
        all_fixture_ids = {f.fixture_id for f in expanded_fixtures}

        logger.debug(f"Checking gaps against {len(expanded_fixtures)} fixtures")

        # Build fixture activity map if segment effects provided
        fixture_activity: dict[str, list[tuple[float, float]]] = {}
        if segment_effects:
            for effect in segment_effects:
                fixture_id = effect.fixture_id
                if fixture_id not in fixture_activity:
                    fixture_activity[fixture_id] = []
                fixture_activity[fixture_id].append((effect.start_ms, effect.end_ms))

        for gap in gaps:
            # Skip zero-duration gaps (defensive check)
            gap_duration = gap.end_ms - gap.start_ms
            if gap_duration < 1.0:  # Less than 1ms
                logger.debug(f"Skipping zero-duration gap: {gap.start_ms}ms - {gap.end_ms}ms")
                continue

            # Determine which fixtures are idle during this gap
            idle_fixtures = self._detect_idle_fixtures(
                gap=gap,
                all_fixture_ids=all_fixture_ids,
                fixture_activity=fixture_activity,
                expanded_fixtures=expanded_fixtures,
            )

            if not idle_fixtures:
                logger.debug(
                    f"No idle fixtures during gap {gap.start_ms}ms - {gap.end_ms}ms, skipping"
                )
                continue

            logger.debug(
                f"Gap {gap.start_ms}ms - {gap.end_ms}ms: {len(idle_fixtures)} idle fixtures "
                f"({', '.join(f.fixture_id for f in idle_fixtures)})"
            )

            # Determine which section's channel overlay to use
            section_overlay = self._get_gap_overlay(gap, channel_overlays)

            # Render gap only for idle fixtures
            for fixture in idle_fixtures:
                effect = self._render_gap_for_fixture(
                    gap=gap,
                    fixture=fixture,
                    channel_overlay=section_overlay,
                )
                gap_effects.append(effect)

        logger.info(f"Created {len(gap_effects)} gap effects for idle fixtures")
        return gap_effects

    def _detect_idle_fixtures(
        self,
        gap: GapSegment,
        all_fixture_ids: set[str],
        fixture_activity: dict[str, list[tuple[float, float]]],
        expanded_fixtures: list,
    ) -> list:
        """Detect which fixtures are idle during a gap period.

        A fixture is idle if it has no active effects overlapping the gap period.

        Args:
            gap: Gap segment to check
            all_fixture_ids: Set of all fixture IDs in the show
            fixture_activity: Map of fixture_id to list of (start_ms, end_ms) active periods
            expanded_fixtures: List of all FixtureInstance objects

        Returns:
            List of FixtureInstance objects that are idle during the gap
        """
        idle_fixtures = []

        for fixture in expanded_fixtures:
            fixture_id = fixture.fixture_id

            # Get active periods for this fixture
            active_periods = fixture_activity.get(fixture_id, [])

            # Check if fixture is active during gap period
            is_active = False
            for active_start, active_end in active_periods:
                # Check for overlap: gap overlaps if gap.start < active_end AND gap.end > active_start
                if gap.start_ms < active_end and gap.end_ms > active_start:
                    is_active = True
                    break

            # If not active, fixture is idle and needs gap fill
            if not is_active:
                idle_fixtures.append(fixture)

        return idle_fixtures

    def _render_gap_for_fixture(
        self,
        gap: GapSegment,
        fixture,
        channel_overlay: ChannelOverlay | None,
    ) -> SequencedEffect:
        """Render a gap for a single fixture.

        Args:
            gap: Gap segment
            fixture: Fixture instance
            channel_overlay: Optional channel overlay

        Returns:
            SequencedEffect with SOFT_HOME position and dimmer off
        """
        # Get SOFT_HOME position (0°, 0°)
        domain_pose = STANDARD_POSES[PoseID.SOFT_HOME]

        # Convert to config Pose for DMX conversion
        config_pose = Pose(pan_deg=domain_pose.pan_deg, tilt_deg=domain_pose.tilt_deg)

        # Convert to DMX
        pan_dmx, tilt_dmx = fixture.config.degrees_to_dmx(config_pose)

        logger.debug(
            f"Gap for {fixture.fixture_id}: SOFT_HOME @ pan={pan_dmx}, tilt={tilt_dmx}, dimmer=0"
        )

        # Create ChannelSpecs with SOFT_HOME and overlay
        # Filter out strings from overlay (ChannelSpecs doesn't accept strings)
        shutter_value = None
        color_value = None
        gobo_value = None
        if channel_overlay:
            shutter_value = (
                channel_overlay.shutter
                if isinstance(channel_overlay.shutter, (ValueCurveSpec, int))
                else None
            )
            color_value = (
                channel_overlay.color if isinstance(channel_overlay.color, (int, tuple)) else None
            )
            gobo_value = channel_overlay.gobo if isinstance(channel_overlay.gobo, int) else None

        channels = ChannelSpecs(
            pan=pan_dmx,
            tilt=tilt_dmx,
            dimmer=0,  # Off during gap
            # Appearance channels from overlay (if present and not strings)
            shutter=shutter_value,
            color=color_value,
            gobo=gobo_value,
        )

        # Create boundary info
        boundary_info = BoundaryInfo(
            section_id=gap.section_id,
            is_gap_fill=True,
            gap_type=gap.gap_type,
        )

        # Create SequencedEffect
        return SequencedEffect(
            fixture_id=fixture.fixture_id,
            start_ms=int(gap.start_ms),
            end_ms=int(gap.end_ms),
            channels=channels,
            boundary_info=boundary_info,
            label=f"gap_{gap.gap_type}",
            metadata={
                "source": "gap_renderer",
                "gap_type": gap.gap_type,
                "section_id": gap.section_id,
            },
        )

    def _get_gap_overlay(
        self,
        gap: GapSegment,
        channel_overlays: dict[str, ChannelOverlay],
    ) -> ChannelOverlay | None:
        """Get appropriate channel overlay for gap.

        Strategy:
        1. If gap has section_id and overlay exists, use it
        2. Otherwise, use first available overlay
        3. If no overlays, return None

        Args:
            gap: Gap segment
            channel_overlays: Available channel overlays per section

        Returns:
            ChannelOverlay or None
        """
        # Try to find overlay for gap's section
        if gap.section_id and gap.section_id in channel_overlays:
            logger.debug(f"Using overlay for section '{gap.section_id}'")
            return channel_overlays[gap.section_id]

        # Fallback to first available overlay
        if channel_overlays:
            first_overlay = next(iter(channel_overlays.values()))
            logger.debug("Using first available overlay for gap")
            return first_overlay

        # No overlays available
        logger.debug("No channel overlay available for gap")
        return None
