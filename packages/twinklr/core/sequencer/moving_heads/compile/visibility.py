"""Visibility envelopes and masked attribute overlays for cues (P2.4b).

Both only cut compiled cues apart: `apply_visibility` keeps the lit slices of a cue and
`apply_overlay` splits cues around a temporary wheel state. Every dark span they leave
is a gap between cues, which `plan_prepositions` authors as an ordinary transaction
(darkness, wheel turns, travel, settle, reveal), so there is one dark-motion algorithm
and nothing here authors motion in the dark. Slices are cut with
`slice_segment`, so each keeps its cue's phase origin and its motion does not
restart.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import pairwise
import math

from twinklr.core.config.fixtures.capabilities import FixtureCapabilities
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    DISCRETE_KEYS,
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalChannelError,
    PhysicalPoint,
    check_physical_value,
)
from twinklr.core.sequencer.models.template import Movement, VisibilityEnvelope
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.step import slice_segment
from twinklr.core.sequencer.timing.musical_phase import (
    MusicalPhaseMap,
    exact_decimal,
    musical_phase_fraction,
    musical_time_at,
)


def apply_visibility(
    segment: FixtureSegment,
    envelope: VisibilityEnvelope,
    *,
    movement: Movement,
    offset: Fraction,
    profile: FixtureCapabilities,
    phase_map: MusicalPhaseMap,
) -> tuple[FixtureSegment, ...]:
    """The lit slices of one compiled cue under its step's visibility envelope.

    A frame is lit when the fixture's movement phase at its start, the step phase from
    the cue's phase origin minus `offset` (its pan/tilt distribution offset), lies in
    `[visible_phase_start, visible_phase_end)` of a cycle: of every cycle for a periodic
    movement. A finite movement's phase clamps to `[0, 1]` as its motion does, and a
    window ending at 1 includes 1: a window from 0 lights a lagging head holding its
    start, one ending at 1 the terminal hold after the move. Each lit slice authors the dimmer at
    `envelope.level`, ramped linearly from 0 over `attack_beats` after the window start
    and to 0 over `release_beats` before the window end, read at each frame's phase; and
    the shutter at the cue's own static state, else the profile's `discrete.open_state`.

    Args:
        segment: A compiled cue on the frame grid, with `phase_origin_ms`.
        envelope: The step's envelope.
        movement: The step's movement, whose `period_beats` and mode set the cycles.
        offset: The fixture's pan/tilt phase offset in cycles.
        profile: The fixture's physical profile.
        phase_map: The song's musical phase map.

    Returns:
        The lit slices in time order; none when the cue is dark throughout.

    Raises:
        PhysicalChannelError: For a lit window or dark interval inside the cue shorter
            than one frame (one cut by the cue's start or end is exempt, as for pulses),
            a ramp or a level below 1 on a profile without a dimmer axis, or no shutter
            state to light through.
    """
    assert movement.period_beats is not None  # an envelope step has a period (validation)
    period = movement.period_beats
    origin = int(segment.metadata["phase_origin_ms"])
    start = exact_decimal(envelope.visible_phase_start)
    end = exact_decimal(envelope.visible_phase_end)
    attack = exact_decimal(envelope.attack_beats)
    release = exact_decimal(envelope.release_beats)

    def phase(time_ms: int) -> Fraction:
        return (
            musical_phase_fraction(phase_map, time_ms, origin_ms=origin, period_beats=period)
            - offset
        )

    def time_at(movement_phase: Fraction) -> Fraction:
        return musical_time_at(
            phase_map, movement_phase + offset, origin_ms=origin, period_beats=period
        )

    def fail(
        time_ms: int, reason: str, channel: ChannelName = ChannelName.DIMMER
    ) -> PhysicalChannelError:
        return PhysicalChannelError(
            fixture_id=segment.fixture_id, channel=channel, time_ms=time_ms, reason=reason
        )

    dimmer = profile.axes.get("dimmer")
    if dimmer is None and (attack or release or envelope.level != 1):
        raise fail(
            segment.t0_ms,
            "the envelope's ramps and level need a dimmer, but the profile declares no "
            "dimmer axis; light it through the shutter with zero ramps and level 1",
        )
    # The step's own static state (validation leaves no pulse) is already on the cue.
    open_state = None
    capability = profile.discrete.get("shutter")
    if ChannelName.SHUTTER not in segment.channels and capability is not None:
        open_state = capability.open_state
        if open_state is None:
            raise fail(
                segment.t0_ms,
                "the envelope lights the step through its static shutter state or the "
                "profile's open_state, but the step sets none and the profile declares no "
                "open_state",
                ChannelName.SHUTTER,
            )

    finite = movement.mode == "finite"
    low, high = phase(segment.t0_ms), phase(segment.t1_ms)
    if finite:
        # The phase clamps to [0, 1] as the motion does: a window from 0 also lights a
        # lagging head holding its start, and one ending at 1 lights the terminal hold.
        windows = [(start if start else min(start, low), end if end < 1 else max(end, high))]
    else:
        cycles = range(math.floor(low) - 1, math.floor(high) + 1)
        windows = [(cycle + start, cycle + end) for cycle in cycles]
    dark = [(earlier[1], later[0]) for earlier, later in pairwise(windows)]
    for kind, intervals in (("lit window", windows), ("dark interval", dark)):
        for first, last in intervals:
            if low < first < last < high and time_at(last) - time_at(first) < EFFECT_GRID_MS:
                at = time_at(first)
                raise fail(
                    math.floor(at),
                    f"{kind} [{float(at):g}, {float(time_at(last)):g}) ms lasts "
                    f"{float(time_at(last) - at):g} ms, shorter than one {EFFECT_GRID_MS} ms frame",
                )

    spans: list[tuple[int, int]] = []
    for first, last in windows:
        if last <= low or first >= high:
            continue
        lit_start = segment.t0_ms if first <= low else _frame_at_or_after(time_at(first))
        lit_end = (
            segment.t1_ms if last >= high else min(segment.t1_ms, _frame_at_or_after(time_at(last)))
        )
        if lit_start >= lit_end:
            continue
        if spans and spans[-1][1] == lit_start:  # a whole-period window: one slice
            lit_start = spans.pop()[0]
        spans.append((lit_start, lit_end))

    slices: list[FixtureSegment] = []
    for lit_start, lit_end in spans:
        lit = slice_segment(segment, lit_start, lit_end)
        if open_state is not None:
            held = DiscreteTrajectory(events=(DiscretePoint(t_ms=lit_start, state=open_state),))
            lit.channels[ChannelName.SHUTTER] = ChannelValue(
                channel=ChannelName.SHUTTER, physical=held
            )
        if dimmer is not None:
            levels: list[PhysicalPoint] = []
            for time_ms in range(lit_start, lit_end, EFFECT_GRID_MS):
                here = phase(time_ms)
                if finite:
                    here = min(max(here, Fraction(0)), Fraction(1))
                opened = start if finite else math.floor(here - start) + start
                share = _ramped(here, opened, opened - start + end, period, attack, release)
                value = float(exact_decimal(envelope.level) * share)
                if not levels or levels[-1].value != value:
                    levels.append(PhysicalPoint(t_ms=time_ms, value=value))
            trajectory = ContinuousTrajectory(
                unit="normalized", points=tuple(levels), interpolation="hold"
            )
            check_physical_value(segment.fixture_id, ChannelName.DIMMER, trajectory, profile)
            lit.channels[ChannelName.DIMMER] = ChannelValue(
                channel=ChannelName.DIMMER, physical=trajectory
            )
        slices.append(lit)
    return tuple(slices)


def apply_overlay(
    segments: Sequence[FixtureSegment],
    *,
    channel: ChannelName,
    states: Mapping[str, str],
    start_ms: int,
    flick_start_ms: int,
    flick_end_ms: int,
    end_ms: int,
    profiles: Mapping[str, FixtureCapabilities],
) -> list[FixtureSegment]:
    """Split every cue crossing one overlay: base, dark mask, overlay, dark mask, base.

    `[start_ms, flick_start_ms)` and `[flick_end_ms, end_ms)` are left as gaps, so the
    transaction pass turns the wheel there in the dark and lets it settle;
    `[flick_start_ms, flick_end_ms)` keeps each cue's own content with `channel` held at
    the fixture's state in `states`. Outside `[start_ms, end_ms)` every cue is unchanged,
    so what follows the overlay is whatever base cue is in force then. A cue whose base
    already holds the overlay's state (its own, or the profile's default where it
    authors none) is kept whole, with no masks, and records the channel under
    `overlay_unchanged` in its metadata. Bounds are on the frame grid; a mask that leaves
    no frame is not widened, and the transaction pass then refuses the wheel turn it
    would need.

    Returns:
        The cues, in input order, each crossing one replaced by its kept parts.

    Raises:
        PhysicalChannelError: If a fixture's profile does not declare the state.
    """
    out: list[FixtureSegment] = []
    for segment in segments:
        if segment.t1_ms <= start_ms or segment.t0_ms >= end_ms:
            out.append(segment)
            continue
        state = states[segment.fixture_id]
        if _base_state(segment, channel, profiles[segment.fixture_id]) == state:
            unchanged = [segment.metadata.get("overlay_unchanged", ""), channel.value]
            metadata = {
                **segment.metadata,
                "overlay_unchanged": ",".join(name for name in unchanged if name),
            }
            out.append(segment.model_copy(update={"metadata": metadata}))
            continue
        for part_start, part_end, flick in (
            (segment.t0_ms, start_ms, False),
            (flick_start_ms, flick_end_ms, True),
            (end_ms, segment.t1_ms, False),
        ):
            part_start, part_end = max(part_start, segment.t0_ms), min(part_end, segment.t1_ms)
            if part_start >= part_end:
                continue
            part = slice_segment(segment, part_start, part_end)
            if flick:
                held = DiscreteTrajectory(events=(DiscretePoint(t_ms=part_start, state=state),))
                check_physical_value(
                    segment.fixture_id, channel, held, profiles[segment.fixture_id]
                )
                part.channels[channel] = ChannelValue(channel=channel, physical=held)
            out.append(part)
    return out


def _base_state(
    segment: FixtureSegment, channel: ChannelName, profile: FixtureCapabilities
) -> str | None:
    """The one state a cue holds on a wheel (the default where it authors none); None
    when it changes state inside the cue."""
    value = segment.channels.get(channel)
    if value is None:
        capability = profile.discrete.get(DISCRETE_KEYS[channel])
        return None if capability is None else capability.default_state
    physical = value.physical
    if not isinstance(physical, DiscreteTrajectory) or len(physical.events) != 1:
        return None
    return physical.events[0].state


def _frame_at_or_after(time_ms: Fraction) -> int:
    """The first frame start at or after an exact time."""
    return math.ceil(time_ms / EFFECT_GRID_MS) * EFFECT_GRID_MS


def _ramped(
    movement_phase: Fraction,
    first: Fraction,
    last: Fraction,
    period_beats: float,
    attack: Fraction,
    release: Fraction,
) -> Fraction:
    """The envelope's share of its level at a movement phase inside `[first, last)`: rising
    over `attack` beats from `first`, falling over `release` beats to `last`."""
    period = exact_decimal(period_beats)
    share = Fraction(1)
    if attack:
        share = min(share, (movement_phase - first) * period / attack)
    if release:
        share = min(share, (last - movement_phase) * period / release)
    return max(share, Fraction(0))
