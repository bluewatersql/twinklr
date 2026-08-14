"""CLI contract for live injection and per-section regeneration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from twinklr.cli import main as cli_main
from twinklr.core.api.xlights.injection import (
    InjectionPartialError,
    InjectionResult,
    LiveEffect,
)
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.pipeline.result import PipelineResult


def test_live_injection_commands_parse() -> None:
    parser = cli_main.build_arg_parser()
    inject = parser.parse_args(
        ["inject", "--audio", "song.mp3", "--config", "job.json", "--dry-run"]
    )
    regenerate = parser.parse_args(
        ["regenerate", "chorus_2", "--audio", "song.mp3", "--config", "job.json"]
    )

    assert inject.cmd == "inject" and inject.dry_run
    assert regenerate.cmd == "regenerate" and regenerate.section == "chorus_2"


def test_live_command_help_warns_about_unauthenticated_port(capsys) -> None:
    parser = cli_main.build_arg_parser()
    inject = next(action for action in parser._actions if action.dest == "cmd").choices["inject"]

    inject.print_help()
    help_text = capsys.readouterr().out.lower()

    assert "no documented authentication" in help_text
    assert "never saves" in help_text
    assert "dry-run" in help_text


@pytest.mark.anyio
async def test_run_pipeline_reports_structured_partial_injection_failure(
    tmp_path, monkeypatch, capsys
) -> None:
    effect = LiveEffect(
        target="Dmx MH1",
        effect="DMX",
        settings="E_SLIDER_DMX1=1",
        palette="",
        start_ms=0,
        end_ms=500,
        section_id="chorus",
    )
    result = InjectionResult(
        complete=False,
        dry_run=False,
        sequence_path=Path("/tmp/scratch.xsq"),
        commands=(),
        injected=(effect,),
        deleted=(effect,),
        unchanged=(),
        failed_command={"cmd": "addEffect", "target": "Dmx MH1"},
        error="response lost after apply",
        recovery="Inspect reserved layers, then re-run safely.",
    )

    app_config = AppConfig()
    job_config = JobConfig(write_checkpoint=False)
    fixture_group = MagicMock()
    fixture_group.expand_fixtures.return_value = [MagicMock()]
    pipeline = MagicMock()
    pipeline.validate_pipeline.return_value = []
    pipeline.stages = []

    class FakeXLightsClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get_models(self, request):
            return SimpleNamespace(models=("Dmx MH1",))

    class SuccessfulExecutor:
        async def execute(self, *, pipeline, initial_input, context):
            context.set_state("rendered_segments", ())
            return PipelineResult(success=True)

    class FailingWorkflow:
        def __init__(self, client, *, ownership):
            pass

        async def inject(self, effects, *, dry_run=False):
            raise InjectionPartialError(result)

    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setattr(cli_main, "XLightsAutomationClient", FakeXLightsClient)
    monkeypatch.setattr(cli_main, "load_app_config", lambda _: app_config)
    monkeypatch.setattr(cli_main, "load_job_config", lambda _: job_config)
    monkeypatch.setattr(cli_main, "load_fixture_group", lambda _: fixture_group)
    monkeypatch.setattr(cli_main, "load_builtin_templates", lambda: None)
    monkeypatch.setattr(cli_main, "list_templates", list)
    monkeypatch.setattr(
        cli_main,
        "reconcile_live_layout",
        lambda *args, **kwargs: SimpleNamespace(
            rig=fixture_group,
            report=SimpleNamespace(has_divergence=False),
        ),
    )
    monkeypatch.setattr(
        cli_main,
        "build_run_pipeline",
        lambda **kwargs: (pipeline, SimpleNamespace(groups=[]), MagicMock()),
    )
    monkeypatch.setattr(
        cli_main,
        "TwinklrSession",
        lambda **kwargs: SimpleNamespace(
            app_config=app_config,
            job_config=job_config,
        ),
    )
    monkeypatch.setattr(cli_main, "PipelineExecutor", SuccessfulExecutor)
    monkeypatch.setattr(cli_main, "live_effects_from_segments", lambda *args: (effect,))
    monkeypatch.setattr(cli_main, "LiveInjectionWorkflow", FailingWorkflow)

    exit_code = await cli_main.run_pipeline_async(
        audio_path=tmp_path / "song.wav",
        output_dir=tmp_path,
        app_config_path=tmp_path / "config.json",
        job_config_path=tmp_path / "job.json",
        session_id="offline-session",
        live_injection=True,
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Confirmed injected prefix: 1" in output
    assert "Confirmed deletions: 1" in output
    assert '"cmd": "addEffect"' in output
    assert "response lost after apply" in output
    assert "Inspect reserved layers, then re-run safely." in output
