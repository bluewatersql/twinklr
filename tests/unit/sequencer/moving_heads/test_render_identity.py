"""Render identity: a fingerprint of the functional inputs to a moving-head render.

Functional inputs change the hash; key order inside mappings, the order templates are
supplied in, and output paths do not.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel
import pytest

from tests.support.mh_physical import (
    family_job,
    family_rig,
    initial_state_payload,
    physical_bars_grid,
    physical_catalog,
    physical_sections,
)
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import JobConfig, MHRenderPolicy
from twinklr.core.sequencer.models.template import StepPatch, TemplateDoc
from twinklr.core.sequencer.moving_heads.export.frame_encoder import ENCODER_VERSION
from twinklr.core.sequencer.moving_heads.identity import (
    LEGACY_BACKEND_ID,
    PHYSICAL_RENDERER_REVISION,
    render_fingerprint,
)
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.moving_heads.templates import get_template
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import build_musical_phase_map

HEADS = ("MH1", "MH2", "MH3", "MH4")


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    with physical_catalog():
        yield


class _PhaseMap(BaseModel):
    """Stand-in for a typed boundary map."""

    boundaries_ms: list[int]


def _plan() -> ChoreographyPlan:
    return physical_sections(("mirror_wings", 1, 4), ("target_orbit", 5, 8))


def _grid() -> BeatGrid:
    return physical_bars_grid(*([500.0] * 8))


def _templates(plan: ChoreographyPlan) -> list[TemplateDoc]:
    ids = {section.template_id for section in plan.sections if section.template_id}
    return [get_template(template_id) for template_id in sorted(ids)]


def _inputs() -> dict[str, Any]:
    """What `RenderingPipeline.fingerprint` hashes for `_pipeline()`."""
    plan = _plan()
    return {
        "plan": plan,
        "beat_grid": _grid(),
        "fixtures": family_rig(HEADS),
        "templates": _templates(plan),
        "policy": family_job(HEADS).moving_heads,
        "backend_id": LEGACY_BACKEND_ID,
        "renderer_revision": f"physical_v2.{PHYSICAL_RENDERER_REVISION}+encoder.{ENCODER_VERSION}",
        "phase_map": build_musical_phase_map(_grid()),
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
    fixtures = family_rig(HEADS)
    payload = fixtures.model_dump(mode="python")
    flick = payload["presets"]["attributes"]["flick"]
    flick["fixtures"] = dict(reversed(list(flick["fixtures"].items())))
    reordered = FixtureGroup.model_validate(payload)
    assert list(reordered.presets.attributes["flick"].fixtures) != list(
        fixtures.presets.attributes["flick"].fixtures
    )

    assert _fingerprint(fixtures=reordered) == _fingerprint()


def test_template_supply_order_does_not_change_the_hash() -> None:
    templates = _templates(_plan())

    assert _fingerprint(templates=list(reversed(templates))) == _fingerprint()


def test_template_content_changes_the_hash() -> None:
    templates = _templates(_plan())
    first = templates[0]
    steps = []
    for step in first.template.steps:
        movement = step.movement.physical
        assert movement is not None and movement.period_beats is not None
        slower = movement.model_copy(update={"period_beats": movement.period_beats * 2})
        steps.append(
            step.model_copy(
                update={"movement": step.movement.model_copy(update={"physical": slower})},
                deep=True,
            )
        )
    edited = [_edit_template(first, steps=steps), *templates[1:]]

    assert _fingerprint(templates=edited) != _fingerprint()


def test_preset_content_changes_the_hash() -> None:
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="verse",
                start_bar=1,
                end_bar=4,
                template_id="mirror_wings",
                preset_id="narrow",
            )
        ]
    )
    doc = get_template("mirror_wings")
    narrow = next(preset for preset in doc.presets if preset.preset_id == "narrow")
    patch = StepPatch(movement={"physical": {"pan_extent_deg": 21.0, "tilt_extent_deg": 10.0}})
    edited_presets = [
        preset.model_copy(update={"step_patches": {"wings": patch}}, deep=True)
        if preset is narrow
        else preset
        for preset in doc.presets
    ]
    assert narrow.step_patches["wings"] != patch
    edited = doc.model_copy(update={"presets": edited_presets}, deep=True)

    assert _fingerprint(plan=plan, templates=[edited]) != _fingerprint(plan=plan, templates=[doc])


def test_fixture_order_changes_the_hash() -> None:
    fixtures = family_rig(HEADS)
    reordered = FixtureGroup.model_validate(
        {**fixtures.model_dump(), "fixtures": list(reversed(fixtures.model_dump()["fixtures"]))}
    )

    assert _fingerprint(fixtures=reordered) != _fingerprint()


def test_policy_changes_the_hash() -> None:
    policy = family_job(HEADS, reposition_fallback="drop_accent").moving_heads

    assert _fingerprint(policy=policy) != _fingerprint()


def test_physical_profile_and_initial_states_change_the_hash() -> None:
    """Physical inputs are functional; an empty policy dumps no initial states."""
    assert "initial_states" not in MHRenderPolicy().model_dump(mode="json")

    payload = family_rig(HEADS).model_dump(mode="python")
    payload["fixtures"][0]["config"]["physical_profile"]["axes"]["pan"]["settle_ms"] = 80
    profiled = FixtureGroup.model_validate(payload)
    started = MHRenderPolicy.model_validate({"initial_states": {"MH1": initial_state_payload()}})

    assert _fingerprint(fixtures=profiled) != _fingerprint()
    assert _fingerprint(policy=started) != _fingerprint()


def test_beat_grid_changes_the_hash() -> None:
    faster = physical_bars_grid(*([495.0] * 8))

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
        "template_id": "mirror_wings",
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
        return _pipeline(_plan(), output_path=output_path)

    fingerprint = pipeline(tmp_path / "a" / "show.xsq").fingerprint()

    assert pipeline(tmp_path / "b" / "other.xsq").fingerprint() == fingerprint
    assert pipeline(None).fingerprint() == fingerprint
    assert fingerprint == _fingerprint()
    assert not list(tmp_path.iterdir())


def _pipeline(
    plan: ChoreographyPlan, *, output_path: Path | None = None, job: JobConfig | None = None
) -> RenderingPipeline:
    return RenderingPipeline(
        choreography_plan=plan,
        beat_grid=_grid(),
        fixture_group=family_rig(HEADS),
        job_config=job or family_job(HEADS),
        output_path=output_path,
    )


def _single_section_pipeline(template_id: str) -> RenderingPipeline:
    return _pipeline(
        ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="verse",
                    start_bar=1,
                    end_bar=4,
                    template_id=template_id,
                )
            ]
        )
    )


@pytest.mark.parametrize(
    ("spelling", "canonical"),
    [
        pytest.param("MIRROR_WINGS", "mirror_wings", id="upper-case"),
        pytest.param("Fly-In Cascade", "fly_in_cascade", id="display-name"),
    ],
)
def test_template_spelling_does_not_change_the_hash(spelling: str, canonical: str) -> None:
    """The registry resolves every spelling to one template, which renders identically."""
    assert get_template(spelling).template.template_id == canonical

    assert (
        _single_section_pipeline(spelling).fingerprint()
        == _single_section_pipeline(canonical).fingerprint()
    )
