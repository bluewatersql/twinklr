"""The moving-head planner's response model: one plan of song intent per section.

The planner chooses typed categories only. Deterministic code owns timing, DMX values and
physical limits: it places bars and beats on the song's beat grid, resolves a palette role
through the song's palette, and repairs what a rig cannot do (`moment_cues.py`).

A null intent field means "as the template is authored"; a section whose intent is all
neutral renders exactly as its templates are authored.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.models.transition import PlanTransition, TransitionEdge
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern


class PlanColor(StrEnum):
    """A colour the planner picks: a role in the song's palette, or a named colour.

    The palette roles resolve through the song's macro palette; the named colours are the
    moving-head colour presets (`ColorPreset`), spelled as they are.
    """

    PALETTE_PRIMARY = "PALETTE_PRIMARY"
    PALETTE_ACCENT = "PALETTE_ACCENT"
    PALETTE_WARM = "PALETTE_WARM"
    PALETTE_COOL = "PALETTE_COOL"
    PALETTE_NEUTRAL = "PALETTE_NEUTRAL"
    RED = "red"
    BLUE = "blue"
    GREEN = "green"
    YELLOW = "yellow"
    MAGENTA = "magenta"
    CYAN = "cyan"
    ORANGE = "orange"
    PURPLE = "purple"
    AMBER = "amber"
    LIME = "lime"
    WHITE = "white"
    WARM_WHITE = "warm_white"
    COOL_WHITE = "cool_white"
    UV = "uv"


class EventAction(StrEnum):
    """What a timed event does to the heads."""

    OPEN = "open"
    CLOSED = "closed"
    STROBE_SLOW = "strobe_slow"
    STROBE_MEDIUM = "strobe_medium"
    STROBE_FAST = "strobe_fast"
    PULSE = "pulse"
    HIT = "hit"
    COLOR = "color"
    GOBO = "gobo"


class Variation(StrEnum):
    """How a section varies the motif it returns to."""

    NONE = "NONE"
    NARROW = "NARROW"
    WIDEN = "WIDEN"
    SLOWER = "SLOWER"
    FASTER = "FASTER"


class Density(StrEnum):
    """How busy a section's movement is."""

    REST = "REST"
    SPARSE = "SPARSE"
    BALANCED = "BALANCED"
    BUSY = "BUSY"


class RepairAction(StrEnum):
    """What deterministic repair did with one planned item."""

    DROPPED = "dropped"
    ADJUSTED = "adjusted"
    RECORDED = "recorded"


# Nullable choices are spelled as one enum that includes null, so a provider's grammar
# sees one enum rather than a union.
IntensityChoice = Literal[
    Intensity.SLOW,
    Intensity.SMOOTH,
    Intensity.FAST,
    Intensity.DRAMATIC,
    Intensity.INTENSE,
    None,
]
ColorChoice = Literal[
    PlanColor.PALETTE_PRIMARY,
    PlanColor.PALETTE_ACCENT,
    PlanColor.PALETTE_WARM,
    PlanColor.PALETTE_COOL,
    PlanColor.PALETTE_NEUTRAL,
    PlanColor.RED,
    PlanColor.BLUE,
    PlanColor.GREEN,
    PlanColor.YELLOW,
    PlanColor.MAGENTA,
    PlanColor.CYAN,
    PlanColor.ORANGE,
    PlanColor.PURPLE,
    PlanColor.AMBER,
    PlanColor.LIME,
    PlanColor.WHITE,
    PlanColor.WARM_WHITE,
    PlanColor.COOL_WHITE,
    PlanColor.UV,
    None,
]
GoboChoice = Literal[
    GoboPattern.OPEN,
    GoboPattern.CIRCLES,
    GoboPattern.TRIANGLES,
    GoboPattern.STARS,
    GoboPattern.DIAMONDS,
    GoboPattern.CLOUDS,
    GoboPattern.PRISM,
    GoboPattern.SHATTER,
    GoboPattern.DOTS,
    GoboPattern.FLAME,
    GoboPattern.WATER,
    GoboPattern.FOLIAGE,
    GoboPattern.ABSTRACT,
    None,
]

PART_IDS = ("A", "B", "C")
"""The ids code gives a section's unlabelled parts, by position, when it has more than one."""


class PlanModifier(BaseModel):
    """One free-form modifier the planner attaches to a part."""

    key: str = Field(min_length=1, description="Modifier name")
    value: str = Field(description="Modifier value")

    model_config = ConfigDict(extra="forbid", frozen=True)


class PlanPart(BaseModel):
    """One template over a run of a section's bars, up to the next part's start."""

    start_bar: int = Field(ge=1, description="First bar of this part (1-indexed)")
    template_id: str = Field(description="Template from the Template Library")
    preset_id: str | None = Field(description="A preset the template declares, or null")
    modifiers: list[PlanModifier] = Field(description="Modifier entries; empty when unused")
    label: str | None = Field(
        description="A short name for this part of the section (e.g. 'pickup', 'drop'), or null"
    )
    reasoning: str = Field(description="Why this template here")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("label")
    @classmethod
    def _strip_label(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class PlanEvent(BaseModel):
    """A timed accent at a bar and beat, optionally tied to a lyric moment cue."""

    bar: int = Field(ge=1, description="Absolute 1-indexed bar")
    beat: int = Field(ge=1, description="1-indexed beat within the bar")
    moment_cue_id: str | None = Field(
        description="The lyric moment cue this event lands on, or null"
    )
    action: EventAction = Field(description="What the heads do")
    color: ColorChoice = Field(description="The colour for a color event; otherwise null")
    gobo: GoboChoice = Field(description="The pattern for a gobo event; otherwise null")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("moment_cue_id")
    @classmethod
    def _strip_cue_id(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    def describe(self) -> str:
        """One line: where, what, and the cue it lands on."""
        detail = " ".join(
            value.value for value in (self.action, self.color, self.gobo) if value is not None
        )
        cue = f" on cue '{self.moment_cue_id}'" if self.moment_cue_id else ""
        return f"bar {self.bar} beat {self.beat}: {detail}{cue}"


class PlanSection(BaseModel):
    """The planner's song intent for one song section."""

    section_id: str = Field(
        description="Unique SongSectionRef.section_id (e.g. 'chorus_2'), never the display name"
    )
    start_bar: int = Field(ge=1, description="Start bar (1-indexed)")
    end_bar: int = Field(ge=1, description="End bar (1-indexed, inclusive)")
    section_role: str | None = Field(
        description="What the section does in the song (verse, chorus, bridge, build, drop, ...)"
    )
    energy_level: int | None = Field(
        ge=0, le=100, description="How much energy the light answers with here, 0-100"
    )
    parts: list[PlanPart] = Field(
        description="One to three templates in bar order; one part covers the whole section",
        min_length=1,
        max_length=len(PART_IDS),
    )
    intensity: IntensityChoice = Field(
        description="How hard the light drives, from the section's energy (null: the template's own)"
    )
    color: ColorChoice = Field(
        description="The section's colour, a role in its palette or a named colour "
        "(null: the template's own)"
    )
    gobo: GoboChoice = Field(description="The section's beam pattern (null: the template's own)")
    moment_cues: list[str] = Field(description="Lyric moment cue ids this section answers")
    events: list[PlanEvent] = Field(
        description="Timed accents on the section's lyric cues and musical moments"
    )
    motif_id: str | None = Field(description="The macro motif this section carries, or null")
    variation: Variation = Field(description="How this section varies its motif")
    density: Density = Field(description="How busy the movement is")
    transitions: list[PlanTransition] = Field(
        description="At most one ENTRY and one EXIT transition, chosen for the boundary",
        max_length=len(TransitionEdge),
    )
    reasoning: str = Field(description="Why these choices serve the song here")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("moment_cues")
    @classmethod
    def _cue_ids(cls, value: list[str]) -> list[str]:
        stripped = [cue_id.strip() for cue_id in value]
        if any(not cue_id for cue_id in stripped):
            raise ValueError("moment cue ids must not be blank")
        if len(stripped) != len(set(stripped)):
            raise ValueError("moment_cues must contain unique cue ids")
        return stripped

    @model_validator(mode="after")
    def _bars_and_parts(self) -> PlanSection:
        if self.end_bar < self.start_bar:
            raise ValueError(f"end_bar ({self.end_bar}) must be >= start_bar ({self.start_bar})")
        starts = [part.start_bar for part in self.parts]
        if starts[0] != self.start_bar:
            raise ValueError(
                f"the first part starts at bar {starts[0]}, not the section's start "
                f"{self.start_bar}"
            )
        if starts != sorted(set(starts)):
            raise ValueError(f"parts must be ordered by start_bar, each later: {starts}")
        if starts[-1] > self.end_bar:
            raise ValueError(
                f"part start bar {starts[-1]} is not inside the section "
                f"({self.start_bar}-{self.end_bar})"
            )
        edges = [transition.edge for transition in self.transitions]
        for edge in TransitionEdge:
            if edges.count(edge) > 1:
                raise ValueError(f"a section has at most one {edge.value} transition")
        return self

    @property
    def entry(self) -> PlanTransition | None:
        """The transition into this section, if the planner chose one."""
        return self._transition(TransitionEdge.ENTRY)

    @property
    def exit(self) -> PlanTransition | None:
        """The transition out of this section, if the planner chose one."""
        return self._transition(TransitionEdge.EXIT)

    def _transition(self, edge: TransitionEdge) -> PlanTransition | None:
        return next((t for t in self.transitions if t.edge is edge), None)

    def part_bars(self) -> list[tuple[PlanPart, int, int]]:
        """Each part with its bars: from its start to the bar before the next part's."""
        ends = [part.start_bar - 1 for part in self.parts[1:]] + [self.end_bar]
        return [(part, part.start_bar, end) for part, end in zip(self.parts, ends, strict=True)]

    def set_intent_fields(self) -> tuple[str, ...]:
        """The song-intent fields the planner set away from "as authored"."""
        chosen = {
            "intensity": self.intensity is not None,
            "color": self.color is not None,
            "gobo": self.gobo is not None,
            "moment_cues": bool(self.moment_cues),
            "events": bool(self.events),
            "motif_id": self.motif_id is not None,
            "variation": self.variation is not Variation.NONE,
            "density": self.density is not Density.BALANCED,
            "entry": self.entry is not None,
            "exit": self.exit is not None,
            "modifiers": any(part.modifiers for part in self.parts),
        }
        return tuple(name for name, is_set in chosen.items() if is_set)


class PlanRepair(BaseModel):
    """One planned item deterministic repair dropped, adjusted or recorded, and why."""

    section_id: str
    item: str
    action: RepairAction
    reason: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    def describe(self) -> str:
        """One line for the planner and the reader: what was repaired and why."""
        return f"section '{self.section_id}': {self.item} {self.action.value}: {self.reason}"


class ChoreographyPlan(BaseModel):
    """Complete choreography plan from the moving-head planner agent."""

    sections: list[PlanSection] = Field(description="One entry per song section", min_length=1)
    overall_strategy: str = Field(description="High-level choreography strategy")
    repairs: SkipJsonSchema[list[PlanRepair]] = Field(
        default_factory=list,
        description="What deterministic repair changed in the planner's response (not planned)",
    )

    model_config = ConfigDict(extra="forbid", frozen=True)


def part_ids(section: PlanSection) -> list[str]:
    """The id of each of the section's parts in timing labels and the trace: its label,
    else `A`, `B`, `C` by position; a label or letter already taken in the section gives
    way to the first free letter."""
    ids: list[str] = []
    for index, part in enumerate(section.parts):
        candidate = part.label or PART_IDS[index]
        if candidate in ids:
            candidate = next(letter for letter in PART_IDS if letter not in ids)
        ids.append(candidate)
    return ids


def flatten_section(section: PlanSection) -> list[PlanSection]:
    """The section as the renderer places it: one section per part.

    One unlabelled part is the section itself. Otherwise each part becomes a section
    named `<section_id>|<part id>` (`part_ids`) over its own bars, carrying the section's
    intent, with the events on its bars (event bars are absolute), the moment cues
    (untimed, so on every part), the entry transition on the first part and the exit on
    the last.
    """
    if len(section.parts) == 1 and section.parts[0].label is None:
        return [section]
    bars = section.part_bars()
    ids = part_ids(section)
    flattened: list[PlanSection] = []
    for index, (part, start, end) in enumerate(bars):
        edges = {TransitionEdge.ENTRY} if index == 0 else set()
        if index == len(bars) - 1:
            edges.add(TransitionEdge.EXIT)
        flattened.append(
            section.model_copy(
                update={
                    "section_id": f"{section.section_id}|{ids[index]}",
                    "start_bar": start,
                    "end_bar": end,
                    "parts": [part],
                    "events": [event for event in section.events if start <= event.bar <= end],
                    "transitions": [t for t in section.transitions if t.edge in edges],
                }
            )
        )
    return flattened


_OLD_SECTION_KEYS = frozenset(
    {"section_name", "template_id", "segments", "color_intent", "shutter_events", "gobo_events"}
)


def load_plan(data: object, *, remedy: str) -> ChoreographyPlan:
    """Read a saved plan, refusing one in the contract before 2026-11-17 by name.

    Args:
        data: The plan's JSON value.
        remedy: What the user runs to write the plan again, appended to the refusal.

    Raises:
        ValueError: If `data` is a plan in the old contract (a moving-head plan whose
            sections carry `section_name`, `template_id` or `segments`), naming it and
            `remedy`.
        ValidationError: If `data` is not a valid plan otherwise.
    """
    try:
        return ChoreographyPlan.model_validate(data)
    except ValidationError as error:
        sections = data.get("sections") if isinstance(data, dict) else None
        if isinstance(sections, list) and any(
            isinstance(section, dict) and not _OLD_SECTION_KEYS.isdisjoint(section)
            for section in sections
        ):
            raise ValueError(
                "this moving-head plan was saved in the planner contract before 2026-11-17 "
                "(its sections carry `section_name`, `template_id` or `segments`); this "
                f"version reads only the song-intent contract. To write it again, {remedy}"
            ) from error
        raise
