"""Main rendering pipeline orchestration.

Ties all renderer_v2 components together:
- Timeline planning (bars → segments)
- Channel overlay resolution
- Segment rendering (per-fixture expansion)
- Gap rendering
- Curve rendering & blending
- XSQ export

This is the single entry point for the new rendering architecture.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.models.timeline import (
    ExplodedTimeline,
    TemplateStepSegment,
)
from blinkb0t.core.domains.sequencing.rendering.channel_overlay import (
    resolve_channel_overlays,
)
from blinkb0t.core.domains.sequencing.rendering.curve_pipeline import CurvePipeline
from blinkb0t.core.domains.sequencing.rendering.gap_renderer import GapRenderer
from blinkb0t.core.domains.sequencing.rendering.segment_renderer import SegmentRenderer
from blinkb0t.core.domains.sequencing.rendering.xlights_provider import XlightsProvider

if TYPE_CHECKING:
    from blinkb0t.core.agents.moving_heads.models_agent_plan import AgentImplementation
    from blinkb0t.core.config.fixtures import FixtureGroup
    from blinkb0t.core.config.models import JobConfig
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.timing.beat_grid import BeatGrid
    from blinkb0t.core.domains.sequencing.models.templates import Template

logger = logging.getLogger(__name__)


class RenderingPipeline:
    """Main rendering pipeline orchestrator.

    Clean architecture pipeline that converts AgentImplementation to XSQ:

    1. Timeline Planning: AgentImplementation → ExplodedTimeline (segments)
    2. Channel Overlay: Resolve shutter/color/gobo specifications
    3. Segment Rendering: Template steps → SequencedEffects (per-fixture)
    4. Gap Rendering: Fill gaps with hold positions
    5. Curve Rendering: Generate/blend curves → RenderedEffects
    6. XSQ Export: RenderedEffects → xLights XSQ file

    Usage:
        pipeline = RenderingPipeline(
            curve_generator=curve_generator,
            fixture_group=fixtures,
            job_config=job_config
        )

        pipeline.render_to_xsq(
            implementation=agent_implementation,
            template_library=templates,
            beat_grid=beat_grid,
            output_path="output.xsq"
        )
    """

    def __init__(
        self,
        curve_generator: CurveGenerator,
        fixture_group: FixtureGroup,
        job_config: JobConfig,
    ):
        """Initialize rendering pipeline.

        Args:
            curve_generator: Curve generation engine
            fixture_group: Fixture configuration
            job_config: Job configuration
        """
        self.curve_generator = curve_generator
        self.fixture_group = fixture_group
        self.job_config = job_config

        # Initialize components
        self.curve_pipeline = CurvePipeline(curve_generator=curve_generator)
        self.xlights_provider = XlightsProvider()
        self.gap_renderer = GapRenderer()

        logger.debug("RenderingPipeline initialized")

    def render_to_xsq(
        self,
        implementation: AgentImplementation,
        template_library: dict[str, Template],
        beat_grid: BeatGrid,
        output_path: str | Path,
        template_xsq: str | Path | None = None,
    ) -> None:
        """Render AgentImplementation to xLights XSQ file.

        Complete end-to-end pipeline from agent output to xLights sequence.

        Args:
            implementation: Agent-generated implementation (bar-level timing)
            template_library: Template definitions
            beat_grid: Musical timing grid
            output_path: Output XSQ file path
            template_xsq: Optional template XSQ to merge into
        """
        logger.info("=" * 70)
        logger.info("RENDERING PIPELINE START")
        logger.info("=" * 70)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: TIMELINE PLANNING (bars → segments)
        # ═══════════════════════════════════════════════════════════════════
        logger.info("Step 1: Timeline Planning")

        from blinkb0t.core.domains.sequencing.moving_heads.timeline_planner import (
            TemplateTimelinePlanner,
        )

        planner = TemplateTimelinePlanner()
        total_duration_ms = beat_grid.duration_ms

        timeline = planner.plan(
            choreography_plan=implementation,
            beat_grid=beat_grid,
            template_library=template_library,
            total_duration_ms=total_duration_ms,
        )

        logger.info(f"  Timeline: {len(timeline.segments)} segments")

        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: CHANNEL OVERLAY RESOLUTION
        # ═══════════════════════════════════════════════════════════════════
        logger.info("Step 2: Resolving Channel Overlays")

        from blinkb0t.core.domains.sequencing.channels.handlers import (
            ColorHandler,
            GoboHandler,
            ShutterHandler,
        )
        from blinkb0t.core.domains.sequencing.libraries.channels import (
            ColorLibrary,
            GoboLibrary,
            ShutterLibrary,
        )

        shutter_handler = ShutterHandler(ShutterLibrary())
        color_handler = ColorHandler(ColorLibrary())
        gobo_handler = GoboHandler(GoboLibrary())

        channel_overlays = resolve_channel_overlays(
            agent_implementation=implementation,
            shutter_handler=shutter_handler,
            color_handler=color_handler,
            gobo_handler=gobo_handler,
            job_config=self.job_config,
        )

        logger.info(f"  Channel overlays: {len(channel_overlays)} sections")

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: SEGMENT RENDERING (Per-Fixture Expansion)
        # ═══════════════════════════════════════════════════════════════════
        logger.info("Step 3: Rendering Segments (per-fixture)")

        segment_renderer = self._create_segment_renderer()

        # Extract section boundaries for boundary detection
        section_boundaries = self._extract_section_boundaries(timeline)

        template_segments = [s for s in timeline.segments if isinstance(s, TemplateStepSegment)]

        segment_effects = list(
            segment_renderer.render_segments(
                segments=template_segments,
                channel_overlays=channel_overlays,
                section_info=section_boundaries,
            )
        )

        logger.info(f"  Segment effects: {len(segment_effects)} (per-fixture)")

        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: PER-FIXTURE GAP DETECTION AND RENDERING
        # ═══════════════════════════════════════════════════════════════════
        logger.info("Step 4: Detecting and Rendering Per-Fixture Gaps")

        # Detect gaps per-fixture by analyzing segment effects, not global gap segments
        gap_effects = self.gap_renderer.detect_and_render_gaps_per_fixture(
            segment_effects=segment_effects,
            fixture_group=self.fixture_group,
            channel_overlays=channel_overlays,
            total_duration_ms=timeline.total_duration_ms,
        )

        logger.info(f"  Gap effects: {len(gap_effects)} (per-fixture)")

        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: CURVE GENERATION & BLENDING
        # ═══════════════════════════════════════════════════════════════════
        logger.info("Step 5: Curve Pipeline (Generate & Blend)")

        all_effects = segment_effects + gap_effects
        rendered_effects = self.curve_pipeline.render(all_effects)

        logger.info(f"  Rendered effects: {len(rendered_effects)}")

        # ═══════════════════════════════════════════════════════════════════
        # STEP 6: WRITE TO XLIGHTS
        # ═══════════════════════════════════════════════════════════════════
        logger.info("Step 6: Writing to xLights")

        # Build fixture definitions dict for XlightsProvider
        # Extract DMX channel mappings from fixture configs
        # Expand fixtures to ensure we have FixtureInstance objects (not SimplifiedFixtureInstance)
        expanded_fixtures = self.fixture_group.expand_fixtures()
        fixture_definitions = {}
        for fixture in expanded_fixtures:
            # Extract channel numbers from dmx_mapping
            mapping = fixture.config.dmx_mapping
            channels = {
                "pan": mapping.pan_channel
                if isinstance(mapping.pan_channel, int)
                else mapping.pan_channel.channel,
                "tilt": mapping.tilt_channel
                if isinstance(mapping.tilt_channel, int)
                else mapping.tilt_channel.channel,
                "dimmer": mapping.dimmer_channel
                if isinstance(mapping.dimmer_channel, int)
                else mapping.dimmer_channel.channel,
            }
            # Add optional channels if present
            if mapping.shutter_channel:
                channels["shutter"] = (
                    mapping.shutter_channel
                    if isinstance(mapping.shutter_channel, int)
                    else mapping.shutter_channel.channel
                )
            if hasattr(mapping, "color_channel") and mapping.color_channel:
                channels["color"] = (
                    mapping.color_channel
                    if isinstance(mapping.color_channel, int)
                    else mapping.color_channel.channel
                )
            if hasattr(mapping, "gobo_channel") and mapping.gobo_channel:
                channels["gobo"] = (
                    mapping.gobo_channel
                    if isinstance(mapping.gobo_channel, int)
                    else mapping.gobo_channel.channel
                )
            fixture_definitions[fixture.fixture_id] = channels

        self.xlights_provider.write_to_xsq(
            rendered_effects=rendered_effects,
            output_path=output_path,
            fixture_definitions=fixture_definitions,
            template_xsq=template_xsq,
        )

        logger.info(f"  Complete! XSQ saved to {output_path}")
        logger.info("=" * 70)

    def _create_segment_renderer(self) -> SegmentRenderer:
        """Create SegmentRenderer with all dependencies.

        Returns:
            Configured SegmentRenderer instance
        """
        from blinkb0t.core.domains.sequencing.moving_heads.dimmer_handler import (
            DimmerHandler,
        )
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.engine import (
            GeometryEngine,
        )
        from blinkb0t.core.domains.sequencing.moving_heads.templates.handlers.default import (
            DefaultMovementHandler,
        )
        from blinkb0t.core.domains.sequencing.poses.resolver import (
            PoseResolver,
        )

        # Create dependencies
        pose_resolver = PoseResolver()
        movement_handler = DefaultMovementHandler()
        geometry_engine = GeometryEngine()
        dimmer_handler = DimmerHandler()

        # Create renderer
        return SegmentRenderer(
            fixture_group=self.fixture_group,
            pose_resolver=pose_resolver,
            movement_handler=movement_handler,
            geometry_engine=geometry_engine,
            dimmer_handler=dimmer_handler,
        )

    def _extract_section_boundaries(self, timeline: ExplodedTimeline) -> dict[str, tuple[int, int]]:
        """Extract section boundaries from timeline segments.

        Args:
            timeline: Exploded timeline with segments

        Returns:
            Dict mapping section_id to (start_ms, end_ms) tuple as integers
        """
        from collections import defaultdict

        boundaries: dict[str, list[tuple[float, float]]] = defaultdict(list)

        # Collect all segments per section
        for segment in timeline.segments:
            if isinstance(segment, TemplateStepSegment):
                boundaries[segment.section_id].append((segment.start_ms, segment.end_ms))

        # Compute section boundaries (min start, max end) and convert to int
        section_boundaries: dict[str, tuple[int, int]] = {}
        for section_id, seg_bounds in boundaries.items():
            if seg_bounds:
                min_start = min(start for start, _ in seg_bounds)
                max_end = max(end for _, end in seg_bounds)
                section_boundaries[section_id] = (int(min_start), int(max_end))

        return section_boundaries
