"""Typed macro-level choreography contract.

The macro planner owns cross-element creative intent.  Downstream planners receive
these models as data; deterministic renderers continue to own exact timing and effect
math.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.vocabulary import (
    ChoreographyStyle,
    CoordinationMode,
    EnergyTarget,
    MotionDensity,
    StepUnit,
    TargetType,
)
from twinklr.core.sequencer.vocabulary.visual import PaletteRole

if TYPE_CHECKING:
    from pydantic import ValidationInfo

    from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph


class PaletteRef(BaseModel):
    """Reference to a catalog palette without embedding color values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    palette_id: str = Field(min_length=1, description="Palette catalog ID")
    role: PaletteRole | None = Field(
        description="Optional usage role (PRIMARY, ACCENT, WARM, or COOL)"
    )
    intensity: float | None = Field(
        ge=0.0,
        le=1.0,
        description="Optional global intensity scaler for this palette usage",
    )
    variant: str | None = Field(description="Optional palette variant key")

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        """Keep catalog-created PaletteRefs strict-schema compatible."""
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for key in ("role", "intensity", "variant"):
            normalized.setdefault(key, None)
        return normalized


class PaletteTransition(StrEnum):
    """How a palette stop enters at its first section."""

    HOLD = "HOLD"
    CROSSFADE = "CROSSFADE"
    CUT = "CUT"


class MotifEvolution(StrEnum):
    """How a recurring motif changes over its declared sections."""

    INTRODUCE = "INTRODUCE"
    RESTATE = "RESTATE"
    VARY = "VARY"
    RESOLVE = "RESOLVE"


class FocalRoleKind(StrEnum):
    """A target's visual responsibility within one section."""

    LEAD = "LEAD"
    SUPPORT = "SUPPORT"
    REST = "REST"


class PaletteStop(BaseModel):
    """One ordered palette/theme stop in the song-level color arc."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stop_id: str = Field(min_length=1)
    palette: PaletteRef
    applies_from_section_id: str = Field(min_length=1)
    transition: PaletteTransition


class PaletteRoleRef(BaseModel):
    """Palette selection for a section.

    ``override`` has precedence when present.  Otherwise the referenced
    ``PaletteStop.palette`` is authoritative.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    stop_id: str = Field(min_length=1)
    override: PaletteRef | None = Field(
        description="Section palette override; null means use the referenced arc stop"
    )


class MotifThread(BaseModel):
    """A recurring motif and the sections through which it evolves."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    motif_id: str = Field(min_length=1)
    section_ids: list[str] = Field(min_length=1)
    evolution: MotifEvolution
    description: str

    @field_validator("section_ids")
    @classmethod
    def _unique_section_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("MotifThread.section_ids must be unique")
        return value


class FocalRole(BaseModel):
    """A target's lead, support, or rest role in one section."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: PlanTarget
    role: FocalRoleKind


class FocalAssignment(BaseModel):
    """Song-level statement of the lead target for one section."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str = Field(min_length=1)
    lead_target: PlanTarget


class CallResponsePair(BaseModel):
    """Typed call-and-response relationship between two display targets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    call: PlanTarget
    response: PlanTarget
    step_unit: StepUnit
    step_duration: int = Field(ge=1)

    @model_validator(mode="after")
    def _distinct_targets(self) -> CallResponsePair:
        if self.call == self.response:
            raise ValueError("CallResponsePair call and response must differ")
        return self


class MacroSection(BaseModel):
    """Strategic typed contract for one audio section.

    ``notes`` is intentionally prose.  Every other member is structured input for
    downstream planning.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    section: SongSectionRef
    energy_target: EnergyTarget
    motion_density: MotionDensity
    choreography_style: ChoreographyStyle
    palette_role: PaletteRoleRef
    theme: ThemeRef
    motif_ids: list[str] = Field(max_length=5)
    focal_roles: list[FocalRole] = Field(min_length=1)
    call_response_pairs: list[CallResponsePair]
    coordination_intent: CoordinationMode
    notes: str = Field(min_length=20, description="Planner-facing prose guidance")

    @field_validator("theme")
    @classmethod
    def _section_theme(cls, value: ThemeRef) -> ThemeRef:
        if value.scope != ThemeScope.SECTION:
            raise ValueError("MacroSection.theme.scope must be ThemeScope.SECTION")
        return value

    @field_validator("motif_ids")
    @classmethod
    def _unique_motif_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("MacroSection.motif_ids must be unique")
        return value

    @field_validator("focal_roles")
    @classmethod
    def _unique_focal_targets(cls, value: list[FocalRole]) -> list[FocalRole]:
        keys = [(item.target.type, item.target.id) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("MacroSection.focal_roles targets must be unique")
        return value


class MacroPlan(BaseModel):
    """Slim song-level cross-element coordination contract.

    Palette precedence is deterministic: a section's ``palette_role.override`` wins;
    otherwise its referenced ``palette_arc`` stop supplies the palette.
    """

    model_config = ConfigDict(extra="forbid")

    sections: list[MacroSection] = Field(min_length=1)
    palette_arc: list[PaletteStop] = Field(min_length=1)
    motif_continuity: list[MotifThread]
    focal_arc: list[FocalAssignment]

    @model_validator(mode="after")
    def _validate_contract(self, info: ValidationInfo) -> MacroPlan:
        section_ids = [item.section.section_id for item in self.sections]
        self._validate_unique(section_ids, "section_id")
        self._validate_section_coverage()

        known_sections = set(section_ids)
        palette_ids = [item.stop_id for item in self.palette_arc]
        self._validate_unique(palette_ids, "palette stop_id")
        known_palette_stops = set(palette_ids)
        for stop in self.palette_arc:
            if stop.applies_from_section_id not in known_sections:
                raise ValueError(
                    "Palette stop "
                    f"'{stop.stop_id}' references unknown section "
                    f"'{stop.applies_from_section_id}'"
                )

        section_order = {section_id: index for index, section_id in enumerate(section_ids)}
        stop_positions = [section_order[item.applies_from_section_id] for item in self.palette_arc]
        if stop_positions[0] != 0:
            raise ValueError("The first palette stop must start at the first section")
        if stop_positions != sorted(stop_positions):
            raise ValueError("palette_arc stops must follow section order")
        if len(stop_positions) != len(set(stop_positions)):
            raise ValueError("Only one palette stop may begin at a section")
        active_stop_by_section: dict[str, str] = {}
        active_stop_id = self.palette_arc[0].stop_id
        stop_by_position = {
            section_order[item.applies_from_section_id]: item.stop_id for item in self.palette_arc
        }
        for index, section_id in enumerate(section_ids):
            active_stop_id = stop_by_position.get(index, active_stop_id)
            active_stop_by_section[section_id] = active_stop_id

        motif_ids = [item.motif_id for item in self.motif_continuity]
        self._validate_unique(motif_ids, "motif_id")
        known_motifs = set(motif_ids)
        for thread in self.motif_continuity:
            unknown_sections = set(thread.section_ids) - known_sections
            if unknown_sections:
                raise ValueError(
                    f"Motif '{thread.motif_id}' references unknown section(s): "
                    f"{sorted(unknown_sections)}"
                )
            for section_id in thread.section_ids:
                section = next(
                    item for item in self.sections if item.section.section_id == section_id
                )
                if thread.motif_id not in section.motif_ids:
                    raise ValueError(
                        f"Motif '{thread.motif_id}' declares section '{section_id}', but that "
                        "section does not reference the motif"
                    )

        for item in self.sections:
            section_id = item.section.section_id
            if item.palette_role.stop_id not in known_palette_stops:
                raise ValueError(
                    f"Section '{section_id}' references unknown palette stop "
                    f"'{item.palette_role.stop_id}'"
                )
            expected_stop = active_stop_by_section[section_id]
            if item.palette_role.stop_id != expected_stop:
                raise ValueError(
                    f"Section '{section_id}' palette stop '{item.palette_role.stop_id}' "
                    f"is not the active stop '{expected_stop}'"
                )
            for motif_id in item.motif_ids:
                if motif_id not in known_motifs:
                    raise ValueError(
                        f"Section '{section_id}' references unknown motif '{motif_id}'"
                    )
                thread = next(
                    motif for motif in self.motif_continuity if motif.motif_id == motif_id
                )
                if section_id not in thread.section_ids:
                    raise ValueError(
                        f"Section '{section_id}' references motif '{motif_id}', but the motif "
                        "thread does not declare that section"
                    )
            resolved_palette = self._palette_for_role(item.palette_role)
            if item.theme.palette_id not in (None, resolved_palette.palette_id):
                raise ValueError(
                    f"Section '{section_id}' theme palette_id '{item.theme.palette_id}' "
                    f"conflicts with typed palette role '{resolved_palette.palette_id}'"
                )

        focal_section_ids = [item.section_id for item in self.focal_arc]
        self._validate_unique(focal_section_ids, "focal_arc section_id")
        missing_focal_sections = known_sections - set(focal_section_ids)
        unknown_focal_sections = set(focal_section_ids) - known_sections
        if missing_focal_sections or unknown_focal_sections:
            raise ValueError(
                "focal_arc must contain exactly one assignment per section; "
                f"missing={sorted(missing_focal_sections)}, "
                f"unknown={sorted(unknown_focal_sections)}"
            )
        assignment_by_section = {item.section_id: item for item in self.focal_arc}
        for item in self.sections:
            leads = [role.target for role in item.focal_roles if role.role == FocalRoleKind.LEAD]
            if len(leads) != 1:
                raise ValueError(
                    f"Section '{item.section.section_id}' must declare exactly one LEAD focal role"
                )
            assignment = assignment_by_section[item.section.section_id]
            if assignment.lead_target != leads[0]:
                raise ValueError(
                    f"Section '{item.section.section_id}' focal_arc lead_target must equal "
                    "its one LEAD focal role"
                )

        graph = (info.context or {}).get("choreo_graph") if info.context else None
        if graph is not None:
            self._validate_targets_against_graph(graph)
        return self

    @staticmethod
    def _validate_unique(values: list[str], label: str) -> None:
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            raise ValueError(f"Duplicate {label}: {duplicates}")

    def _validate_section_coverage(self) -> None:
        starts = [item.section.start_ms for item in self.sections]
        if starts != sorted(starts):
            raise ValueError("Sections not sorted by start_ms")
        for current, following in zip(self.sections, self.sections[1:], strict=False):
            current_end = current.section.end_ms
            next_start = following.section.start_ms
            if current_end < next_start:
                raise ValueError(
                    f"Gap detected between sections '{current.section.section_id}' and "
                    f"'{following.section.section_id}': {current_end}ms to {next_start}ms"
                )
            if current_end > next_start:
                raise ValueError(
                    f"Overlap detected between sections '{current.section.section_id}' and "
                    f"'{following.section.section_id}': current ends at {current_end}ms, "
                    f"next starts at {next_start}ms"
                )

    def _validate_targets_against_graph(self, graph: ChoreographyGraph) -> None:
        targets = [assignment.lead_target for assignment in self.focal_arc]
        for section in self.sections:
            targets.extend(role.target for role in section.focal_roles)
            for pair in section.call_response_pairs:
                targets.extend((pair.call, pair.response))

        for target in targets:
            if not self._target_exists(target, graph):
                raise ValueError(
                    f"Macro target '{target.type.value}:{target.id}' does not resolve "
                    "against the choreography graph"
                )

    @staticmethod
    def _target_exists(target: PlanTarget, graph: ChoreographyGraph) -> bool:
        if target.type == TargetType.GROUP:
            return graph.get_group(target.id) is not None
        if target.type == TargetType.ZONE:
            return any(tag.value == target.id for tag in graph.groups_by_tag)
        if target.type == TargetType.SPLIT:
            return any(split.value == target.id for split in graph.groups_by_split)
        return False

    def palette_for_section(self, section_id: str) -> PaletteRef:
        """Resolve the documented section-override-over-song-arc precedence."""
        section = next(
            (item for item in self.sections if item.section.section_id == section_id),
            None,
        )
        if section is None:
            raise KeyError(f"Unknown macro section '{section_id}'")
        return self._palette_for_role(section.palette_role)

    def reader_projection(self) -> dict[str, Any]:
        """Return every contract leaf through explicit, by-name reads.

        This is the canonical downstream prompt/cache projection. It deliberately
        avoids ``model_dump`` so a new schema field cannot become transport-only.
        """
        return {
            "sections": [self.section_reader_projection(item) for item in self.sections],
            "palette_arc": [self.palette_stop_reader_projection(item) for item in self.palette_arc],
            "motif_continuity": [
                self.motif_thread_reader_projection(item) for item in self.motif_continuity
            ],
            "focal_arc": [self.focal_assignment_reader_projection(item) for item in self.focal_arc],
        }

    @staticmethod
    def target_reader_projection(target: PlanTarget) -> dict[str, str]:
        """Read every typed target leaf by name."""
        return {"type": target.type.value, "id": target.id}

    @staticmethod
    def palette_reader_projection(palette: PaletteRef | None) -> dict[str, Any]:
        """Read every palette leaf, retaining a stable nullable shape."""
        return {
            "palette_id": palette.palette_id if palette is not None else None,
            "role": palette.role.value
            if palette is not None and palette.role is not None
            else None,
            "intensity": palette.intensity if palette is not None else None,
            "variant": palette.variant if palette is not None else None,
        }

    @classmethod
    def section_reader_projection(cls, section: MacroSection) -> dict[str, Any]:
        """Read every per-section contract leaf by name."""
        return {
            "section": {
                "section_id": section.section.section_id,
                "name": section.section.name,
                "start_ms": section.section.start_ms,
                "end_ms": section.section.end_ms,
            },
            "energy_target": section.energy_target.value,
            "motion_density": section.motion_density.value,
            "choreography_style": section.choreography_style.value,
            "palette_role": {
                "stop_id": section.palette_role.stop_id,
                "override": cls.palette_reader_projection(section.palette_role.override),
            },
            "theme": {
                "theme_id": section.theme.theme_id,
                "scope": section.theme.scope.value,
                "tags": list(section.theme.tags),
                "palette_id": section.theme.palette_id,
            },
            "motif_ids": list(section.motif_ids),
            "focal_roles": [
                {
                    "target": cls.target_reader_projection(item.target),
                    "role": item.role.value,
                }
                for item in section.focal_roles
            ],
            "call_response_pairs": [
                {
                    "call": cls.target_reader_projection(item.call),
                    "response": cls.target_reader_projection(item.response),
                    "step_unit": item.step_unit.value,
                    "step_duration": item.step_duration,
                }
                for item in section.call_response_pairs
            ],
            "coordination_intent": section.coordination_intent.value,
            "notes": section.notes,
        }

    @classmethod
    def palette_stop_reader_projection(cls, stop: PaletteStop) -> dict[str, Any]:
        """Read every palette-stop contract leaf by name."""
        return {
            "stop_id": stop.stop_id,
            "palette": cls.palette_reader_projection(stop.palette),
            "applies_from_section_id": stop.applies_from_section_id,
            "transition": stop.transition.value,
        }

    @staticmethod
    def motif_thread_reader_projection(thread: MotifThread) -> dict[str, Any]:
        """Read every motif-thread contract leaf by name."""
        return {
            "motif_id": thread.motif_id,
            "section_ids": list(thread.section_ids),
            "evolution": thread.evolution.value,
            "description": thread.description,
        }

    @classmethod
    def focal_assignment_reader_projection(cls, item: FocalAssignment) -> dict[str, Any]:
        """Read every focal-assignment contract leaf by name."""
        return {
            "section_id": item.section_id,
            "lead_target": cls.target_reader_projection(item.lead_target),
        }

    def _palette_for_role(self, palette_role: PaletteRoleRef) -> PaletteRef:
        if palette_role.override is not None:
            return palette_role.override
        stop = next(item for item in self.palette_arc if item.stop_id == palette_role.stop_id)
        return stop.palette


__all__ = [
    "CallResponsePair",
    "FocalAssignment",
    "FocalRole",
    "FocalRoleKind",
    "MacroPlan",
    "MacroSection",
    "MotifEvolution",
    "MotifThread",
    "PaletteRef",
    "PaletteRoleRef",
    "PaletteStop",
    "PaletteTransition",
]
