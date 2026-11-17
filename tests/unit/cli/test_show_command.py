"""Additive user-facing surface for coordinated show generation."""

from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.support.moving_heads import p1_job, p1_rig
from twinklr.cli.main import build_arg_parser
from twinklr.cli.profile_tags import PROFILE_TAGS_FILENAME
from twinklr.cli.show_cmd import run_show_command, run_show_pipeline_async
from twinklr.core.config.fixtures import FixtureGroup, FixtureInstance
from twinklr.core.config.fixtures.dmx import DmxMapping
from twinklr.core.config.fixtures.instances import FixtureConfig
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
        patch("twinklr.cli.show_cmd.preflight_render_policy"),
        patch("twinklr.cli.show_cmd.load_template_catalog"),
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
        patch("twinklr.cli.show_cmd.load_job_config", return_value=JobConfig()),
        patch("twinklr.cli.show_cmd.load_fixture_group"),
        patch("twinklr.cli.show_cmd.load_display_fe_bundle", return_value=bundle) as loader,
        patch("twinklr.cli.show_cmd.preflight_render_policy"),
        patch("twinklr.cli.show_cmd.load_template_catalog"),
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


@pytest.mark.asyncio
async def test_show_refuses_a_rig_without_profiles_before_any_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A show checks the rig when its fixtures load, as `twinklr run` does, so a rig the
    renderer cannot render is refused before analysis or any provider call."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    job_path = tmp_path / "job.json"
    job_path.write_text("{}", encoding="utf-8")
    rig = FixtureGroup(group_id="MOVING_HEADS", xlights_group="Moving Heads")
    rig.add_fixture(
        FixtureInstance(
            fixture_id="MH1",
            config=FixtureConfig(
                fixture_id="MH1",
                dmx_mapping=DmxMapping(pan_channel=1, tilt_channel=2, dimmer_channel=3),
            ),
            xlights_model_name="Dmx MH1",
        )
    )
    with (
        patch("twinklr.cli.show_cmd.load_app_config", return_value=AppConfig()),
        patch("twinklr.cli.show_cmd.load_fixture_group", return_value=rig),
        patch("twinklr.cli.show_cmd.prepare_combined_show_pipeline") as prepare,
    ):
        exit_code = await run_show_pipeline_async(
            audio_path=tmp_path / "song.wav",
            layout_path=tmp_path / "layout.xml",
            fixture_config_path=tmp_path / "fixtures.json",
            output_dir=tmp_path / "out",
            app_config_path=None,
            job_config_path=job_path,
        )

    assert exit_code == 1
    output = " ".join(capsys.readouterr().out.split())
    assert "the moving-head renderer cannot render this rig" in output
    assert "MH1: physical_profile is missing" in output
    prepare.assert_not_called()


@pytest.mark.asyncio
async def test_show_notes_untagged_wheel_states_like_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`twinklr show` prints the one-line note and writes the paste-ready tags, using the
    layout models its wiring read, before any analysis."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    (tmp_path / "song.wav").write_bytes(b"synthetic audio")
    wiring = MagicMock(layout_models=())
    wiring.pipeline.validate_pipeline.return_value = []
    with (
        patch("twinklr.cli.show_cmd.load_app_config", return_value=AppConfig()),
        patch("twinklr.cli.show_cmd.load_job_config", return_value=p1_job()),
        patch("twinklr.cli.show_cmd.load_fixture_group", return_value=p1_rig()),
        patch("twinklr.cli.show_cmd.load_display_fe_bundle"),
        patch("twinklr.cli.show_cmd.load_template_catalog"),
        patch("twinklr.cli.show_cmd.list_templates", return_value=[]),
        patch("twinklr.cli.show_cmd.prepare_combined_show_pipeline", return_value=wiring),
        patch("twinklr.cli.show_cmd.TwinklrSession", side_effect=RuntimeError("stop")),
        pytest.raises(RuntimeError, match="stop"),
    ):
        await run_show_pipeline_async(
            audio_path=tmp_path / "song.wav",
            layout_path=tmp_path / "layout.xml",
            fixture_config_path=tmp_path / "fixtures.json",
            output_dir=tmp_path / "out",
            app_config_path=None,
            job_config_path=tmp_path / "job.json",
        )

    (note,) = [line for line in capsys.readouterr().out.splitlines() if "NOTE:" in line]
    (tags,) = (tmp_path / "out").rglob(PROFILE_TAGS_FILENAME)
    assert note.startswith("NOTE: MH1, MH2: wheel or shutter states without a meaning tag")
    assert note.endswith(str(tags))
