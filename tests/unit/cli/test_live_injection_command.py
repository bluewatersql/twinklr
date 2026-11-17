"""CLI contract for live injection and per-section regeneration."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tests.golden.harness import RIGS, build_fixture_group
from tests.support.live_xlights import FakeLiveXLights
from tests.support.mh_physical import (
    CATALOG_IDS,
    SUBSET_TEMPLATE_ID,
    TEMPLATE_ID,
    physical_bars_grid,
    physical_catalog,
    physical_job,
    physical_layout_xml,
    physical_rig,
    physical_test_templates,
)
from twinklr.cli import main as cli_main
from twinklr.core.agents.audio.profile.models import (
    AudioProfileModel,
    Contrast,
    CreativeGuidance,
    EnergyPoint,
    EnergyProfile,
    LyricProfile,
    MacroEnergy,
    MotionDensity,
    PlannerHints,
    SectionEnergyProfile,
    SongIdentity,
    SongSectionRef,
    Structure,
)
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.agents.sequencer.moving_heads.orchestrator import (
    MovingHeadPlannerOrchestrator,
)
from twinklr.core.agents.sequencer.moving_heads.rendering_stage import (
    MovingHeadRenderingStage,
    RenderPreflightStage,
)
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage
from twinklr.core.agents.shared.judge.controller import IterationContext, IterationResult
from twinklr.core.agents.shared.judge.models import IterationState
from twinklr.core.api.xlights.injection import (
    TWINKLR_LAYER_BASE,
    InjectionPartialError,
    InjectionResult,
    LiveEffect,
)
from twinklr.core.caching.identity import hash_file_content
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.formats.xlights.sequence.parser import XSQParser
from twinklr.core.pipeline import PipelineDefinition, StageDefinition
from twinklr.core.pipeline.result import PipelineResult, success_result
from twinklr.core.reporting.evaluation.generator import generate_evaluation_report


@pytest.fixture(autouse=True)
def _restore_template_registry() -> Iterator[None]:
    """`twinklr run` admits the physical catalog into the shared registry for a
    physical_v2 job; each test removes what its run registered."""
    with physical_catalog(admit=False):
        yield


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


LIVE_GRID = physical_bars_grid(500.0, 500.0, 500.0, 500.0)
"""Four 4/4 bars of 2 s: an intro on bars 1-2 and a chorus on bars 3-4."""
BASE_PLAN = ChoreographyPlan(
    sections=[
        PlanSection.model_validate(
            {"section_name": name, "start_bar": start, "end_bar": end, "template_id": TEMPLATE_ID}
        )
        for name, start, end in (("intro", 1, 2), ("chorus", 3, 4))
    ],
    overall_strategy="sweep, then sweep again",
)
CHORUS_REPLAN = ChoreographyPlan(
    sections=[
        PlanSection.model_validate(
            {
                "section_name": "chorus",
                "start_bar": 3,
                "end_bar": 4,
                "template_id": SUBSET_TEMPLATE_ID,
            }
        )
    ],
    overall_strategy="the right head alone",
)
INTRO_REPLAN = ChoreographyPlan(
    sections=[
        PlanSection.model_validate(
            {
                "section_name": "intro",
                "start_bar": 1,
                "end_bar": 2,
                "template_id": SUBSET_TEMPLATE_ID,
            }
        )
    ],
    overall_strategy="the right head opens",
)


def _audio_profile() -> AudioProfileModel:
    sections = [
        SongSectionRef(section_id="intro", name="intro", start_ms=15, end_ms=4015),
        SongSectionRef(section_id="chorus", name="chorus", start_ms=4015, end_ms=8015),
    ]
    return AudioProfileModel(
        song_identity=SongIdentity(
            title="Song", artist="Artist", duration_ms=8030, bpm=120.0, time_signature="4/4"
        ),
        structure=Structure(sections=sections, structure_confidence=0.9),
        energy_profile=EnergyProfile(
            macro_energy=MacroEnergy.MED,
            section_profiles=[
                SectionEnergyProfile(
                    section_id=section.section_id,
                    start_ms=section.start_ms,
                    end_ms=section.end_ms,
                    energy_curve=[
                        EnergyPoint(t_ms=section.start_ms),
                        EnergyPoint(t_ms=(section.start_ms + section.end_ms) // 2),
                        EnergyPoint(t_ms=section.end_ms - 1),
                    ],
                    mean_energy=0.5,
                    peak_energy=0.6,
                )
                for section in sections
            ],
            peaks=[],
        ),
        lyric_profile=LyricProfile(
            has_plain_lyrics=False,
            has_timed_words=False,
            has_phonemes=False,
            lyric_confidence=0.0,
            phoneme_confidence=0.0,
        ),
        creative_guidance=CreativeGuidance(
            recommended_layer_count=1,
            recommended_contrast=Contrast.MED,
            recommended_motion_density=MotionDensity.MED,
        ),
        planner_hints=PlannerHints(),
    )


class _SyntheticAudio:
    """The audio stage: the run's beat grid, no analysis."""

    name = "audio"

    async def execute(self, input, context):
        context.set_state("beat_grid", LIVE_GRID)
        return success_result(SimpleNamespace(features={}), stage_name=self.name)


class _RecordedProfile:
    """The profile stage: a recorded audio profile, no provider; logs each run."""

    name = "profile"

    def __init__(self, runs: list[str]) -> None:
        self.runs = runs

    async def execute(self, input, context):
        self.runs.append(self.name)
        return success_result(_audio_profile(), stage_name=self.name)


def _live_physical_cli(monkeypatch, fake: FakeLiveXLights) -> dict:
    """Patch a physical `inject`/`regenerate` up to the real planner stage, render stage
    and injection workflow: audio, profile and the planner's provider are recorded
    stand-ins (the planner answers `BASE_PLAN` for the whole song, `CHORUS_REPLAN` for
    the chorus alone and `INTRO_REPLAN` for the intro alone), and xLights is `fake`.
    `captured["planned"]` logs every planner call, the profile's included."""
    captured: dict = {"build_calls": 0, "planned": []}

    def build(**kwargs):
        captured["build_calls"] += 1
        graph, mapping = cli_main.build_moving_head_graph(kwargs["fixture_group"])
        stages = [
            StageDefinition(id="audio", stage=_SyntheticAudio()),
            StageDefinition(
                id="render_preflight",
                stage=RenderPreflightStage(available_templates=[TEMPLATE_ID, SUBSET_TEMPLATE_ID]),
                inputs=["audio"],
            ),
            StageDefinition(
                id="profile",
                stage=_RecordedProfile(captured["planned"]),
                inputs=["render_preflight"],
            ),
            StageDefinition(
                id="moving_heads",
                stage=MovingHeadStage(
                    fixture_count=2,
                    available_templates=kwargs["available_templates"],
                    section_id=kwargs["section_id"],
                    regeneration_nonce=kwargs["regeneration_nonce"],
                    macro_planning_enabled=False,
                ),
                inputs=["audio", "profile"],
            ),
            StageDefinition(
                id="render",
                stage=MovingHeadRenderingStage(xsq_output_path=kwargs["xsq_output_path"]),
                inputs=["moving_heads"],
            ),
        ]
        return PipelineDefinition(name="live", stages=stages), graph, mapping

    async def recorded_planner(self, planning_context):
        sections = [s.section_id for s in planning_context.audio_profile.structure.sections]
        captured["planned"].append(sections)
        replans = {("chorus",): CHORUS_REPLAN, ("intro",): INTRO_REPLAN}
        return IterationResult(
            success=True,
            plan=replans.get(tuple(sections), BASE_PLAN),
            context=IterationContext(current_iteration=1, state=IterationState.COMPLETE),
        )

    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setattr(cli_main, "XLightsAutomationClient", lambda: fake)
    monkeypatch.setattr(cli_main, "load_app_config", lambda _: AppConfig(llm_api_key="k"))
    monkeypatch.setattr(cli_main, "load_job_config", lambda _: physical_job())
    monkeypatch.setattr(cli_main, "load_fixture_group", lambda _: physical_rig())
    monkeypatch.setattr(cli_main, "build_run_pipeline", build)
    monkeypatch.setattr(
        cli_main,
        "TwinklrSession",
        lambda **kwargs: SimpleNamespace(
            app_config=kwargs["app_config"],
            job_config=kwargs["job_config"],
            session_id=kwargs["session_id"],
            llm_provider=MagicMock(),
            agent_cache=None,
            llm_logger=MagicMock(),
        ),
    )
    monkeypatch.setattr(MovingHeadPlannerOrchestrator, "run", recorded_planner)
    return captured


async def _live(tmp_path: Path, section_id: str | None = None, dry_run: bool = False) -> int:
    audio = tmp_path / "song.wav"
    if not audio.exists():
        audio.write_bytes(b"synthetic audio")
    return await cli_main.run_pipeline_async(
        audio_path=audio,
        output_dir=tmp_path / "out",
        app_config_path=tmp_path / "config.json",
        job_config_path=tmp_path / "job.json",
        live_injection=True,
        dry_run=dry_run,
        section_id=section_id,
    )


def _xsq_live_form(path: Path) -> list[tuple[str, int, str, str, str, int, int]]:
    """The written `.xsq`'s effects as xLights would hold them after injection: the
    model, the file layer moved into Twinklr's reserved layers, effect, settings,
    palette settings (none when the file defines no palette) and times."""
    sequence = XSQParser().parse(path)
    palettes = [palette.settings for palette in sequence.color_palettes]
    effects = []
    for element in sequence.element_effects:
        for index, layer in enumerate(element.layers):
            for effect in layer.effects:
                assert effect.ref is not None
                effects.append(
                    (
                        element.element_name,
                        TWINKLR_LAYER_BASE + index,
                        effect.effect_type,
                        sequence.effect_db.get(effect.ref) or "",
                        palettes[int(effect.palette)] if palettes else "",
                        effect.start_time_ms,
                        effect.end_time_ms,
                    )
                )
    return sorted(effects)


def _render_trace(tmp_path: Path) -> dict:
    (trace,) = (tmp_path / "out").glob("*/*_twinklr_mh.xsq.trace.json")
    return json.loads(trace.read_text(encoding="utf-8"))["render"]


def _section_cues(render: dict, section_id: str) -> list[dict]:
    return [cue for cue in render["quantized_cues"] if cue["section_id"] == section_id]


@pytest.mark.anyio
async def test_inject_on_a_physical_job_injects_exactly_the_written_xsq(
    tmp_path, monkeypatch, capsys
) -> None:
    """`twinklr inject` on a physical job renders as `twinklr run` does and injects the
    `.xsq`'s effects one for one: the same per-fixture models, layer, DMX settings and
    frame-aligned times. A second identical inject changes nothing."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    _live_physical_cli(monkeypatch, fake)

    with physical_test_templates():
        first = await _live(tmp_path)
        output = capsys.readouterr().out
        injected = fake.placed()
        fake.requests.clear()
        second = await _live(tmp_path)
    again = " ".join(capsys.readouterr().out.split())

    (xsq,) = (tmp_path / "out").glob("*/*_twinklr_mh.xsq")
    assert first == 0, output
    assert injected == _xsq_live_form(xsq)
    assert {model for model, *_ in injected} == {"Dmx MH1", "Dmx MH2"}
    assert len(injected) == _render_trace(tmp_path)["output"]["effect_count"]
    assert second == 0
    assert "addEffect" not in fake.requests and "deleteEffect" not in fake.requests
    assert f"0 added, 0 replaced, {len(injected)} unchanged" in again


@pytest.mark.anyio
async def test_regenerate_on_a_physical_job_rerenders_the_whole_song_and_replaces_its_effects(
    tmp_path, monkeypatch, capsys
) -> None:
    """`twinklr regenerate chorus` on a physical job re-plans only the chorus, renders the
    moving heads for the whole song from the previous plan with that section replaced,
    and makes the sequence hold exactly the new `.xsq`'s effects; the intro's plan and
    cues are unchanged, the chorus's are new, and the render identity changes."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    captured = _live_physical_cli(monkeypatch, fake)

    with physical_test_templates():
        assert await _live(tmp_path) == 0
        before = _render_trace(tmp_path)
        injected = fake.placed()
        capsys.readouterr()
        exit_code = await _live(tmp_path, section_id="chorus")
    output = " ".join(capsys.readouterr().out.split())
    after = _render_trace(tmp_path)

    (xsq,) = (tmp_path / "out").glob("*/*_twinklr_mh.xsq")
    assert exit_code == 0, output
    assert captured["planned"] == ["profile", ["intro", "chorus"], "profile", ["chorus"]]
    assert fake.placed() == _xsq_live_form(xsq)
    assert fake.placed() != injected
    assert _section_cues(after, "intro") == _section_cues(before, "intro")
    assert _section_cues(after, "chorus") != _section_cues(before, "chorus")
    assert {cue["fixture_id"] for cue in _section_cues(after, "chorus")} == {"MH2"}
    assert after["render_fingerprint"] != before["render_fingerprint"]
    assert after["template_sha256"].keys() == {TEMPLATE_ID, SUBSET_TEMPLATE_ID}
    assert "re-rendered the moving heads for the whole song" in output
    assert after["render_fingerprint"] in output


class _SongMetadataOnly:
    """The audio analysis `eval-report` runs, read only for the song's metadata."""

    def __init__(self, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> _SongMetadataOnly:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def analyze(self, path: str) -> SimpleNamespace:
        return SimpleNamespace(features={"tempo": {"bpm": 120.0}})


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("groups", "named"),
    [
        pytest.param(("GROUP - MOVING HEADS",), [], id="layout-holds-the-rig"),
        pytest.param(
            (),
            [
                "rig (fixture group): the run rendered on its rig as reconciled with the live "
                "xLights layout, which differs from this fixture config in xlights_group"
            ],
            id="layout-lacks-the-group",
        ),
    ],
)
async def test_eval_report_on_an_inject_names_the_rig_the_live_layout_reconciled(
    tmp_path, monkeypatch, groups, named
) -> None:
    """`inject` renders on the rig as the open layout leaves it and records that render.
    Where the layout holds the configured rig, `eval-report` reproduces it from the
    fixture config; where the layout lacks the group the config names, no fixture config
    reproduces it, and the report says why and names the field."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"), groups=groups)
    _live_physical_cli(monkeypatch, fake)
    # The plan as a planner states it, every intent field present, as the checkpoint
    # carries it.
    monkeypatch.setitem(
        globals(), "BASE_PLAN", ChoreographyPlan.model_validate(BASE_PLAN.model_dump(mode="json"))
    )
    fixture_path = tmp_path / "fixture_config.json"
    fixture_path.write_text(physical_rig().model_dump_json(), encoding="utf-8")

    with physical_test_templates():
        assert await _live(tmp_path) == 0
        (checkpoint,) = (tmp_path / "out").glob("*/checkpoints/plans/final.json")
        with patch("twinklr.core.audio.analyzer.AudioAnalyzer", _SongMetadataOnly):
            report = await generate_evaluation_report(
                checkpoint_path=checkpoint,
                audio_path=tmp_path / "song.wav",
                fixture_config_path=fixture_path,
                output_dir=tmp_path / "report",
            )

    assert json.loads(checkpoint.read_text())["render"]["inputs"]["rig"]["live_layout"] is True
    assert report.physical is not None
    assert report.physical.run_fingerprint == _render_trace(tmp_path)["render_fingerprint"]
    assert report.physical.fingerprint_matches is not named
    assert report.physical.mismatched_inputs == named


@pytest.mark.anyio
async def test_regenerate_on_a_physical_job_without_an_injected_plan_is_refused_before_planning(
    tmp_path, monkeypatch, capsys
) -> None:
    """A whole-song re-render needs the plan of the effects already in the sequence; with
    none recorded for it (no earlier `inject`, or only a dry run), nothing is planned."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    captured = _live_physical_cli(monkeypatch, fake)

    with physical_test_templates():
        assert await _live(tmp_path, dry_run=True) == 0
        captured["build_calls"] = 0
        capsys.readouterr()
        exit_code = await _live(tmp_path, section_id="chorus")
    output = " ".join(capsys.readouterr().out.split())

    assert exit_code == 1
    assert captured["build_calls"] == 0
    assert "run `twinklr inject` first" in output
    assert fake.placed() == []


@pytest.mark.anyio
async def test_regenerate_on_a_physical_job_twice_builds_on_each_recorded_plan(
    tmp_path, monkeypatch, capsys
) -> None:
    """inject, regenerate the chorus, regenerate the intro: neither regenerate is refused,
    each starts from the plan the one before recorded, and the record follows."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    _live_physical_cli(monkeypatch, fake)
    recorded: list[list[str | None]] = []

    with physical_test_templates():
        for section_id in (None, "chorus", "intro"):
            assert await _live(tmp_path, section_id=section_id) == 0, capsys.readouterr().out
            (record,) = json.loads(_live_plans(tmp_path).read_text(encoding="utf-8")).values()
            recorded.append([s["template_id"] for s in record["plan"]["sections"]])
            (xsq,) = (tmp_path / "out").glob("*/*_twinklr_mh.xsq")
            assert fake.placed() == _xsq_live_form(xsq)

    assert recorded == [
        [TEMPLATE_ID, TEMPLATE_ID],
        [TEMPLATE_ID, SUBSET_TEMPLATE_ID],
        [SUBSET_TEMPLATE_ID, SUBSET_TEMPLATE_ID],
    ]


@pytest.mark.anyio
async def test_regenerate_refuses_a_recorded_plan_the_gate_no_longer_admits_before_any_planner(
    tmp_path, monkeypatch, capsys
) -> None:
    """A kept section naming a template this run's pre-planning check did not admit is
    refused by that check, before the profile or any other planner runs."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    captured = _live_physical_cli(monkeypatch, fake)

    with physical_test_templates():
        assert await _live(tmp_path) == 0
        payload = json.loads(_live_plans(tmp_path).read_text(encoding="utf-8"))
        for record in payload.values():
            record["plan"]["sections"][0]["template_id"] = "fly_in_cascade"
        _live_plans(tmp_path).write_text(json.dumps(payload), encoding="utf-8")
        injected = fake.placed()
        captured["planned"].clear()
        capsys.readouterr()
        exit_code = await _live(tmp_path, section_id="chorus")
    output = " ".join(capsys.readouterr().out.split())

    assert exit_code == 1
    assert captured["planned"] == []
    assert "names template 'fly_in_cascade'" in output and "run `twinklr inject`" in output
    assert fake.placed() == injected


def _ownership_path(tmp_path: Path) -> Path:
    (path,) = (tmp_path / "out").glob("*/.twinklr-live-ownership.json")
    return path


def _drop_one_owned_effect(tmp_path: Path, monkeypatch) -> None:
    """As a partial or interrupted inject leaves it: the manifest no longer matches."""
    path = _ownership_path(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    for rows in payload.values():
        rows.pop()
    path.write_text(json.dumps(payload), encoding="utf-8")


def _change_audio(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "song.wav").write_bytes(b"another song")


def _change_job(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "load_job_config", lambda _: physical_job(max_effects=99_999))


def _change_rig(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "load_fixture_group", lambda _: physical_rig(mh1_pan_max=260.0))


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (_drop_one_owned_effect, "Twinklr's effects in the open sequence changed"),
        (_change_audio, "the audio differs"),
        (_change_job, "the job config differs"),
        (_change_rig, "the rig differs"),
    ],
)
async def test_regenerate_on_a_physical_job_refuses_a_stale_recorded_plan_before_planning(
    tmp_path, monkeypatch, capsys, change, reason
) -> None:
    """The recorded plan is used only while it still describes the sequence: the same
    owned effects, audio, job and rig as when it was injected."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    captured = _live_physical_cli(monkeypatch, fake)

    with physical_test_templates():
        assert await _live(tmp_path) == 0
        injected = fake.placed()
        change(tmp_path, monkeypatch)
        captured["build_calls"] = 0
        capsys.readouterr()
        exit_code = await _live(tmp_path, section_id="chorus")
    output = " ".join(capsys.readouterr().out.split())

    assert exit_code == 1, output
    assert captured["build_calls"] == 0
    assert reason in output and "run `twinklr inject` first" in output
    assert fake.placed() == injected


class _SwitchingSequence(FakeLiveXLights):
    """Reports another open sequence from its second `getOpenSequence` on."""

    async def get_open_sequence(self, request: object = None):
        opened = await super().get_open_sequence(request)
        if self.requests.count("getOpenSequence") > 1 and self.switch:
            return replace(opened, sequence_path=Path("/tmp/other.xsq"))
        return opened

    switch = False


@pytest.mark.anyio
async def test_regenerate_on_a_physical_job_refuses_a_sequence_switched_during_the_run(
    tmp_path, monkeypatch, capsys
) -> None:
    fake = _SwitchingSequence(models=("Dmx MH1", "Dmx MH2"))
    _live_physical_cli(monkeypatch, fake)

    with physical_test_templates():
        assert await _live(tmp_path) == 0
        injected = fake.placed()
        fake.requests.clear()
        fake.switch = True
        capsys.readouterr()
        exit_code = await _live(tmp_path, section_id="chorus")
    output = " ".join(capsys.readouterr().out.split())

    assert exit_code == 1
    assert "/tmp/other.xsq" in output
    assert fake.placed() == injected
    assert "addEffect" not in fake.requests and "deleteEffect" not in fake.requests


def _live_plans(tmp_path: Path) -> Path:
    return tmp_path / "out" / "song" / ".twinklr-live-plans.json"


@pytest.mark.anyio
@pytest.mark.parametrize("content", ["{not json", "[]"])
async def test_a_corrupt_live_plans_file_is_named_on_regenerate_and_on_inject(
    tmp_path, monkeypatch, capsys, content
) -> None:
    """Regenerate refuses naming the file and what to do; inject completes and says the
    plan was not recorded, without a traceback."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    _live_physical_cli(monkeypatch, fake)

    with physical_test_templates():
        assert await _live(tmp_path) == 0
        _live_plans(tmp_path).write_text(content, encoding="utf-8")
        capsys.readouterr()
        regenerated = await _live(tmp_path, section_id="chorus")
        refused = " ".join(capsys.readouterr().out.split())
        injected = await _live(tmp_path)
        recorded = " ".join(capsys.readouterr().out.split())

    path = str(_live_plans(tmp_path))
    assert regenerated == 1
    # Rich wraps a long path anywhere, so it is compared without whitespace.
    assert path in "".join(refused.split()) and "delete it" in refused
    assert injected == 0
    assert "Live injection complete" in recorded
    assert "plan was not recorded" in recorded and path in "".join(recorded.split())
    assert _live_plans(tmp_path).read_text(encoding="utf-8") == content


@pytest.mark.anyio
async def test_live_physical_injection_names_a_fixture_the_live_layout_lacks(
    tmp_path, monkeypatch, capsys
) -> None:
    """A fixture whose model the open layout does not have is named with what to do;
    the physical path never suggests the old renderer."""
    fake = FakeLiveXLights(models=("Dmx MH1",))
    captured = _live_physical_cli(monkeypatch, fake)

    with physical_test_templates():
        exit_code = await _live(tmp_path)
    output = " ".join(capsys.readouterr().out.split())

    assert exit_code == 1
    assert captured["build_calls"] == 0
    assert "MH2 ('Dmx MH2')" in output and "moving_heads.initial_states" in output
    assert "legacy_v1" not in output


@pytest.mark.anyio
async def test_live_physical_injection_refuses_a_rig_without_profiles_without_suggesting_legacy(
    tmp_path, monkeypatch, capsys
) -> None:
    rig = build_fixture_group(RIGS["mh4_minimal"])
    fake = FakeLiveXLights(models=tuple(f.xlights_model_name for f in rig.expand_fixtures()))
    captured = _live_physical_cli(monkeypatch, fake)
    monkeypatch.setattr(cli_main, "load_fixture_group", lambda _: rig)

    exit_code = await _live(tmp_path)
    output = " ".join(capsys.readouterr().out.split())

    assert exit_code == 1
    assert captured["build_calls"] == 0
    assert "MH1: physical_profile is missing" in output
    assert "legacy_v1" not in output


@pytest.mark.anyio
async def test_a_physical_dry_run_prints_a_summary_and_writes_every_command_to_a_file(
    tmp_path, monkeypatch, capsys
) -> None:
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    _live_physical_cli(monkeypatch, fake)

    with physical_test_templates():
        assert await _live(tmp_path, dry_run=True) == 0
    output = capsys.readouterr().out

    (written,) = (tmp_path / "out").glob("*/live-dry-run.jsonl")
    commands = [json.loads(line) for line in written.read_text(encoding="utf-8").splitlines()]
    assert {command["cmd"] for command in commands} == {"addEffect"}
    assert written.name in " ".join(output.split())
    for model in ("Dmx MH1", "Dmx MH2"):
        count = sum(command["target"] == model for command in commands)
        assert f"addEffect {model}: {count}" in output
    assert '"cmd": "addEffect"' not in output
    assert fake.placed() == []


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
    templates could render under the physical renderer (here, without the physical
    catalog, which otherwise always supplies some)."""
    calls = _prepared_physical_run(monkeypatch, physical_job(), physical_rig())
    monkeypatch.setattr(cli_main, "admit_physical_catalog", lambda _: [])

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
    assert sorted(call["available_templates"]) == sorted(
        [TEMPLATE_ID, SUBSET_TEMPLATE_ID, *CATALOG_IDS]
    )


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
    layout.write_text(physical_layout_xml({"Dmx MH2": {"DmxChannelCount": "16"}}), encoding="utf-8")
    captured = _captured_run(monkeypatch, physical_job(), physical_rig())

    with physical_test_templates():
        exit_code = await _run_with(tmp_path, layout)

    output = " ".join(capsys.readouterr().out.split())
    assert exit_code == 1
    assert captured["build_calls"] == 0
    assert "MH2: model 'Dmx MH2' has 16 channels by DmxChannelCount" in output


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
