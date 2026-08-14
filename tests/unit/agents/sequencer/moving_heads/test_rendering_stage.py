"""Unit tests for the moving head rendering stage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from twinklr.core.agents.sequencer.moving_heads.rendering_stage import MovingHeadRenderingStage
from twinklr.core.audio.models.metadata import EmbeddedMetadata, MetadataBundle
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
