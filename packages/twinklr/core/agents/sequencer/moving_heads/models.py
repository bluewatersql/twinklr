"""Response models for moving heads agents."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.models.transition import TransitionHint
from twinklr.core.sequencer.moving_heads.libraries.color import ColorPreset
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern
from twinklr.core.sequencer.moving_heads.libraries.shutter import ShutterPattern
from twinklr.core.sequencer.vocabulary.visual import PaletteRole


class PlanModifier(BaseModel):
    """One planner modifier entry, encoded as a strict-schema-compatible list item."""

    key: str = Field(min_length=1, description="Modifier name")
    value: str = Field(description="Modifier value")

    model_config = ConfigDict(extra="forbid", frozen=True)


class ColorIntentKind(StrEnum):
    """How a planned color is selected."""

    PALETTE_ROLE = "PALETTE_ROLE"
    EXPLICIT = "EXPLICIT"


class PaletteRoleColorIntent(BaseModel):
    """Color selected from the active show palette."""

    kind: Literal[ColorIntentKind.PALETTE_ROLE]
    palette_role: PaletteRole
    explicit_color: None

    model_config = ConfigDict(extra="forbid", frozen=True)


class ExplicitColorIntent(BaseModel):
    """Color selected from the named moving-head preset library."""

    kind: Literal[ColorIntentKind.EXPLICIT]
    palette_role: None
    explicit_color: ColorPreset

    model_config = ConfigDict(extra="forbid", frozen=True)


ColorIntentSelection = Annotated[
    PaletteRoleColorIntent | ExplicitColorIntent,
    Field(discriminator="kind"),
]


class ColorIntent(BaseModel):
    """Renderer-resolvable color selection without fixture-specific DMX values.

    The nested selection is a genuine discriminated union in the generated response
    schema. A pre-validator accepts the historical flat constructor shape so existing
    deterministic callers remain compatible while model output uses the strict nested
    contract.
    """

    selection: ColorIntentSelection = Field(description="Discriminated color selection")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        if isinstance(value, dict) and "selection" not in value and "kind" in value:
            return {"selection": value}
        return value

    @property
    def kind(self) -> ColorIntentKind:
        """Expose the historical flat read interface to renderer callers."""
        return ColorIntentKind(self.selection.kind)

    @property
    def palette_role(self) -> PaletteRole | None:
        """Expose the selected palette role, if any."""
        return self.selection.palette_role

    @property
    def explicit_color(self) -> ColorPreset | None:
        """Expose the selected explicit preset, if any."""
        return self.selection.explicit_color


class MomentCueReference(BaseModel):
    """Reference to a lyric ``MomentCue`` defined by P2P-T4."""

    cue_id: str = Field(min_length=1, description="Stable MomentCue identifier")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("cue_id")
    @classmethod
    def _strip_cue_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("cue_id must not be blank")
        return stripped


class ShutterEvent(BaseModel):
    """Discrete shutter intent resolved against the beat grid by P2P-T2."""

    bar: int = Field(ge=1, description="Absolute 1-indexed bar")
    beat: int = Field(ge=1, description="1-indexed beat within the bar")
    pattern: ShutterPattern = Field(description="Named shutter pattern")
    moment_cue_id: str | None = Field(
        description="Referenced MomentCue id when lyric-driven; otherwise null"
    )

    model_config = ConfigDict(extra="forbid", frozen=True)


class GoboEvent(BaseModel):
    """Discrete gobo-wheel intent resolved against the beat grid by P2P-T2."""

    bar: int = Field(ge=1, description="Absolute 1-indexed bar")
    beat: int = Field(ge=1, description="1-indexed beat within the bar")
    pattern: GoboPattern = Field(description="Named gobo pattern")
    moment_cue_id: str | None = Field(
        description="Referenced MomentCue id when lyric-driven; otherwise null"
    )

    model_config = ConfigDict(extra="forbid", frozen=True)


class PlanSegment(BaseModel):
    """LLM selection for a contiguous sub-range within a section."""

    segment_id: str = Field(description="Short id within the section (e.g., 'A', 'B', 'C')")
    start_bar: int = Field(ge=1, description="Start bar (1-indexed)")
    end_bar: int = Field(ge=1, description="End bar (1-indexed, inclusive)")
    template_id: str = Field(description="Template ID to use for this segment")
    preset_id: str | None = Field(description="Optional preset ID; null when unused")
    modifiers: list[PlanModifier] = Field(description="Modifier entries; empty when unused")
    reasoning: str = Field(description="Why this segment choice was made")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        """Keep deterministic callers compatible while the response schema stays strict."""
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized.setdefault("preset_id", None)
        normalized.setdefault("modifiers", [])
        normalized.setdefault("reasoning", "")
        if isinstance(normalized["modifiers"], dict):
            normalized["modifiers"] = [
                {"key": key, "value": modifier_value}
                for key, modifier_value in normalized["modifiers"].items()
            ]
        return normalized

    @model_validator(mode="after")
    def _validate_bar_range(self) -> PlanSegment:
        if self.end_bar < self.start_bar:
            raise ValueError(f"end_bar ({self.end_bar}) must be >= start_bar ({self.start_bar})")
        return self


class PlanSection(BaseModel):
    """Typed LLM intent for one song section.

    Renderer contract: ``intensity`` resolves through the moving-head parameter tables;
    ``color_intent`` resolves through the palette or color library; shutter and gobo
    events resolve their bar/beat positions against the authoritative beat grid; and
    ``moment_cues`` are joined to lyric MomentCues by id. P2P-T2 implements those
    renderer resolutions.

    The template-versus-segments XOR intentionally remains a post-validation check.
    A nested discriminated selection object would break the live renderer's stable
    ``template_id``/``segments`` interface and risk changing golden output in this
    schema-only task. All keys remain required for strict structured outputs, with the
    unused arm explicitly ``null``; P2P-T11 therefore retains this one repair surface.
    """

    section_name: str = Field(description="Section name (e.g., 'verse_1', 'chorus_1')")
    start_bar: int = Field(ge=1, description="Start bar (1-indexed)")
    end_bar: int = Field(ge=1, description="End bar (1-indexed, inclusive)")
    section_role: str | None = Field(
        description="Section role (verse, chorus, bridge, build, drop, etc.) or null"
    )
    energy_level: int | None = Field(ge=0, le=100, description="Energy level 0-100 or null")
    template_id: str | None = Field(
        description="Template ID for an unsegmented section; otherwise null"
    )
    preset_id: str | None = Field(description="Optional preset ID; null when unused")
    modifiers: list[PlanModifier] = Field(description="Modifier entries; empty when unused")
    reasoning: str = Field(description="Why this template or segmentation was chosen")
    segments: list[PlanSegment] | None = Field(
        description="One to three contiguous segments, or null for a single template",
        min_length=1,
        max_length=3,
    )
    transition_in: TransitionHint | None = Field(
        description="Transition into this section, or null for renderer defaults"
    )
    transition_out: TransitionHint | None = Field(
        description="Transition out of this section, or null for renderer defaults"
    )
    intensity: Intensity = Field(
        description="Categorical movement/dimmer intensity resolved by P2P-T2"
    )
    color_intent: ColorIntent = Field(
        description="Palette-role or explicit-preset color resolved by P2P-T2"
    )
    shutter_events: list[ShutterEvent] = Field(
        description="Discrete shutter changes resolved to DMX events by P2P-T2"
    )
    gobo_events: list[GoboEvent] = Field(
        description="Discrete gobo-wheel changes resolved to DMX events by P2P-T2"
    )
    moment_cues: list[MomentCueReference] = Field(
        description="Lyric MomentCue ids referenced by this section"
    )

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        """Supply historical internal defaults without weakening the generated schema."""
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        legacy_defaults: dict[str, object] = {
            "section_role": None,
            "energy_level": None,
            "template_id": None,
            "preset_id": None,
            "modifiers": [],
            "reasoning": "",
            "segments": None,
            "transition_in": None,
            "transition_out": None,
            "intensity": Intensity.SMOOTH,
            "color_intent": {
                "selection": {
                    "kind": ColorIntentKind.PALETTE_ROLE,
                    "palette_role": PaletteRole.PRIMARY,
                    "explicit_color": None,
                }
            },
            "shutter_events": [],
            "gobo_events": [],
            "moment_cues": [],
        }
        for key, default in legacy_defaults.items():
            normalized.setdefault(key, default)
        if isinstance(normalized["modifiers"], dict):
            normalized["modifiers"] = [
                {"key": key, "value": modifier_value}
                for key, modifier_value in normalized["modifiers"].items()
            ]
        return normalized

    @model_validator(mode="after")
    def _validate_section(self) -> PlanSection:
        if self.end_bar < self.start_bar:
            raise ValueError(f"end_bar ({self.end_bar}) must be >= start_bar ({self.start_bar})")

        has_segments = bool(self.segments)
        has_single = bool(self.template_id)
        if has_segments and has_single:
            raise ValueError("Provide either 'segments' OR 'template_id', not both.")
        if not has_segments and not has_single:
            raise ValueError("Must provide either 'segments' or 'template_id'.")

        cue_ids = [reference.cue_id for reference in self.moment_cues]
        if len(cue_ids) != len(set(cue_ids)):
            raise ValueError("moment_cues must contain unique cue_id values")
        known_cues = set(cue_ids)
        for shutter_event in self.shutter_events:
            if not self.start_bar <= shutter_event.bar <= self.end_bar:
                raise ValueError("Discrete event bar must be within the section bar range.")
            if (
                shutter_event.moment_cue_id is not None
                and shutter_event.moment_cue_id not in known_cues
            ):
                raise ValueError(
                    "Discrete event references unknown MomentCue id "
                    f"'{shutter_event.moment_cue_id}'."
                )
        for gobo_event in self.gobo_events:
            if not self.start_bar <= gobo_event.bar <= self.end_bar:
                raise ValueError("Discrete event bar must be within the section bar range.")
            if gobo_event.moment_cue_id is not None and gobo_event.moment_cue_id not in known_cues:
                raise ValueError(
                    f"Discrete event references unknown MomentCue id '{gobo_event.moment_cue_id}'."
                )

        if self.segments:
            segs = sorted(self.segments, key=lambda segment: (segment.start_bar, segment.end_bar))
            if segs[0].start_bar != self.start_bar:
                raise ValueError("First segment must start at section start_bar.")
            if segs[-1].end_bar != self.end_bar:
                raise ValueError("Last segment must end at section end_bar.")
            for index in range(len(segs) - 1):
                if segs[index].end_bar + 1 != segs[index + 1].start_bar:
                    raise ValueError("Segments must be contiguous and non-overlapping.")
            for segment in segs:
                if segment.start_bar < self.start_bar or segment.end_bar > self.end_bar:
                    raise ValueError("Segment bar range must be within the section bar range.")

        return self


def flatten_plan_segment(section: PlanSection, segment: PlanSegment) -> PlanSection:
    """Project one parent section onto a contiguous segment.

    Event bars are absolute and section segments are contiguous and non-overlapping, so
    both segment endpoints are inclusive: an event on ``end_bar`` belongs to that segment
    and the following segment starts at ``end_bar + 1``. Untimed MomentCue references
    cannot be range-routed; they remain available on each derived section so routed
    shutter/gobo events keep resolvable cue references. All other parent creative intent
    is inherited unchanged unless the segment supplies its own template metadata.
    """

    return PlanSection(
        section_name=f"{section.section_name}|{segment.segment_id}",
        start_bar=segment.start_bar,
        end_bar=segment.end_bar,
        section_role=section.section_role,
        energy_level=section.energy_level,
        template_id=segment.template_id,
        preset_id=segment.preset_id,
        modifiers=segment.modifiers,
        reasoning=segment.reasoning or section.reasoning,
        segments=None,
        transition_in=section.transition_in,
        transition_out=section.transition_out,
        intensity=section.intensity,
        color_intent=section.color_intent,
        shutter_events=[
            event
            for event in section.shutter_events
            if segment.start_bar <= event.bar <= segment.end_bar
        ],
        gobo_events=[
            event
            for event in section.gobo_events
            if segment.start_bar <= event.bar <= segment.end_bar
        ],
        moment_cues=section.moment_cues,
    )


class ChoreographyPlan(BaseModel):
    """Complete choreography plan from the moving-head planner agent."""

    sections: list[PlanSection] = Field(
        description="Section selections and typed intents", min_length=1
    )
    overall_strategy: str = Field(description="High-level choreography strategy")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        """Retain the historical empty-strategy default for internal construction."""
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized.setdefault("overall_strategy", "")
        return normalized
