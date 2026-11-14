"""CLI contract for live injection and per-section regeneration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.golden.harness import RIGS, build_fixture_group
from tests.support.mh_physical import (
    SUBSET_TEMPLATE_ID,
    TEMPLATE_ID,
    physical_job,
    physical_rig,
    physical_test_templates,
)
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

    app_config = AppConfig(llm_api_key="offline-test-key")
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


def _stop_if_planning_starts(**kwargs):
    raise AssertionError("the pipeline must not be built for a refused job")


@pytest.mark.anyio
async def test_live_injection_refuses_a_physical_job_before_reading_the_layout(
    tmp_path, monkeypatch, capsys
) -> None:
    """Live injection serializes through the legacy exporter, so a physical job is
    refused at load, before xLights is queried or anything is planned."""

    class UnqueriedXLightsClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get_models(self, request):
            raise AssertionError("the live layout must not be read for a refused job")

    physical = JobConfig.model_validate(
        {"schema_version": "3.1", "moving_heads": {"mode": "physical_v2"}}
    )
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setattr(cli_main, "XLightsAutomationClient", UnqueriedXLightsClient)
    monkeypatch.setattr(cli_main, "load_app_config", lambda _: AppConfig(llm_api_key="k"))
    monkeypatch.setattr(cli_main, "load_job_config", lambda _: physical)
    monkeypatch.setattr(cli_main, "build_run_pipeline", _stop_if_planning_starts)

    exit_code = await cli_main.run_pipeline_async(
        audio_path=tmp_path / "song.wav",
        output_dir=tmp_path,
        app_config_path=tmp_path / "config.json",
        job_config_path=tmp_path / "job.json",
        live_injection=True,
        section_id="chorus_2",
    )

    output = " ".join(capsys.readouterr().out.split())
    assert exit_code == 1
    assert "`twinklr regenerate` does not support moving_heads.mode 'physical_v2'" in output


@pytest.mark.anyio
async def test_run_refuses_a_physical_job_on_a_rig_without_profiles_before_planning(
    tmp_path, monkeypatch, capsys
) -> None:
    """`twinklr run` checks a physical job against the loaded rig before any analysis
    or provider request, naming each fixture and the missing item."""
    physical = JobConfig.model_validate(
        {"schema_version": "3.1", "moving_heads": {"mode": "physical_v2"}}
    )
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setattr(cli_main, "load_app_config", lambda _: AppConfig(llm_api_key="k"))
    monkeypatch.setattr(cli_main, "load_job_config", lambda _: physical)
    monkeypatch.setattr(
        cli_main, "load_fixture_group", lambda _: build_fixture_group(RIGS["mh4_minimal"])
    )
    monkeypatch.setattr(cli_main, "build_run_pipeline", _stop_if_planning_starts)

    exit_code = await cli_main.run_pipeline_async(
        audio_path=tmp_path / "song.wav",
        output_dir=tmp_path,
        app_config_path=tmp_path / "config.json",
        job_config_path=tmp_path / "job.json",
    )

    output = " ".join(capsys.readouterr().out.split())
    assert exit_code == 1
    assert "MH1: physical_profile is missing" in output
    assert "MH4: physical_profile is missing" in output


def _prepared_physical_run(monkeypatch, physical_job, physical_rig) -> list[dict]:
    """Patch `twinklr run` up to the pipeline build; return the captured build calls."""
    calls: list[dict] = []

    def capture(**kwargs):
        calls.append(kwargs)
        raise AssertionError("stop at the pipeline build")

    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setattr(cli_main, "load_app_config", lambda _: AppConfig(llm_api_key="k"))
    monkeypatch.setattr(cli_main, "load_job_config", lambda _: physical_job)
    monkeypatch.setattr(cli_main, "load_fixture_group", lambda _: physical_rig)
    monkeypatch.setattr(cli_main, "build_run_pipeline", capture)
    return calls


@pytest.mark.anyio
async def test_run_refuses_a_physical_job_when_no_template_has_physical_data(
    tmp_path, monkeypatch, capsys
) -> None:
    """A prepared physical job is refused before any analysis when none of the loaded
    templates could render under the physical renderer."""
    calls = _prepared_physical_run(monkeypatch, physical_job(), physical_rig())

    exit_code = await cli_main.run_pipeline_async(
        audio_path=tmp_path / "song.wav",
        output_dir=tmp_path,
        app_config_path=tmp_path / "config.json",
        job_config_path=tmp_path / "job.json",
    )

    output = " ".join(capsys.readouterr().out.split())
    assert exit_code == 1
    assert calls == []
    assert "no template with physical data" in output


@pytest.mark.anyio
async def test_run_offers_the_planner_only_physical_templates(tmp_path, monkeypatch) -> None:
    calls = _prepared_physical_run(monkeypatch, physical_job(), physical_rig())

    with physical_test_templates(), pytest.raises(AssertionError, match="stop at"):
        await cli_main.run_pipeline_async(
            audio_path=tmp_path / "song.wav",
            output_dir=tmp_path,
            app_config_path=tmp_path / "config.json",
            job_config_path=tmp_path / "job.json",
        )

    (call,) = calls
    assert sorted(call["available_templates"]) == sorted([TEMPLATE_ID, SUBSET_TEMPLATE_ID])
