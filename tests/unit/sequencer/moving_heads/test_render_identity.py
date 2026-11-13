"""Render identity: a fingerprint of the functional inputs to a moving-head render.

Functional inputs change the hash; key order inside mappings, the order templates are
supplied in, and output paths do not.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel
import pytest

from tests.golden.harness import RIGS, build_beat_grid, build_fixture_group, build_plan
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import JobConfig, MHRenderPolicy, TransitionConfig
from twinklr.core.sequencer.models.template import TemplateDoc
from twinklr.core.sequencer.moving_heads.identity import (
    LEGACY_BACKEND_ID,
    LEGACY_RENDERER_REVISION,
    render_fingerprint,
)
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.moving_heads.templates import get_template, load_builtin_templates
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

load_builtin_templates()


class _PhaseMap(BaseModel):
    """Stand-in for the typed boundary map P1 introduces."""

    boundaries_ms: list[int]


def _templates(plan: ChoreographyPlan) -> list[TemplateDoc]:
    ids = {section.template_id for section in plan.sections if section.template_id}
    return [get_template(template_id) for template_id in sorted(ids)]


def _inputs() -> dict[str, Any]:
    plan = build_plan()
    return {
        "plan": plan,
        "beat_grid": build_beat_grid(),
        "fixtures": build_fixture_group(RIGS["mh4_minimal"]),
        "templates": _templates(plan),
        "policy": MHRenderPolicy(),
        "transitions": TransitionConfig(),
        "backend_id": LEGACY_BACKEND_ID,
        "renderer_revision": LEGACY_RENDERER_REVISION,
    }


def _fingerprint(**overrides: Any) -> str:
    return render_fingerprint(**{**_inputs(), **overrides})


def _edit_template(doc: TemplateDoc, **template_updates: Any) -> TemplateDoc:
    template = doc.template.model_copy(update=template_updates, deep=True)
    return doc.model_copy(update={"template": template}, deep=True)


def test_fingerprint_is_64_hex_and_repeatable() -> None:
    first = _fingerprint()

    assert len(first) == 64
    assert int(first, 16) >= 0
    assert _fingerprint() == first
    assert render_fingerprint(**_inputs()) == first


def test_mapping_key_order_does_not_change_the_hash() -> None:
    templates = _templates(build_plan())
    reordered = [
        _edit_template(doc, defaults=dict(reversed(list(doc.template.defaults.items()))))
        for doc in templates
    ]
    assert list(reordered[0].template.defaults) != list(templates[0].template.defaults)

    assert _fingerprint(templates=reordered) == _fingerprint()


def test_template_supply_order_does_not_change_the_hash() -> None:
    templates = _templates(build_plan())

    assert _fingerprint(templates=list(reversed(templates))) == _fingerprint()


def test_template_content_changes_the_hash() -> None:
    templates = _templates(build_plan())
    first = templates[0]
    steps = [
        step.model_copy(
            update={"dimmer": step.dimmer.model_copy(update={"max_norm": 0.5})}, deep=True
        )
        for step in first.template.steps
    ]
    edited = [_edit_template(first, steps=steps), *templates[1:]]

    assert _fingerprint(templates=edited) != _fingerprint()


def test_preset_content_changes_the_hash() -> None:
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="verse",
                start_bar=1,
                end_bar=4,
                template_id="cascade_pulse_lr",
                preset_id="gentle",
            )
        ]
    )
    doc = get_template("cascade_pulse_lr")
    gentle = next(preset for preset in doc.presets if preset.preset_id == "gentle")
    edited_presets = [
        preset.model_copy(update={"defaults": {**preset.defaults, "extra": 1}}, deep=True)
        if preset is gentle
        else preset
        for preset in doc.presets
    ]
    edited = doc.model_copy(update={"presets": edited_presets}, deep=True)

    assert _fingerprint(plan=plan, templates=[edited]) != _fingerprint(plan=plan, templates=[doc])


def test_fixture_order_changes_the_hash() -> None:
    fixtures = build_fixture_group(RIGS["mh4_minimal"])
    reordered = FixtureGroup.model_validate(
        {**fixtures.model_dump(), "fixtures": list(reversed(fixtures.model_dump()["fixtures"]))}
    )

    assert _fingerprint(fixtures=reordered) != _fingerprint()


def test_policy_changes_the_hash() -> None:
    assert _fingerprint(policy=MHRenderPolicy(mode="physical_v2")) != _fingerprint()


def test_beat_grid_changes_the_hash() -> None:
    faster = BeatGrid.from_tempo(tempo_bpm=121.0, total_bars=32, beats_per_bar=4)

    assert _fingerprint(beat_grid=faster) != _fingerprint()


@pytest.mark.parametrize(
    "override",
    [
        pytest.param({"backend_id": "other_backend"}, id="backend"),
        pytest.param({"renderer_revision": "other_revision"}, id="revision"),
        pytest.param({"seed": 7}, id="seed"),
        pytest.param({"phase_map": _PhaseMap(boundaries_ms=[0, 2000])}, id="phase-map"),
    ],
)
def test_other_functional_inputs_change_the_hash(override: dict[str, Any]) -> None:
    assert _fingerprint(**override) != _fingerprint()


def test_omitted_intent_flag_changes_the_hash() -> None:
    """Two plans that dump identically but differ in legacy intent omission."""
    base = {
        "section_name": "verse",
        "start_bar": 1,
        "end_bar": 4,
        "template_id": "sweep_lr_fan_hold",
        "preset_id": None,
    }
    omitted = ChoreographyPlan(sections=[PlanSection.model_validate(base)])
    explicit = ChoreographyPlan(
        sections=[
            PlanSection.model_validate(
                {
                    **base,
                    **omitted.sections[0].model_dump(include={"intensity", "color_intent"}),
                    "shutter_events": [],
                    "gobo_events": [],
                    "moment_cues": [],
                }
            )
        ]
    )
    assert omitted.sections[0].legacy_intent_omitted
    assert not explicit.sections[0].legacy_intent_omitted
    assert omitted.model_dump() == explicit.model_dump()

    templates = _templates(omitted)
    assert _fingerprint(plan=omitted, templates=templates) != _fingerprint(
        plan=explicit, templates=templates
    )


def test_pipeline_fingerprint_ignores_the_output_path(tmp_path: Path) -> None:
    def pipeline(output_path: Path | None) -> RenderingPipeline:
        return RenderingPipeline(
            choreography_plan=build_plan(),
            beat_grid=build_beat_grid(),
            fixture_group=build_fixture_group(RIGS["mh4_minimal"]),
            job_config=JobConfig(),
            output_path=output_path,
        )

    fingerprint = pipeline(tmp_path / "a" / "show.xsq").fingerprint()

    assert pipeline(tmp_path / "b" / "other.xsq").fingerprint() == fingerprint
    assert pipeline(None).fingerprint() == fingerprint
    assert fingerprint == _fingerprint()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "transitions",
    [
        pytest.param(TransitionConfig(enabled=False), id="disabled"),
        pytest.param(TransitionConfig(default_duration_bars=1.0), id="duration"),
    ],
)
def test_transition_settings_change_the_hash(transitions: TransitionConfig) -> None:
    """Transition settings change the emitted segments, so they are functional."""
    assert _fingerprint(transitions=transitions) != _fingerprint()


def _single_section_pipeline(
    template_id: str, job_config: JobConfig | None = None
) -> RenderingPipeline:
    return RenderingPipeline(
        choreography_plan=ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="verse",
                    start_bar=1,
                    end_bar=4,
                    template_id=template_id,
                    preset_id="chill",
                )
            ]
        ),
        beat_grid=build_beat_grid(),
        fixture_group=build_fixture_group(RIGS["mh4_minimal"]),
        job_config=job_config or JobConfig(),
    )


def test_pipeline_fingerprint_follows_the_transition_settings() -> None:
    disabled = JobConfig.model_validate({"transitions": {"enabled": False}})

    assert (
        _single_section_pipeline("sweep_lr_fan_hold", disabled).fingerprint()
        != _single_section_pipeline("sweep_lr_fan_hold").fingerprint()
    )


@pytest.mark.parametrize(
    ("spelling", "canonical"),
    [
        pytest.param("SWEEP_LR_FAN_HOLD", "sweep_lr_fan_hold", id="upper-case"),
        pytest.param(
            "Wave Vertical Spotlight Fade", "wave_vertical_spotlight_fade", id="display-name"
        ),
    ],
)
def test_template_spelling_does_not_change_the_hash(spelling: str, canonical: str) -> None:
    """The registry resolves every spelling to one template, which renders identically."""
    assert get_template(spelling).template.template_id == canonical

    assert (
        _single_section_pipeline(spelling).fingerprint()
        == _single_section_pipeline(canonical).fingerprint()
    )
