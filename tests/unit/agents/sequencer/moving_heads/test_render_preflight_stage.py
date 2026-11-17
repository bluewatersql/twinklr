"""The render preflight: a physical job that cannot render is refused right after audio
analysis, before the profile, lyrics, macro and moving-head planners spend anything."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager, nullcontext
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.support.mh_physical import (
    FAMILY_IDS,
    PHYSICAL_INITIAL_STATE,
    SUBSET_TEMPLATE_ID,
    TEMPLATE_DIR,
    TEMPLATE_ID,
    family_job,
    family_rig,
    hold_step,
    physical_bars_grid,
    physical_catalog,
    physical_grid,
    physical_job,
    physical_rig,
    physical_sections,
    physical_template_doc,
    physical_test_templates,
    registered_templates,
    unprofiled_rig,
)
from twinklr.core.agents.audio.lyrics.stage import LyricsStage
from twinklr.core.agents.audio.profile.stage import AudioProfileStage
from twinklr.core.agents.audio.stages.analysis import AudioAnalysisStage
from twinklr.core.agents.sequencer.macro_planner.stage import MacroPlannerStage
from twinklr.core.agents.sequencer.moving_heads.rendering_stage import (
    MovingHeadRenderingStage,
    RenderPreflightStage,
)
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.formats.xlights.layout.models.rgb_effects import Model
from twinklr.core.pipeline import PipelineExecutor
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.definitions.moving_heads import build_moving_heads_pipeline
from twinklr.core.pipeline.result import success_result
from twinklr.core.sequencer.models.template import TemplateDoc
from twinklr.core.sequencer.moving_heads.templates.data_loader import load_template_document
from twinklr.core.sequencer.moving_heads.templates.library import REGISTRY
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

_BUNDLE = object()


def _context(job: JobConfig, beat_grid: BeatGrid | None = None) -> PipelineContext:
    session = MagicMock()
    session.job_config = job
    context = PipelineContext(session=session)
    if beat_grid is not None:
        context.set_state("beat_grid", beat_grid)
    return context


async def _run(
    job: JobConfig, *, templates: list[str], rig: Any, beat_grid: BeatGrid | None = None
) -> tuple[Any, PipelineContext]:
    stage = RenderPreflightStage(available_templates=templates)
    context = _context(job, beat_grid)
    with patch(
        "twinklr.core.agents.sequencer.moving_heads.rendering_stage.load_render_fixture_group",
        return_value=rig,
    ):
        result = await stage.execute(_BUNDLE, context)
    return result, context


def _long_tail_grid() -> BeatGrid:
    """The physical grid with two silent seconds after its last observed beat."""
    grid = physical_grid()
    return grid.model_copy(update={"duration_ms": grid.duration_ms + 2000})


@pytest.mark.asyncio
async def test_physical_job_on_a_rig_without_profiles_is_refused() -> None:
    with physical_test_templates():
        result, _ = await _run(
            physical_job(),
            templates=[TEMPLATE_ID],
            rig=unprofiled_rig(),
            beat_grid=physical_grid(),
        )

    assert not result.success
    assert "MH1: physical_profile is missing" in (result.error or "")


@pytest.mark.asyncio
async def test_physical_job_offered_a_template_without_physical_data_is_refused() -> None:
    no_physical = TemplateDoc.model_validate(
        {
            "template": {
                "template_id": "no_physical_data",
                "version": 1,
                "name": "No Physical Data",
                "category": "medium_energy",
                "repeat": {"cycle_bars": 1.0, "loop_step_ids": ["main"]},
                "steps": [
                    {
                        "step_id": "main",
                        "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 1}},
                        "geometry": {},
                        "movement": {"movement_type": "sweep_lr"},
                        "dimmer": {"dimmer_type": "hold"},
                    }
                ],
                "metadata": {"energy_range": [20, 60], "recommended_sections": ["verse"]},
            }
        }
    )
    with physical_test_templates(), registered_templates(no_physical):
        result, _ = await _run(
            physical_job(),
            templates=[TEMPLATE_ID, "no_physical_data"],
            rig=physical_rig(),
            beat_grid=physical_grid(),
        )

    assert not result.success
    assert "without physical data" in (result.error or "")
    assert "no_physical_data" in (result.error or "")


@pytest.mark.asyncio
async def test_physical_job_whose_song_has_an_uncovered_tail_is_accepted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Two silent seconds after the last beat are outside the covered span: the render
    holds the heads dark there instead of inferring tempo, so the job passes and the
    gate logs the span it will cover."""
    with physical_test_templates(), caplog.at_level("INFO"):
        result, _ = await _run(
            physical_job(),
            templates=[TEMPLATE_ID],
            rig=physical_rig(),
            beat_grid=_long_tail_grid(),
        )

    assert result.success, result.error
    # One 400 ms interval past the last beat at 3615 ms; the song runs to 5615 ms.
    assert "covers the span [0.0, 4015.0] ms of the song's [0, 5615.0] ms" in caplog.text


@pytest.mark.asyncio
async def test_physical_job_whose_grid_has_one_beat_is_refused() -> None:
    """One observed beat gives no interval to measure phase by; nothing is inferred."""
    grid = physical_grid()
    one_beat = grid.model_copy(
        update={
            "bar_boundaries": grid.bar_boundaries[:1],
            "beat_boundaries": grid.beat_boundaries[:1],
            "eighth_boundaries": grid.eighth_boundaries[:1],
            "sixteenth_boundaries": grid.sixteenth_boundaries[:1],
        }
    )
    with physical_test_templates():
        result, _ = await _run(
            physical_job(), templates=[TEMPLATE_ID], rig=physical_rig(), beat_grid=one_beat
        )

    assert not result.success
    assert "musical phase" in (result.error or "")
    assert "no adjacent observed interval" in (result.error or "")


@pytest.mark.asyncio
async def test_prepared_physical_job_passes_and_shares_its_beat_grid() -> None:
    grid = physical_grid()
    with physical_test_templates():
        result, context = await _run(
            physical_job(),
            templates=[TEMPLATE_ID, SUBSET_TEMPLATE_ID],
            rig=physical_rig(),
            beat_grid=grid,
        )

    assert result.success, result.error
    assert result.output is _BUNDLE
    assert context.get_state("beat_grid") is grid


def test_moving_heads_pipeline_gates_every_planner_behind_the_preflight() -> None:
    """Profile and lyrics read the audio through the preflight; macro and moving-head
    planning follow them, so no planner starts before it passes."""
    pipeline = build_moving_heads_pipeline(
        display_groups=[{"id": "MH", "role_key": "MH", "model_count": 2, "group_type": "mh"}],
        fixture_count=2,
        available_templates=[TEMPLATE_ID],
        xsq_output_path=Path("/tmp/unused.xsq"),
    )
    stages = {stage.id: stage for stage in pipeline.stages}

    assert stages["render_preflight"].inputs == ["audio"]
    assert stages["profile"].inputs == ["render_preflight"]
    assert stages["lyrics"].inputs == ["render_preflight"]
    preflight = stages["render_preflight"].stage
    assert isinstance(preflight, RenderPreflightStage)
    assert preflight.available_templates == [TEMPLATE_ID]
    assert pipeline.validate_pipeline() == []


_VARIANT_ID = "p1_preflight_variant"


@contextmanager
def _variant(step_update: dict[str, Any] | None = None, presets: list[dict] | None = None):
    """Register a copy of the test template, with one step change or extra presets."""
    document = load_template_document(TEMPLATE_DIR / f"{TEMPLATE_ID}.json")
    payload = document.model_dump(mode="json")
    payload["template"].update(template_id=_VARIANT_ID, name="P1 Preflight Variant")
    payload["template"]["steps"][0].update(step_update or {})
    payload["presets"] = presets or []
    REGISTRY.register_document(TemplateDoc.model_validate(payload))
    try:
        yield
    finally:
        REGISTRY._remove_registration(_VARIANT_ID)


def _rig_with(change: Callable[[dict[str, Any]], None]) -> FixtureGroup:
    """`physical_rig` with the same edit applied to both heads' profiles."""
    payload = physical_rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        change(fixture["config"]["physical_profile"])
    return FixtureGroup.model_validate(payload)


def _rename_open_state(profile: dict[str, Any]) -> None:
    shutter = profile["discrete"]["shutter"]
    shutter["states"]["lit"] = shutter["states"].pop("open")
    shutter["open_state"] = "lit"


def _remove_gobo(profile: dict[str, Any]) -> None:
    del profile["discrete"]["gobo"]


def _job_without_gobo() -> JobConfig:
    """`physical_job` whose initial states name no gobo, for a rig that has none."""
    state = {
        **PHYSICAL_INITIAL_STATE,
        "discrete_states": {"shutter": "closed", "color": "white"},
    }
    return physical_job(initial_states={"MH1": state, "MH2": state})


_TILT_OUT_OF_RANGE = {
    "movement": {
        "physical": {
            "shape": "hold",
            "mode": "periodic",
            "start_pan_deg": 0.0,
            "start_tilt_deg": 200.0,
        }
    }
}
_LEGACY_PRESET = [
    {
        "preset_id": "SNAPPY",
        "name": "Snappy",
        "step_patches": {"reveal": {"movement": {"intensity": "FAST"}}},
    }
]

_CASES = [
    pytest.param(
        lambda: nullcontext(),
        lambda: _rig_with(_rename_open_state),
        physical_job,
        TEMPLATE_ID,
        [f"template '{TEMPLATE_ID}'", "step 'reveal'", "fixture 'MH1'", "state 'open'"],
        id="renamed-shutter-state",
    ),
    pytest.param(
        lambda: _variant({"physical_gobo": "open"}),
        lambda: _rig_with(_remove_gobo),
        _job_without_gobo,
        _VARIANT_ID,
        [f"template '{_VARIANT_ID}'", "step 'reveal'", "fixture 'MH1'", "no gobo channel"],
        id="undeclared-discrete-channel",
    ),
    pytest.param(
        lambda: _variant(_TILT_OUT_OF_RANGE),
        physical_rig,
        physical_job,
        _VARIANT_ID,
        [f"template '{_VARIANT_ID}'", "step 'reveal'", "fixture 'MH1'", "tilt", "200"],
        id="axis-target-out-of-bounds",
    ),
    pytest.param(
        lambda: _variant(presets=_LEGACY_PRESET),
        physical_rig,
        physical_job,
        _VARIANT_ID,
        [f"template '{_VARIANT_ID}'", "step 'reveal'", "preset 'SNAPPY'", "movement.intensity"],
        id="preset-adds-legacy-data",
    ),
]


@pytest.mark.parametrize(("template", "rig", "job", "template_id", "expected"), _CASES)
@pytest.mark.asyncio
async def test_template_the_rig_cannot_render_is_refused_before_planning(
    template: Callable[[], Any],
    rig: Callable[[], FixtureGroup],
    job: Callable[[], JobConfig],
    template_id: str,
    expected: list[str],
) -> None:
    """The gate dry-compiles every offered template, and each preset, on the real rig;
    a template that would fail at render is refused before any planner runs."""
    planners = {
        name: AsyncMock(side_effect=AssertionError(f"{name} planned"))
        for name in ("AudioProfileStage", "LyricsStage", "MacroPlannerStage", "MovingHeadStage")
    }
    grid = physical_grid()

    async def analyzed(self: Any, input: Any, context: PipelineContext) -> Any:
        context.set_state("beat_grid", grid)
        context.set_state("has_lyrics", True)
        return success_result(_BUNDLE, stage_name="audio")

    pipeline = build_moving_heads_pipeline(
        display_groups=[{"id": "MH", "role_key": "MH", "model_count": 2, "group_type": "mh"}],
        fixture_count=2,
        available_templates=[template_id],
        xsq_output_path=Path("/tmp/unused.xsq"),
    )
    context = _context(job())
    context.set_state("live_fixture_group", rig())
    with (
        physical_test_templates(),
        template(),
        patch.object(AudioAnalysisStage, "execute", analyzed),
        patch.object(AudioProfileStage, "execute", planners["AudioProfileStage"]),
        patch.object(LyricsStage, "execute", planners["LyricsStage"]),
        patch.object(MacroPlannerStage, "execute", planners["MacroPlannerStage"]),
        patch.object(MovingHeadStage, "execute", planners["MovingHeadStage"]),
    ):
        result = await PipelineExecutor().execute(pipeline, "song.wav", context)

    assert not result.success
    assert result.failed_stages == ["render_preflight"]
    error = result.stage_results["render_preflight"].error or ""
    for item in expected:
        assert item in error, (item, error)
    for planner in planners.values():
        planner.assert_not_awaited()


_JUMP_ID = "p24a_preflight_jump"


def _jump_template(fallback: str | None) -> TemplateDoc:
    """Two lit steps per cycle back to back at -90 and +90 degrees: the second cannot
    continue the first, whatever the plan does around the template."""
    extra = {} if fallback is None else {"physical_reposition_fallback": fallback}
    return physical_template_doc(
        _JUMP_ID,
        [
            hold_step("left", -90.0, duration=0.5, **extra),
            hold_step("right", 90.0, start=0.5, duration=0.5, **extra),
        ],
    )


@pytest.mark.parametrize(
    ("declared", "policy", "admitted"),
    [
        pytest.param("drop_accent", None, False, id="error-policy-refuses"),
        pytest.param(None, "drop_accent", False, id="undeclared-fallback-refuses"),
        pytest.param("drop_accent", "drop_accent", True, id="declared-fallback-admits"),
    ],
)
@pytest.mark.asyncio
async def test_template_whose_own_cycles_cannot_reposition_is_refused_before_planning(
    declared: str | None, policy: str | None, admitted: bool
) -> None:
    """The gate plans the dark repositioning between a template's own cues: under the
    default `error` a template that cannot reposition inside itself is refused before
    any planner runs; under a fallback the template declares, it is admitted."""
    job = physical_job(reposition_fallback=policy) if policy else physical_job()
    with physical_test_templates(), registered_templates(_jump_template(declared)):
        result, _ = await _run(
            job, templates=[_JUMP_ID], rig=physical_rig(), beat_grid=physical_grid()
        )

    assert result.success is admitted, result.error
    if not admitted:
        error = result.error or ""
        assert f"template {_JUMP_ID!r}" in error
        assert "repositioning" in error and "jumps across the cue" in error


_HEADS = ("MH1", "MH2", "MH3", "MH4")
_FAMILY_GRID = physical_bars_grid(500.0, 500.0, 430.0, 500.0)
_NO_TOPOLOGY = "declares no topology"
_NO_FLICK = "attribute preset 'flick', which the fixture group does not declare"


@pytest.mark.parametrize(
    ("topology", "excluded"),
    [
        pytest.param(True, {"masked_wheel_flick": _NO_FLICK}, id="preset-less"),
        pytest.param(
            False,
            {
                "fly_in_cascade": _NO_TOPOLOGY,
                "fly_out_cascade": _NO_TOPOLOGY,
                "masked_wheel_flick": _NO_FLICK,
                "mirror_wings": _NO_TOPOLOGY,
            },
            id="preset-and-topology-less",
        ),
    ],
)
@pytest.mark.asyncio
async def test_rig_is_offered_every_family_it_can_render_and_told_why_not_the_rest(
    topology: bool, excluded: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    """A catalog family the rig cannot render is left out of the offer with its reason;
    the run goes on with the rest, which the gate publishes for the planner, logging
    each exclusion and each admitted family's worst-case entry dip."""
    with physical_catalog(), caplog.at_level("INFO"):
        result, context = await _run(
            family_job(_HEADS),
            templates=list(FAMILY_IDS),
            rig=family_rig(_HEADS, topology=topology, presets=False),
            beat_grid=_FAMILY_GRID,
        )

    assert result.success, result.error
    admission = context.get_state("template_admission")
    assert admission.admitted == tuple(t for t in FAMILY_IDS if t not in excluded)
    reasons = {exclusion["template_id"]: exclusion["reason"] for exclusion in admission.exclusions}
    assert reasons.keys() == excluded.keys()
    for template_id, needle in excluded.items():
        assert needle in reasons[template_id], reasons[template_id]
        assert f"template {template_id!r} is left out of the planner's offer" in caplog.text
    assert admission.entry_dips.keys() == set(admission.admitted)
    for template_id in admission.admitted:
        assert f"template {template_id!r} enters a section dark for up to" in caplog.text


@pytest.mark.asyncio
async def test_a_rig_without_a_shutter_state_named_open_is_offered_only_the_cascades() -> None:
    """Four families hold the shutter in the state named `open`; a profile that names
    its open state otherwise leaves them out, naming the missing state. The cascades
    open the shutter through the profile's `open_state` and stay."""
    payload = family_rig(_HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        _rename_open_state(fixture["config"]["physical_profile"])
    with physical_catalog():
        result, context = await _run(
            family_job(_HEADS),
            templates=list(FAMILY_IDS),
            rig=FixtureGroup.model_validate(payload),
            beat_grid=_FAMILY_GRID,
        )

    assert result.success, result.error
    admission = context.get_state("template_admission")
    assert admission.admitted == ("fly_in_cascade", "fly_out_cascade")
    assert len(admission.exclusions) == 4
    for exclusion in admission.exclusions:
        assert "state 'open'" in exclusion["reason"], exclusion


@pytest.mark.asyncio
async def test_render_stage_records_the_gates_exclusions_in_the_trace(tmp_path: Path) -> None:
    rig = family_rig(_HEADS, presets=False)
    with physical_catalog():
        _, context = await _run(
            family_job(_HEADS), templates=list(FAMILY_IDS), rig=rig, beat_grid=_FAMILY_GRID
        )
        context.set_state("live_fixture_group", rig)
        stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "show.xsq")
        result = await stage.execute(
            {"moving_heads": physical_sections(("target_orbit", 1, 2))}, context
        )

    assert result.success, result.error
    trace = json.loads((tmp_path / "show.xsq.trace.json").read_text(encoding="utf-8"))
    [exclusion] = trace["render"]["admission_exclusions"]
    assert exclusion["template_id"] == "masked_wheel_flick"
    assert _NO_FLICK in exclusion["reason"]
    assert "admission_preset_exclusions" not in trace["render"]  # none: left out


@pytest.mark.asyncio
async def test_rig_that_can_render_no_family_is_refused() -> None:
    """Every family aims above a 5° tilt limit: none remains, so the run is refused,
    naming each family and why."""
    payload = family_rig(_HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        tilt = fixture["config"]["physical_profile"]["axes"]["tilt"]
        tilt.update(physical_min=-5.0, physical_max=5.0)
    with physical_catalog():
        result, context = await _run(
            family_job(_HEADS),
            templates=list(FAMILY_IDS),
            rig=FixtureGroup.model_validate(payload),
            beat_grid=_FAMILY_GRID,
        )

    assert not result.success
    error = result.error or ""
    assert "no template remains" in error
    for template_id in FAMILY_IDS:
        assert f"{template_id!r}" in error, template_id
    assert context.get_state("template_admission") is None


@pytest.mark.asyncio
async def test_template_dir_template_that_fails_still_refuses_the_run() -> None:
    """Exclusion is only for the shipped catalog: a user template that fails the gate
    refuses the run although every family would be admitted."""
    with physical_catalog(), registered_templates(_jump_template(None)):
        result, _ = await _run(
            family_job(_HEADS),
            templates=[*FAMILY_IDS, _JUMP_ID],
            rig=family_rig(_HEADS),
            beat_grid=_FAMILY_GRID,
        )

    assert not result.success
    error = result.error or ""
    assert f"template {_JUMP_ID!r}" in error and "repositioning" in error
    assert not any(f"{template_id!r}" in error for template_id in FAMILY_IDS)


@pytest.mark.asyncio
async def test_layout_models_in_state_are_checked_before_planning() -> None:
    """A caller that hands the run a layout gets the model check at the gate too."""
    stage = RenderPreflightStage(available_templates=[TEMPLATE_ID])
    context = _context(physical_job(), physical_grid())
    context.set_state(
        "layout_models",
        (
            Model.model_validate(
                {"name": "Dmx MH1", "DisplayAs": "DmxMovingHeadAdv", "DmxChannelCount": "18"}
            ),
            Model.model_validate(
                {"name": "Dmx MH2", "DisplayAs": "DmxMovingHead", "StringType": "RGB Nodes"}
            ),
        ),
    )
    with (
        physical_test_templates(),
        patch(
            "twinklr.core.agents.sequencer.moving_heads.rendering_stage.load_render_fixture_group",
            return_value=physical_rig(),
        ),
    ):
        result = await stage.execute(_BUNDLE, context)

    assert not result.success
    assert "MH2: model 'Dmx MH2' has StringType='RGB Nodes'" in (result.error or "")
