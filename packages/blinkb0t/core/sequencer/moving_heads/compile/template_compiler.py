"""Template Compiler (Orchestrator) for the moving head sequencer.

This module provides the top-level compilation function that orchestrates
all components to compile a complete template to IR segments.
"""

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.sequencer.moving_heads.channels.state import FixtureSegment
from blinkb0t.core.sequencer.moving_heads.compile.phase_offset import (
    calculate_fixture_offsets,
)
from blinkb0t.core.sequencer.moving_heads.compile.preset import apply_preset
from blinkb0t.core.sequencer.moving_heads.compile.scheduler import schedule_repeats
from blinkb0t.core.sequencer.moving_heads.compile.step_compiler import (
    StepCompileContext,
    compile_step,
)
from blinkb0t.core.sequencer.moving_heads.models.context import TemplateCompileContext
from blinkb0t.core.sequencer.moving_heads.models.template import (
    Template,
    TemplatePreset,
    TemplateStep,
)


class TemplateCompileResult(BaseModel):
    """Result of compiling a template.

    Contains all compiled IR segments and metadata.

    Attributes:
        template_id: The template that was compiled.
        segments: All compiled channel segments.
        num_complete_cycles: Number of complete repeat cycles.
        provenance: Provenance tracking list.
    """

    model_config = ConfigDict(extra="forbid")

    template_id: str
    segments: list[FixtureSegment] = Field(default_factory=list)
    num_complete_cycles: int = Field(default=0)
    provenance: list[str] = Field(default_factory=list)

    def segments_by_fixture(self, fixture_id: str) -> list[FixtureSegment]:
        """Get segments for a specific fixture."""
        return [seg for seg in self.segments if seg.fixture_id == fixture_id]


def compile_template(
    template: Template,
    context: TemplateCompileContext,
    preset: TemplatePreset | None = None,
) -> TemplateCompileResult:
    """Compile a template to IR segments.

    Orchestrates all compilation steps:
    1. Apply preset if provided
    2. Schedule repeat cycles
    3. Calculate phase offsets
    4. Compile each step for each fixture

    Args:
        template: The template to compile.
        context: Compilation context.
        preset: Optional preset to apply.

    Returns:
        TemplateCompileResult with all compiled segments.

    Example:
        >>> template = Template(...)
        >>> context = TemplateCompileContext(...)
        >>> result = compile_template(template, context)
    """
    # Initialize provenance
    provenance: list[str] = [f"template:{template.template_id}"]

    # Apply preset if provided
    working_template = template
    if preset:
        working_template = apply_preset(template, preset)
        provenance.append(f"preset:{preset.preset_id}")

    # Build step duration map
    step_durations: dict[str, float] = {}
    step_map: dict[str, TemplateStep] = {}
    for step in working_template.steps:
        step_durations[step.step_id] = step.timing.base_timing.duration_bars
        step_map[step.step_id] = step

    # Schedule repeats
    schedule_result = schedule_repeats(
        working_template.repeat,
        context.window_bars,
        step_durations=step_durations,
    )

    # Compile each scheduled instance for each fixture
    all_segments: list[FixtureSegment] = []

    for instance in schedule_result.instances:
        step = step_map[instance.step_id]

        # Calculate phase offsets for this step
        phase_config = step.timing.phase_offset
        fixture_ids = [f.fixture_id for f in context.fixtures]

        if phase_config:
            phase_offsets = calculate_fixture_offsets(phase_config, fixture_ids)
        else:
            # No phase offset - all fixtures get 0
            from blinkb0t.core.sequencer.moving_heads.compile.phase_offset import (
                PhaseOffsetResult,
            )

            phase_offsets = PhaseOffsetResult(offsets=dict.fromkeys(fixture_ids, 0.0))

        # Calculate timing in milliseconds
        start_ms = context.start_ms + int(instance.start_bars * context.ms_per_bar)
        duration_ms = int(instance.duration_bars * context.ms_per_bar)

        # Compile for each fixture
        for fixture in context.fixtures:
            # Get phase offset for this fixture
            offset_bars = phase_offsets.offsets.get(fixture.fixture_id, 0.0)
            step_duration = step.timing.base_timing.duration_bars
            phase_offset_norm = offset_bars / step_duration if step_duration > 0 else 0.0
            if phase_offsets.wrap:
                phase_offset_norm = phase_offset_norm % 1.0

            # Build step compile context
            step_context = StepCompileContext(
                fixture_id=fixture.fixture_id,
                role=fixture.role,
                calibration=fixture.calibration,
                start_ms=start_ms,
                duration_ms=duration_ms,
                n_samples=context.n_samples,
                geometry_registry=context.geometry_registry,
                movement_registry=context.movement_registry,
                dimmer_registry=context.dimmer_registry,
            )

            # Compile the step
            step_result = compile_step(step, step_context, phase_offset_norm)

            # Add segments
            all_segments.append(step_result.segment)

    return TemplateCompileResult(
        template_id=working_template.template_id,
        segments=all_segments,
        num_complete_cycles=schedule_result.num_complete_cycles,
        provenance=provenance,
    )
