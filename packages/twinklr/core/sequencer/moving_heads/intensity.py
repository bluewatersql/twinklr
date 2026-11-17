"""The planner's section intensity, played on the dimmer (song-intent rendering W5).

The planner names a category; this module turns it into dimmer levels on musical phase.
Everything that decides how intensity looks is the table (`SHAPES`, `HEADROOM_BELOW`,
`ACCENT`, `dramatic_period_beats`), the curve (`accent`) and the focal mapping
(`effective_intensity`). The values are a first proposal for the owner to judge on a
render (W5 view), not measured or accepted looks.

- **Identity levels.** A level without an entry in `SHAPES` (as authored, `SMOOTH`,
  `SLOW`, `FAST`) plays the template exactly as authored (the owner's 2026-11-12 ruling
  made SLOW and FAST equal SMOOTH; the revised plan made SMOOTH the identity).
- **Shaped levels** (`DRAMATIC`, `INTENSE`) multiply each lit frame's authored level `a`
  by a gain that follows a beat-locked accent `e` (`accent`: 1 where an accent starts,
  easing to 0 over `ACCENT.decay_beats`, 0 until the next). The accents fall on every
  beat (`INTENSE`) or the strong beats (`DRAMATIC`, `dramatic_period_beats`), and on the
  first lit frame of every lit run, so a head revealed after any darkness (a dark phase,
  a show's rest, a colour change's dip) comes in on an accent. Per lit run, by the run's
  highest authored level `M`:
  - **headroom** (`M` below `HEADROOM_BELOW` of the dimmer's top): gain `1 + g * (floor
    + peak * e)`, `g` scaling the table's gains down just enough that the run's peak
    reaches the top at most. The light rises and peaks on the beat; the template's own
    shape (a held level, its own pulse, a ramp) stays readable under it;
  - **full** (`M` at or above it, every catalog family): gain `full_peak - (full_peak -
    full_floor) * (1 - e)`, a dip-and-return on the run's own shape: the authored level
    on the accent, easing down to `full_floor` of it between accents. More movement in
    the light, not more light: the only case where frames play below the template.
  A frame the template commands dark (dimmer zero, or an extinguishing shutter state) is
  never touched, and no lit frame goes to zero, so the dark frames are the template's.
- **Physical limits.** A head without a dimmer axis cannot pulse: it plays as authored,
  recorded. Where the dimmer axis declares `travel_speed_per_s`, a shape whose largest
  frame-to-frame step exceeds it is scaled down (accent and dip together) until it fits,
  recorded; where it declares `latency_ms`, the accents are commanded that much earlier
  (at most just under half the section's shortest beat), so the light lands on the beat.
  The template's own dimmer edges are not led.
- **Focal role (`twinklr show`).** `effective_intensity`: LEAD raises the section one
  step toward INTENSE, SUPPORT leaves the planner's choice, REST caps it at the identity.

The shaping runs once the render has placed every darkness of a section (dark spans,
boundary dips, deferred turns, entry windows), on the cues as they will play.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import pairwise
from typing import Any, Literal

from twinklr.core.config.fixtures.capabilities import AxisCapability, FixtureCapabilities
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscreteTrajectory,
    PhysicalPoint,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.preposition import frame_values, state_at
from twinklr.core.sequencer.moving_heads.export.frame_encoder import quantize_cue
from twinklr.core.sequencer.timing.musical_phase import (
    MusicalPhaseError,
    MusicalPhaseMap,
    musical_phase_fraction,
    musical_time_at,
)

SHAPED_LEVELS = ("DRAMATIC", "INTENSE")
"""The intensities that pulse on the dimmer (a rig without one cannot show them)."""


@dataclass(frozen=True)
class IntensityShape:
    """One shaped level's values (`SHAPES`): gains on the authored level."""

    every: Literal["beat", "strong_beat"]
    """Its accents: every beat, or the strong beats (`dramatic_period_beats`)."""
    floor_gain: float
    """Headroom: the floor rises to `a * (1 + floor_gain)`."""
    peak_gain: float
    """Headroom: the accent adds `a * peak_gain` on top of the floor."""
    full_floor: float
    """Full: between accents the level eases down to `a * full_floor`."""
    full_peak: float
    """Full: on the accent the level is `a * full_peak`."""


SHAPES: dict[str, IntensityShape] = {
    "DRAMATIC": IntensityShape(
        every="strong_beat", floor_gain=0.10, peak_gain=0.40, full_floor=0.75, full_peak=1.0
    ),
    "INTENSE": IntensityShape(
        every="beat", floor_gain=0.15, peak_gain=0.60, full_floor=0.60, full_peak=1.0
    ),
}
"""Proposed (W5, 2026-11-17), for the owner to judge. Keyed by the effective intensity; a
level without an entry plays as authored. INTENSE accents every beat and drives harder
than DRAMATIC: a higher floor and peak with headroom, a deeper dip at full. On a full
family the mean lit level is about 0.80 of the authored light under DRAMATIC (0.84 on a
cascade, whose short lit windows each start on an accent) and 0.74 under INTENSE (owner
question H2 of the W5 review)."""

HEADROOM_BELOW = 0.85
"""A lit run whose highest authored level is below this share of the dimmer's top is
shaped with headroom (it brightens and peaks on the beat); at or above it, with the
dip-and-return. Below it a pulse up to the top is at least 18% of the level; at 0.85 and
above too little room is left for one to read. Proposed (W5 review fix round)."""


@dataclass(frozen=True)
class AccentCurve:
    """The accent's shape over musical phase (`accent`)."""

    decay_beats: float
    """The accent eases from 1 on the beat to 0 over this many beats (or the period,
    whichever is shorter), then holds 0 until the next accent."""


ACCENT = AccentCurve(decay_beats=1.0)
"""Proposed (W5). One beat: short enough to read as a pulse, not a fade, at every
tempo; DRAMATIC's longer period therefore holds its floor for the rest of the period."""


def dramatic_period_beats(beats_per_bar: int) -> int:
    """DRAMATIC's accent period, a whole number of beats of at least two from the meter:
    the half bar in an even meter of four beats or more (2 in 4/4, 3 in 6/8 counted in
    eighths), otherwise the bar (3 in 3/4, 2 in 2/4, 5 in 5/4). INTENSE accents every
    beat."""
    if beats_per_bar >= 4 and beats_per_bar % 2 == 0:
        return beats_per_bar // 2
    return max(2, beats_per_bar)


def period_beats(shape: IntensityShape, beats_per_bar: int) -> int:
    """The accent period of a shape, in beats."""
    return 1 if shape.every == "beat" else dramatic_period_beats(beats_per_bar)


def accent(beats_into_period: float, period: float) -> float:
    """The accent at a phase into its period: `(1 - p / d)**2` for `p < d`, else 0, where
    `d` is `ACCENT.decay_beats` or the period, whichever is shorter. A quadratic ease-out:
    the level is at its accent on the beat's first frame and falls fastest right after
    it, so it reads as a hit on the beat."""
    decay = min(ACCENT.decay_beats, period)
    if beats_into_period >= decay:
        return 0.0
    share = 1.0 - beats_into_period / decay
    return share * share


# --- the focal role (`twinklr show`) --------------------------------------------------

_ONE_STEP_HOTTER = {"DRAMATIC": "INTENSE", "INTENSE": "INTENSE"}


def effective_intensity(asked: str | None, focal_role: str | None) -> str | None:
    """The intensity a section plays, given the moving heads' macro focal role there.

    - LEAD: one step toward INTENSE: as authored, SLOW, SMOOTH or FAST → DRAMATIC;
      DRAMATIC → INTENSE; INTENSE stays.
    - REST: capped at the identity: DRAMATIC or INTENSE → as authored; the rest stay.
    - SUPPORT, or no focal role (`twinklr run`): the planner's choice.
    """
    if focal_role == "LEAD":
        return _ONE_STEP_HOTTER.get(asked or "", "DRAMATIC")
    if focal_role == "REST" and asked in SHAPED_LEVELS:
        return None
    return asked


# --- shaping a section's cues ---------------------------------------------------------


def shape_for(level: str | None) -> IntensityShape | None:
    """The shape an effective intensity plays, or None where it plays as authored."""
    return SHAPES.get(level or "AS_AUTHORED")


def _dimmer_samples(
    cue: FixtureSegment, axis: AxisCapability, profile: FixtureCapabilities
) -> dict[int, Fraction | float]:
    """The cue's authored dimmer level at each of its frames, as the encoder writes it
    (its trajectory, or the profile's default word where it authors none)."""
    times = range(cue.t0_ms, cue.t1_ms, EFFECT_GRID_MS)
    authored = cue.channels.get(ChannelName.DIMMER)
    if authored is not None and isinstance(authored.physical, ContinuousTrajectory):
        return dict(frame_values(authored.physical, cue.t0_ms, cue.t1_ms, EFFECT_GRID_MS))
    return dict.fromkeys(times, axis.word_center(axis.default_word(profile.defaults)))


def _shutter_dark(cue: FixtureSegment, profile: FixtureCapabilities) -> set[int]:
    """The cue's frames whose shutter state extinguishes."""
    extinguishing = profile.visibility.extinguishing_shutter_states
    capability = profile.discrete.get("shutter")
    if capability is None or not extinguishing:
        return set()
    held = cue.channels.get(ChannelName.SHUTTER)
    times = range(cue.t0_ms, cue.t1_ms, EFFECT_GRID_MS)
    if held is None or not isinstance(held.physical, DiscreteTrajectory):
        return set(times) if capability.default_state in extinguishing else set()
    return {t for t in times if state_at(held.physical, t) in extinguishing}


@dataclass(frozen=True)
class _Grid:
    """A section's beats: where its accents are commanded and how far a frame is into
    the musical time since one."""

    phase_map: MusicalPhaseMap
    origin_ms: float
    accents: tuple[int, ...]
    lead_ms: int

    @classmethod
    def of(
        cls,
        phase_map: MusicalPhaseMap,
        origin_ms: float,
        end_ms: float,
        period: int,
        latency_ms: int,
    ) -> _Grid:
        """The accent frames of every `period`-th beat in `[origin_ms, end_ms)`, each the
        frame nearest the beat less the lead (as the compiler places a template's own
        beat edges), none before the section's first frame. The lead is the dimmer's
        latency, at most just under half the section's shortest beat."""
        beats: list[Fraction] = []
        while True:
            try:
                beat = musical_time_at(
                    phase_map, Fraction(len(beats)), origin_ms=origin_ms, period_beats=1
                )
            except MusicalPhaseError:
                break
            if beat >= end_ms:
                break
            beats.append(beat)
        shortest = min((b - a for a, b in pairwise(beats)), default=Fraction(0))
        lead = max(0, min(latency_ms, int(shortest / 2) - 1)) if latency_ms else 0
        first = quantize_cue(round(origin_ms)).actual_ms
        accents = tuple(
            max(first, quantize_cue(round(beat - lead)).actual_ms) for beat in beats[::period]
        )
        return cls(phase_map, origin_ms, accents, lead)

    def beats(self, time_ms: int) -> Fraction:
        return musical_phase_fraction(
            self.phase_map, time_ms, origin_ms=self.origin_ms, period_beats=1
        )


@dataclass
class _Run:
    """Consecutive lit frames of one head: `(time, authored level, cue index)`."""

    frames: list[tuple[int, Fraction | float, int]] = field(default_factory=list)


def _lit_runs(
    cues: Sequence[FixtureSegment], profile: FixtureCapabilities, axis: AxisCapability
) -> list[_Run]:
    """A head's lit runs over its cues (in time order): broken by a dark frame, a zero
    dimmer, or a gap between cues."""
    zero = axis.dmx_word(0)
    runs: list[_Run] = []
    last = None
    for index, cue in enumerate(cues):
        dark = _shutter_dark(cue, profile)
        for time_ms, level in _dimmer_samples(cue, axis, profile).items():
            if time_ms in dark or axis.dmx_word(level) == zero:
                last = None
                continue
            if last != time_ms - EFFECT_GRID_MS:
                runs.append(_Run())
            runs[-1].frames.append((time_ms, level, index))
            last = time_ms
    return runs


def _gains(
    run: _Run, shape: IntensityShape, grid: _Grid, period: int, top: Fraction
) -> tuple[str, list[tuple[float, float]]]:
    """The run's shape name and, per frame, its gain as `(fixed, moving)`: the gain is
    `fixed + scale * moving` (`scale` 1, or less for a slow dimmer, shrinking the accent
    and the dip together)."""
    times = [time_ms for time_ms, _, _ in run.frames]
    highest = max(Fraction(level) for _, level, _ in run.frames)
    # The run starts on an accent; a beat accent one frame after it is the same one.
    starts = [times[0]] + [f for f in grid.accents if times[0] + EFFECT_GRID_MS < f <= times[-1]]
    start, gains = 0, []
    for time_ms in times:
        while start + 1 < len(starts) and starts[start + 1] <= time_ms:
            start += 1
        e = accent(float(grid.beats(time_ms) - grid.beats(starts[start])), period)
        if highest >= top * Fraction(HEADROOM_BELOW):
            depth = shape.full_peak - shape.full_floor
            gains.append((shape.full_peak, -depth * (1 - e)))
            continue
        room = float(top / highest) - 1
        total = shape.floor_gain + shape.peak_gain
        g = min(1.0, room / total) if total > 0 else 1.0
        gains.append((1 + g * shape.floor_gain, g * shape.peak_gain * e))
    if highest >= top * Fraction(HEADROOM_BELOW):
        return "dip_and_return", gains
    held = len({level for _, level, _ in run.frames}) == 1
    return ("headroom_pulse" if held else "authored_pulse_accent"), gains


@dataclass
class _HeadShape:
    """What shaping did on one head over a section."""

    shapes: set[str] = field(default_factory=set)
    scale: float = 1.0
    lead_ms: int = 0


def _shape_head(
    cues: Sequence[FixtureSegment],
    shape: IntensityShape,
    profile: FixtureCapabilities,
    axis: AxisCapability,
    grid: _Grid,
    period: int,
) -> tuple[list[FixtureSegment], _HeadShape]:
    """One head's cues of a section (in time order) under `shape` (`shape_section`)."""
    top = Fraction(axis.operable_range[1])
    head = _HeadShape(lead_ms=grid.lead_ms)
    runs = [(run, *_gains(run, shape, grid, period, top)) for run in _lit_runs(cues, profile, axis)]
    for _, name, _ in runs:
        head.shapes.add(name)
    if axis.travel_speed_per_s is not None:
        # The largest frame-to-frame step the accent adds to the template's own.
        allowed = axis.travel_speed_per_s * EFFECT_GRID_MS / 1000
        steepest = max(
            (
                abs(float(b[1]) * gb[1] - float(a[1]) * ga[1])
                for run, _, gains in runs
                for (a, ga), (b, gb) in pairwise(zip(run.frames, gains, strict=True))
            ),
            default=0.0,
        )
        if steepest > allowed:
            head.scale = allowed / steepest
    zero = axis.dmx_word(0)
    levels: dict[int, dict[int, float]] = {}
    for run, _, gains in runs:
        for (time_ms, level, index), (fixed, accented) in zip(run.frames, gains, strict=True):
            value = float(min(top, Fraction(level) * Fraction(fixed + head.scale * accented)))
            # A lit frame stays lit, however low a ramp starts.
            levels.setdefault(index, {})[time_ms] = (
                value if axis.dmx_word(value) != zero else float(level)
            )
    out = []
    for index, cue in enumerate(cues):
        if index not in levels:
            out.append(cue)
            continue
        values = {t: float(v) for t, v in _dimmer_samples(cue, axis, profile).items()}
        values |= levels[index]
        points: list[PhysicalPoint] = []
        for time_ms, value in values.items():
            if not points or points[-1].value != value:
                points.append(PhysicalPoint(t_ms=time_ms, value=value))
        channels = dict(cue.channels)
        channels[ChannelName.DIMMER] = ChannelValue(
            channel=ChannelName.DIMMER,
            physical=ContinuousTrajectory(
                unit="normalized", points=tuple(points), interpolation="hold"
            ),
        )
        out.append(cue.model_copy(update={"channels": channels}))
    return out, head


def shape_section(
    cues: Sequence[FixtureSegment],
    level: str | None,
    *,
    profiles: Mapping[str, FixtureCapabilities],
    phase_map: MusicalPhaseMap,
    origin_ms: float,
    end_ms: float,
    beats_per_bar: int,
) -> tuple[list[FixtureSegment], dict[str, Any]]:
    """A section's cues, as they will play, with `level` (an effective intensity with a
    shape, `shape_for`) played on the dimmer (in the
    order given), and what it did, for the trace: the table's values, the shapes applied
    by head, and the heads scaled for a slow dimmer (`degraded`), led by their dimmer's
    latency (`lead_ms`) or without a dimmer axis (`unavailable`).

    Accents count beats from `origin_ms`, the section's first downbeat, so a DRAMATIC
    accent lands on the bar's strong beats. Only the dimmer of lit frames changes.
    """
    shape = shape_for(level)
    assert shape is not None  # the render shapes only a level with a shape
    period = period_beats(shape, beats_per_bar)
    order = sorted(range(len(cues)), key=lambda i: (cues[i].fixture_id, cues[i].t0_ms))
    out: list[FixtureSegment] = list(cues)
    heads: dict[str, _HeadShape] = {}
    unavailable: list[str] = []
    for fixture_id in sorted({cue.fixture_id for cue in cues}):
        own = [i for i in order if cues[i].fixture_id == fixture_id]
        profile = profiles[fixture_id]
        axis = profile.axes.get("dimmer")
        if axis is None:
            unavailable.append(fixture_id)
            continue
        grid = _Grid.of(phase_map, origin_ms, end_ms, period, axis.latency_ms or 0)
        shaped, heads[fixture_id] = _shape_head(
            [cues[i] for i in own], shape, profile, axis, grid, period
        )
        for i, cue in zip(own, shaped, strict=True):
            out[i] = cue
    applied: dict[str, list[str]] = {}
    for fixture_id, head in sorted(heads.items()):
        for name in sorted(head.shapes):
            applied.setdefault(name, []).append(fixture_id)
    record: dict[str, Any] = {
        "period_beats": period,
        "decay_beats": min(ACCENT.decay_beats, period),
        "floor_gain": shape.floor_gain,
        "peak_gain": shape.peak_gain,
        "full_floor": shape.full_floor,
        "full_peak": shape.full_peak,
        "headroom_below": HEADROOM_BELOW,
        "applied": applied,
    }
    degraded = {f: round(h.scale, 4) for f, h in sorted(heads.items()) if h.scale < 1}
    if degraded:
        record["degraded"] = degraded
    lead = {f: h.lead_ms for f, h in sorted(heads.items()) if h.lead_ms}
    if lead:
        record["lead_ms"] = lead
    if unavailable:
        record["unavailable"] = unavailable
    return out, record


def describe_intensity(record: Mapping[str, Any]) -> str:
    """A section's intensity trace entry (`section_looks[].intensity`) as one line."""
    said = f"intensity {record['asked'] or 'as authored'}"
    if "focal_role" in record:
        said += f" ({record['focal_role']} in the show: {record['effective'] or 'as authored'})"
    shape = record.get("shape")
    if shape is None:
        return said + ": plays the template's own level"
    floor = f"{1 + shape['floor_gain']:g}"
    peak = f"{1 + shape['floor_gain'] + shape['peak_gain']:g}"
    names = {
        "headroom_pulse": f"the authored level x{floor} rising to x{peak} on the accent",
        "authored_pulse_accent": f"the template's own pulse x{floor} rising to x{peak} on "
        "the accent",
        "dip_and_return": f"{shape['full_peak']:.0%} of the authored level on the accent, "
        f"easing to {shape['full_floor']:.0%} of it between",
    }
    parts = [f"{names[label]} on {', '.join(heads)}" for label, heads in shape["applied"].items()]
    parts += [
        f"{fixture_id}'s dimmer is too slow for the full shape: scaled to {scale:.0%}"
        for fixture_id, scale in shape.get("degraded", {}).items()
    ]
    if shape.get("unavailable"):
        parts.append(f"{', '.join(shape['unavailable'])} play their own level (no dimmer axis)")
    every = "every beat" if shape["period_beats"] == 1 else f"every {shape['period_beats']} beats"
    return f"{said}: a pulse on the beat {every}: " + "; ".join(parts or ["no lit frame"])
