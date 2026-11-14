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
    physical_layout_xml,
    physical_rig,
    physical_test_templates,
)
from twinklr.cli import main as cli_main
from twinklr.core.api.xlights.injection import (
    InjectionPartialError,
    InjectionResult,
    LiveEffect,
)
from twinklr.core.caching.identity import hash_file_content
from twinklr.core.config.fixtures import FixtureGroup
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


def test_run_accepts_an_optional_layout() -> None:
    parser = cli_main.build_arg_parser()
    with_layout = parser.parse_args(
        ["run", "--audio", "song.mp3", "--config", "job.json", "--layout", "layout.xml"]
    )
    without = parser.parse_args(["run", "--audio", "song.mp3", "--config", "job.json"])

    assert (with_layout.layout, without.layout) == ("layout.xml", None)


def _captured_run(monkeypatch, job, rig) -> dict:
    """Patch `twinklr run` around planning; capture the session id and pipeline state."""
    captured: dict = {"build_calls": 0}
    pipeline = MagicMock()
    pipeline.validate_pipeline.return_value = []
    pipeline.stages = []

    def build(**kwargs):
        captured["build_calls"] += 1
        return pipeline, SimpleNamespace(groups=[]), MagicMock()

    def session(**kwargs):
        captured["session_id"] = kwargs["session_id"]
        return SimpleNamespace(app_config=kwargs["app_config"], job_config=kwargs["job_config"])

    class CapturingExecutor:
        async def execute(self, *, pipeline, initial_input, context):
            captured["state"] = dict(context.state)
            return PipelineResult(success=False)

    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setattr(cli_main, "load_app_config", lambda _: AppConfig(llm_api_key="k"))
    monkeypatch.setattr(cli_main, "load_job_config", lambda _: job)
    monkeypatch.setattr(cli_main, "load_fixture_group", lambda _: rig)
    monkeypatch.setattr(cli_main, "build_run_pipeline", build)
    monkeypatch.setattr(cli_main, "TwinklrSession", session)
    monkeypatch.setattr(cli_main, "PipelineExecutor", CapturingExecutor)
    return captured


async def _run_with(tmp_path, layout: Path | None) -> int:
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"synthetic audio")
    return await cli_main.run_pipeline_async(
        audio_path=audio,
        output_dir=tmp_path / "out",
        app_config_path=tmp_path / "config.json",
        job_config_path=tmp_path / "job.json",
        layout_path=layout,
    )


@pytest.mark.anyio
async def test_run_refuses_a_physical_model_the_layout_says_cannot_take_the_mapping(
    tmp_path, monkeypatch, capsys
) -> None:
    layout = tmp_path / "xlights_rgbeffects.xml"
    layout.write_text(physical_layout_xml({"Dmx MH2": {"parm1": "16"}}), encoding="utf-8")
    captured = _captured_run(monkeypatch, physical_job(), physical_rig())

    with physical_test_templates():
        exit_code = await _run_with(tmp_path, layout)

    output = " ".join(capsys.readouterr().out.split())
    assert exit_code == 1
    assert captured["build_calls"] == 0
    assert "MH2: model 'Dmx MH2' has 16 channels" in output


@pytest.mark.anyio
async def test_run_checks_a_physical_rig_against_its_layout_and_hands_it_on(
    tmp_path, monkeypatch, capsys
) -> None:
    layout = tmp_path / "xlights_rgbeffects.xml"
    layout.write_text(physical_layout_xml(), encoding="utf-8")
    captured = _captured_run(monkeypatch, physical_job(), physical_rig())

    with physical_test_templates():
        await _run_with(tmp_path, layout)

    output = " ".join(capsys.readouterr().out.split())
    assert "model check was not performed" not in output
    state = captured["state"]
    assert [model.name for model in state["layout_models"]] == ["Dmx MH1", "Dmx MH2"]
    assert state["layout_sha256"] == hash_file_content(layout)


@pytest.mark.anyio
async def test_a_layout_changes_nothing_for_a_legacy_run(tmp_path, monkeypatch) -> None:
    """Legacy runs accept the option and ignore it: same session, same pipeline state."""
    layout = tmp_path / "xlights_rgbeffects.xml"
    layout.write_text(physical_layout_xml({"Dmx MH1": {"DisplayAs": "Arches"}}), "utf-8")
    runs = []
    for path in (layout, None):
        captured = _captured_run(monkeypatch, JobConfig(), build_fixture_group(RIGS["mh4_minimal"]))
        await _run_with(tmp_path, path)
        runs.append(captured)

    assert runs[0]["session_id"] == runs[1]["session_id"]
    assert runs[0]["state"].keys() == runs[1]["state"].keys()
    assert "layout_models" not in runs[0]["state"]


def test_run_refuses_a_missing_layout_file(tmp_path, monkeypatch) -> None:
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"synthetic audio")
    job = tmp_path / "job.json"
    job.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli_main, "run_pipeline_async", MagicMock())
    args = cli_main.build_arg_parser().parse_args(
        [
            "run",
            "--audio",
            str(audio),
            "--config",
            str(job),
            "--app-config",
            str(tmp_path / "config.json"),
            "--layout",
            str(tmp_path / "missing.xml"),
        ]
    )

    with pytest.raises(SystemExit) as error:
        cli_main.run_pipeline(args)

    assert error.value.code == 1
    cli_main.run_pipeline_async.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("names", "message"),
    [
        (("Dmx MH1", "Dmx MH1"), "MH1 and MH2: both map to xLights model 'Dmx MH1'"),
        (("Dmx MH1", ""), "MH2: xlights_model_name is blank"),
    ],
)
async def test_run_refuses_unusable_model_names_before_planning(
    tmp_path, monkeypatch, capsys, names, message
) -> None:
    """A physical job on a rig with a shared or blank model name stops before analysis;
    the same rig under legacy_v1 still reaches the pipeline build as before."""
    payload = physical_rig().model_dump(mode="json")
    for fixture, name in zip(payload["fixtures"], names, strict=True):
        fixture["xlights_model_name"] = name
    rig = FixtureGroup.model_validate(payload)

    captured = _captured_run(monkeypatch, physical_job(), rig)
    with physical_test_templates():
        assert await _run_with(tmp_path, None) == 1
    assert captured["build_calls"] == 0
    assert message in " ".join(capsys.readouterr().out.split())

    captured = _captured_run(monkeypatch, JobConfig(), rig)
    await _run_with(tmp_path, None)
    assert captured["build_calls"] == 1
