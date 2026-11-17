"""The planner's section colour and gobo, resolved on a rig; and what a rig can show.

The planner names categories; deterministic code resolves them (song-intent rendering
W3/W4):

- `requested_color`: a planned colour as one `#RRGGBB`: an explicit colour preset's
  canonical value, or a palette role's stop of the section's macro palette
  (`palette_role_color`), or, with no macro palette, the fixed role table.
- `HeadWheels`: one head's offered wheel states: tagged (`hex`, `pattern`) and with a
  known settle, so the transaction pass can turn to them in the dark.
- `RigOffer`: what the rig can show, computed by the pre-planning gate and shown to the
  planner: each colour, each gobo pattern, each strobe speed, whether a dimmer hit is
  possible, and how long a wheel change takes.
- `resolve_section_look`: per head, the wheel states that play a section's colour and
  gobo. The renderer and the plan repair (`repair_rig_intent`) use the same resolution,
  so what the planner is told, what repair keeps and what plays agree.

A head plays a colour when its nearest offered colour state (`nearest_tagged_color`) is
not a `hue_mismatch`; it keeps its authored colour otherwise, and a head without a
colour wheel always does. Gobo: the state tagged with the pattern (`tagged_gobo`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
import math
from typing import TYPE_CHECKING, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict

from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    EventAction,
    PlanColor,
    PlanRepair,
    PlanSection,
    RepairAction,
)
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

RENDERED_INTENT_FIELDS = frozenset({"color", "gobo"})
"""The section song-intent fields (`PlanSection.set_intent_fields`) the renderer plays."""

FIXED_ROLE_COLORS: dict[PaletteRole, ColorPreset] = {
    PaletteRole.PRIMARY: ColorPreset.RED,
    PaletteRole.ACCENT: ColorPreset.MAGENTA,
    PaletteRole.WARM: ColorPreset.AMBER,
    PaletteRole.COOL: ColorPreset.CYAN,
    PaletteRole.NEUTRAL: ColorPreset.WHITE,
}
"""A palette role's colour where the section has no macro palette (`twinklr run` without
a macro plan, the deterministic selector): the deleted renderer's fixed role table
(`pipeline.py:146-157` at tag `mh-last-with-legacy-renderer`)."""

WARM_HUE = 55.0
"""OKLCh hue (degrees) a WARM role's stop is nearest: orange, between red (29°) and
amber (68°). Chosen, not measured."""
COOL_HUE = 230.0
"""OKLCh hue (degrees) a COOL role's stop is nearest: between cyan (195°) and blue
(264°). Chosen, not measured."""


def _role(color: PlanColor) -> PaletteRole | None:
    """The palette role a planned colour names, or None for a named colour."""
    prefix = "PALETTE_"
    return PaletteRole(color.value[len(prefix) :]) if color.value.startswith(prefix) else None


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
    """The index of the stop that plays `role`: PRIMARY the first, ACCENT the second (the
    first in a one-stop palette), NEUTRAL the least saturated (OKLCh chroma), WARM and
    COOL the stop with a hue (chroma at least `NEUTRAL_CHROMA`) nearest `WARM_HUE` /
    `COOL_HUE`. Ties go to the earlier stop. None for WARM or COOL in a palette of
    whites only."""
    if role is PaletteRole.PRIMARY:
        return 0
    if role is PaletteRole.ACCENT:
        return 1 if len(stops) > 1 else 0
    colours = [oklch(stop) for stop in stops]
    if role is PaletteRole.NEUTRAL:
        return min(range(len(stops)), key=lambda index: (colours[index][1], index))
    target = WARM_HUE if role is PaletteRole.WARM else COOL_HUE
    hued = [index for index, colour in enumerate(colours) if colour[1] >= NEUTRAL_CHROMA]

    def away(index: int) -> float:
        turn = abs(colours[index][2] - target) % 360
        return min(turn, 360 - turn)

    return min(hued, key=lambda index: (away(index), index), default=None)


@dataclass(frozen=True)
class RequestedColor:
    """A planned colour as one colour, and where it came from."""

    hex: str
    source: str
    """`explicit`, `palette '<id>' stop <n>` (1-based), or `fixed table` with the reason."""


def requested_color(color: PlanColor, palette: SectionPalette | None) -> RequestedColor:
    """The colour `color` asks for in a section with `palette` (None without one)."""
    role = _role(color)
    if role is None:
        return RequestedColor(canonical_hex(color.value), "explicit")
    if palette is not None:
        index = palette_role_color(role, palette.stops)
        if index is not None:
            return RequestedColor(
                palette.stops[index], f"palette {palette.palette_id!r} stop {index + 1}"
            )
        reason = f"palette {palette.palette_id!r} has no stop with a hue"
    else:
        reason = "no macro palette for this section"
    fixed = FIXED_ROLE_COLORS[role]
    return RequestedColor(COLOR_PRESET_HEX[fixed], f"fixed table ({fixed.value}: {reason})")


# --- What a head and a rig can show --------------------------------------------------


class HeadWheels(BaseModel):
    """One head's offered wheel states: tagged, and with a known settle (a wheel turn
    needs it to be timed in the dark), by state name."""

    fixture_id: str
    color_wheel: bool
    gobo_wheel: bool
    colors: dict[str, str]
    """Offered colour states and their `hex`."""
    gobos: dict[str, str]
    """Offered gobo states and their `pattern`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def from_profile(cls, fixture_id: str, profile: FixtureCapabilities) -> HeadWheels:
        color, gobo = profile.discrete.get("color"), profile.discrete.get("gobo")
        return cls(
            fixture_id=fixture_id,
            color_wheel=color is not None,
            gobo_wheel=gobo is not None,
            colors={
                name: state.hex
                for name, state in sorted((color.states if color else {}).items())
                if state.hex is not None and state.settle_ms is not None
            },
            gobos={
                name: state.pattern.value
                for name, state in sorted((gobo.states if gobo else {}).items())
                if state.pattern is not None and state.settle_ms is not None
            },
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


def wheel_change_ms(profile: FixtureCapabilities, settle_ms: int) -> int | None:
    """The time a wheel change into a state with `settle_ms` needs from a lit head: its
    darkness (close latency, plus the slowest extinguishing shutter settle where only the
    shutter extinguishes), then the turn and settle (at least one frame), each rounded up
    to the frame grid, as the transaction pass times them. None when a term is unknown."""
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

    def frames(ms: int) -> int:
        return -(-ms // EFFECT_GRID_MS) * EFFECT_GRID_MS

    return frames(dark) + frames(max(settle_ms, EFFECT_GRID_MS))


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
    wheel_change_ms: int | None
    """The longest wheel change of any head into any offered state (`wheel_change_ms`):
    dark, turn and settle. None when no state is offered, or a head's is unknown."""
    beat_ms: float | None
    """The song's median beat, for `wheel_change_beats`; None without two beats."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @property
    def wheel_change_beats(self) -> float | None:
        """`wheel_change_ms` in beats at the song's median beat."""
        if self.wheel_change_ms is None or not self.beat_ms:
            return None
        return self.wheel_change_ms / self.beat_ms

    def color(self, color: str) -> ColorOffer:
        """`color_offer` on this rig."""
        return color_offer(self.heads, color)

    def gobo(self, pattern: GoboPattern | str) -> StateOffer:
        """Which heads show a gobo pattern."""
        return self.gobos[GoboPattern(pattern).value]

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


def rig_offer(fixture_group: FixtureGroup, beat_grid: BeatGrid) -> RigOffer:
    """The rig's offer for one song (`RigOffer`)."""
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
        wheel_change_ms=None
        if not changes or None in changes
        else max(change for change in changes if change is not None),
        beat_ms=intervals[len(intervals) // 2] if intervals else None,
    )


# --- A section's look on the rig ------------------------------------------------------


@dataclass(frozen=True)
class SectionLook:
    """What a section's colour and gobo play on each head (`resolve_section_look`)."""

    section_id: str
    color: PlanColor | None
    requested: RequestedColor | None
    color_offer: ColorOffer | None
    gobo: GoboPattern | None
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
        (`describe_look` reads it)."""
        record: dict[str, Any] = {"section_id": self.section_id}
        if self.color is not None and self.requested is not None and self.color_offer:
            record["color"] = {
                "asked": self.color.value,
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
                "asked": self.gobo.value,
                "available": self.gobo_offer.available,
                "heads": dict(self.gobo_offer.states),
                "kept_authored": list(self.gobo_offer.missing),
            }
        return record


def resolve_section_look(
    section: PlanSection, heads: Sequence[HeadWheels], palette: SectionPalette | None
) -> SectionLook:
    """The wheel states that play `section`'s colour and gobo on each head: the colour
    through `requested_color` (with `palette`, the section's macro palette, or None) and
    `color_offer`, the gobo through `gobo_offer`. A head that cannot show one keeps its
    authored state; an as-authored colour or gobo resolves to nothing."""
    requested = None if section.color is None else requested_color(section.color, palette)
    return SectionLook(
        section_id=section.section_id,
        color=section.color,
        requested=requested,
        color_offer=None if requested is None else color_offer(heads, requested.hex),
        gobo=section.gobo,
        gobo_offer=None if section.gobo is None else gobo_offer(heads, section.gobo),
    )


# --- Repair ---------------------------------------------------------------------------


def repair_rig_intent(
    plan: ChoreographyPlan, offer: RigOffer, palettes: Mapping[str, SectionPalette]
) -> ChoreographyPlan:
    """Repair the colours and gobos no head of the rig can show, one item at a time.

    A section colour no head shows (`unavailable`) is cleared to as authored, and a colour
    event's colour that no head shows drops the event; a section gobo, or a gobo event's
    pattern, that no head has likewise. One some colour-wheel (or gobo-wheel) heads show
    is kept and recorded, naming the heads that keep their authored look. A colour a
    head shows only approximately is not a repair: the offer says so up front and the
    render trace records what plays. Each repair is appended to `plan.repairs`.
    """
    repairs = list(plan.repairs)
    sections: list[PlanSection] = []
    for section in plan.sections:
        palette = palettes.get(section.section_id)
        update: dict[str, Any] = {}

        def note(
            item: str, action: RepairAction, reason: str, section_id: str = section.section_id
        ) -> None:
            repairs.append(
                PlanRepair(section_id=section_id, item=item, action=action, reason=reason)
            )

        if section.color is not None:
            asked = requested_color(section.color, palette)
            shown = offer.color(asked.hex)
            item = f"colour {section.color.value} ({asked.hex}, {asked.source})"
            if shown.status == "unavailable":
                update["color"] = None
                note(
                    item,
                    RepairAction.ADJUSTED,
                    _unshown_color(offer) + "; the section keeps its authored colour (as_authored)",
                )
            elif shown.status == "partial":
                note(item, RepairAction.RECORDED, _partial(shown.heads, shown.missing))
        if section.gobo is not None:
            shown_gobo = offer.gobo(section.gobo)
            item = f"gobo {section.gobo.value}"
            if shown_gobo.available == "none":
                update["gobo"] = None
                note(
                    item,
                    RepairAction.ADJUSTED,
                    _unshown_gobo(offer) + "; the section keeps its authored gobo (as_authored)",
                )
            elif shown_gobo.available == "some":
                note(item, RepairAction.RECORDED, _partial(shown_gobo.states, shown_gobo.missing))
        events = []
        for event in section.events:
            if event.action is EventAction.COLOR and event.color is not None:
                asked = requested_color(event.color, palette)
                shown = offer.color(asked.hex)
                item = f"event at {event.describe()} ({asked.hex}, {asked.source})"
                if shown.status == "unavailable":
                    note(item, RepairAction.DROPPED, _unshown_color(offer))
                    continue
                if shown.status == "partial":
                    note(item, RepairAction.RECORDED, _partial(shown.heads, shown.missing))
            if event.action is EventAction.GOBO and event.gobo is not None:
                shown_gobo = offer.gobo(event.gobo)
                item = f"event at {event.describe()}"
                if shown_gobo.available == "none":
                    note(item, RepairAction.DROPPED, _unshown_gobo(offer))
                    continue
                if shown_gobo.available == "some":
                    note(
                        item, RepairAction.RECORDED, _partial(shown_gobo.states, shown_gobo.missing)
                    )
            events.append(event)
        if len(events) != len(section.events):
            update["events"] = events
        sections.append(section.model_copy(update=update) if update else section)
    if len(repairs) == len(plan.repairs):
        return plan
    return plan.model_copy(update={"sections": sections, "repairs": repairs})


def _unshown_color(offer: RigOffer) -> str:
    if not any(head.color_wheel for head in offer.heads):
        return "this rig has no colour wheel"
    if not offer.offers_colors():
        return "this rig's colour wheel states carry no `hex` tag, so no colour is offered"
    return "no head's colour wheel shows anything like it"


def _unshown_gobo(offer: RigOffer) -> str:
    if not any(head.gobo_wheel for head in offer.heads):
        return "this rig has no gobo wheel"
    return "no head's gobo wheel has a state tagged with this pattern"


def _partial(shown: Mapping[str, Any], missing: Sequence[str]) -> str:
    return (
        f"plays on {', '.join(shown)}; {', '.join(missing)} cannot show it and keep their "
        "authored look"
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
    offer: RigOffer, palettes: Mapping[str, SectionPalette], section_ids: Sequence[str]
) -> dict[str, Any]:
    """The offer as the planner prompt shows it: colours by how faithfully the rig shows
    them, each section's palette roles and the wheel colour each lands on (the fixed
    role table where a section has no macro palette), gobos and strobe speeds by how many
    heads have them, whether a hit is possible, and the wheel change time. Sections that
    share a palette share one entry."""
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
        for role in PaletteRole:
            asked = requested_color(PlanColor(f"PALETTE_{role.value}"), palette)
            shown = offer.color(asked.hex)
            roles.append(
                {
                    "role": f"PALETTE_{role.value}",
                    "hex": asked.hex,
                    "status": shown.status,
                    "shown": _shown(shown) if shown.heads else "",
                }
            )
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

    return {
        "colors": colors,
        "color_wheel": any(head.color_wheel for head in offer.heads),
        "colors_tagged": offer.offers_colors(),
        "no_color_wheel": list(offer.without("color")),
        "sections": sections,
        "gobos": by_availability(offer.gobos),
        "gobo_wheel": any(head.gobo_wheel for head in offer.heads),
        "gobos_tagged": any(head.gobos for head in offer.heads),
        "no_gobo_wheel": list(offer.without("gobo")),
        "strobes": by_availability(offer.strobes),
        "hit": offer.hit,
        "wheel_change_ms": offer.wheel_change_ms,
        "wheel_change_beats": round_beats(offer.wheel_change_beats),
    }


def describe_look(record: Mapping[str, Any]) -> list[str]:
    """A section's trace entry (`SectionLook.record`, with its `boundaries`) as lines for
    a reader: what each asked colour and gobo plays on which heads, and each wheel
    change at the section's start."""
    lines = []
    color = record.get("color")
    if color is not None:
        by_state: dict[str, list[str]] = {}
        for fixture_id, head in color["heads"].items():
            by_state.setdefault(f"{head['state']} ({head['fit']})", []).append(fixture_id)
        played = "; ".join(f"{state} on {', '.join(heads)}" for state, heads in by_state.items())
        kept = (
            f"; {', '.join(color['kept_authored'])} keep their authored colour"
            if color["kept_authored"]
            else ""
        )
        lines.append(
            f"colour {color['asked']} ({color['hex']}, {color['source']}): "
            f"{played or 'no head shows it'}{kept}"
        )
    gobo = record.get("gobo")
    if gobo is not None:
        played = ", ".join(f"{state} on {head}" for head, state in gobo["heads"].items())
        kept = (
            f"; {', '.join(gobo['kept_authored'])} keep their authored gobo"
            if gobo["kept_authored"]
            else ""
        )
        lines.append(f"gobo {gobo['asked']}: {played or 'no head shows it'}{kept}")
    for boundary in record.get("boundaries", []):
        wheels = ", ".join(
            f"{wheel} {change['from']} → {change['to']}"
            for wheel, change in boundary["wheels"].items()
        )
        dip = boundary.get("dark_dip")
        what = (
            f"dark dip of {dip['lead_ms']} ms before the section's first frame"
            if dip is not None
            else f"kept the previous state ({boundary['kept_previous']['reason']})"
        )
        lines.append(f"{boundary['fixture_id']} at {boundary['boundary_ms']} ms: {wheels}: {what}")
    return lines
