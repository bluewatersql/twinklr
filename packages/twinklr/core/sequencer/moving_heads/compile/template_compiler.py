"""Template Compiler (Orchestrator) for the moving head sequencer.

This module provides the top-level compilation function that orchestrates
all components to compile a complete template to IR segments.
"""

from collections.abc import Mapping, Sequence
from fractions import Fraction
import logging
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.config.fixtures import FixtureCapabilities
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.context import (
    FixtureContext,
    ResolvedStepComponents,
    StepCompileContext,
    TemplateCompileContext,
)
from twinklr.core.sequencer.models.enum import ChannelName, TemplateRole
from twinklr.core.sequencer.models.moving_heads.physical import (
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalChannelError,
    check_physical_value,
)
from twinklr.core.sequencer.models.moving_heads.topology import (
    ResolvedFixturePhase,
    resolve_distribution,
)
from twinklr.core.sequencer.models.template import (
    AttributeOverlay,
    RemainderPolicy,
    RepeatMode,
    Template,
    TemplatePreset,
    TemplateStep,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    FALLBACK_METADATA_KEY,
    dark_throughout,
    follow_lag,
)
from twinklr.core.sequencer.moving_heads.compile.preset import apply_preset
from twinklr.core.sequencer.moving_heads.compile.presets import (
    ComponentRefError,
    resolve_component_refs,
)
from twinklr.core.sequencer.moving_heads.compile.scheduler import schedule_repeats
from twinklr.core.sequencer.moving_heads.compile.step import (
    CompileError,
    compile_step,
    slice_segment,
)
from twinklr.core.sequencer.moving_heads.compile.visibility import (
    apply_overlay,
    apply_visibility,
)
from twinklr.core.sequencer.moving_heads.diagnostics import MHDiagnostic
from twinklr.core.sequencer.moving_heads.export.frame_encoder import quantize_cue
from twinklr.core.sequencer.moving_heads.utils import resolve_semantic_group
from twinklr.core.sequencer.timing.musical_phase import (
    MusicalPhaseMap,
    exact_decimal,
    musical_phase_fraction,
)

logger = logging.getLogger(__name__)


class EmptyStepError(ValueError):
    """A step instance starting inside the cue limits leaves no frame once quantized."""


class UnsupportedRigShapeError(ValueError):
    """A step targets a fixture group the rig cannot supply.

    Raised instead of skipping the step in silence. An 8-head rig used to render
    *nothing* — every step's role filter came back empty and the compile
    `continue`d past it without an exception or a surfaced warning, so the show was
    dark and the pipeline reported success (P4-F26).
    """


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
    dropped_steps: list[dict[str, str | int]] = Field(
        default_factory=list,
        description="Step instances starting outside the covered "
        "phase span or at or after the song's last whole frame, which have no frame to play",
    )

    def segments_by_fixture(self, fixture_id: str) -> list[FixtureSegment]:
        """Get segments for a specific fixture."""
        return [seg for seg in self.segments if seg.fixture_id == fixture_id]


def compile_template(
    template: Template,
    context: TemplateCompileContext,
    preset: TemplatePreset | None = None,
    *,
    phase_map: MusicalPhaseMap,
    start_limit_ms: int = 0,
    end_limit_ms: int,
    step_cache: dict[tuple[Any, ...], FixtureSegment] | None = None,
    unplayable: list[dict[str, str | int]] | None = None,
    held_states: Mapping[str, Mapping[ChannelName, str]] | None = None,
) -> TemplateCompileResult:
    """Compile a template's scheduled steps for the renderer.

    Applies the preset, the repeat schedule and target resolution, the repeating cycle
    first grown to whole bars holding whole
    movement periods at the grid's meter (`whole_period_cycle`), then every step
    instance is compiled by
    `compile_step` on the frame grid. Its musical bounds are cut at the
    section end, quantized with the encoder's `quantize_cue`, and its end is cut at
    `end_limit_ms`, the last frame boundary inside the song and the covered phase span,
    so a step running past it is truncated there without error. A step starting before
    `start_limit_ms`, the first frame boundary inside the covered span, or at or after
    `end_limit_ms` is dropped per target fixture and listed in `dropped_steps`: its
    phase origin would lie outside the map. A cue whose pose
    commands the head cannot follow within one encoded word (`follow_lag`) is refused.
    Each segment records its requested musical bounds in metadata `requested_t0_ms`
    and `requested_t1_ms`, and a step's `reposition_fallback` under
    `FALLBACK_METADATA_KEY`. A step's `component_refs` are resolved per target
    fixture against `context.presets`, after the preset patch, and each such segment
    records `component_provenance`. A step's `distribution` is resolved over
    `context.topology`, the canonical full rig, so each target fixture's phase offsets
    and pan sign depend on its rank there alone; each such segment records them, with
    the rank, as `phase_distribution`. A step's `visibility` keeps only each
    cue's lit slices (`apply_visibility`), and the template's `overlays` then
    split each fixture's cues around every cycle's overlay (`apply_overlay`); both leave
    their dark spans as gaps for the transaction pass, so the pre-planning gate, which
    compiles through here, sees exactly the cues the render does.

    Args:
        template: The template to compile.
        context: Compilation context; its fixtures carry their physical profiles.
        preset: Optional preset to apply.
        phase_map: The song's musical phase map, built from the detected grid.
        start_limit_ms: Frame-grid time no step may start before.
        end_limit_ms: Frame-grid time no step may end after.
        step_cache: Compiled step instances to reuse, keyed by template, preset, step,
            frame span and what the fixture contributes (its profile, resolved
            components and phase), for a caller compiling one template at many
            placements against one phase map and rig (the pre-planning gate).
        unplayable: When given (a render under `on_unplayable="dark"`), a step instance
            a fixture cannot play here (a `CompileError` or `PhysicalChannelError`
            it raises for that fixture, or an `EmptyStepError`) and every fixture's cues of a
            ONCE cycle the section is too short for are left out and recorded here
            instead of raised: fixture, section, template, step, frames, `reason`
            "unplayable", `code` (`compile_refused` or `once_section_too_short`) and
            `detail`. Errors of the template as a whole still raise.
        held_states: Per fixture, wheel states (color, gobo) its cues hold for their
            whole length in place of what the steps and their component presets author:
            a section's colour and gobo (`song_intent.resolve_section_look`). Applied to
            every cue before the overlays, so an overlay keeps its own state over its
            window and its cues then return to the held state, not the authored one.

    Returns:
        TemplateCompileResult with the segments.

    Raises:
        CompileError: For a FADE_OUT remainder policy, which has no
            fade, a cycle `whole_period_cycle` would grow too far, a ONCE template
            whose single cycle the section is too short for (a cut at `end_limit_ms`
            is not refused) or with a step whose finite move
            outlasts the step, a step the step compile
            rejects, a component reference that
            does not resolve on this rig (naming template, step, preset and fixture),
            a distribution on a rig without a topology (naming the fixture group)
            or over a fixture the topology does not place, or an overlay that ends
            after its cycle or whose attribute preset sets no state for a fixture.
        PhysicalChannelError: For a value, rate or state the profile cannot honor, pose
            motion the head cannot follow, or an envelope the profile cannot light
            (`apply_visibility`).
        UnsupportedRigShapeError: If a step's target group matches no fixture.
        EmptyStepError: If a step starting inside the limits is zero-length on the grid
            (a `ValueError`).
    """
    provenance: list[str] = [f"template:{template.template_id}"]
    working_template = template
    if preset:
        working_template = apply_preset(template, preset)
        provenance.append(f"preset:{preset.preset_id}")
    if working_template.repeat.remainder_policy == RemainderPolicy.FADE_OUT:
        raise CompileError(
            MHDiagnostic(
                code="unsupported_attribute",
                severity="error",
                message=(
                    f"template {template.template_id!r} uses remainder_policy FADE_OUT, "
                    "which the renderer does not implement"
                ),
                section_id=context.section_id,
                action="rejected",
            )
        )
    working_template = whole_period_cycle(working_template, context.beat_grid.beats_per_bar)

    if working_template.repeat.mode == RepeatMode.ONCE:
        for step in working_template.steps:
            _require_move_within_step(step, template, context)

    step_map = {step.step_id: step for step in working_template.steps}
    schedule_result = schedule_repeats(
        working_template.repeat,
        context.duration_bars,
        step_durations={
            step.step_id: step.timing.base_timing.duration_bars for step in working_template.steps
        },
        step_offsets={
            step.step_id: step.timing.base_timing.start_offset_bars
            for step in working_template.steps
        },
    )
    if working_template.repeat.mode == RepeatMode.ONCE and schedule_result.num_complete_cycles == 0:
        error = CompileError(
            MHDiagnostic(
                code="unsupported_attribute",
                severity="error",
                message=(
                    f"template {template.template_id!r} plays one ONCE cycle of "
                    f"{working_template.repeat.cycle_bars} bars, but section "
                    f"{context.section_id!r} lasts {context.duration_bars} bar(s): a "
                    "section end may not cut it short"
                ),
                section_id=context.section_id,
                action="rejected",
            )
        )
        if unplayable is None:
            raise error
        t0 = quantize_cue(context.start_ms).actual_ms
        t1 = max(t0, min(quantize_cue(context.end_ms).actual_ms, end_limit_ms))
        unplayable.extend(
            _unplayable_record(
                fixture.fixture_id,
                context.section_id.split("|")[0],
                template.template_id,
                None,
                t0,
                t1,
                "once_section_too_short",
                error,
            )
            for fixture in context.fixtures
        )
        return TemplateCompileResult(
            template_id=working_template.template_id,
            segments=[],
            num_complete_cycles=0,
            provenance=provenance,
        )
    section_segment = context.section_id.split("|")
    section_id = section_segment[0]
    segment_id = section_segment[1] if len(section_segment) > 1 else "A"

    segments: list[FixtureSegment] = []
    dropped: list[dict[str, str | int]] = []
    resolved: dict[str, dict[str, ResolvedStepComponents]] = {}
    phases: dict[str, dict[str, ResolvedFixturePhase]] = {}
    profile_keys: dict[str, str | None] = {}
    # Per step, the first instance of the run of instances each starting where the one
    # before it ends (its start in bars and on the frame grid), and where the last ends.
    chains: dict[str, tuple[float, int, float]] = {}
    for instance in schedule_result.instances:
        step = step_map[instance.step_id]
        requested_t0 = context.bar_offset_to_ms(instance.start_bars)
        requested_t1 = min(
            context.bar_offset_to_ms(instance.end_bars),
            context.end_ms,
        )
        t0 = quantize_cue(requested_t0).actual_ms
        t1 = min(quantize_cue(requested_t1).actual_ms, end_limit_ms)
        if t0 < start_limit_ms or t0 >= end_limit_ms:
            dropped.extend(
                {
                    "fixture_id": fixture.fixture_id,
                    "section_id": section_id,
                    "step_id": step.step_id,
                    "requested_start_ms": requested_t0,
                    "requested_end_ms": requested_t1,
                    "start_ms": t0,
                    "end_ms": quantize_cue(requested_t1).actual_ms,
                    "start_limit_ms": start_limit_ms,
                    "end_limit_ms": end_limit_ms,
                }
                for fixture in _resolve_target_fixtures(step, template, context)
            )
            continue
        if t1 <= t0:
            empty = EmptyStepError(
                f"step {step.step_id!r} of template {template.template_id!r} in section "
                f"{context.section_id!r} ({requested_t0}-{requested_t1} ms) leaves no "
                f"frame once quantized and cut at {end_limit_ms} ms"
            )
            if unplayable is None:
                raise empty
            unplayable.extend(
                _unplayable_record(
                    fixture.fixture_id,
                    section_id,
                    template.template_id,
                    step.step_id,
                    t0,
                    max(t0, t1),
                    "compile_refused",
                    empty,
                )
                for fixture in _resolve_target_fixtures(step, template, context)
            )
            continue
        targets = _resolve_target_fixtures(step, template, context)
        chain = chains.get(step.step_id)
        anchor = (
            (chain[0], chain[1])
            if chain is not None and math.isclose(chain[2], instance.start_bars, abs_tol=1e-9)
            else (instance.start_bars, t0)
        )
        chains[step.step_id] = (*anchor, instance.end_bars)
        shift = _phase_shift(
            step,
            anchor,
            instance.start_bars,
            t0,
            beats_per_bar=context.beat_grid.beats_per_bar,
            phase_map=phase_map,
        )
        components = None
        if step.component_refs is not None:
            if step.step_id not in resolved:
                try:
                    resolved[step.step_id] = resolve_component_refs(
                        step, tuple(fixture.fixture_id for fixture in targets), context.presets
                    )
                except ComponentRefError as error:
                    raise CompileError(
                        MHDiagnostic(
                            code="unsupported_attribute",
                            severity="error",
                            message=f"template {template.template_id!r}, {error}",
                            fixture_id=error.fixture_id,
                            section_id=context.section_id,
                            action="rejected",
                        )
                    ) from error
            components = resolved[step.step_id]
        distribution = None
        if step.distribution:
            if step.step_id not in phases:
                phases[step.step_id] = _resolve_phases(step, template, context, targets)
            distribution = phases[step.step_id]
        # This instance's sampled channels, by profile and resolved components, for heads
        # that share a channel's phase (`compile_step`).
        shared: dict[tuple[str | None, str | None], dict[tuple[Any, ...], Any]] = {}
        for fixture in targets:
            fixture_components = None if components is None else components[fixture.fixture_id]
            phase = None if distribution is None else distribution[fixture.fixture_id]
            step_context = StepCompileContext(
                section_id=section_id,
                segment_id=segment_id,
                template_id=context.template_id,
                preset_id=context.preset_id,
                fixture_id=fixture.fixture_id,
                role=fixture.role,
                start_ms=t0,
                duration_ms=t1 - t0,
                beat_grid=context.beat_grid,
                physical_profile=fixture.physical_profile,
                phase_map=phase_map,
                resolved_components=fixture_components,
                phase_offset_by_channel=_shifted(
                    {} if phase is None else phase.phase_by_channel, shift
                ),
                pan_sign=1 if phase is None else phase.pan_sign,
            )
            # Everything `compile_step` and `follow_lag` read besides identity, so a
            # head on the same profile, resolved components and phase reuses another's cue.
            fixture_key = (
                profile_keys.setdefault(
                    fixture.fixture_id,
                    None
                    if fixture.physical_profile is None
                    else fixture.physical_profile.model_dump_json(),
                ),
                None if fixture_components is None else fixture_components.model_dump_json(),
            )
            key = (
                template.template_id,
                context.preset_id,
                step.step_id,
                t0,
                t1,
                *fixture_key,
                tuple(sorted(step_context.phase_offset_by_channel.items())),
                step_context.pan_sign,
            )
            try:
                cached = None if step_cache is None else step_cache.get(key)
                if cached is not None:
                    segment = FixtureSegment(
                        **{
                            **dict(cached),
                            "fixture_id": fixture.fixture_id,
                            "channels": dict(cached.channels),
                            "metadata": dict(cached.metadata),
                        }
                    )
                else:
                    segment = compile_step(
                        step,
                        step_context,
                        sample_times_ms=tuple(range(t0, t1, EFFECT_GRID_MS)),
                        shared=shared.setdefault(fixture_key, {}),
                    )
                    assert fixture.physical_profile is not None  # checked by the step compile
                    lag = follow_lag(segment, fixture.physical_profile, frame_ms=EFFECT_GRID_MS)
                    if lag is not None:
                        channel, time_ms, reason = lag
                        raise PhysicalChannelError(
                            fixture_id=fixture.fixture_id,
                            channel=channel,
                            time_ms=time_ms,
                            reason=reason,
                        )
                    if step_cache is not None:
                        step_cache[key] = FixtureSegment(
                            **{
                                **dict(segment),
                                "channels": dict(segment.channels),
                                "metadata": dict(segment.metadata),
                            }
                        )
            except (CompileError, PhysicalChannelError, ValueError) as error:
                error.add_note(
                    f"template {template.template_id!r}, step {step.step_id!r}, "
                    f"fixture {fixture.fixture_id!r}"
                )
                # Only a deliberate refusal is left dark; any other error is a defect.
                if unplayable is None or not isinstance(
                    error, (CompileError, PhysicalChannelError)
                ):
                    raise
                unplayable.append(
                    _unplayable_record(
                        fixture.fixture_id,
                        section_id,
                        template.template_id,
                        step.step_id,
                        t0,
                        t1,
                        "compile_refused",
                        error,
                    )
                )
                continue
            assert fixture.physical_profile is not None  # the step compiled on it
            segment.add_metadata("requested_t0_ms", requested_t0)
            segment.add_metadata("requested_t1_ms", requested_t1)
            segment.add_metadata(FALLBACK_METADATA_KEY, step.reposition_fallback)
            if fixture_components is not None:
                segment.add_metadata("component_provenance", fixture_components.provenance)
            if phase is not None:
                segment.add_metadata(
                    "phase_distribution",
                    {
                        "rank": phase.rank,
                        "pan_sign": phase.pan_sign,
                        "offsets": {
                            channel.value: str(offset)
                            for channel, offset in phase.phase_by_channel.items()
                        },
                    },
                )
            if step.visibility is None:
                segments.append(segment)
                continue
            # After the metadata, so every lit slice carries it.
            try:
                segments.extend(
                    apply_visibility(
                        segment,
                        step.visibility,
                        movement=step.movement,
                        offset=step_context.phase_offset_by_channel.get(
                            ChannelName.PAN, Fraction(0)
                        ),
                        profile=fixture.physical_profile,
                        phase_map=phase_map,
                    )
                )
            except PhysicalChannelError as error:
                error.add_note(
                    f"template {template.template_id!r}, step {step.step_id!r}, "
                    f"fixture {fixture.fixture_id!r}"
                )
                if unplayable is None:
                    raise
                unplayable.append(
                    _unplayable_record(
                        fixture.fixture_id,
                        section_id,
                        template.template_id,
                        step.step_id,
                        t0,
                        t1,
                        "compile_refused",
                        error,
                    )
                )

    if held_states:
        segments = [_hold_states(segment, held_states, context) for segment in segments]
    if working_template.overlays:
        # A HOLD_LAST_POSE remainder replays the cycle's closing step from a new phase
        # origin; no authored cycle plays it there, so it takes no overlay. A TRUNCATE
        # remainder is the head of a cycle and keeps them; ONCE has no remainder instance.
        held = (
            schedule_result.num_complete_cycles
            if working_template.repeat.mode != RepeatMode.ONCE
            and schedule_result.remainder_policy == RemainderPolicy.HOLD_LAST_POSE
            and schedule_result.num_complete_cycles > 0
            else None
        )
        segments = _apply_overlays(
            working_template,
            context,
            sorted({instance.cycle_number for instance in schedule_result.instances} - {held}),
            segments,
        )
    return TemplateCompileResult(
        template_id=working_template.template_id,
        segments=segments,
        num_complete_cycles=schedule_result.num_complete_cycles,
        provenance=provenance,
        dropped_steps=dropped,
    )


def _hold_states(
    segment: FixtureSegment,
    held_states: Mapping[str, Mapping[ChannelName, str]],
    context: TemplateCompileContext,
) -> FixtureSegment:
    """`segment` with each of its fixture's `held_states` held from its start to its end."""
    held = held_states.get(segment.fixture_id)
    if not held:
        return segment
    profile = next(
        fixture.physical_profile
        for fixture in context.fixtures
        if fixture.fixture_id == segment.fixture_id
    )
    assert profile is not None  # the segment compiled on it
    channels = dict(segment.channels)
    for channel, state in held.items():
        trajectory = DiscreteTrajectory(events=(DiscretePoint(t_ms=segment.t0_ms, state=state),))
        check_physical_value(segment.fixture_id, channel, trajectory, profile)
        channels[channel] = ChannelValue(channel=channel, physical=trajectory)
    return segment.model_copy(update={"channels": channels})


def _step_periods(step: TemplateStep) -> set[Fraction]:
    """The periods, in beats, at which a step's motion and pulses repeat: a periodic
    movement's, and each dimmer or shutter pulse's that is not lit throughout."""
    movement = step.movement
    periods = {
        exact_decimal(pulse.period_beats)
        for pulse in (step.dimmer, step.shutter)
        if pulse is not None and pulse.duty_cycle < 1
    }
    if movement.mode == "periodic" and movement.period_beats is not None:
        periods.add(exact_decimal(movement.period_beats))
    return periods


def _phase_shift(
    step: TemplateStep,
    anchor: tuple[float, int],
    start_bars: float,
    t0: int,
    *,
    beats_per_bar: int,
    phase_map: MusicalPhaseMap,
) -> dict[ChannelName, Fraction]:
    """The cycles each channel's phase of a step instance lags behind its own start, so
    that it continues the phase of `anchor` (its start in bars and on the frame grid):
    the first of the run of the step's instances in which each starts where the one
    before it ends, as a step spanning its whole cycle repeats.

    Each instance starts on the frame grid nearest its musical start, so measured from
    its own start a step's phase would restart off by that instance's quantization, and
    the pose would step where one cue meets the next. Each channel whose period the
    instance starts whole periods after the anchor (pan and tilt, with the zoom and a
    visibility envelope that follow pan, for a periodic movement; the dimmer and the
    shutter for a pulse not lit throughout) measures its phase that many periods after
    the anchor's: shifted by the musical time between the two frame-grid starts beyond
    those whole beats. A finite movement restarts by design, so pan and tilt keep the
    instance's own start then, as does every other channel. Empty when nothing shifts
    (on a grid where every bar sits at the same distance from the frame grid, nothing
    does).
    """
    anchor_bars, anchor_t0 = anchor
    movement = step.movement
    periods = {
        channel: exact_decimal(pulse.period_beats)
        for channel, pulse in (
            (ChannelName.DIMMER, step.dimmer),
            (ChannelName.SHUTTER, step.shutter),
        )
        if pulse is not None and pulse.duty_cycle < 1
    }
    if movement.mode == "periodic" and movement.period_beats is not None:
        periods[ChannelName.PAN] = periods[ChannelName.TILT] = exact_decimal(movement.period_beats)
    beats = (exact_decimal(start_bars) - exact_decimal(anchor_bars)) * beats_per_bar
    periods = {c: p for c, p in periods.items() if (beats / p).denominator == 1}
    if not periods:
        return {}
    # The anchor's frame-grid start plus those whole beats, less this instance's.
    lag = beats - musical_phase_fraction(phase_map, t0, origin_ms=anchor_t0, period_beats=1.0)
    if not lag:
        return {}
    return {channel: lag / period for channel, period in periods.items()}


def _shifted(
    offsets: Mapping[ChannelName, Fraction], shift: Mapping[ChannelName, Fraction]
) -> dict[ChannelName, Fraction]:
    """`offsets` (a distribution's, in cycles each channel lags) plus `shift`."""
    if not shift:
        return dict(offsets)
    return {
        channel: offsets.get(channel, Fraction(0)) + shift.get(channel, Fraction(0))
        for channel in {*offsets, *shift}
    }


MAX_GROWN_CYCLE_BARS = 8
"""The longest cycle `whole_period_cycle` grows one to: every shipped family's cycle, in
any meter, fits (8 bars is its `slow` variant at an odd number of beats a bar)."""


def whole_period_cycle(template: Template, beats_per_bar: int) -> Template:
    """`template` with a repeating cycle that holds whole movement periods at this meter.

    Each cycle restarts its steps' motion and pulses, so a cycle whose length in beats is
    not a whole number of every periodic step's movement period, and of every dimmer or
    shutter pulse's period that is not lit throughout (duty below 1), would make the head
    jump or the pulse restart at each cycle boundary, and one ending before an overlay
    ends cannot hold the overlay.
    When every loop step spans the whole cycle, such a cycle and its loop steps grow to
    the smallest whole number of bars, no fewer than authored, that holds whole periods
    of each and every overlay; an overlay still plays once per (grown) cycle. Any other
    template is returned as it is: a ONCE template, a cycle that already holds them (the
    shipped families' 2-bar cycles in 4/4), and a cycle whose loop steps do not each
    span it, whose motion restarts at each step by design. The template compile, and so
    the pre-planning gate, plays every template through here.

    Raises:
        CompileError: If the grown cycle would be longer than
            `MAX_GROWN_CYCLE_BARS`.
    """
    repeat = template.repeat
    if repeat.mode == RepeatMode.ONCE:
        return template
    cycle = exact_decimal(repeat.cycle_bars)
    steps = [step for step in template.steps if step.step_id in repeat.loop_step_ids]
    if any(
        step.timing.base_timing.start_offset_bars != 0
        or exact_decimal(step.timing.base_timing.duration_bars) != cycle
        for step in steps
    ):
        return template
    periods = {period for step in steps for period in _step_periods(step)}
    ends = [exact_decimal(overlay.end_beats) for overlay in template.overlays]
    beats = cycle * beats_per_bar
    if all((beats / period).denominator == 1 for period in periods) and all(
        beats >= end for end in ends
    ):
        return template
    # Whole bars hold whole periods of each when their beats are a multiple of the
    # periods' least common multiple: every `multiple` bars.
    multiple = 1
    if periods:
        lcm = Fraction(
            math.lcm(*(period.numerator for period in periods)),
            math.gcd(*(period.denominator for period in periods)),
        )
        multiple = (beats_per_bar / lcm).denominator
    least = max([math.ceil(cycle), *(math.ceil(end / beats_per_bar) for end in ends)])
    bars = -(-least // multiple) * multiple
    if bars > MAX_GROWN_CYCLE_BARS:
        raise CompileError(
            MHDiagnostic(
                code="unsupported_attribute",
                severity="error",
                message=(
                    f"template {template.template_id!r} repeats a {float(cycle):g}-bar cycle, "
                    f"{float(beats):g} beats at {beats_per_bar} beats a bar, which holds no "
                    "whole number of its movement and pulse periods ("
                    + ", ".join(f"{float(period):g}" for period in sorted(periods))
                    + " beats) or ends before an overlay ends; the shortest cycle of whole "
                    f"bars that does is {bars} bars, longer than the {MAX_GROWN_CYCLE_BARS} "
                    "bars a cycle may grow to"
                ),
                action="rejected",
            )
        )
    grown = float(bars)
    return template.model_copy(
        update={
            "repeat": repeat.model_copy(update={"cycle_bars": grown}),
            "steps": [
                step.model_copy(
                    update={
                        "timing": step.timing.model_copy(
                            update={
                                "base_timing": step.timing.base_timing.model_copy(
                                    update={"duration_bars": grown}
                                )
                            }
                        )
                    }
                )
                if step.step_id in repeat.loop_step_ids
                else step
                for step in template.steps
            ],
        }
    )


def _unplayable_record(
    fixture_id: str,
    section_id: str,
    template_id: str,
    step_id: str | None,
    start_ms: int,
    end_ms: int,
    code: str,
    error: Exception,
) -> dict[str, str | int]:
    """A cue left out of an `on_unplayable="dark"` render, in the trace's record shape."""
    detail = "; ".join((str(error), *getattr(error, "__notes__", ())))
    return {
        "fixture_id": fixture_id,
        "section_id": section_id,
        "template_id": template_id,
        "step_id": step_id or "",
        "start_ms": start_ms,
        "end_ms": end_ms,
        "frames": (end_ms - start_ms) // EFFECT_GRID_MS,
        "reason": "unplayable",
        "code": code,
        "detail": detail,
    }


def _require_move_within_step(
    step: TemplateStep, template: Template, context: TemplateCompileContext
) -> None:
    """A ONCE step's finite move must end within the step, so a head without a phase
    offset reaches its terminal pose there: from a path's `transform.phase_cycles` c,
    the move takes `period_beats * (1 - c)`. Bars become beats at the grid's meter."""
    movement = step.movement
    if movement.period_beats is None:
        return
    step_beats = exact_decimal(step.timing.base_timing.duration_bars) * (
        context.beat_grid.beats_per_bar
    )
    phase = movement.transform.phase_cycles if movement.transform else 0.0
    if exact_decimal(movement.period_beats) * (1 - exact_decimal(phase)) > step_beats:
        raise CompileError(
            MHDiagnostic(
                code="unsupported_attribute",
                severity="error",
                message=(
                    f"template {template.template_id!r} repeats ONCE, but step "
                    f"{step.step_id!r} moves over {movement.period_beats} beats from phase "
                    f"{phase} in a {float(step_beats):g}-beat step, so it would still be "
                    "moving at its "
                    "end instead of reaching its terminal pose"
                ),
                section_id=context.section_id,
                action="rejected",
            )
        )


def _apply_overlays(
    template: Template,
    context: TemplateCompileContext,
    cycles: Sequence[int],
    segments: list[FixtureSegment],
) -> list[FixtureSegment]:
    """Split each fixture's cues around every overlay of every scheduled cycle.

    An overlay's beats are offsets from its cycle's start, placed and quantized exactly
    as a step starting there would be, so an overlay ending on a step boundary ends on
    that step's first frame.
    """
    beats_per_bar = context.beat_grid.beats_per_bar
    cycle_bars = template.repeat.cycle_bars
    cycle_beats = exact_decimal(cycle_bars) * beats_per_bar
    profiles = {
        fixture.fixture_id: fixture.physical_profile
        for fixture in context.fixtures
        if fixture.physical_profile is not None
    }
    fixture_ids = sorted({segment.fixture_id for segment in segments})
    for overlay in template.overlays:
        where = (
            f"template {template.template_id!r}, overlay on {overlay.channel} over beats "
            f"[{overlay.start_beats:g}, {overlay.end_beats:g})"
        )
        if exact_decimal(overlay.end_beats) > cycle_beats:
            raise _overlay_error(
                f"{where} ends after its {float(cycle_beats):g}-beat cycle", context
            )
        states = _overlay_states(overlay, fixture_ids, context, where)
        for cycle in cycles:

            def at(beats: float, cycle: int = cycle) -> int:
                bars = cycle * cycle_bars + beats / beats_per_bar
                return quantize_cue(context.bar_offset_to_ms(bars)).actual_ms

            segments = apply_overlay(
                segments,
                channel=ChannelName(overlay.channel),
                states=states,
                start_ms=at(overlay.start_beats),
                flick_start_ms=at(overlay.start_beats + overlay.mask_beats),
                flick_end_ms=at(overlay.end_beats - overlay.mask_beats),
                end_ms=at(overlay.end_beats),
                profiles=profiles,
            )
    return segments


def _overlay_states(
    overlay: AttributeOverlay,
    fixture_ids: Sequence[str],
    context: TemplateCompileContext,
    where: str,
) -> dict[str, str]:
    """Each fixture's overlay state: the named state, or the `channel` entry of the rig
    attribute preset's first entry for the fixture along its fallback chain."""
    if overlay.state is not None:
        return dict.fromkeys(fixture_ids, overlay.state)
    preset_id = overlay.attribute_preset_id
    assert preset_id is not None  # one of the two is set (validation)
    attributes = context.presets.attributes
    if preset_id not in attributes:
        raise _overlay_error(
            f"{where} references attribute preset {preset_id!r}, which the fixture group "
            f"does not declare (declared: {sorted(attributes)})",
            context,
        )
    states: dict[str, str] = {}
    for fixture_id in fixture_ids:
        current: str | None = preset_id
        entry = None
        while current is not None and entry is None:
            entry = attributes[current].fixtures.get(fixture_id)
            current = attributes[current].fallback
        state = None if entry is None else getattr(entry, overlay.channel)
        if state is None:
            raise _overlay_error(
                f"{where}: attribute preset {preset_id!r} sets no {overlay.channel} for "
                f"fixture {fixture_id!r} along its fallback chain",
                context,
                fixture_id,
            )
        states[fixture_id] = state
    return states


def _overlay_error(
    message: str, context: TemplateCompileContext, fixture_id: str | None = None
) -> CompileError:
    return CompileError(
        MHDiagnostic(
            code="unsupported_attribute",
            severity="error",
            message=message,
            fixture_id=fixture_id,
            section_id=context.section_id,
            action="rejected",
        )
    )


def _resolve_phases(
    step: TemplateStep,
    template: Template,
    context: TemplateCompileContext,
    targets: Sequence[FixtureContext],
) -> dict[str, ResolvedFixturePhase]:
    """Each target fixture's phase offsets and pan sign under the step's distribution."""

    def reject(message: str) -> CompileError:
        return CompileError(
            MHDiagnostic(
                code="unsupported_attribute",
                severity="error",
                message=f"template {template.template_id!r}, step {step.step_id!r}: {message}",
                section_id=context.section_id,
                action="rejected",
            )
        )

    if context.topology is None:
        raise reject(
            f"distribution needs the rig's topology, but fixture group "
            f"{context.fixture_group_id!r} declares no topology and not every fixture "
            "declares position.position_index to derive one row from"
        )
    try:
        return resolve_distribution(
            context.topology,
            step.distribution,
            tuple(fixture.fixture_id for fixture in targets),
        )
    except ValueError as error:
        raise reject(str(error)) from error


def apply_entry_window(
    segments: Sequence[FixtureSegment],
    window_ends: Mapping[str, int],
    *,
    profiles: Mapping[str, FixtureCapabilities],
    keep_dark: bool = False,
) -> tuple[list[FixtureSegment], list[dict[str, str | int]]]:
    """Hold each fixture's section opening dark until its entry window ends.

    For a fixture in `window_ends`, its first cue to be revealed after the window is
    entered from the transaction pass's darkness: a cue running across the window end is
    cut to begin there with `slice_segment`, so its phase origin is kept, and
    that cue (or, when every earlier cue lies in the window, the first cue after it)
    begins where its shutter state can be held for the visibility latency plus settle
    it needs, moving on to the cue's next shutter change otherwise and dropping the
    partial state. A cue with no such point, or cut where it stays commanded dark to its
    end (it would show nothing, and its darkness would count only from the cut), is
    dropped and recorded, and the next one is tried; later cues are unchanged. Fixtures not in `window_ends` keep every cue.
    With `keep_dark` (a section's REST, dark by design) a cue cut dark to its end is kept:
    the planner's events may light it.

    Args:
        segments: A section's compiled cues on the frame grid, each fixture's in
            time order.
        window_ends: Each windowed fixture's window end, on the frame grid.
        profiles: Each fixture's physical profile.

    Returns:
        The kept cues, in input order, and one record per dropped cue: its step's requested
        bounds and the frames `[start_ms, end_ms)` it held, which for a lit slice or an
        overlay part are that part's own.
    """
    kept: list[FixtureSegment] = []
    dropped: list[dict[str, str | int]] = []
    entered: set[str] = set()
    for segment in segments:
        window_end = window_ends.get(segment.fixture_id)
        if window_end is None or segment.fixture_id in entered:
            kept.append(segment)
            continue
        start = max(segment.t0_ms, window_end)
        cut = (
            None
            if segment.t1_ms <= start
            else _holdable_cut(segment, start, profiles[segment.fixture_id])
        )
        if cut is not None and (
            cut == segment.t0_ms
            or keep_dark
            or not dark_throughout(segment, profiles[segment.fixture_id], cut)
        ):
            entered.add(segment.fixture_id)
            kept.append(
                segment if cut == segment.t0_ms else slice_segment(segment, cut, segment.t1_ms)
            )
            continue
        dropped.append(
            {
                "fixture_id": segment.fixture_id,
                "section_id": segment.section_id,
                "step_id": segment.step_id,
                "requested_start_ms": int(segment.metadata["requested_t0_ms"]),
                "requested_end_ms": int(segment.metadata["requested_t1_ms"]),
                "start_ms": segment.t0_ms,
                "end_ms": segment.t1_ms,
                "entry_window_end_ms": window_end,
            }
        )
    return kept, dropped


def _holdable_cut(
    segment: FixtureSegment, start_ms: int, profile: FixtureCapabilities
) -> int | None:
    """The first time from `start_ms` at which the cue's shutter state can begin a reveal.

    Entered from the transaction's dark state, a state must hold until the cue's next
    shutter change (or its end) for the latency it may cross plus its settle, both
    known; None when no state of the cue's remainder does.
    """
    value = segment.channels.get(ChannelName.SHUTTER)
    capability = profile.discrete.get("shutter")
    if value is None or capability is None or not isinstance(value.physical, DiscreteTrajectory):
        return start_ms
    events = value.physical.events
    visibility = profile.visibility
    cut = start_ms
    while cut < segment.t1_ms:
        state = [event.state for event in events if event.t_ms <= cut][-1]
        following = next((event.t_ms for event in events if event.t_ms > cut), None)
        dark = state in visibility.extinguishing_shutter_states
        latency = visibility.close_latency_ms if dark else visibility.open_latency_ms
        settle = capability.states[state].settle_ms
        holds = (following or segment.t1_ms) - cut
        if latency is not None and settle is not None and holds >= latency + settle:
            return cut
        if following is None:
            return None
        cut = following
    return None


def _resolve_target_fixtures(
    step: TemplateStep,
    template: Template,
    context: TemplateCompileContext,
) -> list[FixtureContext]:
    """Resolve the fixtures a step targets, against the roles the rig actually has.

    The semantic group is resolved against the *rig's* roles rather than the roles
    the template declares. A template declaring the four-head
    `OUTER_LEFT/INNER_LEFT/INNER_RIGHT/OUTER_RIGHT` vocabulary is not a statement
    that it may only light four heads; it is the shape it was authored for. Resolving
    against the template's list is what made every step on a rig with any other
    fixture count match nothing at all.

    Args:
        step: The step whose target group is being resolved.
        template: The template being compiled.
        context: Compile context carrying the rig's fixtures.

    Returns:
        Fixtures the step should be compiled for.

    Raises:
        UnsupportedRigShapeError: If the step's target group matches no fixture.
    """
    rig_roles: list[TemplateRole] = []
    for fixture in context.fixtures:
        try:
            role = TemplateRole(fixture.role)
        except ValueError:
            continue
        if role not in rig_roles:
            rig_roles.append(role)

    available_roles = rig_roles

    try:
        target_roles = resolve_semantic_group(step.target, available_roles)
    except ValueError as error:
        raise UnsupportedRigShapeError(
            f"template '{template.template_id}' step '{step.step_id}' targets group "
            f"'{step.target.value}', which no fixture in this rig can fill "
            f"(rig roles: {[role.value for role in rig_roles] or 'none recognized'}). "
            "Use a rig whose fixture count maps onto the group, or a template that "
            "does not address it."
        ) from error

    target_fixtures = [fixture for fixture in context.fixtures if fixture.role in target_roles]

    if not target_fixtures:
        raise UnsupportedRigShapeError(
            f"template '{template.template_id}' step '{step.step_id}' targets group "
            f"'{step.target.value}' (roles {[role.value for role in target_roles]}), "
            f"but no fixture in this rig holds any of them "
            f"(rig roles: {sorted({fixture.role for fixture in context.fixtures})})."
        )

    return target_fixtures
