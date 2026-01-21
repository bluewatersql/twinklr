"""Per-fixture segment renderer with section awareness.

SegmentRenderer is the core component that converts TemplateStepSegments
into per-fixture SequencedEffects by:
1. Expanding target groups to individual fixtures
2. Calling handlers directly (movement, geometry, dimmer)
3. Applying per-fixture geometry offsets
4. Detecting section boundaries (first/last segments)
5. Handling SOFT_HOME transitions at boundaries
6. Merging with channel overlays
"""

import logging
from collections.abc import Generator
from typing import Any

from blinkb0t.core.config.fixtures import FixtureGroup, FixtureInstance, Pose
from blinkb0t.core.domains.sequencing.infrastructure.curves.factory import get_curve_factory
from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import CustomCurveSpec
from blinkb0t.core.domains.sequencing.libraries.moving_heads import (
    DIMMER_LIBRARY,
    MOVEMENT_LIBRARY,
    CategoricalIntensity,
    DimmerID,
    MovementID,
)
from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec
from blinkb0t.core.domains.sequencing.models.timeline import TemplateStepSegment
from blinkb0t.core.domains.sequencing.moving_heads.dimmer_handler import DimmerHandler
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.engine import (
    GeometryEngine,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.handlers.default import (
    DefaultMovementHandler,
)
from blinkb0t.core.domains.sequencing.poses.resolver import PoseResolver
from blinkb0t.core.domains.sequencing.rendering.models import (
    BoundaryInfo,
    ChannelOverlay,
    ChannelSpecs,
    SequencedEffect,
)
from blinkb0t.core.utils.fixtures import build_semantic_groups

logger = logging.getLogger(__name__)


class SegmentRenderer:
    """Render template segments to per-fixture SequencedEffects.

    Key Responsibilities:
    - Expand target groups to individual fixtures
    - Call handlers directly per fixture
    - Apply geometry transformations (per-fixture offsets)
    - Detect section boundaries (first/last segments)
    - Handle SOFT_HOME transitions
    - Merge with channel overlays

    Output: ONE SequencedEffect per fixture with ALL channels defined.
    """

    def __init__(
        self,
        fixture_group: FixtureGroup,
        pose_resolver: PoseResolver,
        movement_handler: DefaultMovementHandler,
        geometry_engine: GeometryEngine,
        dimmer_handler: DimmerHandler,
    ):
        """Initialize SegmentRenderer with all required dependencies.

        Args:
            fixture_group: All fixtures in the show
            pose_resolver: Resolves pose IDs to degree values
            movement_handler: Generates movement curves
            geometry_engine: Applies per-fixture geometry transformations
            dimmer_handler: Generates dimmer curves
        """
        self.fixture_group = fixture_group
        self.pose_resolver = pose_resolver
        self.movement_handler = movement_handler
        self.geometry_engine = geometry_engine
        self.dimmer_handler = dimmer_handler

        # Build semantic groups for target expansion
        fixture_ids = [f.fixture_id for f in fixture_group.fixtures]
        self.semantic_groups = build_semantic_groups(fixture_ids)

        # Initialize curve factory for generating curve specs
        self.curve_factory = get_curve_factory()

        logger.debug(f"SegmentRenderer initialized with {len(fixture_group.fixtures)} fixtures")

    def render_segments(
        self,
        segments: list[TemplateStepSegment],
        channel_overlays: dict[str, ChannelOverlay],
        section_info: dict[str, tuple[int, int]],
    ) -> Generator[SequencedEffect, None, None]:
        """Render all segments to per-fixture effects.

        Args:
            segments: Template step segments from ExplodedTimeline
            channel_overlays: Pre-resolved channel overlays per section
            section_info: Section boundaries for detecting first/last (section_id -> (start_ms, end_ms))

        Yields:
            SequencedEffect (one per fixture per segment)
        """
        logger.info(f"Rendering {len(segments)} segments")

        for segment in segments:
            # 1. Expand target to fixtures
            target_fixtures = self._expand_target(segment.target)

            # 2. Get channel overlay for this segment's section
            channel_overlay = channel_overlays.get(segment.section_id)

            # 3. Detect section boundaries
            is_first = self._is_first_segment(segment, section_info)
            is_last = self._is_last_segment(segment, section_info)

            # 4. Render per fixture
            for fixture_idx, fixture in enumerate(target_fixtures):
                yield self._render_segment_for_fixture(
                    segment=segment,
                    fixture=fixture,
                    fixture_idx=fixture_idx,
                    total_fixtures=len(target_fixtures),
                    is_first=is_first,
                    is_last=is_last,
                    channel_overlay=channel_overlay,
                )

    def _expand_target(self, target: str) -> list[FixtureInstance]:
        """Expand target specification to list of fixtures.

        Args:
            target: Target specification (e.g., "ALL", "LEFT", "RIGHT", "MH1", "MH1,MH3")

        Returns:
            List of FixtureInstance objects

        Raises:
            ValueError: If target is invalid or fixture not found
        """
        # Handle "ALL" target
        if target.upper() == "ALL":
            # Expand fixtures to ensure we have FixtureInstance objects
            expanded = self.fixture_group.expand_fixtures()
            return expanded

        # Handle semantic groups (LEFT, RIGHT, ODD, EVEN, CENTER, OUTER, INNER)
        if target in self.semantic_groups:
            fixture_ids = self.semantic_groups[target]
            return [self._find_fixture_by_id(fid) for fid in fixture_ids]

        # Handle range (e.g., "MH1-MH3")
        if "-" in target and not target[0].isdigit():  # Avoid confusing with negative numbers
            start_id, end_id = target.split("-", 1)
            start_idx = self._find_fixture_index(start_id.strip())
            end_idx = self._find_fixture_index(end_id.strip())
            expanded = self.fixture_group.expand_fixtures()
            return expanded[start_idx : end_idx + 1]

        # Handle comma-separated list (e.g., "MH1,MH3")
        if "," in target:
            fixture_ids = [fid.strip() for fid in target.split(",")]
            return [self._find_fixture_by_id(fid) for fid in fixture_ids]

        # Handle single fixture
        return [self._find_fixture_by_id(target)]

    def _find_fixture_by_id(self, fixture_id: str) -> FixtureInstance:
        """Find fixture by ID.

        Args:
            fixture_id: Fixture identifier

        Returns:
            FixtureInstance

        Raises:
            ValueError: If fixture not found
        """
        # Expand fixtures to ensure we have FixtureInstance objects
        expanded = self.fixture_group.expand_fixtures()
        for fixture in expanded:
            if fixture.fixture_id == fixture_id:
                return fixture
        raise ValueError(f"Unknown fixture: {fixture_id}")

    def _find_fixture_index(self, fixture_id: str) -> int:
        """Find fixture index by ID.

        Args:
            fixture_id: Fixture identifier

        Returns:
            Index in fixture group

        Raises:
            ValueError: If fixture not found
        """
        for idx, fixture in enumerate(self.fixture_group.fixtures):
            if fixture.fixture_id == fixture_id:
                return idx
        raise ValueError(f"Unknown fixture: {fixture_id}")

    def _is_first_segment(
        self,
        segment: TemplateStepSegment,
        section_info: dict[str, tuple[int, int]],
    ) -> bool:
        """Check if segment is the first in its section.

        Args:
            segment: Template step segment
            section_info: Section boundaries (section_id -> (start_ms, end_ms))

        Returns:
            True if segment starts at section start
        """
        if segment.section_id not in section_info:
            return False

        section_start, _ = section_info[segment.section_id]
        return segment.start_ms == section_start

    def _is_last_segment(
        self,
        segment: TemplateStepSegment,
        section_info: dict[str, tuple[int, int]],
    ) -> bool:
        """Check if segment is the last in its section.

        Args:
            segment: Template step segment
            section_info: Section boundaries (section_id -> (start_ms, end_ms))

        Returns:
            True if segment ends at section end
        """
        if segment.section_id not in section_info:
            return False

        _, section_end = section_info[segment.section_id]
        return segment.end_ms == section_end

    def _create_boundary_info(
        self,
        is_first: bool,
        is_last: bool,
        section_id: str,
    ) -> BoundaryInfo:
        """Create BoundaryInfo for segment.

        Args:
            is_first: True if first segment in section
            is_last: True if last segment in section
            section_id: Section identifier

        Returns:
            BoundaryInfo with appropriate flags set
        """
        return BoundaryInfo(
            is_section_start=is_first,
            is_section_end=is_last,
            section_id=section_id,
            is_gap_fill=False,
        )

    def _create_curve_from_movement(
        self,
        movement_id: str,
        intensity: str,
        base_dmx: int,
        fixture: FixtureInstance,
        channel: str,
    ) -> ValueCurveSpec | CustomCurveSpec | int:
        """Create curve spec from movement pattern.

        Args:
            movement_id: Movement pattern ID (e.g., "sweep_lr", "hold")
            intensity: Categorical intensity ("SMOOTH", "DRAMATIC", "INTENSE")
            base_dmx: Base DMX value (center position)
            fixture: Fixture instance for DMX limits
            channel: Channel name ("pan" or "tilt")

        Returns:
            ValueCurveSpec, CustomCurveSpec, or static int if movement is "hold"
        """
        # Handle "hold" as static position
        if movement_id == "hold":
            return base_dmx

        try:
            # Look up movement pattern
            movement_enum = MovementID(movement_id)
            pattern = MOVEMENT_LIBRARY[movement_enum]

            # Get categorical params based on intensity
            intensity_enum = CategoricalIntensity(intensity)
            cat_params = pattern.categorical_params[intensity_enum]

            # Get fixture-specific limits for this channel
            if channel == "pan":
                fixture_min = fixture.config.limits.pan_min
                fixture_max = fixture.config.limits.pan_max
            elif channel == "tilt":
                fixture_min = fixture.config.limits.tilt_min
                fixture_max = fixture.config.limits.tilt_max
            else:
                # Fallback to full DMX range for other channels
                fixture_min = 0
                fixture_max = 255

            # Calculate DMX range from amplitude within fixture limits
            # Amplitude is 0-1 fraction of fixture's available range
            fixture_range = fixture_max - fixture_min
            amplitude_dmx = fixture_range * cat_params.amplitude

            # Calculate min/max around center, clamped to fixture limits
            min_dmx = max(fixture_min, int(base_dmx - amplitude_dmx / 2))
            max_dmx = min(fixture_max, int(base_dmx + amplitude_dmx / 2))

            # Get curve name from primary curve
            curve_name = pattern.primary_curve.curve.value  # CurveType enum value

            # Create params dict for factory
            params: dict[str, Any] = {
                "frequency": cat_params.frequency,
            }

            # Create curve spec using factory
            curve_spec = self.curve_factory.create_curve(
                curve_name=curve_name,
                min_dmx=min_dmx,
                max_dmx=max_dmx,
                params=params,
                num_points=100,
            )

            logger.debug(
                f"Created curve for {channel} from {movement_id}/{intensity}: "
                f"curve={curve_name}, range=[{min_dmx}, {max_dmx}]"
            )

            return curve_spec

        except (KeyError, ValueError) as e:
            logger.warning(
                f"Failed to create curve from movement {movement_id}: {e}, using static value"
            )
            return base_dmx

    def _create_curve_from_dimmer(
        self,
        dimmer_id: str,
        dimmer_params: dict[str, Any],
        intensity: str,
    ) -> ValueCurveSpec | CustomCurveSpec | int:
        """Create curve spec from dimmer pattern.

        Args:
            dimmer_id: Dimmer pattern ID (e.g., "breathe", "fade_in")
            dimmer_params: Dimmer parameters (may include base_pct for static patterns)
            intensity: Categorical intensity ("SMOOTH", "DRAMATIC", "INTENSE")

        Returns:
            ValueCurveSpec, CustomCurveSpec, or static int for "full"/"hold"
        """
        # Handle static patterns with base_pct
        if dimmer_id in ["full", "hold", "static"]:
            base_pct = dimmer_params.get("base_pct", 100)
            return int(round((float(base_pct) / 100.0) * 255.0))

        try:
            # Look up dimmer pattern
            dimmer_enum = DimmerID(dimmer_id)
            pattern = DIMMER_LIBRARY[dimmer_enum]

            # Get categorical params based on intensity
            intensity_enum = CategoricalIntensity(intensity)
            cat_params = pattern.categorical_params[intensity_enum]

            # DimmerCategoricalParams uses min_intensity/max_intensity, not amplitude/center
            min_dmx = cat_params.min_intensity
            max_dmx = cat_params.max_intensity

            # Get curve name from primary curve
            curve_name = pattern.primary_curve.curve.value

            # Dimmer patterns don't use frequency parameter
            params: dict[str, Any] = {}

            # Create curve spec
            curve_spec = self.curve_factory.create_curve(
                curve_name=curve_name,
                min_dmx=min_dmx,
                max_dmx=max_dmx,
                params=params,
                num_points=100,
            )

            logger.debug(
                f"Created dimmer curve from {dimmer_id}/{intensity}: "
                f"curve={curve_name}, range=[{min_dmx}, {max_dmx}]"
            )

            return curve_spec

        except (KeyError, ValueError) as e:
            logger.warning(
                f"Failed to create dimmer curve from {dimmer_id}: {e}, using static value"
            )
            return 255

    def _render_segment_for_fixture(
        self,
        segment: TemplateStepSegment,
        fixture: FixtureInstance,
        fixture_idx: int,
        total_fixtures: int,
        is_first: bool,
        is_last: bool,
        channel_overlay: ChannelOverlay | None,
    ) -> SequencedEffect:
        """Render a segment for a single fixture.

        Args:
            segment: Template step segment
            fixture: Target fixture
            fixture_idx: Index of this fixture in the target group
            total_fixtures: Total number of fixtures in target
            is_first: True if first segment in section
            is_last: True if last segment in section
            channel_overlay: Optional channel overlay for appearance channels

        Returns:
            SequencedEffect with all channels defined

        Phase 3 Implementation:
            - Uses PoseResolver for base positions
            - Returns static DMX values for pan/tilt/dimmer
            - Merges channel overlays for appearance channels
            - Will be enhanced in Phase 4 to return full ValueCurveSpecs
        """
        # 1. Resolve base pose to pan/tilt degrees
        base_pan_deg, base_tilt_deg = self.pose_resolver.resolve_pose(segment.base_pose)

        logger.debug(
            f"Resolved pose {segment.base_pose} for {fixture.fixture_id}: "
            f"pan={base_pan_deg}°, tilt={base_tilt_deg}°"
        )

        # 2. Convert degrees to DMX values (as center/base values for curves)
        pose = Pose(pan_deg=base_pan_deg, tilt_deg=base_tilt_deg)
        pan_dmx, tilt_dmx = fixture.config.degrees_to_dmx(pose)

        # 3. Apply geometry offsets if specified
        if segment.geometry_id:
            # Geometry engine applies per-fixture offsets
            logger.debug(f"Geometry '{segment.geometry_id}' specified but not yet implemented")
            # TODO: Implement geometry engine integration

        # 4. Get intensity from movement params (or default to SMOOTH)
        intensity = segment.movement_params.get("intensity", "SMOOTH")

        # 5. Create movement curves from patterns (pan/tilt)
        pan_spec = self._create_curve_from_movement(
            movement_id=segment.movement_id,
            intensity=intensity,
            base_dmx=pan_dmx,
            fixture=fixture,
            channel="pan",
        )

        tilt_spec = self._create_curve_from_movement(
            movement_id=segment.movement_id,
            intensity=intensity,
            base_dmx=tilt_dmx,
            fixture=fixture,
            channel="tilt",
        )

        # 6. Create dimmer curve from pattern
        dimmer_spec = self._create_curve_from_dimmer(
            dimmer_id=segment.dimmer_id,
            dimmer_params=segment.dimmer_params,
            intensity=intensity,
        )

        # 7. Create BoundaryInfo
        boundary_info = self._create_boundary_info(is_first, is_last, segment.section_id)

        # 8. Create ChannelSpecs with movement curves and appearance channels
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
            pan=pan_spec,  # Now a curve spec!
            tilt=tilt_spec,  # Now a curve spec!
            dimmer=dimmer_spec,  # Now a curve spec!
            # Appearance channels from overlay (if present and not strings)
            shutter=shutter_value,
            color=color_value,
            gobo=gobo_value,
        )

        # 7. Create SequencedEffect
        effect = SequencedEffect(
            fixture_id=fixture.fixture_id,
            start_ms=int(segment.start_ms),
            end_ms=int(segment.end_ms),
            channels=channels,
            boundary_info=boundary_info,
            label=f"{segment.template_id}_{segment.movement_id}",
            metadata={
                "segment_id": segment.step_id,
                "section_id": segment.section_id,
                "template_id": segment.template_id,
                "movement_id": segment.movement_id,
                "dimmer_id": segment.dimmer_id,
                "fixture_idx": fixture_idx,
                "total_fixtures": total_fixtures,
            },
        )

        logger.debug(
            f"Created SequencedEffect for {fixture.fixture_id}: "
            f"{segment.start_ms}-{segment.end_ms}ms"
        )

        return effect
