"""P3-T3 display command contract."""

from argparse import Namespace
import json
from pathlib import Path
import sys
from unittest.mock import AsyncMock, patch

import pytest

from twinklr.cli.display_cmd import (
    export_display_artifacts,
    load_display_fe_bundle,
    run_display_command,
    run_display_pipeline_async,
)
from twinklr.cli.main import build_arg_parser, main
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.feature_engineering.loader import FEArtifactBundle
from twinklr.core.formats.xlights.sequence.fresh import build_fresh_sequence
from twinklr.core.pipeline.result import PipelineResult
from twinklr.core.sequencer.display.models.render_plan import RenderPlan
from twinklr.core.sequencer.display.renderer import RenderResult


def test_command_registered_and_args() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(
        [
            "display",
            "--audio",
            "song.wav",
            "--layout",
            "xlights_rgbeffects.xml",
            "--config",
            "job.json",
            "--out",
            "build",
            "--fe-output-dir",
            "fe",
            "--style",
            "bright",
        ]
    )

    assert args.cmd == "display"
    assert args.audio == "song.wav"
    assert args.layout == "xlights_rgbeffects.xml"
    assert args.config == "job.json"
    assert args.app_config is None
    assert args.out == "build"
    assert args.fe_output_dir == "fe"
    assert args.style == "bright"


def test_display_requires_offline_layout_file() -> None:
    parser = build_arg_parser()
    try:
        parser.parse_args(["display", "--audio", "song.wav", "--config", "job.json"])
    except SystemExit as error:
        assert error.code != 0
    else:
        raise AssertionError("--layout must be required")


def test_style_is_forwarded_to_fe_loader(tmp_path: Path) -> None:
    bundle = FEArtifactBundle()
    with patch("twinklr.cli.display_cmd.load_fe_artifacts", return_value=bundle) as loader:
        assert load_display_fe_bundle(tmp_path, style_name="bright") is bundle
    loader.assert_called_once_with(tmp_path, style_name="bright")


def test_style_without_fe_directory_is_actionable() -> None:
    with pytest.raises(ValueError, match="--style requires --fe-output-dir"):
        load_display_fe_bundle(None, style_name="bright")


def test_export_writes_required_xsq_and_trace_layout(tmp_path: Path) -> None:
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1000)
    render_result = RenderResult(
        render_plan=RenderPlan(render_id="fixture", duration_ms=1000),
    )
    xsq_path, trace_path = export_display_artifacts(
        {"sequence": sequence, "render_result": render_result},
        artifact_dir=tmp_path / "song",
        song_name="song",
    )
    assert xsq_path == tmp_path / "song" / "song_twinklr_display.xsq"
    assert trace_path == Path(f"{xsq_path}.trace.json")
    assert xsq_path.is_file()
    assert trace_path.is_file()
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace == {
        "schema_version": "twinklr-xsq-trace.v2",
        "entry_count": 0,
        "fallback_substitutions": 0,
        "entries": [],
    }


def test_export_rejects_missing_render_payload(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="display_render output"):
        export_display_artifacts(None, artifact_dir=tmp_path, song_name="song")


def test_main_dispatches_display_command() -> None:
    argv = [
        "twinklr",
        "display",
        "--audio",
        "song.wav",
        "--layout",
        "layout.xml",
        "--config",
        "job.json",
    ]
    with (
        patch.object(sys, "argv", argv),
        patch("twinklr.cli.main.run_display_command") as command,
    ):
        main()
    command.assert_called_once()
    assert command.call_args.args[0].cmd == "display"


def test_display_command_rejects_missing_input_before_execution(tmp_path: Path) -> None:
    args = Namespace(
        audio=str(tmp_path / "missing.wav"),
        layout=str(tmp_path / "missing.xml"),
        config=str(tmp_path / "missing-job.json"),
        app_config=str(tmp_path / "missing-app.json"),
        out=str(tmp_path),
        fe_output_dir=None,
        style=None,
        session_id=None,
    )
    with pytest.raises(SystemExit) as error:
        run_display_command(args)
    assert error.value.code == 1


def test_explicit_missing_app_config_is_rejected(tmp_path: Path) -> None:
    audio = tmp_path / "song.wav"
    layout = tmp_path / "layout.xml"
    job = tmp_path / "job.json"
    for path in (audio, layout, job):
        path.write_text("fixture", encoding="utf-8")
    args = Namespace(
        audio=str(audio),
        layout=str(layout),
        config=str(job),
        app_config=str(tmp_path / "explicit-missing.json"),
        out=str(tmp_path),
        fe_output_dir=None,
        style=None,
        session_id=None,
    )
    with pytest.raises(SystemExit) as error:
        run_display_command(args)
    assert error.value.code == 1


@pytest.mark.asyncio
async def test_omitted_app_config_uses_loader_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    with (
        patch("twinklr.cli.display_cmd.load_app_config", return_value=AppConfig()) as loader,
        patch(
            "twinklr.cli.display_cmd.prepare_display_pipeline",
            side_effect=ValueError("stop after config"),
        ),
    ):
        exit_code = await run_display_pipeline_async(
            audio_path=tmp_path / "song.wav",
            layout_path=tmp_path / "layout.xml",
            output_dir=tmp_path / "out",
            app_config_path=None,
            job_config_path=tmp_path / "job.json",
        )
    assert exit_code == 1
    loader.assert_called_once_with(None)


def test_export_failure_is_not_silenced(tmp_path: Path) -> None:
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1000)
    render_result = RenderResult(render_plan=RenderPlan(render_id="fixture", duration_ms=1000))
    with (
        patch("twinklr.cli.display_cmd.XSQExporter.export", side_effect=OSError("disk full")),
        pytest.raises(OSError, match="disk full"),
    ):
        export_display_artifacts(
            {"sequence": sequence, "render_result": render_result},
            artifact_dir=tmp_path,
            song_name="song",
        )


@pytest.mark.asyncio
async def test_async_command_executes_and_exports_without_live_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fixture")
    layout = Path(__file__).resolve().parents[2] / "fixtures" / "display_layout_a.xml"
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1000)
    render_result = RenderResult(render_plan=RenderPlan(render_id="fixture", duration_ms=1000))
    result = PipelineResult(
        success=True,
        outputs={"display_render": {"sequence": sequence, "render_result": render_result}},
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    with (
        patch("twinklr.cli.display_cmd.load_app_config", return_value=AppConfig()),
        patch("twinklr.cli.display_cmd.load_job_config", return_value=JobConfig()),
        patch(
            "twinklr.cli.display_cmd.PipelineExecutor.execute",
            new=AsyncMock(return_value=result),
        ),
    ):
        exit_code = await run_display_pipeline_async(
            audio_path=audio,
            layout_path=layout,
            output_dir=tmp_path / "out",
            app_config_path=tmp_path / "app.json",
            job_config_path=tmp_path / "job.json",
        )

    assert exit_code == 0
    artifact_dir = tmp_path / "out" / "song"
    assert (artifact_dir / "song_twinklr_display.xsq").is_file()
    assert (artifact_dir / "song_twinklr_display.xsq.trace.json").is_file()


@pytest.mark.asyncio
async def test_async_command_reports_invalid_render_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fixture")
    layout = Path(__file__).resolve().parents[2] / "fixtures" / "display_layout_a.xml"
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    with (
        patch("twinklr.cli.display_cmd.load_app_config", return_value=AppConfig()),
        patch("twinklr.cli.display_cmd.load_job_config", return_value=JobConfig()),
        patch(
            "twinklr.cli.display_cmd.PipelineExecutor.execute",
            new=AsyncMock(return_value=PipelineResult(success=True)),
        ),
    ):
        exit_code = await run_display_pipeline_async(
            audio_path=audio,
            layout_path=layout,
            output_dir=tmp_path / "out",
            app_config_path=tmp_path / "app.json",
            job_config_path=tmp_path / "job.json",
        )
    assert exit_code == 1
