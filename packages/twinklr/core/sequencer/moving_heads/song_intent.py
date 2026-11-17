"""The planner's section colour and gobo, resolved on a rig; and what a rig can show.

The planner names categories; deterministic code resolves them (song-intent rendering
W3/W4):

- `requested_color`: a planned colour as one `#RRGGBB`: an explicit colour preset's
  canonical value, or a palette role's stop of the section's macro palette
  (`palette_role_color`; a role the palette has no stop for is not available there),
  or, with no macro palette, the fixed role table.
- `HeadWheels`: one head's offered wheel states: tagged (`hex`, `pattern`) on a wheel
  whose every state has a known settle, so the transaction pass can time a turn to them
  and back in the dark.
- `RigOffer`: what the rig can show, computed by the pre-planning gate and shown to the
  planner: each colour, each gobo pattern, each strobe speed, whether a dimmer hit is
  possible, how long a wheel change takes, and per template its dark phases and the
  states its overlay masks cannot turn to in time.
- `resolve_section_look`: per head, the wheel states that play a section's colour and
  gobo. The renderer and the plan repair (`agents/.../rig_repair.py`) use the same
  resolution, so what the planner is told, what repair keeps and what plays agree.

A head plays a colour when its nearest offered colour state (`nearest_tagged_color`) is
not a `hue_mismatch`; it keeps its authored colour otherwise, and a head without a
colour wheel always does. Gobo: the state tagged with the pattern (`tagged_gobo`).

This module imports nothing from the planner package at run time (the plan's values are
read as strings), so either side can import it first.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
import math
from typing import TYPE_CHECKING, Any, Literal, Protocol, get_args

from pydantic import BaseModel, ConfigDict

from twinklr.core.config.fixtures.capabilities import FixtureCapabilities, StrobeSpeed
from twinklr.core.config.fixtures.state_tags import (
    NEUTRAL_CHROMA,
    ColorFit,
    nearest_tagged_color,
    oklch,
    strobe_state,
    tagged_gobo,
)
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.moving_heads.intensity import describe_intensity
from twinklr.core.sequencer.moving_heads.libraries.color import (
    COLOR_PRESET_HEX,
    ColorPreset,
    canonical_hex,
)
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern
from twinklr.core.sequencer.vocabulary.visual import PaletteRole

if TYPE_CHECKING:
    from twinklr.core.config.fixtures import FixtureGroup
    from twinklr.core.sequencer.planning import MacroPlan
    from twinklr.core.sequencer.timing.beat_grid import BeatGrid

RENDERED_INTENT_FIELDS = frozenset({"intensity", "color", "gobo", "events", "moment_cues"})
"""The section song-intent fields (`PlanSection.set_intent_fields`) the renderer plays:
colour and gobo here, intensity in `intensity.py`, events and the lyric cues they land on
in `events.py`."""

FIXED_ROLE_COLORS: dict[PaletteRole, ColorPreset] = {
    PaletteRole.PRIMARY: ColorPreset.RED,
    PaletteRole.ACCENT: ColorPreset.MAGENTA,
    PaletteRole.WARM: ColorPreset.AMBER,
    PaletteRole.COOL: ColorPreset.CYAN,
    PaletteRole.NEUTRAL: ColorPreset.WHITE,
}
"""A palette role's colour where the section has no macro palette (`twinklr run` without
a macro plan, the deterministic selector): the deleted renderer's fixed role table
(`pipeline.py:146-157` at tag `mh-last-with-legacy-renderer`). Never used where a macro
palette exists: that palette is the song's."""

WARM_HUE = 55.0
"""OKLCh hue (degrees) a WARM role's stop is nearest: orange, between red (29°) and
amber (68°). Chosen, not measured."""
COOL_HUE = 230.0
"""OKLCh hue (degrees) a COOL role's stop is nearest: between cyan (195°) and blue
(264°). Chosen, not measured."""
ROLE_HUE_RANGE = 90.0
"""A WARM or COOL stop lies within this many degrees of its reference hue; a palette
with none has no such role."""

PALETTE_PREFIX = "PALETTE_"


class PlannedLook(Protocol):
    """What the resolver reads of a planned section (`PlanSection`): its id, and its
    colour and gobo as their values (None for `as_authored`)."""

    @property
    def section_id(self) -> str: ...

    @property
    def color(self) -> str | None: ...

    @property
    def gobo(self) -> str | None: ...


def palette_role(color: str) -> PaletteRole | None:
    """The palette role a planned colour (`PALETTE_<ROLE>` or a preset name) names."""
    if not color.startswith(PALETTE_PREFIX):
        return None
    return PaletteRole(color[len(PALETTE_PREFIX) :])


class SectionPalette(BaseModel):
    """The macro palette a section's palette roles take their colours from."""

    palette_id: str
    stops: tuple[str, ...]
    """Its stops as uppercase `#RRGGBB` (alpha dropped), in the palette's order."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def section_palettes(macro_plan: MacroPlan | None) -> dict[str, SectionPalette]:
    """Each macro section's palette (`MacroPlan.palette_for_section`), by section id; empty
    without a macro plan. The moving-head plan's section ids are the same song section
    ids."""
    from twinklr.core.sequencer.theming.catalog import get_palette

    if macro_plan is None:
        return {}
    palettes: dict[str, SectionPalette] = {}
    for section in macro_plan.sections:
        section_id = section.section.section_id
        palette_id = macro_plan.palette_for_section(section_id).palette_id
        stops = tuple(stop.hex[:7].upper() for stop in get_palette(palette_id).stops)
        palettes[section_id] = SectionPalette(palette_id=palette_id, stops=stops)
    return palettes


def palette_role_color(role: PaletteRole, stops: Sequence[str]) -> int | None:
    """The index of the stop that plays `role`, or None when the palette has no stop that
    fits it:

    - PRIMARY: the first stop; ACCENT: the second (the first in a one-stop palette);
    - WARM / COOL: among stops with a hue (OKLCh chroma at least `NEUTRAL_CHROMA`) within
      `ROLE_HUE_RANGE` of `WARM_HUE` / `COOL_HUE`, the nearest;
    - NEUTRAL: among stops below `NEUTRAL_CHROMA` (a white), the least saturated.

    Ties go to the earlier stop."""
    if role is PaletteRole.PRIMARY:
        return 0
    if role is PaletteRole.ACCENT:
        return 1 if len(stops) > 1 else 0
    colours = [oklch(stop) for stop in stops]
    if role is PaletteRole.NEUTRAL:
        whites = [index for index, colour in enumerate(colours) if colour[1] < NEUTRAL_CHROMA]
        return min(whites, key=lambda index: (colours[index][1], index), default=None)
    target = WARM_HUE if role is PaletteRole.WARM else COOL_HUE

    def away(index: int) -> float:
        turn = abs(colours[index][2] - target) % 360
        return min(turn, 360 - turn)

    fitting = [
        index
        for index, colour in enumerate(colours)
        if colour[1] >= NEUTRAL_CHROMA and away(index) <= ROLE_HUE_RANGE
    ]
    return min(fitting, key=lambda index: (away(index), index), default=None)


@dataclass(frozen=True)
class RequestedColor:
    """A planned colour as one colour, and where it came from."""

    hex: str
    source: str
    """`explicit`, `palette '<id>' stop <n>` (1-based), `fixed table (...)`, or, for a role
    the palette has no stop for, `palette '<id>' has no <role> stop: PRIMARY's stop 1`."""
    role_missing: bool = False
    """The palette role is not in the section's palette; PRIMARY's stop stands in (the
    plan repair turns such a choice into `PALETTE_PRIMARY` and records it)."""


def requested_color(color: str, palette: SectionPalette | None) -> RequestedColor:
    """The colour `color` (a `PlanColor` value) asks for in a section with `palette`
    (None without one)."""
    role = palette_role(color)
    if role is None:
        return RequestedColor(canonical_hex(color), "explicit")
    if palette is not None:
        index = palette_role_color(role, palette.stops)
        if index is not None:
            return RequestedColor(
                palette.stops[index], f"palette {palette.palette_id!r} stop {index + 1}"
            )
        return RequestedColor(
            palette.stops[0],
            f"palette {palette.palette_id!r} has no {role.value} stop: PRIMARY's stop 1",
            role_missing=True,
        )
    fixed = FIXED_ROLE_COLORS[role]
    return RequestedColor(
        COLOR_PRESET_HEX[fixed], f"fixed table ({fixed.value}: no macro palette for this section)"
    )


# --- What a head and a rig can show --------------------------------------------------


class HeadWheels(BaseModel):
    """One head's offered wheel states, by state name: tagged, on a wheel whose every
    state has a known settle (a turn to a tagged state, and back to whatever state a
    template authors, must both be timeable in the dark)."""

    fixture_id: str
    color_wheel: bool
    gobo_wheel: bool
    colors: dict[str, str]
    """Offered colour states and their `hex`."""
    gobos: dict[str, str]
    """Offered gobo states and their `pattern`."""
    unsettled: dict[str, tuple[str, ...]] = {}
    """Per wheel (`color`, `gobo`) that has tags, the states without a known settle that
    keep it from being offered; left out when there are none."""
    change_ms: int | None = None
    """This head's longest wheel change into any of its offered states
    (`wheel_change_ms`); None when it offers none or a term is unknown."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def from_profile(cls, fixture_id: str, profile: FixtureCapabilities) -> HeadWheels:
        color, gobo = profile.discrete.get("color"), profile.discrete.get("gobo")
        colors = {
            name: state.hex
            for name, state in sorted((color.states if color else {}).items())
            if state.hex is not None
        }
        gobos = {
            name: state.pattern.value
            for name, state in sorted((gobo.states if gobo else {}).items())
            if state.pattern is not None
        }
        unsettled: dict[str, tuple[str, ...]] = {}
        for channel, wheel, tagged in (("color", color, colors), ("gobo", gobo, gobos)):
            missing = tuple(
                sorted(n for n, s in (wheel.states if wheel else {}).items() if s.settle_ms is None)
            )
            if tagged and missing:
                unsettled[channel] = missing
        offered = {
            "color": {} if "color" in unsettled else colors,
            "gobo": {} if "gobo" in unsettled else gobos,
        }
        changes = [
            wheel_change_ms(profile, settle)
            for channel, wheel in (("color", color), ("gobo", gobo))
            for name in offered[channel]
            if wheel is not None and (settle := wheel.states[name].settle_ms) is not None
        ]
        return cls(
            fixture_id=fixture_id,
            color_wheel=color is not None,
            gobo_wheel=gobo is not None,
            colors=offered["color"],
            gobos=offered["gobo"],
            unsettled=unsettled,
            change_ms=None
            if not changes or None in changes
            else max(c for c in changes if c is not None),
        )

    def without(self, excluded: Mapping[str, Collection[str]]) -> HeadWheels:
        """This head with the states `excluded` (by wheel) left out of its offer."""
        return self.model_copy(
            update={
                "colors": {
                    n: c for n, c in self.colors.items() if n not in excluded.get("color", ())
                },
                "gobos": {n: p for n, p in self.gobos.items() if n not in excluded.get("gobo", ())},
            }
        )


OfferStatus = Literal["faithful", "approximate", "partial", "unavailable"]
"""How a rig shows a colour: every colour-wheel head exactly or closely (`faithful`);
every one, some only approximately (`approximate`); some of them, the rest keeping their
authored colour (`partial`); none (`unavailable`)."""

Availability = Literal["all", "some", "none"]


class HeadColor(BaseModel):
    """The state a head plays a colour with."""

    state: str
    hex: str
    fit: ColorFit

    model_config = ConfigDict(extra="forbid", frozen=True)


class ColorOffer(BaseModel):
    """How a rig shows one colour."""

    hex: str
    status: OfferStatus
    heads: dict[str, HeadColor]
    """The heads that play it, by fixture id."""
    missing: tuple[str, ...]
    """The colour-wheel heads that cannot (they keep their authored colour)."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class StateOffer(BaseModel):
    """Which heads with the channel have a state for one gobo pattern or strobe speed."""

    available: Availability
    states: dict[str, str]
    """The heads that have one, and its state, by fixture id."""
    missing: tuple[str, ...]
    """The heads with the channel that have none."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def color_offer(heads: Sequence[HeadWheels], color: str) -> ColorOffer:
    """How the heads show `color` (`#RRGGBB` or a preset name): each colour-wheel head's
    nearest offered state (`nearest_tagged_color`), unless it is a `hue_mismatch`.

    Raises:
        ValueError: If `color` is not a colour.
    """
    wanted = canonical_hex(color)
    shown: dict[str, HeadColor] = {}
    missing: list[str] = []
    for head in heads:
        if not head.color_wheel:
            continue
        match = nearest_tagged_color(head.colors, wanted)
        if match is None or match.fit == "hue_mismatch":
            missing.append(head.fixture_id)
        else:
            shown[head.fixture_id] = HeadColor(state=match.state, hex=match.hex, fit=match.fit)
    status: OfferStatus = (
        "unavailable"
        if not shown
        else "partial"
        if missing
        else "faithful"
        if all(head.fit in ("exact", "close") for head in shown.values())
        else "approximate"
    )
    return ColorOffer(hex=wanted, status=status, heads=shown, missing=tuple(missing))


def gobo_offer(heads: Sequence[HeadWheels], pattern: GoboPattern | str) -> StateOffer:
    """Which gobo-wheel heads have an offered state showing `pattern` (`tagged_gobo`)."""
    found = {h.fixture_id: tagged_gobo(h.gobos, pattern) for h in heads if h.gobo_wheel}
    return _state_offer(found)


def _state_offer(found: Mapping[str, str | None]) -> StateOffer:
    states = {fixture_id: state for fixture_id, state in found.items() if state is not None}
    missing = tuple(fixture_id for fixture_id, state in found.items() if state is None)
    available: Availability = "none" if not states else "some" if missing else "all"
    return StateOffer(available=available, states=states, missing=missing)


def frames_ms(ms: float) -> int:
    """`ms` rounded up to the frame grid."""
    return int(math.ceil(ms / EFFECT_GRID_MS) * EFFECT_GRID_MS)


def darkness_ms(profile: FixtureCapabilities) -> int | None:
    """How long after darkness is commanded the head is optically dark: close latency,
    plus the slowest extinguishing shutter settle where only the shutter extinguishes.
    None when a term is unknown."""
    visibility = profile.visibility
    if visibility.close_latency_ms is None:
        return None
    dark = visibility.close_latency_ms
    if not visibility.dimmer_zero_extinguishes:
        shutter = profile.discrete.get("shutter")
        settles = [
            None if shutter is None else shutter.states[name].settle_ms
            for name in visibility.extinguishing_shutter_states
        ]
        if not settles or None in settles:
            return None
        dark += max(settle for settle in settles if settle is not None)
    return dark


STROBE_FLASHES_PER_BEAT = {"strobe_slow": 2, "strobe_medium": 4, "strobe_fast": 8}
"""Proposed (W6, `events`). Flashes per beat of the square-wave strobe: eighths, sixteenths and
thirty-seconds. A rate the darkness path cannot follow halves until it fits (down to one
flash a beat)."""

PULSE_PERIODS_BEATS = (1, 2, 4)
"""Proposed (W6, `events`). The pulse's period, in beats: lit for the first half, dark for the
second; the first that the darkness path can follow plays."""


def flash_widths(profile: FixtureCapabilities) -> tuple[str, int, int] | None:
    """How a head flashes (its darkness path: `dimmer` or `shutter`) and the shortest
    dark and lit phases it can follow, each on the frame grid: one frame, or the dimmer's
    full swing at its declared speed; through the shutter, the close latency plus the
    closed state's settle and the open latency plus the open state's settle. None when
    it has no darkness to flash with or a term is unknown."""
    visibility = profile.visibility
    dimmer = profile.axes.get("dimmer")
    if visibility.dimmer_zero_extinguishes and dimmer is not None:
        swing = (
            EFFECT_GRID_MS
            if dimmer.travel_speed_per_s is None
            else frames_ms(1000 / dimmer.travel_speed_per_s)
        )
        width = max(EFFECT_GRID_MS, swing)
        return "dimmer", width, width
    shutter = profile.discrete.get("shutter")
    if (
        shutter is None
        or shutter.closed_state is None
        or shutter.closed_state not in visibility.extinguishing_shutter_states
    ):
        return None
    opened = shutter.open_state or shutter.default_state
    close, open_ = visibility.close_latency_ms, visibility.open_latency_ms
    closing, opening = (
        shutter.states[shutter.closed_state].settle_ms,
        shutter.states[opened].settle_ms,
    )
    if None in (close, open_, closing, opening):
        return None
    assert close is not None and open_ is not None and closing is not None and opening is not None
    return (
        "shutter",
        max(EFFECT_GRID_MS, frames_ms(close + closing)),
        max(EFFECT_GRID_MS, frames_ms(open_ + opening)),
    )


WHEEL_LATE_BEATS = 1.0
"""How late, in beats after its beat, a colour or gobo event that cannot dip before its
beat may still be revealed (turned in a dark window of the template); later, it does not
play (`events._turn`; the plan repair predicts it, `rig_repair`). Proposed (W7 fix
round)."""


def dip_fits(added_ms: float, beat_ms: float) -> bool:
    """Whether a wheel change's dark lead adds at most half the beat before its reveal: the
    one test the render (`events._turn`, the darkness the dip adds) and the plan repair
    (each head's wheel change time) apply to a colour or gobo event."""
    return added_ms <= beat_ms / 2


def can_darken(profile: FixtureCapabilities) -> bool:
    """Whether a head can be commanded dark on its cue's path: its dimmer's zero
    extinguishes, or its closed shutter state does."""
    visibility = profile.visibility
    if visibility.dimmer_zero_extinguishes and "dimmer" in profile.axes:
        return True
    shutter = profile.discrete.get("shutter")
    return (
        shutter is not None
        and shutter.closed_state is not None
        and shutter.closed_state in visibility.extinguishing_shutter_states
    )


def strobe_flashes(action: str, beat_ms: float, widest_ms: int) -> int | None:
    """The flashes per beat a strobe plays where the darkness path follows phases of
    `widest_ms`: the asked rate (`STROBE_FLASHES_PER_BEAT`), halved until a half period of
    the beat fits, down to one; None when even that does not."""
    asked = STROBE_FLASHES_PER_BEAT[action]
    rates = [asked >> i for i in range(asked.bit_length())]
    return next((n for n in rates if beat_ms / (2 * n) >= widest_ms), None)


def pulse_period(beat_ms: float, widest_ms: int) -> int | None:
    """The pulse's period in beats (`PULSE_PERIODS_BEATS`) the darkness path can follow;
    None when none."""
    return next((p for p in PULSE_PERIODS_BEATS if beat_ms * p / 2 >= widest_ms), None)


def wheel_change_ms(profile: FixtureCapabilities, settle_ms: int) -> int | None:
    """The time a wheel change into a state with `settle_ms` needs from a lit head: its
    darkness (`darkness_ms`), then the turn and settle (at least one frame), each rounded
    up to the frame grid, as the transaction pass times them. None when a term is
    unknown."""
    dark = darkness_ms(profile)
    if dark is None:
        return None
    return frames_ms(dark) + frames_ms(max(settle_ms, EFFECT_GRID_MS))


class DarkPhases(BaseModel):
    """When a template variant's heads are dark inside one cycle (the gate's bar-1
    compile on this song): the gaps between its cues (visibility envelopes, overlay
    masks, steps that leave time between them) and the frames its cues command dark.
    The section's entry dip is apart (`TemplateAdmission.entry_dips`)."""

    cycle_beats: float
    heads: dict[str, tuple[tuple[float, float], ...]]
    """Per fixture, `[start, end)` in beats from the cycle's start, in time order."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def first_window(self, fixture_id: str, beats: float) -> float | None:
        """Where, in beats from the cycle start, the head's first dark window of at least
        `beats` begins; None when it has none."""
        windows = self.heads.get(fixture_id, ())
        return next((start for start, end in windows if end - start >= beats), None)


class TemplateOffer(BaseModel):
    """What one template adds to the rig's offer."""

    variants: dict[str, DarkPhases]
    """Dark phases per admitted variant: `base`, or the preset id."""
    excluded: dict[str, dict[str, tuple[str, ...]]] = {}
    """Per fixture and wheel, offered states this template cannot hold: its overlay masks
    are too short to turn to them and back (left out when there are none)."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RigOffer(BaseModel):
    """What a rig can show of the planner's song intent (the pre-planning gate's offer).

    Mixed rigs: a colour or gobo plays on every head that can show it; a head that
    cannot, or that has no such wheel, keeps its authored look, and the offer names it.
    """

    heads: tuple[HeadWheels, ...]
    gobos: dict[str, StateOffer]
    """Each `GoboPattern`, over the heads with a gobo wheel."""
    strobes: dict[str, StateOffer]
    """Each strobe speed, over the heads with a shutter: the shutter state tagged with it."""
    hit: Availability
    """The heads with a dimmer axis, which a hit (raising the dimmer on lit frames) needs."""
    dark: Availability = "all"
    """The heads that can be commanded dark (a zero dimmer that extinguishes, or a closed
    shutter state that does), which `closed`, strobe and `pulse` events need."""
    flash_ms: int | None = None
    """The longest of the shortest dark and lit phases any head's darkness path can follow
    (`flash_widths`), which bounds a square-wave strobe or pulse; None when no head can
    flash."""
    wheel_change_ms: int | None
    """The longest wheel change of any head into any offered state (`wheel_change_ms`):
    dark, turn and settle. None when no state is offered, or a head's is unknown."""
    beat_ms: float | None
    """The song's median beat, for `wheel_change_beats`; None without two beats."""
    templates: dict[str, TemplateOffer]
    """Per admitted template id, its dark phases and the states it cannot hold (the gate
    fills it; empty for an offer made without one)."""
    dark_entries: dict[str, dict[str, tuple[str, ...]]] = {}
    """Per admitted template id and admitted predecessor template id, the heads that
    always enter it dark after that template (the gate's check, on every pair of their
    admitted variants, from each bar of the predecessor's cycle): a wheel change there
    rides the entry and needs no dip (empty without a gate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @property
    def wheel_change_beats(self) -> float | None:
        """`wheel_change_ms` in beats at the song's median beat."""
        if self.wheel_change_ms is None or not self.beat_ms:
            return None
        return self.wheel_change_ms / self.beat_ms

    @property
    def dip_fits(self) -> bool:
        """Whether a wheel change fits half the song's median beat, so a change at a
        boundary the heads play lit through can dip dark just before it."""
        return (
            self.wheel_change_ms is not None
            and self.beat_ms is not None
            and self.wheel_change_ms <= self.beat_ms / 2
        )

    def for_templates(self, template_ids: Collection[str]) -> RigOffer:
        """This offer with each head's states that any of `template_ids` cannot hold
        left out."""
        excluded: dict[str, dict[str, set[str]]] = {}
        for template_id in template_ids:
            template = self.templates.get(template_id)
            for fixture_id, wheels in (template.excluded if template else {}).items():
                for wheel, states in wheels.items():
                    excluded.setdefault(fixture_id, {}).setdefault(wheel, set()).update(states)
        if not excluded:
            return self
        return self.model_copy(
            update={"heads": tuple(h.without(excluded.get(h.fixture_id, {})) for h in self.heads)}
        )

    def color(self, color: str) -> ColorOffer:
        """`color_offer` on this rig."""
        return color_offer(self.heads, color)

    def gobo(self, pattern: GoboPattern | str) -> StateOffer:
        """Which heads show a gobo pattern."""
        return gobo_offer(self.heads, pattern)

    def preset_colors(self) -> dict[str, ColorOffer]:
        """Every colour preset the planner can name, by name, on this rig."""
        return {preset.value: self.color(preset.value) for preset in ColorPreset}

    def without(self, wheel: Literal["color", "gobo"]) -> tuple[str, ...]:
        """The heads that have no such wheel."""
        attribute = "color_wheel" if wheel == "color" else "gobo_wheel"
        return tuple(h.fixture_id for h in self.heads if not getattr(h, attribute))

    def offers_colors(self) -> bool:
        """Whether any head offers a colour state."""
        return any(head.colors for head in self.heads)


def rig_offer(
    fixture_group: FixtureGroup,
    beat_grid: BeatGrid,
    templates: Mapping[str, TemplateOffer] | None = None,
    dark_entries: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
) -> RigOffer:
    """The rig's offer for one song (`RigOffer`); `templates` and `dark_entries` from the
    gate."""
    profiles = {
        fixture.fixture_id: fixture.config.physical_profile
        for fixture in fixture_group.expand_fixtures()
        if fixture.config.physical_profile is not None
    }
    heads = tuple(HeadWheels.from_profile(f, p) for f, p in profiles.items())
    strobes = {
        speed: _state_offer(
            {f: strobe_state(p, speed) for f, p in profiles.items() if "shutter" in p.discrete}
        )
        for speed in get_args(StrobeSpeed)
    }
    dimmers = [f for f, p in profiles.items() if "dimmer" in p.axes]
    darkens = [f for f, p in profiles.items() if can_darken(p)]
    widths = [w for p in profiles.values() if (w := flash_widths(p)) is not None]
    changes: list[int | None] = []
    for head in heads:
        profile = profiles[head.fixture_id]
        wheels: tuple[tuple[Literal["color", "gobo"], dict[str, str]], ...] = (
            ("color", head.colors),
            ("gobo", head.gobos),
        )
        for channel, states in wheels:
            for name in states:
                settle = profile.discrete[channel].states[name].settle_ms
                assert settle is not None  # offered states have one
                changes.append(wheel_change_ms(profile, settle))
    intervals = sorted(b - a for a, b in pairwise(beat_grid.beat_boundaries))
    return RigOffer(
        heads=heads,
        gobos={pattern.value: gobo_offer(heads, pattern) for pattern in GoboPattern},
        strobes=strobes,
        hit="none" if not dimmers else "all" if len(dimmers) == len(profiles) else "some",
        dark="none" if not darkens else "all" if len(darkens) == len(profiles) else "some",
        flash_ms=max((max(dark, lit) for _, dark, lit in widths), default=None),
        wheel_change_ms=None
        if not changes or None in changes
        else max(change for change in changes if change is not None),
        beat_ms=intervals[len(intervals) // 2] if intervals else None,
        templates=dict(templates or {}),
        dark_entries={
            t: {before: tuple(heads) for before, heads in after.items()}
            for t, after in (dark_entries or {}).items()
        },
    )


# --- A section's look on the rig ------------------------------------------------------


@dataclass(frozen=True)
class SectionLook:
    """What a section's colour and gobo play on each head (`resolve_section_look`)."""

    section_id: str
    color: str | None
    requested: RequestedColor | None
    color_offer: ColorOffer | None
    gobo: str | None
    gobo_offer: StateOffer | None

    @property
    def states(self) -> dict[str, dict[ChannelName, str]]:
        """Per head, the wheel states the section holds in place of the authored ones."""
        held: dict[str, dict[ChannelName, str]] = {}
        if self.color_offer is not None:
            for fixture_id, head in self.color_offer.heads.items():
                held.setdefault(fixture_id, {})[ChannelName.COLOR] = head.state
        if self.gobo_offer is not None:
            for fixture_id, state in self.gobo_offer.states.items():
                held.setdefault(fixture_id, {})[ChannelName.GOBO] = state
        return held

    def record(self) -> dict[str, Any]:
        """The trace's entry: what was asked, from where, and what each head plays
        (`describe_look` reads it). The renderer moves a head out of `heads` where it
        does not play the state from the section's start (`deferred`, `kept_previous`,
        `kept_authored_unplayable`)."""
        record: dict[str, Any] = {"section_id": self.section_id}
        if self.color is not None and self.requested is not None and self.color_offer:
            record["color"] = {
                "asked": str(self.color),
                "hex": self.requested.hex,
                "source": self.requested.source,
                "status": self.color_offer.status,
                "heads": {
                    fixture_id: head.model_dump(mode="json")
                    for fixture_id, head in self.color_offer.heads.items()
                },
                "kept_authored": list(self.color_offer.missing),
            }
        if self.gobo is not None and self.gobo_offer is not None:
            record["gobo"] = {
                "asked": str(self.gobo),
                "available": self.gobo_offer.available,
                "heads": {
                    fixture_id: {"state": state}
                    for fixture_id, state in self.gobo_offer.states.items()
                },
                "kept_authored": list(self.gobo_offer.missing),
            }
        return record


def resolve_section_look(
    section: PlannedLook, heads: Sequence[HeadWheels], palette: SectionPalette | None
) -> SectionLook:
    """The wheel states that play `section`'s colour and gobo on each head: the colour
    through `requested_color` (with `palette`, the section's macro palette, or None) and
    `color_offer`, the gobo through `gobo_offer`. A head that cannot show one keeps its
    authored state; an as-authored colour or gobo resolves to nothing."""
    color = None if section.color is None else str(section.color)
    gobo = None if section.gobo is None else str(section.gobo)
    requested = None if color is None else requested_color(color, palette)
    return SectionLook(
        section_id=section.section_id,
        color=color,
        requested=requested,
        color_offer=None if requested is None else color_offer(heads, requested.hex),
        gobo=gobo,
        gobo_offer=None if gobo is None else gobo_offer(heads, gobo),
    )


def unshown_color_reason(offer: RigOffer) -> str:
    """Why no head shows a colour."""
    if not any(head.color_wheel for head in offer.heads):
        return "this rig has no colour wheel"
    if not offer.offers_colors():
        return (
            "this rig's colour wheel offers no colour (no state carries a `hex` tag, or a "
            "state's `settle_ms` is unknown)"
        )
    return "no head's colour wheel shows anything like it"


def unshown_gobo_reason(offer: RigOffer) -> str:
    """Why no head shows a gobo pattern."""
    if not any(head.gobo_wheel for head in offer.heads):
        return "this rig has no gobo wheel"
    return "no head's gobo wheel offers a state tagged with this pattern"


def partial_reason(shown: Collection[str], missing: Sequence[str]) -> str:
    """Which heads play a choice and which keep their authored look."""
    return (
        f"plays on {', '.join(shown)}; {', '.join(missing)} cannot show it and keep their "
        "authored look"
    )


def is_late(window_start_ms: float, section_start_ms: float, section_end_ms: float) -> bool:
    """Whether a deferred wheel change waits too long: its dark window opens after half
    the section (a frame of tolerance for the frame grid). The render's trace and the plan
    repair use this one definition."""
    middle = section_start_ms + (section_end_ms - section_start_ms) / 2
    return window_start_ms > middle + EFFECT_GRID_MS


def excluded_reason(offer: RigOffer, template_ids: Collection[str], wheel: str) -> str | None:
    """Why a state the rig shows is not offered with these templates: the templates whose
    overlay masks are too short to turn to it and back (None when none excludes any)."""
    named = sorted(
        template_id
        for template_id in template_ids
        if any(
            wheels.get(wheel)
            for wheels in (
                offer.templates.get(template_id) or TemplateOffer(variants={})
            ).excluded.values()
        )
    )
    if not named:
        return None
    return (
        f"template {', '.join(repr(t) for t in named)} cannot turn the {wheel} wheel to it and "
        "back in time: its overlay masks are too short for that state's settle"
    )


def section_palette_for(
    palettes: Mapping[str, SectionPalette], section_id: str
) -> SectionPalette | None:
    """The palette of a section, or of the plan section a flattened part (`<id>|<part>`)
    belongs to."""
    return palettes.get(section_id.split("|")[0])


def round_beats(value: float | None) -> str:
    """A beat count for the prompt: one decimal, or `unknown`."""
    return "unknown" if value is None else f"{math.ceil(value * 10) / 10:g}"


# --- The offer as the planner reads it ------------------------------------------------


def _shown(offer: ColorOffer) -> str:
    """The wheel colours a colour plays as: one state name, or each with its heads."""
    by_state: dict[str, list[str]] = {}
    for fixture_id, head in offer.heads.items():
        by_state.setdefault(head.state, []).append(fixture_id)
    if len(by_state) == 1:
        return next(iter(by_state))
    return "; ".join(f"{state} on {', '.join(heads)}" for state, heads in by_state.items())


def offer_for_prompt(
    offer: RigOffer,
    palettes: Mapping[str, SectionPalette],
    section_ids: Sequence[str],
    half_beats: Sequence[float] | None = None,
) -> dict[str, Any]:
    """The offer as the planner prompt shows it: colours by how faithfully the rig shows
    them; each section's palette roles, the stop each takes and the wheel colour it lands
    on (a role the palette has no stop for marked missing, one landing on the same wheel
    colour as an earlier role marked so; the fixed role table where a section has no
    macro palette); gobos and strobe speeds by how many heads have them; whether a hit is
    possible; the wheel change time against half a beat; the templates with a dark phase
    long enough for a wheel change; and the states a template cannot hold. Sections
    that share a palette share one entry. With `half_beats` (half the beat before each
    section boundary), how many boundaries a dip fits before (`dip_boundaries`), since
    the render decides per boundary; without them, the median beat (`dip_fits`)."""
    colors: dict[str, list[dict[str, str]]] = {
        "faithful": [],
        "approximate": [],
        "partial": [],
        "unavailable": [],
    }
    for name, shown in offer.preset_colors().items():
        entry = {"color": name}
        if shown.heads:
            entry["shown"] = _shown(shown)
        if shown.missing:
            entry["kept"] = ", ".join(shown.missing)
        colors[shown.status].append(entry)
    sections: list[dict[str, Any]] = []
    by_palette: dict[SectionPalette | None, dict[str, Any]] = {}
    for section_id in section_ids:
        palette = palettes.get(section_id)
        if palette in by_palette:
            by_palette[palette]["section_ids"].append(section_id)
            continue
        roles = []
        seen: dict[str, str] = {}
        for role in PaletteRole:
            name = f"{PALETTE_PREFIX}{role.value}"
            asked = requested_color(name, palette)
            if asked.role_missing:
                roles.append({"role": name, "missing": True})
                continue
            shown = offer.color(asked.hex)
            wheel = _shown(shown) if shown.heads else ""
            roles.append(
                {
                    "role": name,
                    "missing": False,
                    "hex": asked.hex,
                    "status": shown.status,
                    "shown": wheel,
                    "same_as": seen.get(wheel, "") if wheel else "",
                }
            )
            if wheel:
                seen.setdefault(wheel, name)
        by_palette[palette] = {
            "section_ids": [section_id],
            "palette_id": None if palette is None else palette.palette_id,
            "roles": roles,
        }
        sections.append(by_palette[palette])

    def by_availability(states: Mapping[str, StateOffer]) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {"all": [], "some": [], "none": []}
        for name, state in states.items():
            heads = f" ({', '.join(state.states)})" if state.available == "some" else ""
            grouped[state.available].append(name + heads)
        return grouped

    windows = []
    if offer.wheel_change_ms is not None and offer.beat_ms:
        needed = offer.wheel_change_ms / offer.beat_ms
        for template_id, template in offer.templates.items():
            starts = [
                start
                for phases in template.variants.values()
                for fixture_id in phases.heads
                if (start := phases.first_window(fixture_id, needed)) is not None
            ]
            if starts:
                windows.append(f"{template_id} (from beat {round_beats(min(starts))} of its cycle)")
    exclusions = []
    for template_id, template in offer.templates.items():
        states = sorted(
            {state for wheels in template.excluded.values() for s in wheels.values() for state in s}
        )
        if states:
            exclusions.append({"template_id": template_id, "states": states})
    return {
        "colors": colors,
        "color_wheel": any(head.color_wheel for head in offer.heads),
        "colors_tagged": offer.offers_colors(),
        "no_color_wheel": list(offer.without("color")),
        "unsettled": sorted(
            {f"{h.fixture_id} {wheel}" for h in offer.heads for wheel in h.unsettled}
        ),
        "sections": sections,
        "gobos": by_availability(offer.gobos),
        "gobo_wheel": any(head.gobo_wheel for head in offer.heads),
        "gobos_tagged": any(head.gobos for head in offer.heads),
        "no_gobo_wheel": list(offer.without("gobo")),
        "strobes": by_availability(offer.strobes),
        "hit": offer.hit,
        "wheel_change_ms": offer.wheel_change_ms,
        "wheel_change_beats": round_beats(offer.wheel_change_beats),
        "half_beat_ms": None if offer.beat_ms is None else round(offer.beat_ms / 2),
        "dip_fits": offer.dip_fits,
        "dip_boundaries": None
        if offer.wheel_change_ms is None or half_beats is None
        else {
            "fit": sum(1 for half in half_beats if offer.wheel_change_ms <= half),
            "of": len(half_beats),
            "shortest_half_beat_ms": round(min(half_beats)) if half_beats else None,
        },
        "dark_windows": windows,
        "exclusions": exclusions,
        "events": _events_for_prompt(offer),
    }


def _events_for_prompt(offer: RigOffer) -> dict[str, Any]:
    """What `closed`/`open`, the strobes and `pulse` play on this rig at the song's median
    beat: each strobe's flashes per beat (the fixture's own where every head has a state
    tagged for it), the pulse's period, and whether the heads can go dark at all."""
    strobes = []
    for speed, asked in STROBE_FLASHES_PER_BEAT.items():
        tagged = offer.strobes.get(speed.removeprefix("strobe_"))
        plays = (
            None
            if offer.flash_ms is None or offer.beat_ms is None
            else strobe_flashes(speed, offer.beat_ms, offer.flash_ms)
        )
        strobes.append(
            {
                "action": speed,
                "asked": asked,
                "plays": plays,
                "tagged": "none" if tagged is None else tagged.available,
            }
        )
    return {
        "dark": offer.dark,
        "flash_ms": offer.flash_ms,
        # The fastest tempo at which the slowest wheel change fits half a beat (`dip_fits`).
        "wheel_max_bpm": None
        if not offer.wheel_change_ms
        else math.floor(60_000 / (2 * offer.wheel_change_ms)),
        "strobes": strobes,
        "pulse_beats": None
        if offer.flash_ms is None or offer.beat_ms is None
        else pulse_period(offer.beat_ms, offer.flash_ms),
    }


def describe_look(record: Mapping[str, Any]) -> list[str]:
    """A section's trace entry (`SectionLook.record`, as the renderer leaves it) as lines
    for a reader: what each asked colour and gobo plays on which heads from the
    section's start, where a head turns to it later or keeps the previous or authored
    state, each boundary's dark dip, what its intensity plays
    (`intensity.describe_intensity`) and what each event played (`events.describe_events`)."""
    lines = []
    for key, noun in (("color", "colour"), ("gobo", "gobo")):
        entry = record.get(key)
        if entry is None:
            continue
        by_state: dict[str, list[str]] = {}
        for fixture_id, head in entry["heads"].items():
            label = f"{head['state']} ({head['fit']})" if "fit" in head else head["state"]
            by_state.setdefault(label, []).append(fixture_id)
        parts = [f"{state} on {', '.join(heads)}" for state, heads in by_state.items()]
        parts += [
            f"{fixture_id} turns to {late['state']} at {late['from_ms']} ms"
            for fixture_id, late in entry.get("deferred", {}).items()
        ]
        parts += [
            f"{fixture_id} keeps the previous {noun} {state}"
            for fixture_id, state in entry.get("kept_previous", {}).items()
        ]
        parts += [
            f"{fixture_id} keeps its authored {noun} ({why})"
            for fixture_id, why in entry.get("kept_authored_unplayable", {}).items()
        ]
        kept = (
            f"; {', '.join(entry['kept_authored'])} keep their authored {noun}"
            if entry["kept_authored"]
            else ""
        )
        source = f" ({entry['hex']}, {entry['source']})" if key == "color" else ""
        lines.append(
            f"{noun} {entry['asked']}{source}: {'; '.join(parts) or 'no head shows it'}{kept}"
        )
    for boundary in record.get("boundaries", []):
        wheels = ", ".join(
            f"{wheel} {change['from']} → {change['to']}"
            for wheel, change in boundary["wheels"].items()
        )
        if "dark_dip" in boundary:
            dip = boundary["dark_dip"]
            what = (
                f"dark dip of {dip['added_ms']} ms before the section's first frame"
                if dip["added_ms"]
                else "turned in the darkness already there before the section"
            )
        elif "deferred" in boundary:
            what = f"turned in a dark window at {boundary['deferred']['turn_ms']} ms"
        else:
            what = f"kept the previous state ({boundary['kept_previous']['reason']})"
        lines.append(f"{boundary['fixture_id']} at {boundary['boundary_ms']} ms: {wheels}: {what}")
    if "intensity" in record:
        lines.append(describe_intensity(record["intensity"]))
    from twinklr.core.sequencer.moving_heads.events import describe_events

    lines += describe_events(record.get("events", []))
    return lines
