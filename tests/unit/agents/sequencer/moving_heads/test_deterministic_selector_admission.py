"""The deterministic selector over the gate's admitted set (cutover C1.1d)."""

from __future__ import annotations

from collections.abc import Iterator
import hashlib
from itertools import pairwise
import random

import pytest

from tests.support.mh_physical import CATALOG_IDS, physical_catalog
from twinklr.core.agents.sequencer.moving_heads.deterministic_selector import (
    AdmittedTemplate,
    DeterministicSelector,
    FallbackRule,
    NoEligibleTemplateError,
    SelectorAdmission,
    SelectorSection,
)
from twinklr.core.sequencer.moving_heads.pipeline import TemplateAdmission
from twinklr.core.sequencer.moving_heads.templates.library import REGISTRY

LOW_ENERGY_FAMILIES = ("target_orbit", "zoom_wave")
"""The catalog's `low_energy` families. A zoomless rig loses `zoom_wave`; revision 1 lost
the orbit too in 3/4 (inventory F7)."""


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    with physical_catalog():
        yield


def _admission(
    template_ids: tuple[str, ...], effective: dict[str, str | None] | None = None
) -> SelectorAdmission:
    effective = effective or {}
    return SelectorAdmission(
        templates=tuple(
            AdmittedTemplate(
                template_id=template_id,
                effective_preset=effective.get(template_id),
                admitted_presets=("narrow", "slow"),
            )
            for template_id in template_ids
        )
    )


def _section(role: str, energy: int, index: int) -> SelectorSection:
    return SelectorSection(
        section_id=f"{role}_{index}",
        role=role,
        start_bar=(index - 1) * 4 + 1,
        end_bar=index * 4,
        energy=energy,
    )


def _sections(*specs: tuple[str, int]) -> list[SelectorSection]:
    return [_section(role, energy, index) for index, (role, energy) in enumerate(specs, start=1)]


def test_selects_only_admitted_families_with_their_effective_variant() -> None:
    """Across random songs, every section names an admitted family and that family's
    effective variant, which is always one of its admitted presets or the base."""
    admitted = ("finite_snap_hold", "masked_wheel_flick", "mirror_wings", "target_orbit")
    admission = _admission(admitted, {"mirror_wings": "narrow", "target_orbit": "slow"})
    rng = random.Random(1116)
    roles = ["intro", "verse", "chorus", "build", "drop", "bridge", "outro", "groove"]
    for _ in range(50):
        sections = [
            _section(rng.choice(roles), rng.randrange(20, 101), index)
            for index in range(1, rng.randrange(2, 20))
        ]
        result = DeterministicSelector(seed=rng.randrange(10**6), admission=admission).select(
            sections
        )
        for planned, trace in zip(result.plan.sections, result.traces, strict=True):
            assert planned.template_id in admitted
            assert set(trace.eligible_template_ids) <= set(admitted)
            entry = next(t for t in admission.templates if t.template_id == planned.template_id)
            assert planned.preset_id == entry.effective_preset
            assert planned.preset_id in (None, *entry.admitted_presets)
            assert planned.legacy_intent_omitted is False


def test_the_whole_registry_is_not_the_candidate_set() -> None:
    """With the catalog and the 37 builtins registered, the candidates are the admission."""
    selector = DeterministicSelector(seed=3, admission=_admission(("mirror_wings",)))
    candidates = selector.candidates_for(_section("verse", 45, 1))
    assert candidates.template_ids == ("mirror_wings",)
    assert candidates.rule is FallbackRule.ROLE_AND_ENERGY


def test_capability_exclusions_are_never_relaxed_to_make_selection_total() -> None:
    """Variety rules relax (in their fixed order) when the admitted set is small; the
    admission does not: the chorus never borrows the excluded or the role-bound family."""
    admission = _admission(("finite_snap_hold", "target_orbit"))
    sections = _sections(*([("verse", 45)] + [("chorus", 85)] * 6))

    result = DeterministicSelector(seed=11, admission=admission).select(sections)

    choices = [section.template_id for section in result.plan.sections]
    assert choices == ["target_orbit"] + ["finite_snap_hold"] * 6
    assert any(trace.relaxed_constraints for trace in result.traces)
    assert all(
        set(trace.eligible_template_ids) <= {"finite_snap_hold", "target_orbit"}
        for trace in result.traces
    )


def test_a_section_no_rung_can_fill_raises_the_typed_error() -> None:
    """F7: a quiet intro when both low-energy families are excluded matches no admitted
    family by role and energy, energy, role or category; the ladder ends in a typed
    error naming the section, not an assertion and not a borrowed family."""
    admitted = tuple(t for t in CATALOG_IDS if t not in LOW_ENERGY_FAMILIES)
    selector = DeterministicSelector(seed=5, admission=_admission(admitted))
    sections = _sections(("verse", 50), ("intro", 10))

    with pytest.raises(NoEligibleTemplateError, match="intro_2") as raised:
        selector.select(sections)
    message = str(raised.value)
    assert "role 'intro', energy 10" in message
    assert str(sorted(admitted)) in message
    assert isinstance(raised.value, ValueError)

    with pytest.raises(NoEligibleTemplateError, match="intro_2"):
        selector.candidates_for(sections[1])


def test_an_empty_admission_raises_the_typed_error() -> None:
    with pytest.raises(NoEligibleTemplateError):
        DeterministicSelector(seed=5, admission=SelectorAdmission(templates=()))


def test_same_inputs_same_plan_and_trace_with_a_sha256_tie_break() -> None:
    admission = _admission(("finite_snap_hold", "mirror_wings"), {"mirror_wings": "slow"})
    sections = _sections(("chorus", 80), ("verse", 50), ("chorus", 80))

    first = DeterministicSelector(seed=90210, admission=admission).select(sections)
    second = DeterministicSelector(seed=90210, admission=admission).select(sections)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    trace = first.traces[0]
    assert trace.eligible_template_ids == ("finite_snap_hold", "mirror_wings")
    expected = min(
        trace.eligible_template_ids,
        key=lambda t: hashlib.sha256(f"90210:chorus_1:{t}".encode()).hexdigest(),
    )
    assert trace.selected_template_id == expected


def test_trace_candidates_are_sorted_whatever_the_admission_order() -> None:
    """The gate lists families in its own order; rungs and traces list them sorted, so
    the trace does not depend on admission order."""
    admission = _admission(("mirror_wings", "fly_out_cascade", "finite_snap_hold"))
    section = _section("chorus", 85, 1)
    sorted_ids = ("finite_snap_hold", "fly_out_cascade", "mirror_wings")

    selector = DeterministicSelector(seed=7, admission=admission)

    assert selector.candidates_for(section).template_ids == sorted_ids
    assert selector.select([section]).traces[0].eligible_template_ids == sorted_ids


@pytest.mark.parametrize("seed", range(20))
def test_variety_holds_under_an_admission_without_relaxing(seed: int) -> None:
    """With enough admitted families for each role, no rule relaxes: no consecutive
    repeat, at most two uses per family, and distinct roles use distinct families."""
    admission = _admission(tuple(t for t in CATALOG_IDS if t != "zoom_wave"))
    roles = ["verse", "verse", "chorus", "chorus", "verse", "chorus", "verse", "chorus"]
    sections = _sections(*((role, 45 if role == "verse" else 85) for role in roles))

    result = DeterministicSelector(seed=seed, admission=admission).select(sections)

    choices = [section.template_id for section in result.plan.sections]
    assert all(trace.relaxed_constraints == () for trace in result.traces)
    assert all(left != right for left, right in pairwise(choices))
    assert max(choices.count(choice) for choice in choices) <= 2
    by_role = {
        role: {c for r, c in zip(roles, choices, strict=True) if r == role} for role in roles
    }
    assert not by_role["verse"] & by_role["chorus"]


def test_a_reprise_reuses_the_admitted_family_the_ladder_gives_its_role() -> None:
    """Returning choruses and verses keep their families: each role's only admitted
    role-and-energy match, within the repeat cap and without consecutive repeats."""
    admission = _admission(("finite_snap_hold", "target_orbit"), {"finite_snap_hold": "narrow"})
    sections = _sections(("verse", 45), ("chorus", 85), ("verse", 45), ("chorus", 85))

    result = DeterministicSelector(seed=42, admission=admission).select(sections)

    assert [(s.template_id, s.preset_id) for s in result.plan.sections] == [
        ("target_orbit", None),
        ("finite_snap_hold", "narrow"),
        ("target_orbit", None),
        ("finite_snap_hold", "narrow"),
    ]
    assert all(trace.fallback_rule is FallbackRule.ROLE_AND_ENERGY for trace in result.traces)
    assert all(trace.relaxed_constraints == () for trace in result.traces)


def test_admission_from_the_gate_keeps_order_variants_and_exclusions() -> None:
    gate = TemplateAdmission(
        admitted=("mirror_wings", "finite_snap_hold"),
        admitted_presets={"mirror_wings": ("slow",), "finite_snap_hold": ("narrow", "slow")},
        effective_preset={"mirror_wings": "slow", "finite_snap_hold": None},
        exclusions=({"template_id": "zoom_wave", "reason": "no zoom axis"},),
        preset_exclusions=(
            {"template_id": "mirror_wings", "preset_id": None, "reason": "too fast"},
        ),
        entry_dips={},
    )

    admission = SelectorAdmission.from_gate(gate)

    assert admission.template_ids == ("mirror_wings", "finite_snap_hold")
    assert admission.templates[0] == AdmittedTemplate(
        template_id="mirror_wings", effective_preset="slow", admitted_presets=("slow",)
    )
    assert admission.templates[1].effective_preset is None
    assert [(e.template_id, e.reason) for e in admission.exclusions] == [
        ("zoom_wave", "no zoom axis")
    ]


@pytest.mark.parametrize("template_id", CATALOG_IDS)
def test_a_family_yields_the_palette_role_intent_and_no_step_derived_events(
    template_id: str,
) -> None:
    """The step colour, shutter and gobo derivation has nothing to read on a family
    (physical steps carry none of those fields), so a family's section always gets the
    role's palette colour and no events: removing that derivation with the old
    templates (C1.2) cannot change a physical plan."""
    metadata = REGISTRY.get(template_id).template.metadata
    assert metadata is not None and metadata.energy_range is not None
    section = _section(metadata.recommended_sections[0], metadata.energy_range[0], 1)
    result = DeterministicSelector(seed=1, admission=_admission((template_id,))).select([section])

    [planned] = result.plan.sections
    assert planned.template_id == template_id
    selection = planned.color_intent.selection
    assert selection.kind == "PALETTE_ROLE"
    assert selection.palette_role is not None and selection.explicit_color is None
    assert planned.shutter_events == [] and planned.gobo_events == []
    assert result.traces[0].unresolved_intent_fields == ("shutter_events", "gobo_events")


def test_admission_rejects_an_unadmitted_effective_variant_and_duplicates() -> None:
    with pytest.raises(ValueError, match="effective"):
        AdmittedTemplate(template_id="mirror_wings", effective_preset="slow", admitted_presets=())
    entry = AdmittedTemplate(template_id="mirror_wings", effective_preset=None, admitted_presets=())
    with pytest.raises(ValueError, match="mirror_wings"):
        SelectorAdmission(templates=(entry, entry))
