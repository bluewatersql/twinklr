"""P0-T4 restrained reference arm tests."""

from __future__ import annotations

import hashlib

import pytest

from twinklr.core.agents.sequencer.moving_heads.deterministic_selector import (
    DeterministicSelector,
    SelectorSection,
)
from twinklr.core.agents.sequencer.moving_heads.reference_policy import (
    ReferenceSelectionResult,
    build_reference_plan,
)
from twinklr.core.sequencer.moving_heads.templates import load_builtin_templates
from twinklr.core.sequencer.moving_heads.templates.library import REGISTRY

QUIET = "hold_center_out_breathe"
CHORUS = "sweep_lr_pingpong_phase"
ENTRY = "sweep_lr_fan_hold"
ENDING = "wave_scattered_fade_out"


@pytest.fixture(scope="module", autouse=True)
def _load_templates() -> None:
    load_builtin_templates()


def _all_templates() -> frozenset[str]:
    return frozenset(info.template_id for info in REGISTRY.list_all())


def _section(role: str, energy: int, index: int) -> SelectorSection:
    return SelectorSection(
        section_id=f"{role.lower()}_{index}",
        role=role,
        start_bar=(index - 1) * 4 + 1,
        end_bar=index * 4,
        energy=energy,
    )


def _sections(*specs: tuple[str, int]) -> list[SelectorSection]:
    return [_section(role, energy, index) for index, (role, energy) in enumerate(specs, start=1)]


def _seeded_key(seed: int, section_id: str, template_id: str) -> str:
    return hashlib.sha256(f"{seed}:{section_id}:{template_id}".encode()).hexdigest()


def test_preferred_choices_follow_the_declared_precedence() -> None:
    sections = _sections(
        ("intro", 10),  # quiet
        ("verse", 50),  # no preference
        ("build", 10),  # entry emphasis outranks quiet
        ("Chorus", 20),  # chorus outranks quiet; roles compare case-insensitively
        ("drop", 90),  # chorus template
        ("lift", 60),  # entry emphasis
        ("peak", 95),  # chorus template
        ("chorus", 80),  # final section: ending outranks chorus
    )

    result = build_reference_plan(sections, seed=41, admitted_template_ids=_all_templates())

    assert isinstance(result, ReferenceSelectionResult)
    assert [decision.preferred_template_id for decision in result.decisions] == [
        QUIET,
        None,
        ENTRY,
        CHORUS,
        CHORUS,
        ENTRY,
        CHORUS,
        ENDING,
    ]
    verse = result.decisions[1]
    assert verse.reason == "baseline"
    assert verse.selected_template_id == result.baseline.traces[1].selected_template_id
    preferred = [decision for index, decision in enumerate(result.decisions) if index != 1]
    assert all(decision.reason == "preferred" for decision in preferred)
    assert all(
        decision.selected_template_id == decision.preferred_template_id for decision in preferred
    )
    assert [section.template_id for section in result.plan.sections] == [
        decision.selected_template_id for decision in result.decisions
    ]
    assert [decision.section_id for decision in result.decisions] == [
        section.section_id for section in sections
    ]


def test_quiet_preference_stops_at_the_energy_ceiling() -> None:
    sections = _sections(("verse", 33), ("verse", 34), ("outro", 40))

    result = build_reference_plan(sections, seed=41, admitted_template_ids=_all_templates())

    assert [decision.preferred_template_id for decision in result.decisions[:2]] == [QUIET, None]


def test_plan_is_labelled_as_the_reference_arm_not_the_old_experiment() -> None:
    result = build_reference_plan(
        _sections(("verse", 50), ("outro", 40)), seed=314, admitted_template_ids=_all_templates()
    )

    assert result.seed == 314
    assert result.policy_revision == "reference.v1"
    assert "reference_legacy_v1" in result.plan.overall_strategy
    assert "seed=314" in result.plan.overall_strategy
    assert "P2P-T13" not in result.plan.overall_strategy
    assert result.baseline.plan.overall_strategy.startswith("P2P-T13")


def test_identical_seed_and_input_reproduce_the_same_result() -> None:
    sections = _sections(("intro", 10), ("verse", 45), ("chorus", 75), ("bridge", 40))

    first = build_reference_plan(sections, seed=7, admitted_template_ids=_all_templates())
    second = build_reference_plan(sections, seed=7, admitted_template_ids=_all_templates())

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_third_chorus_still_receives_the_chorus_template() -> None:
    sections = _sections(
        ("chorus", 70),
        ("verse", 45),
        ("chorus", 70),
        ("verse", 45),
        ("chorus", 70),
        ("outro", 40),
    )

    result = build_reference_plan(sections, seed=22, admitted_template_ids=_all_templates())

    choruses = [result.decisions[index] for index in (0, 2, 4)]
    assert [decision.selected_template_id for decision in choruses] == [CHORUS] * 3
    assert all(decision.reason == "preferred" for decision in choruses)
    # The frozen selector's repeat cap would not have allowed this.
    assert result.baseline.config.max_uses_per_template < 3


def test_filtered_out_preference_falls_back_to_the_baseline_choice() -> None:
    sections = _sections(("verse", 45), ("chorus", 70), ("outro", 40))
    baseline = DeterministicSelector(seed=5).select(sections)
    baseline_choice = baseline.traces[1].selected_template_id
    assert baseline_choice != CHORUS

    result = build_reference_plan(
        sections, seed=5, admitted_template_ids=_all_templates() - {CHORUS}
    )

    decision = result.decisions[1]
    assert decision.preferred_template_id == CHORUS
    assert decision.reason == "baseline"
    assert decision.selected_template_id == baseline_choice
    assert result.plan.sections[1] == baseline.plan.sections[1]


def test_unadmitted_baseline_choice_falls_back_to_seeded_eligible_order() -> None:
    sections = _sections(("verse", 45), ("chorus", 70), ("outro", 40))
    baseline = DeterministicSelector(seed=5).select(sections)
    trace = baseline.traces[1]
    admitted = _all_templates() - {CHORUS, trace.selected_template_id}
    expected = min(
        (template_id for template_id in trace.eligible_template_ids if template_id in admitted),
        key=lambda template_id: _seeded_key(5, trace.section_id, template_id),
    )

    result = build_reference_plan(sections, seed=5, admitted_template_ids=admitted)

    decision = result.decisions[1]
    assert decision.preferred_template_id == CHORUS
    assert decision.reason == "seeded_fallback"
    assert decision.selected_template_id == expected
    planned = result.plan.sections[1]
    assert planned.template_id == expected
    assert planned.section_name == trace.section_id
    assert planned.legacy_intent_omitted is False


def test_no_eligible_template_names_the_section() -> None:
    sections = _sections(("verse", 45), ("bridge", 40))

    with pytest.raises(ValueError, match="verse_1"):
        build_reference_plan(sections, seed=3, admitted_template_ids=frozenset())


def test_admitted_templates_outside_the_eligible_list_do_not_rescue_a_section() -> None:
    sections = _sections(("verse", 45), ("bridge", 40))
    baseline = DeterministicSelector(seed=3).select(sections)
    admitted = _all_templates() - set(baseline.traces[1].eligible_template_ids) - {ENDING}
    assert set(baseline.traces[0].eligible_template_ids) & admitted

    with pytest.raises(ValueError, match="bridge_2"):
        build_reference_plan(sections, seed=3, admitted_template_ids=admitted)


@pytest.mark.parametrize(
    ("seed", "specs", "expected_choices"),
    [
        (
            90210,
            (("intro", 10), ("verse", 35), ("build", 65), ("chorus", 80), ("outro", 30)),
            (
                "tilt_rock_wall_wash_fade",
                "pendulum_chevron_breathe",
                "crossfade_between_steps",
                "circle_asym_right_pulse",
                "wave_vertical_spotlight_fade",
            ),
        ),
        (
            22,
            (
                ("verse", 45),
                ("verse", 45),
                ("chorus", 70),
                ("verse", 45),
                ("build", 60),
                ("chorus", 70),
                ("drop", 90),
                ("outro", 40),
            ),
            (
                "sweep_lr_continuous_phase",
                "cascade_pulse_lr",
                "bounce_fan_pulse",
                "sweep_lr_fan_hold",
                "sweep_ud_chevron_swell",
                "build_drop_recover",
                "figure8_mirror_strobe",
                "wave_scattered_fade_out",
            ),
        ),
        (17, (("drop", 100),), ("figure8_mirror_strobe",)),
    ],
)
def test_existing_selector_output_is_unchanged_for_its_original_inputs(
    seed: int, specs: tuple[tuple[str, int], ...], expected_choices: tuple[str, ...]
) -> None:
    """Inputs are the selector suite's own; choices were recorded at 577bf06."""
    sections = [
        SelectorSection(
            section_id=f"{role}_{index}",
            role=role,
            start_bar=(index - 1) * 4 + 1,
            end_bar=index * 4,
            energy=energy,
        )
        for index, (role, energy) in enumerate(specs, start=1)
    ]
    before = DeterministicSelector(seed=seed).select(sections)

    result = build_reference_plan(sections, seed=seed, admitted_template_ids=_all_templates())

    after = DeterministicSelector(seed=seed).select(sections)
    assert result.baseline == before
    assert after == before
    assert tuple(section.template_id for section in before.plan.sections) == expected_choices
    assert before.plan.overall_strategy == (
        f"P2P-T13 deterministic baseline/fallback/regression arm; seed={seed}"
    )
