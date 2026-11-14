"""Unit tests for the moving head rendering stage."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.golden.harness import RIGS, build_beat_grid, build_fixture_group, build_plan
from tests.support.mh_physical import (
    PHYSICAL_INITIAL_STATE,
    physical_grid,
    physical_job,
    physical_plan,
    physical_rig,
    physical_test_templates,
)
from twinklr.core.agents.sequencer.moving_heads.rendering_stage import MovingHeadRenderingStage
from twinklr.core.audio.models.metadata import EmbeddedMetadata, MetadataBundle
from twinklr.core.config.models import JobConfig
from twinklr.core.formats.xlights.layout.models.rgb_effects import Model
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.sequencer.moving_heads.compile.template_compiler import UnsupportedRigShapeError


def _context_with_fixture_path(fixture_path: str) -> PipelineContext:
    mock_session = MagicMock()
    mock_session.app_config = MagicMock()
    mock_session.job_config = MagicMock()
    mock_session.job_config.fixture_config_path = fixture_path
    return PipelineContext(session=mock_session)


def test_load_fixture_config_resolves_relative_job_config_path(tmp_path: Path) -> None:
    """Relative fixture path resolves against job_config_dir stored in context state."""
    fixture_file = tmp_path / "fixture_config.json"
    fixture_file.write_text('{"fixtures": []}', encoding="utf-8")

    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _context_with_fixture_path("fixture_config.json")
    context.set_state("job_config_dir", tmp_path)

    sentinel = MagicMock()
    with patch("twinklr.core.config.loader.load_fixture_group", return_value=sentinel) as mock_load:
        result = stage._load_fixture_config(context)

    assert result is sentinel
    mock_load.assert_called_once_with(fixture_file)


def test_media_metadata_comes_from_the_analyzed_audio(tmp_path: Path) -> None:
    """The delivered sequence names the audio it was choreographed against.

    An empty `mediaFile` is fatal to xLights and to Twinklr's own parser, so the
    resolver reads the bundle the audio stage stored rather than leaving it blank.
    """
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _context_with_fixture_path("fixture_config.json")

    bundle = MagicMock()
    bundle.audio_path = "/music/Need A Favor.mp3"
    bundle.metadata = MetadataBundle.model_construct(
        embedded=EmbeddedMetadata(title="Need A Favor", artist="Luke Combs")
    )
    context.set_state("audio_bundle", bundle)

    assert stage._resolve_media_metadata(context) == (
        "Need A Favor.mp3",
        "Need A Favor",
        "Luke Combs",
    )


def test_media_file_falls_back_when_no_audio_bundle(tmp_path: Path) -> None:
    """With nothing to name, the head still gets a non-empty media file."""
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    media_file, song, artist = stage._resolve_media_metadata(_context_with_fixture_path("f.json"))

    assert media_file
    assert (song, artist) == ("", "")


@pytest.mark.asyncio
async def test_unsupported_rig_shape_is_reported_as_an_actionable_message(tmp_path: Path) -> None:
    """A template the rig cannot fill fails with guidance, not a traceback.

    `compile_template` raises `UnsupportedRigShapeError` naming the template, the step,
    the group and the roles the rig has (P1P-T5). The stage passes that text through and
    adds what the user can do about it.
    """
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _context_with_fixture_path("fixture_config.json")
    context.set_state("beat_grid", MagicMock())

    with (
        patch.object(MovingHeadRenderingStage, "_load_fixture_config", return_value=MagicMock()),
        patch.object(MovingHeadRenderingStage, "_build_timeline_tracks", return_value=[]),
        patch(
            "twinklr.core.sequencer.moving_heads.pipeline.RenderingPipeline",
            side_effect=UnsupportedRigShapeError(
                "template 'split_lr_sweep_counter' step 'sweep' targets RIGHT; rig has [CENTER]"
            ),
        ),
    ):
        result = await stage.execute({"moving_heads": MagicMock()}, context)

    assert not result.success
    assert result.error is not None
    assert "split_lr_sweep_counter" in result.error
    assert "rig config" in result.error


@pytest.mark.asyncio
async def test_physical_mode_without_profiles_fails_the_stage(tmp_path: Path) -> None:
    """A physical job on a rig without physical profiles fails, naming each head and
    the missing item, and delivers nothing."""
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _context_with_fixture_path("fixture_config.json")
    context.session.job_config = JobConfig.model_validate(
        {"schema_version": "3.1", "moving_heads": {"mode": "physical_v2"}}
    )
    context.set_state("beat_grid", build_beat_grid())
    fixture_group = build_fixture_group(RIGS["mh4_minimal"])

    with patch.object(MovingHeadRenderingStage, "_load_fixture_config", return_value=fixture_group):
        result = await stage.execute({"moving_heads": build_plan()}, context)

    assert not result.success
    assert result.error is not None
    assert "physical_v2" in result.error
    for fixture_id in ("MH1", "MH2", "MH3", "MH4"):
        assert f"{fixture_id}: physical_profile is missing" in result.error
    assert list(tmp_path.iterdir()) == []
    assert context.get_state("delivery_artifacts") is None


def _physical_context() -> PipelineContext:
    context = _context_with_fixture_path("fixture_config.json")
    context.session.job_config = physical_job()
    context.set_state("beat_grid", physical_grid())
    return context


@pytest.mark.asyncio
async def test_physical_job_renders_and_delivers_through_the_stage(tmp_path: Path) -> None:
    """The stage dispatches a physical job to the physical renderer and delivers it,
    with the render identity in the trace beside the `.xsq`."""
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _physical_context()

    with (
        physical_test_templates(),
        patch.object(MovingHeadRenderingStage, "_load_fixture_config", return_value=physical_rig()),
    ):
        result = await stage.execute({"moving_heads": physical_plan()}, context)

    assert result.success, result.error
    artifacts = context.get_state("delivery_artifacts")
    assert artifacts is not None
    assert artifacts.xsq_path == tmp_path / "out.xsq"
    assert artifacts.model_names == ("Dmx MH1", "Dmx MH2")
    trace = json.loads(artifacts.trace_path.read_text(encoding="utf-8"))
    assert trace["render"]["renderer"] == "physical_v2"
    assert len(trace["render"]["render_fingerprint"]) == 64
    segments = context.get_state("rendered_segments")
    assert all(
        value.physical is not None for segment in segments for value in segment.channels.values()
    )


@pytest.mark.asyncio
async def test_stage_hands_the_run_layout_to_the_physical_render(tmp_path: Path) -> None:
    """The layout `twinklr run` loads reaches the model check, and the trace says so."""
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _physical_context()
    models = tuple(
        Model.model_validate(
            {"name": f"Dmx MH{index}", "DisplayAs": "DmxMovingHeadAdv", "DmxChannelCount": "18"}
        )
        for index in (1, 2)
    )
    context.set_state("layout_models", models)
    context.set_state("layout_sha256", "ef" * 32)

    with (
        physical_test_templates(),
        patch.object(MovingHeadRenderingStage, "_load_fixture_config", return_value=physical_rig()),
    ):
        result = await stage.execute({"moving_heads": physical_plan()}, context)

    assert result.success, result.error
    trace = json.loads(context.get_state("delivery_artifacts").trace_path.read_text())
    assert (trace["render"]["layout_check"], trace["render"]["layout_sha256"]) == (
        "performed",
        "ef" * 32,
    )


@pytest.mark.asyncio
async def test_physical_refusal_fails_the_stage_and_delivers_nothing(tmp_path: Path) -> None:
    """A physical job whose heads are not known to be settled is refused, naming the
    head and the item, and writes no file."""
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _physical_context()
    initial = {**PHYSICAL_INITIAL_STATE, "settled": False}
    context.session.job_config = physical_job(initial_states={"MH1": initial, "MH2": initial})
    rig = physical_rig()

    with (
        physical_test_templates(),
        patch.object(MovingHeadRenderingStage, "_load_fixture_config", return_value=rig),
    ):
        result = await stage.execute({"moving_heads": physical_plan()}, context)

    assert not result.success
    assert result.error is not None
    assert "MH1: moving_heads.initial_states['MH1']: initial state is not settled" in result.error
    assert list(tmp_path.iterdir()) == []
    assert context.get_state("delivery_artifacts") is None
