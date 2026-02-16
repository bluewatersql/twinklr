"""Unit tests for moving head rendering stage fixture resolution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from twinklr.core.agents.sequencer.moving_heads.rendering_stage import MovingHeadRenderingStage
from twinklr.core.pipeline.context import PipelineContext


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
