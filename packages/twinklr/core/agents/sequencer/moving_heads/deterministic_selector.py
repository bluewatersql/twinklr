"""Seeded pure-code planning baseline for the P2P-T13 comparison.

The selector deliberately keeps its small amount of creative policy in one inspectable
configuration object.  It reads the same template documents exposed to the LLM path,
emits today's schema-v2 :class:`ChoreographyPlan`, and never calls a provider.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from enum import StrEnum
import hashlib
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    ColorIntent,
    ColorIntentKind,
    ExplicitColorIntent,
    GoboEvent,
    PaletteRoleColorIntent,
    PlanSection,
    ShutterEvent,
)
from twinklr.core.sequencer.models.enum import Intensity, TemplateCategory
from twinklr.core.sequencer.models.template import TemplateDoc
from twinklr.core.sequencer.moving_heads.templates import load_builtin_templates
from twinklr.core.sequencer.moving_heads.templates.library import REGISTRY
from twinklr.core.sequencer.vocabulary.visual import PaletteRole


class FallbackRule(StrEnum):
    """Ordered candidate sources required by the experiment protocol."""

    ROLE_AND_ENERGY = "role_and_energy"
    ENERGY_ONLY = "energy_only"
    ROLE_ONLY = "role_only"
    CATEGORY = "category"


class ConstraintRelaxation(StrEnum):
    """Deterministic last-resort relaxations which make the fallback total."""

    DISTINCT_ROLES = "distinct_roles_use_distinct_templates"
    REPEAT_CAP = "max_uses_per_template"
    CONSECUTIVE_REPEAT = "no_consecutive_repeats"


class SelectorSection(BaseModel):
    """One authoritative section projected into deterministic planning inputs."""

    section_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    start_bar: int = Field(ge=1)
    end_bar: int = Field(ge=1)
    energy: int = Field(ge=0, le=100)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def ordered_bars(self) -> SelectorSection:
        if self.end_bar < self.start_bar:
            raise ValueError("end_bar must be greater than or equal to start_bar")
        return self


class SelectorConfig(BaseModel):
    """The baseline arm's complete, configurable creative policy."""

    fallback_order: tuple[FallbackRule, ...] = (
        FallbackRule.ROLE_AND_ENERGY,
        FallbackRule.ENERGY_ONLY,
        FallbackRule.ROLE_ONLY,
        FallbackRule.CATEGORY,
    )
    no_consecutive_repeats: bool = True
    max_uses_per_template: int = Field(default=2, ge=1)
    distinct_roles_use_distinct_templates: bool = True
    relaxation_order: tuple[ConstraintRelaxation, ...] = (
        ConstraintRelaxation.DISTINCT_ROLES,
        ConstraintRelaxation.REPEAT_CAP,
        ConstraintRelaxation.CONSECUTIVE_REPEAT,
    )
    low_energy_ceiling: int = Field(default=33, ge=0, le=98)
    medium_energy_ceiling: int = Field(default=66, ge=1, le=99)
    intensity_cutoffs: tuple[int, int, int, int] = (25, 50, 70, 85)
    accent_roles: tuple[str, ...] = ("chorus", "drop", "peak", "build", "lift")
    neutral_roles: tuple[str, ...] = ("intro", "outro", "ambient")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def complete_policy(self) -> SelectorConfig:
        if self.fallback_order != (
            FallbackRule.ROLE_AND_ENERGY,
            FallbackRule.ENERGY_ONLY,
            FallbackRule.ROLE_ONLY,
            FallbackRule.CATEGORY,
        ):
            raise ValueError("fallback_order must preserve the fixed P2P-T13 ladder")
        if self.low_energy_ceiling >= self.medium_energy_ceiling:
            raise ValueError("energy category ceilings must be strictly increasing")
        if tuple(sorted(self.intensity_cutoffs)) != self.intensity_cutoffs:
            raise ValueError("intensity_cutoffs must be ordered")
        if self.relaxation_order != (
            ConstraintRelaxation.DISTINCT_ROLES,
            ConstraintRelaxation.REPEAT_CAP,
            ConstraintRelaxation.CONSECUTIVE_REPEAT,
        ):
            raise ValueError("relaxation_order must preserve the total deterministic policy")
        return self


class CandidateSet(BaseModel):
    """Observable candidate result before seeded variety selection."""

    rule: FallbackRule
    template_ids: tuple[str, ...]

    model_config = ConfigDict(extra="forbid", frozen=True)


class SelectionTrace(BaseModel):
    """Why one deterministic section choice was made."""

    section_id: str
    role: str
    energy: int
    fallback_rule: FallbackRule
    eligible_template_ids: tuple[str, ...]
    selected_template_id: str
    unresolved_intent_fields: tuple[str, ...]
    relaxed_constraints: tuple[ConstraintRelaxation, ...] = ()

    model_config = ConfigDict(extra="forbid", frozen=True)


class SelectorResult(BaseModel):
    """Schema-v2 plan plus the selector policy and auditable choice trace."""

    plan: ChoreographyPlan
    config: SelectorConfig
    traces: list[SelectionTrace]

    model_config = ConfigDict(extra="forbid", frozen=True)


class DeterministicSelector:
    """Select template documents by role/energy, then apply seeded constraints."""

    def __init__(self, *, seed: int, config: SelectorConfig | None = None) -> None:
        self.seed = seed
        self.config = config or SelectorConfig()
        load_builtin_templates()
        self._documents = {
            info.template_id: REGISTRY.get(info.template_id, deep_copy=False)
            for info in REGISTRY.list_all()
        }
        if not self._documents:
            raise ValueError("The deterministic selector requires at least one template")

    def candidates_for(self, section: SelectorSection) -> CandidateSet:
        """Return the first non-empty rung of the fixed fallback ladder."""
        for rule in self.config.fallback_order:
            candidates = self._candidates_at_rule(section, rule)
            if candidates:
                return CandidateSet(rule=rule, template_ids=tuple(candidates))
        raise AssertionError("category fallback must cover a non-empty template registry")

    def select(self, sections: list[SelectorSection]) -> SelectorResult:
        """Produce one complete current-schema plan for the supplied song sections."""
        if not sections:
            raise ValueError("At least one section is required")
        uses: Counter[str] = Counter()
        roles_by_template: dict[str, set[str]] = defaultdict(set)
        previous: str | None = None
        plan_sections: list[PlanSection] = []
        traces: list[SelectionTrace] = []

        for section in sections:
            chosen: str | None = None
            chosen_rule: FallbackRule | None = None
            eligible: list[str] = []
            relaxed: tuple[ConstraintRelaxation, ...] = ()
            relaxation_levels = [
                self.config.relaxation_order[:count]
                for count in range(len(self.config.relaxation_order) + 1)
            ]
            for relaxation in relaxation_levels:
                for rule in self.config.fallback_order:
                    raw = self._candidates_at_rule(section, rule)
                    eligible = [
                        template_id
                        for template_id in raw
                        if self._variety_allows(
                            template_id,
                            role=section.role,
                            previous=previous,
                            uses=uses,
                            roles_by_template=roles_by_template,
                            relaxed=frozenset(relaxation),
                        )
                    ]
                    if eligible:
                        chosen_rule = rule
                        chosen = min(
                            eligible,
                            key=lambda template_id: self._seeded_order_key(
                                section.section_id, template_id
                            ),
                        )
                        relaxed = relaxation
                        break
                if chosen is not None:
                    break
            if chosen is None or chosen_rule is None:
                raise AssertionError("fully relaxed category fallback must be total")

            uses[chosen] += 1
            roles_by_template[chosen].add(section.role)
            previous = chosen
            document = self._documents[chosen]
            plan_section, unresolved = self._build_plan_section(section, document)
            plan_sections.append(plan_section)
            traces.append(
                SelectionTrace(
                    section_id=section.section_id,
                    role=section.role,
                    energy=section.energy,
                    fallback_rule=chosen_rule,
                    eligible_template_ids=tuple(eligible),
                    selected_template_id=chosen,
                    unresolved_intent_fields=unresolved,
                    relaxed_constraints=relaxed,
                )
            )

        return SelectorResult(
            plan=ChoreographyPlan(
                sections=plan_sections,
                overall_strategy=(
                    f"P2P-T13 deterministic baseline/fallback/regression arm; seed={self.seed}"
                ),
            ),
            config=self.config,
            traces=traces,
        )

    def _candidates_at_rule(self, section: SelectorSection, rule: FallbackRule) -> list[str]:
        category = self._category(section.energy)
        matches: list[str] = []
        for template_id, document in self._documents.items():
            template = document.template
            metadata = template.metadata
            assert metadata is not None and metadata.energy_range is not None
            role_match = section.role.lower() in {
                value.lower() for value in metadata.recommended_sections
            }
            energy_match = metadata.energy_range[0] <= section.energy <= metadata.energy_range[1]
            include = {
                FallbackRule.ROLE_AND_ENERGY: role_match and energy_match,
                FallbackRule.ENERGY_ONLY: energy_match,
                FallbackRule.ROLE_ONLY: role_match,
                FallbackRule.CATEGORY: template.category is category,
            }[rule]
            if include:
                matches.append(template_id)
        return sorted(matches)

    def _variety_allows(
        self,
        template_id: str,
        *,
        role: str,
        previous: str | None,
        uses: Counter[str],
        roles_by_template: dict[str, set[str]],
        relaxed: frozenset[ConstraintRelaxation] = frozenset(),
    ) -> bool:
        if (
            self.config.no_consecutive_repeats
            and ConstraintRelaxation.CONSECUTIVE_REPEAT not in relaxed
            and template_id == previous
        ):
            return False
        if (
            ConstraintRelaxation.REPEAT_CAP not in relaxed
            and uses[template_id] >= self.config.max_uses_per_template
        ):
            return False
        existing_roles = roles_by_template[template_id]
        return not (
            self.config.distinct_roles_use_distinct_templates
            and ConstraintRelaxation.DISTINCT_ROLES not in relaxed
            and existing_roles
            and role not in existing_roles
        )

    def _build_plan_section(
        self, section: SelectorSection, document: TemplateDoc
    ) -> tuple[PlanSection, tuple[str, ...]]:
        template = document.template
        first_color = next((step.color for step in template.steps if step.color is not None), None)
        first_shutter = next(
            (step.shutter for step in template.steps if step.shutter is not None), None
        )
        first_gobo = next((step.gobo for step in template.steps if step.gobo is not None), None)

        if first_color is not None:
            color_intent = ColorIntent(
                selection=ExplicitColorIntent(
                    kind=ColorIntentKind.EXPLICIT,
                    palette_role=None,
                    explicit_color=first_color.preset,
                )
            )
        else:
            color_intent = ColorIntent(
                selection=PaletteRoleColorIntent(
                    kind=ColorIntentKind.PALETTE_ROLE,
                    palette_role=self._palette_role(section.role),
                    explicit_color=None,
                )
            )

        shutter_events = (
            [
                ShutterEvent(
                    bar=section.start_bar,
                    beat=1,
                    pattern=first_shutter.pattern,
                    moment_cue_id=None,
                )
            ]
            if first_shutter is not None
            else []
        )
        gobo_events = (
            [
                GoboEvent(
                    bar=section.start_bar,
                    beat=1,
                    pattern=first_gobo.pattern,
                    moment_cue_id=None,
                )
            ]
            if first_gobo is not None
            else []
        )
        unresolved = tuple(
            name
            for name, value in (("shutter_events", first_shutter), ("gobo_events", first_gobo))
            if value is None
        )
        planned = PlanSection(
            section_name=section.section_id,
            start_bar=section.start_bar,
            end_bar=section.end_bar,
            section_role=section.role,
            energy_level=section.energy,
            template_id=template.template_id,
            preset_id=None,
            modifiers=[],
            reasoning=(
                "Deterministic annotation join with seeded choice; "
                f"role={section.role}, energy={section.energy}"
            ),
            segments=None,
            transition_in=None,
            transition_out=None,
            intensity=self._intensity(section.energy),
            color_intent=color_intent,
            shutter_events=shutter_events,
            gobo_events=gobo_events,
            moment_cues=[],
        )
        if planned.legacy_intent_omitted:
            raise AssertionError("selector must explicitly construct every schema-v2 intent field")
        return planned, unresolved

    def _seeded_order_key(self, section_id: str, template_id: str) -> str:
        payload = f"{self.seed}:{section_id}:{template_id}".encode()
        return hashlib.sha256(payload).hexdigest()

    def _category(self, energy: int) -> TemplateCategory:
        if energy <= self.config.low_energy_ceiling:
            return TemplateCategory.LOW_ENERGY
        if energy <= self.config.medium_energy_ceiling:
            return TemplateCategory.MEDIUM_ENERGY
        return TemplateCategory.HIGH_ENERGY

    def _intensity(self, energy: int) -> Intensity:
        low, smooth, fast, dramatic = self.config.intensity_cutoffs
        if energy <= low:
            return Intensity.SLOW
        if energy <= smooth:
            return Intensity.SMOOTH
        if energy <= fast:
            return Intensity.FAST
        if energy <= dramatic:
            return Intensity.DRAMATIC
        return Intensity.INTENSE

    def _palette_role(self, role: str) -> PaletteRole:
        lowered = role.lower()
        if lowered in self.config.accent_roles:
            return PaletteRole.ACCENT
        if lowered in self.config.neutral_roles:
            return PaletteRole.NEUTRAL
        return PaletteRole.PRIMARY


def selector_sections_from_context(context: Any) -> list[SelectorSection]:
    """Project current planning context bars and 0-1 energy into selector inputs.

    The audio-profile energy contract is fractional while ``PlanSection.energy_level``
    and template annotations are 0-100.  This is the single explicit conversion seam.
    Bar positions come from ``MovingHeadPlanningContext.for_prompt()``, which already
    resolves against the renderer's authoritative BeatGrid.
    """
    prompt = context.for_prompt()
    prompt_sections = prompt["song_structure"]["sections"]
    profiles: Sequence[Any] = context.audio_profile.energy_profile.section_profiles
    energy_by_id = {
        str(profile.section_id): max(0, min(100, round(float(profile.mean_energy) * 100)))
        for profile in profiles
    }
    missing = [
        str(section["section_id"])
        for section in prompt_sections
        if str(section["section_id"]) not in energy_by_id
    ]
    if missing:
        raise ValueError(f"sections missing authoritative energy profiles: {missing}")
    return [
        SelectorSection(
            section_id=str(section["section_id"]),
            role=str(section["name"]),
            start_bar=int(section["start_bar"]),
            end_bar=max(int(section["start_bar"]), int(section["end_bar"])),
            energy=energy_by_id[str(section["section_id"])],
        )
        for section in prompt_sections
    ]
