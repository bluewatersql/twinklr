"""P2P-T13 deterministic selector acceptance tests."""

from __future__ import annotations

from collections import Counter
from itertools import pairwise
from types import SimpleNamespace

import pytest

from twinklr.core.agents.sequencer.moving_heads.deterministic_selector import (
    ConstraintRelaxation,
    DeterministicSelector,
    FallbackRule,
    SelectorSection,
    selector_sections_from_context,
)
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.sequencer.models.context import SectionRenderIntent
from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.compile.intent_resolution import apply_template_intent
from twinklr.core.sequencer.moving_heads.templates import load_builtin_templates
from twinklr.core.sequencer.moving_heads.templates.library import REGISTRY


@pytest.fixture(scope="module", autouse=True)
def _load_templates() -> None:
    load_builtin_templates()


def _section(role: str, energy: int, index: int = 1) -> SelectorSection:
    return SelectorSection(
        section_id=f"{role}_{index}",
        role=role,
        start_bar=(index - 1) * 4 + 1,
        end_bar=index * 4,
        energy=energy,
    )


def test_selector_candidate_filter_and_fallback_ladder() -> None:
    selector = DeterministicSelector(seed=13)

    candidates = selector.candidates_for(_section("chorus", 70))
    assert candidates.rule is FallbackRule.ROLE_AND_ENERGY
    assert candidates.template_ids == (
        "bounce_fan_pulse",
        "build_drop_recover",
        "circle_asym_right_pulse",
        "crossfade_between_steps",
        "dual_sweep_audience_pulse",
        "fan_pulse",
        "intro_main_outro_phrase",
        "sweep_lr_chevron_breathe",
        "sweep_lr_fan_pulse",
        "zigzag_alternating_pulse",
    )

    fallback = selector.candidates_for(_section("unlisted_role", 0))
    assert fallback.rule is FallbackRule.CATEGORY
    assert fallback.template_ids


def test_selector_is_seeded_and_schema_v2() -> None:
    sections = [
        _section(role, energy, index)
        for index, (role, energy) in enumerate(
            [("intro", 10), ("verse", 35), ("build", 65), ("chorus", 80), ("outro", 30)],
            start=1,
        )
    ]

    first = DeterministicSelector(seed=90210).select(sections)
    second = DeterministicSelector(seed=90210).select(sections)

    assert first.plan.model_dump(mode="json") == second.plan.model_dump(mode="json")
    assert ChoreographyPlan.model_validate_json(first.plan.model_dump_json()) == first.plan
    for section in first.plan.sections:
        assert section.intensity is not None
        assert section.color_intent is not None
        assert section.shutter_events is not None
        assert section.gobo_events is not None
        assert section.legacy_intent_omitted is False


def test_selector_v2_intensity_reaches_renderer_intent_seam() -> None:
    section = DeterministicSelector(seed=17).select([_section("drop", 100)]).plan.sections[0]
    assert section.intensity is Intensity.INTENSE
    assert section.legacy_intent_omitted is False
    source = REGISTRY.get(section.template_id or "").template
    slow_steps = [
        step.model_copy(
            update={
                "movement": step.movement.model_copy(
                    update={"intensity": Intensity.SLOW}, deep=True
                ),
                "dimmer": step.dimmer.model_copy(update={"intensity": Intensity.SLOW}, deep=True),
            },
            deep=True,
        )
        for step in source.steps
    ]
    rendered = apply_template_intent(
        source.model_copy(update={"steps": slow_steps}, deep=True),
        SectionRenderIntent(intensity=section.intensity),
    )
    assert all(step.movement.intensity is Intensity.INTENSE for step in rendered.steps)
    assert all(step.dimmer.intensity is Intensity.INTENSE for step in rendered.steps)


@pytest.mark.parametrize(
    "role",
    [
        "verse",
        "chorus",
        "drop",
        "build",
        "peak",
        "bridge",
        "intro",
        "breakdown",
        "groove",
        "outro",
        "ambient",
        "lift",
    ],
)
@pytest.mark.parametrize("energy", [0, 5, 30, 50, 80, 100])
def test_selector_always_produces_a_plan(role: str, energy: int) -> None:
    result = DeterministicSelector(seed=7).select([_section(role, energy)])
    assert len(result.plan.sections) == 1
    assert result.plan.sections[0].template_id


def test_variety_constraints_hold() -> None:
    sections = [
        _section(role, energy, index)
        for index, (role, energy) in enumerate(
            [
                ("verse", 45),
                ("verse", 45),
                ("chorus", 70),
                ("verse", 45),
                ("build", 60),
                ("chorus", 70),
                ("drop", 90),
                ("outro", 40),
            ],
            start=1,
        )
    ]
    result = DeterministicSelector(seed=22).select(sections)
    choices = [section.template_id for section in result.plan.sections]
    assert all(left != right for left, right in pairwise(choices))
    assert max(Counter(choices).values()) <= result.config.max_uses_per_template

    role_choices: dict[str, set[str]] = {}
    for source, choice in zip(sections, choices, strict=True):
        role_choices.setdefault(source.role, set()).add(choice or "")
    for left_role, left_choices in role_choices.items():
        for right_role, right_choices in role_choices.items():
            if left_role != right_role:
                assert left_choices.isdisjoint(right_choices)


def test_selector_relaxes_constraints_deterministically_for_long_songs() -> None:
    sections = [_section("verse", 45, index) for index in range(1, 81)]
    first = DeterministicSelector(seed=8080).select(sections)
    second = DeterministicSelector(seed=8080).select(sections)
    assert len(first.plan.sections) == 80
    assert first.plan == second.plan
    assert first.traces == second.traces
    assert any(trace.relaxed_constraints for trace in first.traces)
    assert any(
        ConstraintRelaxation.REPEAT_CAP in trace.relaxed_constraints for trace in first.traces
    )


def test_selector_context_projection_converts_fractional_energy_and_uses_resolved_bars() -> None:
    context = SimpleNamespace(
        audio_profile=SimpleNamespace(
            energy_profile=SimpleNamespace(
                section_profiles=[SimpleNamespace(section_id="chorus_1", mean_energy=0.704)]
            )
        ),
        for_prompt=lambda: {
            "song_structure": {
                "sections": [
                    {
                        "section_id": "chorus_1",
                        "name": "chorus",
                        "start_bar": 9,
                        "end_bar": 16,
                    }
                ]
            }
        },
    )

    assert selector_sections_from_context(context) == [
        SelectorSection(section_id="chorus_1", role="chorus", start_bar=9, end_bar=16, energy=70)
    ]
