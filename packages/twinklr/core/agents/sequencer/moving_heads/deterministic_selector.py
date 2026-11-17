"""Seeded pure-code planning baseline for the P2P-T13 comparison.

The selector deliberately keeps its small amount of creative policy in one inspectable
configuration object.  It chooses among an explicit candidate set: the run's
:class:`SelectorAdmission`, the templates the pre-planning gate admitted on this rig and
song (the same set the LLM path is offered), each named with its effective variant.  It
emits the planner's :class:`ChoreographyPlan`, with the song intent it can derive from
the section alone (intensity from its energy, a palette-role colour from its role), and
never calls a provider.  When no candidate fills a section at any rung of the fallback ladder
it raises :class:`NoEligibleTemplateError`; the admission is never relaxed.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from enum import StrEnum
import hashlib
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    Density,
    PlanColor,
    PlanPart,
    PlanSection,
    Variation,
)
from twinklr.core.sequencer.models.enum import Intensity, TemplateCategory
from twinklr.core.sequencer.models.template import TemplateDoc
from twinklr.core.sequencer.moving_heads.templates.library import REGISTRY
from twinklr.core.sequencer.vocabulary.visual import PaletteRole

if TYPE_CHECKING:
    from twinklr.core.sequencer.moving_heads.pipeline import TemplateAdmission


class NoEligibleTemplateError(ValueError):
    """No candidate template fills a section at any rung of the fallback ladder, or
    there is no candidate at all; the message names the section, its role and energy,
    and the candidates.

    Raised before any plan is returned, so before any provider call or render that
    plan would feed.  Variety rules relax to make selection total; the candidate set
    (the gate's admission) never does.
    """


class AdmittedTemplate(BaseModel):
    """One template the pre-planning gate admitted, with its effective variant (the
    first passing rung, None for the base) and its admitted presets."""

    template_id: str = Field(min_length=1)
    effective_preset: str | None
    admitted_presets: tuple[str, ...]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def effective_is_admitted(self) -> AdmittedTemplate:
        if self.effective_preset is not None and self.effective_preset not in (
            self.admitted_presets
        ):
            raise ValueError(
                f"template {self.template_id!r}: effective preset {self.effective_preset!r} "
                "is not one of its admitted presets"
            )
        return self


class ExcludedTemplate(BaseModel):
    """A catalog template the gate left out of the offer, with its reason."""

    template_id: str = Field(min_length=1)
    reason: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class SelectorAdmission(BaseModel):
    """The selector's candidate set for one rig and song: the gate's admission
    (`admit_templates`) in its order, and its whole-template exclusions.

    The selector reads only `templates`. `exclusions` is provenance: it records why a
    family is absent, travels in the three-arm `AnalysisSnapshot` and is covered by the
    held-constant `admission_sha256`, so a result can be read against what was left out.
    """

    templates: tuple[AdmittedTemplate, ...]
    exclusions: tuple[ExcludedTemplate, ...] = ()

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def unique_templates(self) -> SelectorAdmission:
        seen: set[str] = set()
        for entry in self.templates:
            if entry.template_id in seen:
                raise ValueError(f"template {entry.template_id!r} is admitted twice")
            seen.add(entry.template_id)
        return self

    @property
    def template_ids(self) -> tuple[str, ...]:
        return tuple(entry.template_id for entry in self.templates)

    @classmethod
    def from_gate(cls, admission: TemplateAdmission) -> SelectorAdmission:
        """Project the gate's result onto the selector's frozen candidate set."""
        return cls(
            templates=tuple(
                AdmittedTemplate(
                    template_id=template_id,
                    effective_preset=admission.effective_preset[template_id],
                    admitted_presets=admission.admitted_presets[template_id],
                )
                for template_id in admission.admitted
            ),
            exclusions=tuple(
                ExcludedTemplate(template_id=entry["template_id"], reason=entry["reason"])
                for entry in admission.exclusions
            ),
        )


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
    """The plan plus the selector policy and auditable choice trace."""

    plan: ChoreographyPlan
    config: SelectorConfig
    traces: list[SelectionTrace]

    model_config = ConfigDict(extra="forbid", frozen=True)


class DeterministicSelector:
    """Select template documents by role/energy, then apply seeded constraints."""

    def __init__(
        self,
        *,
        seed: int,
        config: SelectorConfig | None = None,
        admission: SelectorAdmission,
    ) -> None:
        """Choose among `admission`'s templates, each named with its effective variant.

        The admitted templates' documents are read from the registry, which holds them for
        the run the gate checked (and only with the annotations the ladder reads).

        Raises:
            NoEligibleTemplateError: When there is no candidate at all.
        """
        self.seed = seed
        self.config = config or SelectorConfig()
        template_ids = list(admission.template_ids)
        self._presets = {entry.template_id: entry.effective_preset for entry in admission.templates}
        self._documents = {
            template_id: REGISTRY.get(template_id, deep_copy=False) for template_id in template_ids
        }
        if not self._documents:
            raise NoEligibleTemplateError(
                "The deterministic selector requires at least one template"
            )

    def candidates_for(self, section: SelectorSection) -> CandidateSet:
        """Return the first non-empty rung of the fixed fallback ladder.

        Raises:
            NoEligibleTemplateError: When every rung is empty.
        """
        for rule in self.config.fallback_order:
            candidates = self._candidates_at_rule(section, rule)
            if candidates:
                return CandidateSet(rule=rule, template_ids=tuple(candidates))
        raise self._no_candidate(section)

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
                # Fully relaxed variety admits every candidate, so every rung was empty.
                raise self._no_candidate(section)

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

    def _no_candidate(self, section: SelectorSection) -> NoEligibleTemplateError:
        candidates = sorted(self._documents)
        rungs = ", ".join(rule.value for rule in self.config.fallback_order)
        return NoEligibleTemplateError(
            f"no candidate template fits section {section.section_id!r} (role "
            f"{section.role!r}, energy {section.energy}) at any rung ({rungs}) among "
            f"{candidates}; the candidate set is not relaxed"
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
        """One part naming the template with its effective variant; the intensity its
        energy gives and the palette-role colour its role gives. The selector has no
        lyrics, macro motifs or boundaries to read, so the rest of the song intent stays
        as authored and is reported unresolved."""
        template = document.template
        unresolved = (
            "gobo",
            "moment_cues",
            "events",
            "motif_id",
            "variation",
            "density",
            "transitions",
        )
        planned = PlanSection(
            section_id=section.section_id,
            start_bar=section.start_bar,
            end_bar=section.end_bar,
            section_role=section.role,
            energy_level=section.energy,
            parts=[
                PlanPart(
                    start_bar=section.start_bar,
                    template_id=template.template_id,
                    preset_id=self._presets[template.template_id],
                    modifiers=[],
                    label=None,
                    reasoning="",
                )
            ],
            intensity=self._intensity(section.energy),
            color=PlanColor(f"PALETTE_{self._palette_role(section.role).value}"),
            gobo=None,
            moment_cues=[],
            events=[],
            motif_id=None,
            variation=Variation.NONE,
            density=Density.BALANCED,
            transitions=[],
            reasoning=(
                "Deterministic annotation join with seeded choice; "
                f"role={section.role}, energy={section.energy}"
            ),
        )
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
