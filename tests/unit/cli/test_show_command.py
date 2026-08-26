"""Additive user-facing surface for coordinated show generation."""

from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from twinklr.cli.main import build_arg_parser
from twinklr.cli.show_cmd import run_show_command, run_show_pipeline_async
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.feature_engineering.loader import FEArtifactBundle


def test_show_command_requires_layout_and_fixture_config() -> None:
    args = build_arg_parser().parse_args(
        [
            "show",
            "--audio",
            "song.wav",
            "--layout",
            "xlights_rgbeffects.xml",
            "--fixture-config",
            "fixtures.json",
            "--config",
            "job.json",
            "--fe-output-dir",
            "fe",
            "--style",
            "bright",
        ]
    )

    assert args.cmd == "show"
    assert args.audio == "song.wav"
    assert args.layout == "xlights_rgbeffects.xml"
    assert args.fixture_config == "fixtures.json"
    assert args.config == "job.json"
    assert args.fe_output_dir == "fe"
    assert args.style == "bright"


@pytest.mark.asyncio
async def test_local_provider_reaches_show_wiring_without_openai_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    local_config = AppConfig(
        llm_provider="ollama",
        llm_base_url="http://127.0.0.1:11434/v1",
        llm_api_key="",
    )
    with (
        patch("twinklr.cli.show_cmd.load_app_config", return_value=local_config),
        patch("twinklr.cli.show_cmd.load_job_config", return_value=JobConfig()),
        patch("twinklr.cli.show_cmd.load_fixture_group"),
        patch("twinklr.cli.show_cmd.load_builtin_templates"),
        patch("twinklr.cli.show_cmd.list_templates", return_value=[]),
        patch(
            "twinklr.cli.show_cmd.prepare_combined_show_pipeline",
            side_effect=ValueError("stop after provider preflight"),
        ) as prepare,
    ):
        exit_code = await run_show_pipeline_async(
            audio_path=tmp_path / "song.wav",
            layout_path=tmp_path / "layout.xml",
            fixture_config_path=tmp_path / "fixtures.json",
            output_dir=tmp_path / "out",
            app_config_path=None,
            job_config_path=tmp_path / "job.json",
        )

    assert exit_code == 1
    prepare.assert_called_once()


def test_show_command_rejects_missing_fe_output_before_execution(tmp_path: Path) -> None:
    audio = tmp_path / "song.wav"
    layout = tmp_path / "layout.xml"
    fixture = tmp_path / "fixtures.json"
    config = tmp_path / "job.json"
    for path in (audio, layout, fixture, config):
        path.write_text("fixture", encoding="utf-8")
    args = Namespace(
        audio=str(audio),
        layout=str(layout),
        fixture_config=str(fixture),
        config=str(config),
        app_config=None,
        out=str(tmp_path),
        fe_output_dir=str(tmp_path / "missing-fe"),
        style=None,
        session_id=None,
    )

    with pytest.raises(SystemExit) as error:
        run_show_command(args)

    assert error.value.code == 1


@pytest.mark.asyncio
async def test_show_style_without_fe_directory_is_actionable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    with (
        patch("twinklr.cli.show_cmd.load_app_config"),
        patch("twinklr.cli.show_cmd.load_job_config"),
        patch("twinklr.cli.show_cmd.load_fixture_group"),
        patch("twinklr.cli.show_cmd.prepare_combined_show_pipeline") as prepare,
    ):
        exit_code = await run_show_pipeline_async(
            audio_path=tmp_path / "song.wav",
            layout_path=tmp_path / "layout.xml",
            fixture_config_path=tmp_path / "fixtures.json",
            output_dir=tmp_path / "out",
            app_config_path=None,
            job_config_path=tmp_path / "job.json",
            style_name="bright",
        )

    assert exit_code == 1
    prepare.assert_not_called()


@pytest.mark.asyncio
async def test_show_fe_bundle_and_default_catalog_layers_are_forwarded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    fe_dir = tmp_path / "fe"
    bundle = FEArtifactBundle()
    with (
        patch("twinklr.cli.show_cmd.load_app_config"),
        patch("twinklr.cli.show_cmd.load_job_config"),
        patch("twinklr.cli.show_cmd.load_fixture_group"),
        patch("twinklr.cli.show_cmd.load_display_fe_bundle", return_value=bundle) as loader,
        patch("twinklr.cli.show_cmd.load_builtin_templates"),
        patch("twinklr.cli.show_cmd.list_templates", return_value=[MagicMock(template_id="mh")]),
        patch(
            "twinklr.cli.show_cmd.prepare_combined_show_pipeline",
            side_effect=ValueError("stop after wiring"),
        ) as prepare,
    ):
        exit_code = await run_show_pipeline_async(
            audio_path=tmp_path / "song.wav",
            layout_path=tmp_path / "layout.xml",
            fixture_config_path=tmp_path / "fixtures.json",
            output_dir=tmp_path / "out",
            app_config_path=None,
            job_config_path=tmp_path / "job.json",
            fe_output_dir=fe_dir,
            style_name="bright",
        )

    assert exit_code == 1
    loader.assert_called_once_with(fe_dir, style_name="bright")
    assert prepare.call_args.kwargs["fe_bundle"] is bundle
    assert prepare.call_args.kwargs["catalog_dir"].name == "templates"
    assert prepare.call_args.kwargs["local_catalog_dir"].parts[-2:] == ("data", "templates")
