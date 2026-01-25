from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from blinkb0t.core.agents.sequencer.moving_heads import ChoreographyPlan
from blinkb0t.core.agents.sequencer.moving_heads.models import PlanSection
from blinkb0t.core.config.fixtures import FixtureGroup
from blinkb0t.core.config.models import JobConfig
from blinkb0t.core.curves.generator import CurveGenerator
from blinkb0t.core.curves.registry import CurveRegistry
from blinkb0t.core.formats.xlights.sequence.exporter import XSQExporter
from blinkb0t.core.formats.xlights.sequence.models.xsq import (
    Effect,
    SequenceHead,
    TimeMarker,
    XSequence,
)
from blinkb0t.core.formats.xlights.sequence.parser import XSQParser
from blinkb0t.core.sequencer.models.context import FixtureContext, TemplateCompileContext
from blinkb0t.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from blinkb0t.core.sequencer.moving_heads.channels.state import FixtureSegment
from blinkb0t.core.sequencer.moving_heads.compile.template_compiler import (
    compile_template,
)
from blinkb0t.core.sequencer.moving_heads.export.xsq_adapter import XsqAdapter
from blinkb0t.core.sequencer.moving_heads.handlers.defaults import create_default_registries
from blinkb0t.core.sequencer.moving_heads.templates import (
    get_template,
    load_builtin_templates,
)
from blinkb0t.core.sequencer.timing.beat_grid import BeatGrid

logger = logging.getLogger(__name__)


class RenderingPipeline:
    """Rendering pipeline for moving heads."""

    def __init__(
        self,
        *,
        choreography_plan: ChoreographyPlan,
        beat_grid: BeatGrid,
        fixture_group: FixtureGroup,
        job_config: JobConfig,
        output_path: Path | None = None,
        template_xsq: Path | None = None,
    ):
        """Initialize rendering pipeline.

        Args:
            choreography_plan: Choreography plan from agent orchestrator
            beat_grid: Beat grid for musical timing
            fixture_group: Fixture configuration
            job_config: Job configuration
            output_path: Optional output path for XSQ file
            template_xsq: Optional template XSQ path
        """
        self.choreography_plan = choreography_plan
        self.fixture_group = fixture_group
        self.job_config = job_config
        self.beat_grid = beat_grid
        self.output_path = output_path
        self.template_xsq = template_xsq

        # Create shared infrastructure
        self.curve_generator = CurveGenerator()
        self.curve_registry = CurveRegistry()

        # Create rig profile from fixture group
        self.rig_profile = rig_profile_from_fixture_group(fixture_group)

        # Load builtin templates
        load_builtin_templates()

        # Create handler registries
        registries = create_default_registries()
        self.geometry_registry = registries["geometry"]
        self.movement_registry = registries["movement"]
        self.dimmer_registry = registries["dimmer"]

        logger.debug(
            f"Initialized RenderingPipeline with {len(self.rig_profile.fixtures)} fixtures "
            f"and {len(self.choreography_plan.sections)} sections"
        )

    def render(self) -> list[FixtureSegment]:
        """Render the choreography plan to fixture segments.

        Processes each section in the choreography plan:
        1. For each sequence in section, build template ID from components
        2. Load template and apply energy-based preset
        3. Build compile context aligned to beat grid
        4. Compile template to IR segments
        5. Aggregate all segments

        Returns:
            List of all compiled fixture segments across all sections.

        Raises:
            ValueError: If template not found or compilation fails.
        """
        all_segments: list[FixtureSegment] = []

        logger.debug("Starting plan rendering...")
        time_markers: list[TimeMarker] = []

        for section in self.iterate_plan_sections(self.choreography_plan):
            if not section.template_id:
                raise ValueError(f"Section '{section.section_name}' has no template_id")

            logger.debug(
                f"Rendering section '{section.section_name}' "
                f"(bars {section.start_bar}-{section.end_bar}, "
                f"template: {section.template_id}, preset: {section.preset_id})"
            )

            # Load template
            try:
                template_doc = get_template(section.template_id)
                template = template_doc.template
                logger.debug(f"Loaded template: {template.name} (v{template.version})")
            except Exception as e:
                logger.error(f"Failed to load template '{section.template_id}': {e}")
                raise ValueError(f"Template not found: {section.template_id}") from e

            # Apply preset if available
            preset = None
            if section.preset_id:
                try:
                    preset = next(
                        p for p in template_doc.presets if p.preset_id == section.preset_id
                    )
                    logger.debug(f"Applying preset: {preset.name}")
                except StopIteration:
                    logger.warning(
                        f"Preset '{section.preset_id}' not found for template "
                        f"'{section.template_id}', using base template"
                    )

            # Build fixture contexts
            fixture_contexts = self._build_fixture_contexts()

            # Build compile context aligned to beat grid
            context = TemplateCompileContext(
                section_id=section.section_name,
                template_id=template.template_id,
                preset_id=preset.preset_id if preset else None,
                fixtures=fixture_contexts,
                beat_grid=self.beat_grid,
                start_bar=section.start_bar,
                duration_bars=section.end_bar - section.start_bar + 1,
                n_samples=64,  # Default sample count
                curve_registry=self.curve_registry,
                geometry_registry=self.geometry_registry,
                movement_registry=self.movement_registry,
                dimmer_registry=self.dimmer_registry,
            )

            time_markers.append(
                TimeMarker(
                    name=section.section_name, time_ms=context.start_ms, end_time_ms=context.end_ms
                )
            )

            logger.debug(
                f"Compile context: start={context.start_ms}ms, "
                f"duration={context.duration_ms}ms, "
                f"bpm={context.bpm}"
            )

            # Compile template
            try:
                result = compile_template(template, context, preset)
                logger.debug(
                    f"Compiled {len(result.segments)} segments "
                    f"({result.num_complete_cycles} complete cycles)"
                )
                all_segments.extend(result.segments)
            except Exception as e:
                logger.error(f"Compilation failed for section '{section.section_name}': {e}")
                raise

        logger.debug(f"Render complete: {len(all_segments)} total segments")

        # Export to XSQ
        if self.output_path:
            self._export_to_xsq(all_segments, time_markers)

        return all_segments

    def iterate_plan_sections(self, plan: ChoreographyPlan) -> Iterator[PlanSection]:
        """Iterate over the plan sections and yield each section.

        Args:
            plan: The choreography plan to iterate over.

        Returns:
            An iterator over the plan sections.
        """
        for section in plan.sections:
            if section.segments:
                for seg in section.segments:
                    yield PlanSection(
                        section_name=section.section_name,
                        start_bar=seg.start_bar,
                        end_bar=seg.end_bar,
                        section_role=section.section_role,
                        energy_level=section.energy_level,
                        template_id=seg.template_id,
                        preset_id=seg.preset_id,
                        modifiers=seg.modifiers,
                        reasoning=seg.reasoning or section.reasoning,
                        # IMPORTANT: do not carry segments forward once flattened
                        segments=None,
                    )
            else:
                yield section

    def _build_fixture_contexts(self) -> list[FixtureContext]:
        """Build fixture contexts from rig profile.

        Returns:
            List of FixtureContext objects for all fixtures in the rig.
        """
        contexts = []

        # Get actual fixture configs from fixture_group for degree->DMX conversion
        fixture_configs = {fx.fixture_id: fx.config for fx in self.fixture_group.expand_fixtures()}

        for fixture_def in self.rig_profile.fixtures:
            # Build calibration dict from FixtureCalibration model
            calibration: dict[str, Any] = {}
            if fixture_def.calibration:
                calibration = {
                    "pan_min_dmx": fixture_def.calibration.pan_min_dmx,
                    "pan_max_dmx": fixture_def.calibration.pan_max_dmx,
                    "tilt_min_dmx": fixture_def.calibration.tilt_min_dmx,
                    "tilt_max_dmx": fixture_def.calibration.tilt_max_dmx,
                    "pan_inverted": fixture_def.calibration.pan_inverted,
                    "tilt_inverted": fixture_def.calibration.tilt_inverted,
                    "dimmer_floor_dmx": fixture_def.calibration.dimmer_floor_dmx,
                    "dimmer_ceiling_dmx": fixture_def.calibration.dimmer_ceiling_dmx,
                }

            # Add the full FixtureConfig for degree->DMX conversion in geometry handlers
            if fixture_def.fixture_id in fixture_configs:
                calibration["fixture_config"] = fixture_configs[fixture_def.fixture_id]

            # Infer role from fixture groups (first group that contains this fixture)
            role = "UNKNOWN"
            for group in self.rig_profile.groups:
                if fixture_def.fixture_id in group.fixture_ids:
                    # Simple role inference: use position in group
                    idx = group.fixture_ids.index(fixture_def.fixture_id)
                    if len(group.fixture_ids) == 4:
                        roles = ["OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"]
                        role = roles[idx] if idx < len(roles) else f"FIXTURE_{idx}"
                    else:
                        role = f"{group.group_id}_{idx}"
                    break

            contexts.append(
                FixtureContext(
                    fixture_id=fixture_def.fixture_id,
                    role=role,
                    calibration=calibration,
                )
            )

        return contexts

    def _export_to_xsq(
        self, segments: list[FixtureSegment], time_markers: list[TimeMarker]
    ) -> None:
        """Export segments to XSQ file.

        Args:
            segments: List of fixture segments to export.
            time_markers: List of time markers to export.
        Raises:
            ValueError: If output_path is not set or XSQ operations fail.
        """
        if not self.output_path:
            logger.warning("No output_path specified, skipping XSQ export")
            return

        logger.debug(f"Exporting {len(segments)} segments to {self.output_path}")

        # Load template XSQ if provided, otherwise create new
        if self.template_xsq and Path(self.template_xsq).exists():
            logger.debug(f"Loading template XSQ from {self.template_xsq}")
            parser = XSQParser()
            xsq = parser.parse(self.template_xsq)
            logger.debug(
                f"Template loaded: {len(xsq.element_effects)} elements, "
                f"{len(xsq.effect_db.entries)} effects in DB"
            )
        else:
            # Create minimal XSQ
            logger.debug("Creating new XSQ (no template provided)")
            # Calculate duration from segments
            duration_ms = max((s.t1_ms for s in segments), default=0)

            xsq = XSequence(
                head=SequenceHead(
                    version="2024.10",
                    media_file="",
                    sequence_duration_ms=duration_ms,
                    song="Generated Sequence",
                    artist="BlinkB0t",
                    sequence_timing="50 ms",
                )
            )

        # Add timing markers to XSQ
        xsq.add_timing_layer(timing_name="BlinkB0t AudioSections", markers=time_markers)

        adapter = XsqAdapter()
        placements = adapter.convert(segments, self.fixture_group, xsq)

        logger.debug(f"Converted to {len(placements)} effect placements")

        # Add placements to XSQ
        for placement in placements:
            # Create Effect object
            effect = Effect(
                effect_type=placement.effect_name,
                start_time_ms=placement.start_ms,
                end_time_ms=placement.end_ms,
                ref=placement.ref,
                label=placement.effect_label or "",
                palette=str(placement.palette) if placement.palette else "",
            )

            # Add to element (creates element if doesn't exist)
            xsq.add_effect(
                element_name=placement.element_name,
                effect=effect,
            )

        logger.debug(f"Added {len(placements)} effects to XSQ")

        # Export to file
        exporter = XSQExporter()
        exporter.export(xsq, self.output_path, pretty=True)

        logger.debug(f"Successfully exported XSQ to {self.output_path}")
