"""Restrained reference arm composed over the frozen deterministic selector.

The arm prefers four existing templates by a declared precedence and otherwise keeps the
selector's own choice.  It wraps, and never alters, the P2P-T13 experiment selector:
the baseline result is kept verbatim and this module owns all preference provenance.
It is a restrained comparison over existing templates, not a reproduction of xLights'
envelopes, and it never calls a provider.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from twinklr.core.agents.sequencer.moving_heads.deterministic_selector import (
    DeterministicSelector,
    SelectorResult,
    SelectorSection,
)
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection

REFERENCE_ARM_ID = "reference_legacy_v1"

QUIET_TEMPLATE_ID = "hold_center_out_breathe"
CHORUS_TEMPLATE_ID = "sweep_lr_pingpong_phase"
ENTRY_TEMPLATE_ID = "sweep_lr_fan_hold"
ENDING_TEMPLATE_ID = "wave_scattered_fade_out"

CHORUS_ROLES = frozenset({"chorus", "drop", "peak"})
ENTRY_ROLES = frozenset({"build", "lift"})
QUIET_ENERGY_CEILING = 33


class ReferenceSelectionDecision(BaseModel):
    """Which template the reference arm chose for one section, and by which step."""

    section_id: str
    preferred_template_id: str | None
    selected_template_id: str
    reason: Literal["preferred", "baseline", "seeded_fallback"]

    model_config = ConfigDict(extra="forbid", frozen=True)


class ReferenceSelectionResult(BaseModel):
    """Reference plan plus the untouched baseline and per-section provenance."""

    plan: ChoreographyPlan
    baseline: SelectorResult
    decisions: tuple[ReferenceSelectionDecision, ...]
    seed: int
    policy_revision: Literal["reference.v1"] = "reference.v1"

    model_config = ConfigDict(extra="forbid", frozen=True)


def _preferred_template_id(section: SelectorSection, *, is_final: bool) -> str | None:
    role = section.role.lower()
    if is_final:
        return ENDING_TEMPLATE_ID
    if role in CHORUS_ROLES:
        return CHORUS_TEMPLATE_ID
    if role in ENTRY_ROLES:
        return ENTRY_TEMPLATE_ID
    if section.energy <= QUIET_ENERGY_CEILING:
        return QUIET_TEMPLATE_ID
    return None


def build_reference_plan(
    sections: list[SelectorSection],
    *,
    seed: int,
    admitted_template_ids: frozenset[str],
) -> ReferenceSelectionResult:
    """Select each section's template by the declared reference precedence.

    Per section: an admitted, registered preferred template; else the baseline's choice
    if admitted; else the baseline's traced eligible templates that are admitted, in the
    selector's seeded order.  No admitted candidate raises ``ValueError``.
    """
    selector = DeterministicSelector(seed=seed)
    baseline = selector.select(sections)
    documents = selector._documents

    decisions: list[ReferenceSelectionDecision] = []
    plan_sections: list[PlanSection] = []
    for index, (section, trace) in enumerate(zip(sections, baseline.traces, strict=True)):
        preferred = _preferred_template_id(section, is_final=index == len(sections) - 1)
        reason: Literal["preferred", "baseline", "seeded_fallback"]
        if preferred is not None and preferred in documents and preferred in admitted_template_ids:
            selected, reason = preferred, "preferred"
        elif trace.selected_template_id in admitted_template_ids:
            selected, reason = trace.selected_template_id, "baseline"
        else:
            fallback = [
                template_id
                for template_id in trace.eligible_template_ids
                if template_id in admitted_template_ids
            ]
            if not fallback:
                raise ValueError(
                    f"No admitted template is eligible for section {section.section_id!r}"
                )
            selected = min(
                fallback,
                key=lambda template_id: selector._seeded_order_key(section.section_id, template_id),
            )
            reason = "seeded_fallback"

        plan_section, _ = selector._build_plan_section(section, documents[selected])
        plan_sections.append(plan_section)
        decisions.append(
            ReferenceSelectionDecision(
                section_id=section.section_id,
                preferred_template_id=preferred,
                selected_template_id=selected,
                reason=reason,
            )
        )

    return ReferenceSelectionResult(
        plan=ChoreographyPlan(
            sections=plan_sections,
            overall_strategy=f"{REFERENCE_ARM_ID} restrained reference arm; seed={seed}",
        ),
        baseline=baseline,
        decisions=tuple(decisions),
        seed=seed,
    )
