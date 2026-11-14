"""The render preflight: a physical job that cannot render is refused right after audio
analysis, before the profile, lyrics, macro and moving-head planners spend anything."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.golden.harness import RIGS, build_fixture_group
from tests.support.mh_physical import (
    PHYSICAL_INITIAL_STATE,
    SUBSET_TEMPLATE_ID,
    TEMPLATE_DIR,
    TEMPLATE_ID,
    physical_grid,
    physical_job,
    physical_rig,
    physical_test_templates,
)
from twinklr.core.agents.audio.lyrics.stage import LyricsStage
from twinklr.core.agents.audio.profile.stage import AudioProfileStage
from twinklr.core.agents.audio.stages.analysis import AudioAnalysisStage
from twinklr.core.agents.sequencer.macro_planner.stage import MacroPlannerStage
from twinklr.core.agents.sequencer.moving_heads.rendering_stage import RenderPreflightStage
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
async def test_legacy_job_passes_through_untouched() -> None:
    result, context = await _run(JobConfig(), templates=["sweep_lr_fan_hold"], rig=None)

    assert result.success and result.output is _BUNDLE
    assert context.get_state("beat_grid") is None


@pytest.mark.asyncio
async def test_physical_job_on_a_rig_without_profiles_is_refused() -> None:
    with physical_test_templates():
        result, _ = await _run(
            physical_job(),
            templates=[TEMPLATE_ID],
            rig=build_fixture_group(RIGS["mh4_minimal"]),
            beat_grid=physical_grid(),
        )

    assert not result.success
    assert "MH1: physical_profile is missing" in (result.error or "")


@pytest.mark.asyncio
async def test_physical_job_offered_a_template_without_physical_data_is_refused() -> None:
    with physical_test_templates():
        result, _ = await _run(
            physical_job(),
            templates=[TEMPLATE_ID, "sweep_lr_fan_hold"],
            rig=physical_rig(),
            beat_grid=physical_grid(),
        )

    assert not result.success
    assert "without physical data" in (result.error or "")
    assert "sweep_lr_fan_hold" in (result.error or "")


@pytest.mark.asyncio
async def test_physical_job_whose_song_has_an_uncovered_tail_is_refused() -> None:
    """Two silent seconds after the last beat leave the phase undefined there; the
    renderer never infers tempo, so the job is refused before planning."""
    with physical_test_templates():
        result, _ = await _run(
            physical_job(),
            templates=[TEMPLATE_ID],
            rig=physical_rig(),
            beat_grid=_long_tail_grid(),
        )

    assert not result.success
    assert "musical phase" in (result.error or "")
    assert "tail" in (result.error or "")


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


@pytest.mark.asyncio
async def test_layout_models_in_state_are_checked_before_planning() -> None:
    """A caller that hands the run a layout gets the model check at the gate too."""
    stage = RenderPreflightStage(available_templates=[TEMPLATE_ID])
    context = _context(physical_job(), physical_grid())
    context.set_state(
        "layout_models",
        (
            Model.model_validate(
                {"name": "Dmx MH1", "DisplayAs": "DmxMovingHeadAdv", "parm1": "18"}
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
