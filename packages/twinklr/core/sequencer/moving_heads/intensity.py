"""The planner's section intensity, played on the dimmer (song-intent rendering W5).

The planner names a category; this module turns it into dimmer levels on musical phase.
Everything that decides how intensity looks is in the table below (`SHAPES`, `ACCENT`,
`dramatic_period_beats`) and the curve (`accent`). The values are a first proposal for
the owner to judge on a render (W5 view), not measured or accepted looks.

- **Identity levels.** As authored (`None`), `SMOOTH`, `SLOW` and `FAST` play the
  template exactly as authored (the owner's 2026-11-12 ruling made SLOW and FAST equal
  SMOOTH; the revised plan made SMOOTH the identity).
- **`DRAMATIC` and `INTENSE`** shape each lit frame's authored level `a` with a
  beat-locked accent `e` (`accent`: 1 on the accent beat, easing to 0 over
  `ACCENT.decay_beats`, 0 until the next accent):
  - with headroom (`a` below the dimmer's top): `min(top, a * (1 + floor_gain +
    peak_gain * e))`. The floor rises and the accent lands on the beat, scaled by the
    authored level, so a template's own pulse stays readable under it (a headroom pulse
    on a held level, an accent on an authored pulse);
  - at full (`a` at the top, every catalog family today): a dip-and-return,
    `top * (1 - dip_depth * (1 - e))`: full on the beat, easing down to the floor
    `top * (1 - dip_depth)` between accents, back to full on the next. The one case
    where a frame plays below its authored level, and only where there is no headroom.
  A frame the template commands dark (dimmer zero, or an extinguishing shutter state) is
  never touched, and no lit frame goes to zero, so the dark frames are the template's.
- **Physical limits.** A head without a dimmer axis cannot pulse: it plays as authored,
  recorded. Where the dimmer axis declares `travel_speed_per_s`, a shape whose largest
  frame-to-frame step exceeds it is scaled down (accent and dip together) until it fits,
  recorded; where it declares `latency_ms`, the accent is commanded that much earlier, so
  the light lands on the beat.
- **Focal role (`twinklr show`).** `effective_intensity`: LEAD raises the section one
  step toward INTENSE, SUPPORT leaves the planner's choice, REST caps it at the identity.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
import math
from typing import Any

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
from twinklr.core.sequencer.timing.musical_phase import (
    MusicalPhaseMap,
    musical_phase_fraction,
    musical_time_at,
)

SHAPED_LEVELS = ("DRAMATIC", "INTENSE")
"""The intensities that shape the light; every other level plays as authored."""


@dataclass(frozen=True)
class IntensityShape:
    """One shaped level's values (`SHAPES`)."""

    floor_gain: float
    """With headroom: the floor rises to `a * (1 + floor_gain)`."""
    peak_gain: float
    """With headroom: the accent adds `a * peak_gain` on the beat."""
    dip_depth: float
    """At full: the level eases down to `top * (1 - dip_depth)` between accents."""


SHAPES: dict[str, IntensityShape] = {
    "DRAMATIC": IntensityShape(floor_gain=0.10, peak_gain=0.40, dip_depth=0.25),
    "INTENSE": IntensityShape(floor_gain=0.15, peak_gain=0.60, dip_depth=0.40),
}
"""Proposed (W5, 2026-11-17), for the owner to judge. INTENSE accents every beat and
drives harder than DRAMATIC: a higher floor and peak with headroom, a deeper dip at full.
The headroom floor gain stays below 0.25, so a template alternating 0.8 and 0.3 still
falls back from full within its 0.8 beat and its own shape reads under the accent."""


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


def period_beats(level: str, beats_per_bar: int) -> int:
    """The accent period of a shaped level, in beats."""
    return 1 if level == "INTENSE" else dramatic_period_beats(beats_per_bar)


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
    trajectory = held.physical
    return {t for t in times if state_at(trajectory, t) in extinguishing}


@dataclass
class _HeadShape:
    """What shaping did on one head over a section."""

    held: set[Fraction] | None = None
    """The authored lit levels with headroom (None until one is seen)."""
    full: bool = False
    scale: float = 1.0
    lead_ms: int = 0

    def labels(self) -> list[str]:
        labels = []
        if self.held is not None:
            labels.append("headroom_pulse" if len(self.held) == 1 else "authored_pulse_accent")
        if self.full:
            labels.append("dip_and_return")
        return labels


@dataclass(frozen=True)
class _Frame:
    """One lit frame of a cue: its authored level, accent and whether it is at full."""

    time_ms: int
    authored: Fraction | float
    accent: float
    full: bool


class _AccentTiming:
    """Where a head's accents fall: on every `period`-th beat from `origin_ms`, commanded
    `lead_ms` early. An accent starts on the first frame at or after its (led) beat, at
    1; the decay counts musical time from that frame."""

    def __init__(
        self, phase_map: MusicalPhaseMap, origin_ms: float, period: int, lead_ms: int
    ) -> None:
        self.phase_map = phase_map
        self.origin_ms = origin_ms
        self.period = period
        self.lead_ms = lead_ms
        self.starts: dict[Fraction, int] = {}

    def beats(self, time_ms: int) -> Fraction:
        """Beats from the origin at `time_ms`, led by the latency."""
        return musical_phase_fraction(
            self.phase_map,
            min(time_ms + self.lead_ms, self.phase_map.covered_end_ms),
            origin_ms=self.origin_ms,
            period_beats=1,
        )

    def accent_at(self, time_ms: int) -> float:
        now = self.beats(time_ms)
        beat = Fraction(now // self.period * self.period)
        if beat < 0:  # a frame before the section's first downbeat
            return accent(float(now % self.period), self.period)
        start = self.starts.get(beat)
        if start is None:
            beat_ms = musical_time_at(
                self.phase_map, beat, origin_ms=self.origin_ms, period_beats=1
            )
            start = math.ceil((beat_ms - self.lead_ms) / EFFECT_GRID_MS) * EFFECT_GRID_MS
            self.starts[beat] = start
        if start > time_ms:  # only where the lead is clamped at the covered end
            return accent(float(now - beat), self.period)
        return accent(float(now - self.beats(start)), self.period)


def _shaped(frame: _Frame, shape: IntensityShape, top: Fraction, scale: float) -> float:
    """A lit frame's level under `shape`, its accent and dip scaled by `scale`."""
    if frame.full:
        return float(top) * (1 - shape.dip_depth * scale * (1 - frame.accent))
    gain = 1 + shape.floor_gain + shape.peak_gain * scale * frame.accent
    return float(min(top, Fraction(frame.authored) * Fraction(gain)))


def _shape_head(
    cues: Sequence[FixtureSegment],
    shape: IntensityShape,
    period: int,
    profile: FixtureCapabilities,
    axis: AxisCapability,
    *,
    phase_map: MusicalPhaseMap,
    origin_ms: float,
) -> tuple[list[FixtureSegment], _HeadShape]:
    """One head's cues of a section under `shape` (`shape_section`)."""
    head = _HeadShape(lead_ms=axis.latency_ms or 0)
    top = Fraction(axis.operable_range[1])
    zero, full = axis.dmx_word(0), axis.dmx_word(top)
    timing = _AccentTiming(phase_map, origin_ms, period, head.lead_ms)
    lit: list[list[_Frame]] = []
    for cue in cues:
        dark = _shutter_dark(cue, profile)
        frames = []
        for time_ms, level in _dimmer_samples(cue, axis, profile).items():
            word = axis.dmx_word(level)
            if time_ms in dark or word == zero:
                continue
            frames.append(_Frame(time_ms, level, timing.accent_at(time_ms), word == full))
            if word == full:
                head.full = True
            else:
                head.held = (head.held or set()) | {Fraction(level)}
        lit.append(frames)
    if axis.travel_speed_per_s is not None:
        # The largest frame-to-frame step the shape adds to the template's own.
        allowed = axis.travel_speed_per_s * EFFECT_GRID_MS / 1000
        steepest = max(
            (
                abs(
                    (_shaped(b, shape, top, 1.0) - float(b.authored))
                    - (_shaped(a, shape, top, 1.0) - float(a.authored))
                )
                for frames in lit
                for a, b in pairwise(frames)
                if b.time_ms - a.time_ms == EFFECT_GRID_MS
            ),
            default=0.0,
        )
        if steepest > allowed:
            head.scale = allowed / steepest
    out = []
    for cue, frames in zip(cues, lit, strict=True):
        if not frames:
            out.append(cue)
            continue
        values = {t: float(level) for t, level in _dimmer_samples(cue, axis, profile).items()} | {
            frame.time_ms: _shaped(frame, shape, top, head.scale) for frame in frames
        }
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
    level: str,
    *,
    profiles: Mapping[str, FixtureCapabilities],
    phase_map: MusicalPhaseMap,
    origin_ms: float,
    beats_per_bar: int,
) -> tuple[list[FixtureSegment], dict[str, Any]]:
    """A section's compiled cues with `level` (DRAMATIC or INTENSE) played on the dimmer,
    and what it did, for the trace: the table's values, the shapes applied by head, and
    the heads scaled for a slow dimmer (`degraded`), led by their dimmer's latency
    (`lead_ms`) or without a dimmer axis (`unavailable`).

    The accent's phase counts beats from `origin_ms`, the section's first downbeat, so a
    DRAMATIC accent lands on the bar's strong beats. Only the dimmer of lit frames
    changes. The render applies it before its dark spans and boundary dips, which then
    command their darkness over it.
    """
    shape = SHAPES[level]
    period = period_beats(level, beats_per_bar)
    by_head: dict[str, list[FixtureSegment]] = {}
    for cue in cues:
        by_head.setdefault(cue.fixture_id, []).append(cue)
    out: list[FixtureSegment] = []
    heads: dict[str, _HeadShape] = {}
    unavailable: list[str] = []
    for fixture_id, own in by_head.items():
        profile = profiles[fixture_id]
        axis = profile.axes.get("dimmer")
        if axis is None:
            unavailable.append(fixture_id)
            out.extend(own)
            continue
        shaped, heads[fixture_id] = _shape_head(
            own, shape, period, profile, axis, phase_map=phase_map, origin_ms=origin_ms
        )
        out.extend(shaped)
    applied: dict[str, list[str]] = {}
    for fixture_id, head in sorted(heads.items()):
        for label in head.labels():
            applied.setdefault(label, []).append(fixture_id)
    record: dict[str, Any] = {
        "period_beats": period,
        "decay_beats": min(ACCENT.decay_beats, period),
        "floor_gain": shape.floor_gain,
        "peak_gain": shape.peak_gain,
        "dip_floor": round(1 - shape.dip_depth, 6),
        "applied": applied,
    }
    degraded = {f: round(h.scale, 4) for f, h in sorted(heads.items()) if h.scale < 1}
    if degraded:
        record["degraded"] = degraded
    lead = {f: h.lead_ms for f, h in sorted(heads.items()) if h.lead_ms}
    if lead:
        record["lead_ms"] = lead
    if unavailable:
        record["unavailable"] = sorted(unavailable)
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
        "dip_and_return": f"full on the accent, down to {shape['dip_floor']:.0%} between",
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
