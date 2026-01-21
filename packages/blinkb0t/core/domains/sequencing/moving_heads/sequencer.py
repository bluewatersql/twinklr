"""Moving head sequencer - DMX choreography generation.

Simplified orchestration layer that delegates to specialized components.
Phase 4 refactor: Reduced from 579 → <200 lines.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from blinkb0t.core.config.fixtures import FixtureGroup
from blinkb0t.core.domains.sequencing.base import BaseSequencer
from blinkb0t.core.domains.sequencing.infrastructure.xsq import XSQExporter, XSQParser
from blinkb0t.core.domains.sequencing.infrastructure.xsq.compat import effect_placement_to_effect
from blinkb0t.core.domains.sequencing.models.channels import DmxEffect
from blinkb0t.core.domains.sequencing.moving_heads.boundary_enforcer import BoundaryEnforcer
from blinkb0t.core.domains.sequencing.moving_heads.channel_effect_generator import (
    ChannelEffectGenerator,
)
from blinkb0t.core.domains.sequencing.moving_heads.context import SequencerContext
from blinkb0t.core.domains.sequencing.moving_heads.curve_mapper_factory import create_curve_mapper
from blinkb0t.core.domains.sequencing.moving_heads.resolvers.context import ResolverContext
from blinkb0t.core.domains.sequencing.moving_heads.resolvers.registry import ResolverRegistry
from blinkb0t.core.domains.sequencing.moving_heads.resolvers.target_resolver import (
    resolve_plan_targets,
)
from blinkb0t.core.domains.sequencing.moving_heads.resolvers.template_resolver import (
    TemplateResolver,
)

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureInstance
    from blinkb0t.core.config.models import JobConfig
    from blinkb0t.core.domains.sequencing.infrastructure.timing.beat_grid import BeatGrid
    from blinkb0t.core.domains.sequencing.moving_heads.transitions.gap_detector import (
        GapDetector,
    )

logger = logging.getLogger(__name__)


class MovingHeadSequencer(BaseSequencer):
    """Sequencer for moving head fixtures using DMX effects.

    This sequencer handles DMX-based moving head choreography including:
    - Movement patterns (sweep, circle, tilt_rock, etc.)
    - Geometry transformations (fan, mirror_lr, wave_lr, etc.)
    - Gap filling and hold position management
    - Value curve rendering for smooth motion

    The sequencer uses a resolver/handler architecture where:
    - Resolvers map movement patterns to handlers
    - Handlers generate xLights effect placements
    - Gap filling ensures continuous fixture coverage

    Note: Macro expansions and template resolution are handled by the
    adapter layer before plans reach the sequencer.
    """

    def __init__(self, *, job_config: JobConfig, fixtures: FixtureGroup):
        """Initialize moving head sequencer.

        Args:
            job_config: Job configuration with sequence settings
            fixtures: Fixture group configuration
        """
        super().__init__(job_config=job_config, fixtures=fixtures)

        # Initialize components (Phase 4: delegated to factories/helpers)
        self._dmx_curve_mapper = create_curve_mapper()
        self._template_resolver = TemplateResolver(fixtures=self.fixtures)
        self._init_channel_system()

        logger.debug("MovingHeadSequencer initialized")

    def _init_channel_system(self) -> None:
        """Initialize channel handlers and pipeline."""
        from blinkb0t.core.domains.sequencing.channels.handlers import (
            ColorHandler,
            GoboHandler,
            ShutterHandler,
        )
        from blinkb0t.core.domains.sequencing.channels.pipeline import (
            ChannelIntegrationPipeline,
            XsqAdapter,
        )
        from blinkb0t.core.domains.sequencing.libraries.channels import (
            ColorLibrary,
            GoboLibrary,
            ShutterLibrary,
        )

        # Create handlers
        self.shutter_handler = ShutterHandler(ShutterLibrary())
        self.color_handler = ColorHandler(ColorLibrary())
        self.gobo_handler = GoboHandler(GoboLibrary())

        # Create generator and pipeline
        self.channel_effect_generator = ChannelEffectGenerator(
            shutter_handler=self.shutter_handler,
            color_handler=self.color_handler,
            gobo_handler=self.gobo_handler,
            job_config=self.job_config,
        )
        self.channel_pipeline = ChannelIntegrationPipeline()
        self.xsq_adapter = XsqAdapter()

    def apply_implementation(
        self,
        *,
        xsq_in: str,
        xsq_out: str,
        implementation: Any,  # AgentImplementation
        song_features: dict[str, Any],
    ) -> None:
        """Apply AgentImplementation to sequence using new rendering pipeline.

        Args:
            xsq_in: Input sequence file path (used as template)
            xsq_out: Output sequence file path
            implementation: AgentImplementation Pydantic model
            song_features: Song features from audio analysis
        """
        logger.info("Applying agent implementation (renderer_v2)")

        # Build BeatGrid from song features

        beat_grid = self._build_beat_grid_from_features(song_features)

        # Load template library
        from pathlib import Path

        from blinkb0t.core.domains.sequencing.moving_heads.templates.loader import (
            TemplateLoader,
        )

        # Default template directory
        template_dir = Path(__file__).parent.parent / "templates"
        template_loader = TemplateLoader(template_dir=template_dir)
        template_library = template_loader.load_all()

        # Create rendering pipeline
        from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
            CurveGenerator,
            CustomCurveProvider,
            NativeCurveProvider,
        )
        from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
        from blinkb0t.core.domains.sequencing.rendering.pipeline import RenderingPipeline

        # Create curve generator (empty library is fine - curves are generated on demand)
        curve_library = CurveLibrary()
        native_provider = NativeCurveProvider()
        custom_provider = CustomCurveProvider()
        curve_generator = CurveGenerator(
            library=curve_library,
            native_provider=native_provider,
            custom_provider=custom_provider,
        )

        # Create and run pipeline
        pipeline = RenderingPipeline(
            curve_generator=curve_generator,
            fixture_group=self.fixtures,
            job_config=self.job_config,
        )

        pipeline.render_to_xsq(
            implementation=implementation,
            template_library=template_library,
            beat_grid=beat_grid,
            output_path=xsq_out,
            template_xsq=xsq_in,
        )

        logger.info(f"Implementation applied successfully: {xsq_out}")

    def _build_beat_grid_from_features(self, song_features: dict[str, Any]) -> BeatGrid:
        """Build BeatGrid from song features.

        Args:
            song_features: Audio analysis features

        Returns:
            Configured BeatGrid
        """
        from blinkb0t.core.domains.sequencing.infrastructure.timing.beat_grid import BeatGrid

        # Extract timing info
        tempo_bpm = song_features.get("tempo_bpm", 120.0)
        beats_s = song_features.get("beats_s", [])
        duration_s = song_features.get("duration_s", 0.0)
        beats_per_bar = song_features.get("assumptions", {}).get("beats_per_bar", 4)

        # Convert beats to milliseconds
        beat_boundaries = [b * 1000.0 for b in beats_s]

        # Calculate bar boundaries from detected downbeats (bars_s)
        # Don't calculate from beats - use the audio-analyzed bar positions
        bars_s = song_features.get("bars_s", [])
        bar_boundaries = [b * 1000.0 for b in bars_s]

        # Ensure we have at least one bar boundary (fallback for empty features)
        if not bar_boundaries:
            bar_boundaries = [0.0]

        # Calculate eighth and sixteenth boundaries
        eighth_boundaries = BeatGrid._calculate_eighth_boundaries(beat_boundaries)
        sixteenth_boundaries = BeatGrid._calculate_sixteenth_boundaries(beat_boundaries)

        return BeatGrid(
            bar_boundaries=bar_boundaries,
            beat_boundaries=beat_boundaries,
            eighth_boundaries=eighth_boundaries,
            sixteenth_boundaries=sixteenth_boundaries,
            beats_per_bar=beats_per_bar,
            tempo_bpm=tempo_bpm,
            duration_ms=duration_s * 1000.0,
        )

    def apply_plan(
        self,
        *,
        xsq_in: str,
        xsq_out: str,
        plan: dict[str, Any],
        song_features: dict[str, Any],
    ) -> None:
        """Apply moving head plan to sequence (internal method).

        This method:
        1. Loads the input xLights sequence
        2. Fills gaps in the plan (section-level and per-fixture)
        3. Resolves plan targets to fixture groups
        4. Processes each section and instruction using handlers
        5. Generates DMX effect placements
        6. Saves the modified sequence

        Args:
            xsq_in: Input sequence file path
            xsq_out: Output sequence file path
            plan: Moving head plan to apply
            song_features: Song features from audio analysis
        """
        # Load XSQ
        parser = XSQParser()
        sequence = parser.parse(xsq_in)

        # Gap filling removed (Phase 4 refactor)
        # Now handled by ChannelIntegrationPipeline via GapDetector + GapFillHandler
        logger.debug("Proceeding with sequencing (gap filling delegated to pipeline)")

        # ═══════════════════════════════════════════════════════════════════════════
        # RESOLVE TARGETS UPFRONT
        # ═══════════════════════════════════════════════════════════════════════════
        target_groups = resolve_plan_targets(plan, self.fixtures)

        # Template expansion happens after target resolution, so dynamically-generated
        # instructions may reference targets not in the original plan
        if "ALL" not in target_groups:
            target_groups["ALL"] = self.fixtures
            logger.debug("Added 'ALL' target for template-generated instructions")

        # ═══════════════════════════════════════════════════════════════════════════
        # INITIALIZE RESOLVER REGISTRY
        # ═══════════════════════════════════════════════════════════════════════════
        resolver_registry = ResolverRegistry()

        # ═══════════════════════════════════════════════════════════════════════════
        # CREATE SEQUENCER CONTEXT (shared across all instructions)
        # ═══════════════════════════════════════════════════════════════════════════
        first_fixture = list(self.fixtures)[0]
        boundaries = BoundaryEnforcer(first_fixture)
        beats_s = song_features.get("beats_s", []) or []

        sequencer_context = SequencerContext(
            fixture=first_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=self._dmx_curve_mapper,
            beats_s=beats_s,
            song_features=song_features,
        )

        # ═══════════════════════════════════════════════════════════════════════════
        # NOTES TRACK (if enabled)
        # ═══════════════════════════════════════════════════════════════════════════
        TIMING_TRACK_NAME = "BlinkB0t AI MH Notes"
        if self.job_config.include_notes_track:
            sequence.ensure_element(TIMING_TRACK_NAME, element_type="timing")
            sequence.reset_element_effects(TIMING_TRACK_NAME)

        # ═══════════════════════════════════════════════════════════════════════════
        # PHASE 1: COLLECT ALL EFFECTS PER FIXTURE (don't write to XSQ yet)
        # ═══════════════════════════════════════════════════════════════════════════
        from collections import defaultdict

        # Collect all DMX effects per fixture across all sections
        all_dmx_effects_by_fixture: dict[str, list[DmxEffect]] = defaultdict(list)

        sections = plan.get("sections", []) or []
        logger.debug(f"Processing {len(sections)} sections from plan")

        for section in sections:
            section_name = section.get("name", "Unknown")
            plan_section_name = section.get(
                "plan_section_name", section_name
            )  # Fallback to name if not present
            section_start = int(section.get("start_ms", 0))
            section_end = int(section.get("end_ms", 0))

            if section_end <= section_start:
                logger.warning(f"Skipping section '{section_name}' because end time <= start time")
                continue

            # Allocate space for transition_in and transition_out by adjusting section boundaries
            adjusted_section_start = section_start
            adjusted_section_end = section_end

            # Adjust boundaries for transition_in and transition_out
            transition_in = section.get("transition_in")
            if transition_in and transition_in.get("duration_ms", 0) > 0:
                adjusted_section_start = section_start + int(transition_in["duration_ms"])

            transition_out = section.get("transition_out")
            if transition_out and transition_out.get("duration_ms", 0) > 0:
                adjusted_section_end = section_end - int(transition_out["duration_ms"])

            # Validate adjustments
            if adjusted_section_end <= adjusted_section_start:
                logger.warning(
                    f"Section '{section.get('name', '?')}' transition adjustments invalid, skipping"
                )
                adjusted_section_start = section_start
                adjusted_section_end = section_end

            # Add notes track entry if enabled
            if self.job_config.include_notes_track:
                from blinkb0t.core.domains.sequencing.models.xsq import Effect

                effect = Effect(
                    effect_type="timing",
                    start_time_ms=section_start,
                    end_time_ms=section_end,
                    label=plan_section_name,  # Use original plan section name for traceability
                )
                sequence.add_effect(TIMING_TRACK_NAME, effect, layer_index=0)

            # Resolve template to instructions (Phase 4: removed old format support)
            if "template_id" not in section or not section.get("template_id"):
                logger.warning(
                    f"Section '{section.get('name')}' missing template_id - skipping (old format no longer supported)"
                )
                continue

            base_instructions = self._template_resolver.resolve(section, song_features)
            if not base_instructions:
                logger.warning(
                    f"Failed to resolve template '{section.get('template_id')}' for section '{section.get('name')}', skipping"
                )
                continue

            # Expand instructions for each target in section
            section_targets = section.get("targets", ["ALL"])

            # Process each section+target combination independently to ensure correct model targeting
            for target in section_targets:
                logger.debug(
                    f"Processing section '{section.get('name', '?')}' for target '{target}'"
                )

                # Resolve target to FixtureGroup
                if target not in target_groups:
                    logger.warning(f"Unknown target '{target}' - skipping")
                    continue

                target_fixture_group = target_groups[target]

                # Collect all effects for this section+target combination
                from blinkb0t.core.domains.sequencing.models.channels import (
                    ChannelEffect,
                    SequencedEffect,
                )

                section_target_movement_effects: list[SequencedEffect] = []
                section_target_channel_effects: list[ChannelEffect] = []

                # Expand template instructions for this target
                instructions = []
                for instruction in base_instructions:
                    inst_copy = dict(instruction)
                    inst_copy["target"] = target
                    instructions.append(inst_copy)

                logger.debug(f"  {len(instructions)} instructions for target '{target}'")

                # Process all instructions for this section+target
                targets_xlights = [f.xlights_model_name for f in target_fixture_group]

                for instruction in instructions:
                    # Convert instruction timing from bars to milliseconds
                    if "timing" in instruction:
                        timing_dict = instruction["timing"]
                        if "start_offset_bars" in timing_dict and "duration_bars" in timing_dict:
                            from blinkb0t.core.domains.sequencing.infrastructure.timing.resolver import (
                                TimeResolver,
                            )
                            from blinkb0t.core.domains.sequencing.models.templates import (
                                MusicalTiming,
                            )

                            musical_timing = MusicalTiming(
                                start_offset_bars=timing_dict["start_offset_bars"],
                                duration_bars=timing_dict["duration_bars"],
                            )

                            time_resolver = TimeResolver(song_features=song_features)
                            start_ms_relative, end_ms_relative = time_resolver.resolve_timing(
                                musical_timing
                            )

                            instruction["start_ms"] = int(
                                adjusted_section_start + start_ms_relative
                            )
                            instruction["end_ms"] = int(adjusted_section_start + end_ms_relative)

                    # Get movement pattern and resolver
                    movement = instruction.get("movement", {}) or {}
                    move_pattern = movement.get("pattern")
                    resolver = resolver_registry.get_resolver(move_pattern)

                    # Create resolver context
                    resolver_context = ResolverContext(
                        sequencer_context=sequencer_context,
                        xsq=sequence,
                        fixtures=target_fixture_group,
                        instruction=instruction,
                        section=section,
                        job_config=self.job_config,
                    )

                    # Resolve instruction to sequenced effects (movement)
                    try:
                        sequenced_effects = resolver.resolve(
                            instruction, resolver_context, targets_xlights
                        )
                        section_target_movement_effects.extend(sequenced_effects)

                        # Generate channel effects
                        channel_effects = self.channel_effect_generator.generate(
                            section=section,
                            instruction=instruction,
                            fixture_group=target_fixture_group,
                            section_start_ms=adjusted_section_start,
                            section_end_ms=adjusted_section_end,
                            beat_times_ms=song_features.get("beats", {}).get("beat_times_ms"),
                        )
                        section_target_channel_effects.extend(channel_effects)

                    except Exception as e:
                        logger.error(
                            f"Failed to process instruction for pattern '{move_pattern}': {e}",
                            exc_info=True,
                        )
                        continue

                # Process all effects for this section+target combination
                if section_target_movement_effects or section_target_channel_effects:
                    logger.info(
                        f"  Processing section '{section.get('name', '?')}' target '{target}': "
                        f"{len(section_target_movement_effects)} movement, "
                        f"{len(section_target_channel_effects)} channel effects"
                    )

                    try:
                        dmx_effects = self.channel_pipeline.process_section(
                            movement_effects=section_target_movement_effects,
                            channel_effects=section_target_channel_effects,
                            fixtures=target_fixture_group,
                            section_start_ms=adjusted_section_start,
                            section_end_ms=adjusted_section_end,
                        )

                        # Collect DMX effects per fixture (don't write to XSQ yet)
                        for dmx_effect in dmx_effects:
                            fixture_id = dmx_effect.fixture_id
                            all_dmx_effects_by_fixture[fixture_id].append(dmx_effect)

                        logger.info(
                            f"    → Generated {len(dmx_effects)} DMX effects (including transitions)"
                        )

                    except Exception as e:
                        logger.error(
                            f"Failed to process section+target '{section.get('name', '?')}'+'{target}': {e}",
                            exc_info=True,
                        )

        # ═══════════════════════════════════════════════════════════════════════════
        # PHASE 2: FILL INTER-SECTION GAPS AND WRITE TO XSQ
        # ═══════════════════════════════════════════════════════════════════════════
        from blinkb0t.core.domains.sequencing.moving_heads.transitions.gap_detector import (
            GapDetector,
        )

        # Create gap detector with threshold to ignore tiny gaps from per_fixture_offsets
        gap_detector = GapDetector(min_gap_ms=100.0)
        song_duration_ms = song_features.get("duration_s", 0) * 1000

        logger.info(f"Phase 2: Processing gaps for {len(all_dmx_effects_by_fixture)} fixtures")

        # Process gap fills per fixture, collect all effects
        all_final_effects: list[DmxEffect] = []

        for fixture_id, dmx_effects in all_dmx_effects_by_fixture.items():
            logger.debug(
                f"Processing fixture {fixture_id}: {len(dmx_effects)} effects before gap filling"
            )

            # Get the fixture instance
            fixture = next((f for f in self.fixtures if f.fixture_id == fixture_id), None)
            if not fixture:
                logger.warning(
                    f"Fixture {fixture_id} not found in fixture group, skipping gap filling"
                )
                # Still collect effects without gap filling
                all_final_effects.extend(dmx_effects)
                continue

            # Sort by time
            sorted_effects = sorted(dmx_effects, key=lambda e: e.start_ms)

            # Detect gaps and generate gap fill DmxEffect objects
            gap_fill_effects = self._generate_gap_fills(
                sorted_effects,
                fixture,
                song_duration_ms,
                gap_detector,
            )

            # Merge section effects with gap fills
            fixture_effects = sorted_effects + gap_fill_effects

            logger.info(
                f"  Fixture {fixture_id}: {len(sorted_effects)} effects → "
                f"{len(fixture_effects)} effects after gap filling "
                f"({len(gap_fill_effects)} gaps filled)"
            )

            # Collect for batch processing
            all_final_effects.extend(fixture_effects)

        # Convert ALL effects through XsqAdapter at once (enables group aggregation)
        logger.info(f"Converting {len(all_final_effects)} total effects to XSQ placements")
        effect_placements = self.xsq_adapter.convert(all_final_effects, self.fixtures, sequence)

        # Write all effect placements to XSQ
        for effect_placement in effect_placements:
            effect = effect_placement_to_effect(effect_placement)
            sequence.add_effect(effect_placement.element_name, effect, layer_index=0)

        # Save XSQ
        logger.debug(f"Saving sequence to {xsq_out}")
        exporter = XSQExporter()
        exporter.export(sequence, xsq_out)

    def _generate_gap_fills(
        self,
        dmx_effects: list[DmxEffect],
        fixture: FixtureInstance,
        song_duration_ms: float,
        gap_detector: GapDetector,
    ) -> list[DmxEffect]:
        """Generate gap fill DmxEffect objects for a single fixture.

        Args:
            dmx_effects: Sorted list of section DmxEffect objects
            fixture: FixtureInstance for this fixture
            song_duration_ms: Total song duration
            gap_detector: GapDetector instance

        Returns:
            List of gap fill DmxEffect objects
        """
        from blinkb0t.core.domains.sequencing.channels.state import ChannelState

        gap_fills = []

        # Detect gaps (start gaps, mid gaps, end gaps)
        # Simple implementation: Look for time ranges not covered by effects

        current_time = 0.0
        # Use fixture's configured resting position (home) for gap fills
        resting_pos = fixture.config.orientation.resting_position
        home_pan_dmx = resting_pos.pan_dmx
        home_tilt_dmx = resting_pos.tilt_dmx

        for effect in dmx_effects:
            # Gap before this effect?
            if effect.start_ms > current_time + gap_detector.min_gap_ms:
                # Create ChannelState objects for gap fill (using fixture's resting position)
                pan_state = ChannelState(fixture)
                pan_state.set_channel("pan", home_pan_dmx)

                tilt_state = ChannelState(fixture)
                tilt_state.set_channel("tilt", home_tilt_dmx)

                dimmer_state = ChannelState(fixture)
                dimmer_state.set_channel("dimmer", 0)

                shutter_state = ChannelState(fixture)
                shutter_state.set_channel("shutter", 0)

                # Create gap fill from current_time to effect.start_ms
                gap_fill = DmxEffect(
                    fixture_id=fixture.fixture_id,
                    start_ms=int(current_time),
                    end_ms=int(effect.start_ms),
                    channels={
                        "pan": pan_state,
                        "tilt": tilt_state,
                        "dimmer": dimmer_state,
                        "shutter": shutter_state,
                    },
                    metadata={
                        "type": "gap_fill",
                        "source_label": "gap_fill",
                        "is_gap_fill": True,
                    },
                )
                gap_fills.append(gap_fill)
                logger.debug(
                    f"Gap fill: {current_time:.0f}-{effect.start_ms:.0f}ms "
                    f"(duration={effect.start_ms - current_time:.0f}ms)"
                )

            current_time = max(current_time, effect.end_ms)

        # Gap at end?
        if song_duration_ms > current_time + gap_detector.min_gap_ms:
            # Create ChannelState objects for end gap fill (using fixture's resting position)
            pan_state = ChannelState(fixture)
            pan_state.set_channel("pan", home_pan_dmx)

            tilt_state = ChannelState(fixture)
            tilt_state.set_channel("tilt", home_tilt_dmx)

            dimmer_state = ChannelState(fixture)
            dimmer_state.set_channel("dimmer", 0)

            shutter_state = ChannelState(fixture)
            shutter_state.set_channel("shutter", 0)

            gap_fill = DmxEffect(
                fixture_id=fixture.fixture_id,
                start_ms=int(current_time),
                end_ms=int(song_duration_ms),
                channels={
                    "pan": pan_state,
                    "tilt": tilt_state,
                    "dimmer": dimmer_state,
                    "shutter": shutter_state,
                },
                metadata={
                    "type": "gap_fill",
                    "source_label": "gap_fill",
                    "is_gap_fill": True,
                },
            )
            gap_fills.append(gap_fill)
            logger.debug(
                f"Gap fill (end): {current_time:.0f}-{song_duration_ms:.0f}ms "
                f"(duration={song_duration_ms - current_time:.0f}ms)"
            )

        return gap_fills
