"""CLI contract for live injection and per-section regeneration."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from tests.support.live_xlights import FakeLiveXLights
from tests.support.moving_heads import (
    ALL_CATALOG_IDS,
    SUBSET_TEMPLATE_ID,
    TEMPLATE_ID,
    bars_grid,
    family_catalog,
    p1_job,
    p1_layout_xml,
    p1_rig,
    p1_templates,
    plan_section,
    tagged_p1_rig,
    unprofiled_rig,
)
from twinklr.cli import main as cli_main
from twinklr.cli.profile_tags import PROFILE_TAGS_FILENAME, report_profile_tags
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
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
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
from twinklr.core.formats.xlights.sequence.fresh import build_fresh_sequence
from twinklr.core.formats.xlights.sequence.parser import XSQParser
from twinklr.core.pipeline import PipelineDefinition, StageDefinition
from twinklr.core.pipeline.result import PipelineResult, success_result
from twinklr.core.reporting.evaluation.generator import generate_evaluation_report


@pytest.fixture(autouse=True)
def _restore_template_registry() -> Iterator[None]:
    """`twinklr run` admits the family catalog into the shared registry; each test
    removes what its run registered."""
    with family_catalog(admit=False):
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
            context.set_state(
                "rendered_sequence",
                build_fresh_sequence(media_file="song.wav", duration_ms=500),
            )
            return PipelineResult(success=True)

    class FailingWorkflow:
        def __init__(self, client, *, ownership):
            pass

        async def inject(self, effects, *, dry_run=False, expected_sequence=None):
            raise InjectionPartialError(result)

    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setattr(cli_main, "XLightsAutomationClient", FakeXLightsClient)
    monkeypatch.setattr(cli_main, "load_app_config", lambda _: app_config)
    monkeypatch.setattr(cli_main, "load_job_config", lambda _: job_config)
    monkeypatch.setattr(cli_main, "load_fixture_group", lambda _: fixture_group)
    monkeypatch.setattr(cli_main, "load_template_catalog", list)
    monkeypatch.setattr(cli_main, "list_templates", list)
    monkeypatch.setattr(cli_main, "preflight_render_policy", lambda *args: None)
    monkeypatch.setattr(
        cli_main,
        "reconcile_live_layout",
        lambda *args, **kwargs: SimpleNamespace(
            rig=fixture_group,
            report=SimpleNamespace(has_divergence=False, configured_only_models=()),
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
    monkeypatch.setattr(cli_main, "live_effects_from_sequence", lambda *args: (effect,))
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


LIVE_GRID = bars_grid(500.0, 500.0, 500.0, 500.0)
"""Four 4/4 bars of 2 s: an intro on bars 1-2 and a chorus on bars 3-4."""
BASE_PLAN = ChoreographyPlan(
    sections=[
        plan_section(name, start, end, TEMPLATE_ID)
        for name, start, end in (("intro", 1, 2), ("chorus", 3, 4))
    ],
    overall_strategy="sweep, then sweep again",
)
CHORUS_REPLAN = ChoreographyPlan(
    sections=[plan_section("chorus", 3, 4, SUBSET_TEMPLATE_ID)],
    overall_strategy="the right head alone",
)
INTRO_REPLAN = ChoreographyPlan(
    sections=[plan_section("intro", 1, 2, SUBSET_TEMPLATE_ID)],
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


def _live_cli(monkeypatch, fake: FakeLiveXLights) -> dict:
    """Patch an `inject`/`regenerate` up to the real planner stage, render stage
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
    monkeypatch.setattr(cli_main, "load_job_config", lambda _: p1_job())
    monkeypatch.setattr(cli_main, "load_fixture_group", lambda _: p1_rig())
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
async def test_inject_injects_exactly_the_written_xsq(tmp_path, monkeypatch, capsys) -> None:
    """`twinklr inject` renders as `twinklr run` does and injects the
    `.xsq`'s effects one for one: the same per-fixture models, layer, DMX settings and
    frame-aligned times. A second identical inject changes nothing."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    _live_cli(monkeypatch, fake)

    with p1_templates():
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
async def test_regenerate_rerenders_the_whole_song_and_replaces_its_effects(
    tmp_path, monkeypatch, capsys
) -> None:
    """`twinklr regenerate chorus` re-plans only the chorus, renders the
    moving heads for the whole song from the previous plan with that section replaced,
    and makes the sequence hold exactly the new `.xsq`'s effects; the intro's plan and
    cues are unchanged, the chorus's are new, and the render identity changes."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    captured = _live_cli(monkeypatch, fake)

    with p1_templates():
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
    _live_cli(monkeypatch, fake)
    # The plan as a planner states it, every intent field present, as the checkpoint
    # carries it.
    monkeypatch.setitem(
        globals(), "BASE_PLAN", ChoreographyPlan.model_validate(BASE_PLAN.model_dump(mode="json"))
    )
    fixture_path = tmp_path / "fixture_config.json"
    fixture_path.write_text(p1_rig().model_dump_json(), encoding="utf-8")

    with p1_templates():
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
    assert report.render is not None
    assert report.render.run_fingerprint == _render_trace(tmp_path)["render_fingerprint"]
    assert report.render.fingerprint_matches is not named
    assert report.render.mismatched_inputs == named


@pytest.mark.anyio
async def test_regenerate_without_an_injected_plan_is_refused_before_planning(
    tmp_path, monkeypatch, capsys
) -> None:
    """A whole-song re-render needs the plan of the effects already in the sequence; with
    none recorded for it (no earlier `inject`, or only a dry run), nothing is planned."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    captured = _live_cli(monkeypatch, fake)

    with p1_templates():
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
async def test_regenerate_twice_builds_on_each_recorded_plan(tmp_path, monkeypatch, capsys) -> None:
    """inject, regenerate the chorus, regenerate the intro: neither regenerate is refused,
    each starts from the plan the one before recorded, and the record follows."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    _live_cli(monkeypatch, fake)
    recorded: list[list[str | None]] = []

    with p1_templates():
        for section_id in (None, "chorus", "intro"):
            assert await _live(tmp_path, section_id=section_id) == 0, capsys.readouterr().out
            (record,) = json.loads(_live_plans(tmp_path).read_text(encoding="utf-8")).values()
            recorded.append([s["parts"][0]["template_id"] for s in record["plan"]["sections"]])
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
    captured = _live_cli(monkeypatch, fake)

    with p1_templates():
        assert await _live(tmp_path) == 0
        payload = json.loads(_live_plans(tmp_path).read_text(encoding="utf-8"))
        for record in payload.values():
            record["plan"]["sections"][0]["parts"][0]["template_id"] = "fly_in_cascade"
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
    monkeypatch.setattr(cli_main, "load_job_config", lambda _: p1_job(max_effects=99_999))


def _change_rig(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "load_fixture_group", lambda _: p1_rig(mh1_pan_max=260.0))


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
async def test_regenerate_refuses_a_stale_recorded_plan_before_planning(
    tmp_path, monkeypatch, capsys, change, reason
) -> None:
    """The recorded plan is used only while it still describes the sequence: the same
    owned effects, audio, job and rig as when it was injected."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    captured = _live_cli(monkeypatch, fake)

    with p1_templates():
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
async def test_regenerate_refuses_a_sequence_switched_during_the_run(
    tmp_path, monkeypatch, capsys
) -> None:
    fake = _SwitchingSequence(models=("Dmx MH1", "Dmx MH2"))
    _live_cli(monkeypatch, fake)

    with p1_templates():
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
async def test_regenerate_refuses_a_plan_recorded_in_the_old_contract_by_name(
    tmp_path, monkeypatch, capsys
) -> None:
    """A plan recorded before the song-intent contract cannot be read: regenerate says
    so and to re-inject, before any planner runs, and leaves the sequence alone."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    captured = _live_cli(monkeypatch, fake)

    with p1_templates():
        assert await _live(tmp_path) == 0
        payload = json.loads(_live_plans(tmp_path).read_text(encoding="utf-8"))
        for record in payload.values():
            record["plan"]["sections"] = [
                {
                    "section_name": section["section_id"],
                    "start_bar": section["start_bar"],
                    "end_bar": section["end_bar"],
                    "template_id": section["parts"][0]["template_id"],
                }
                for section in record["plan"]["sections"]
            ]
        _live_plans(tmp_path).write_text(json.dumps(payload), encoding="utf-8")
        injected = fake.placed()
        captured["planned"].clear()
        capsys.readouterr()
        exit_code = await _live(tmp_path, section_id="chorus")
    output = " ".join(capsys.readouterr().out.split())

    assert exit_code == 1
    assert captured["planned"] == []
    assert "planner contract before 2026-11-17" in output
    assert "run `twinklr inject` to re-plan the whole song" in output
    assert fake.placed() == injected


@pytest.mark.anyio
async def test_regenerate_renders_the_kept_sections_through_their_injected_palettes(
    tmp_path, monkeypatch, capsys
) -> None:
    """The record keeps the section palettes the injected render used (a palette-role
    colour resolves through them); a regeneration renders every kept section through the
    recorded one and records it again. A record without them is refused, to re-inject."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    _live_cli(monkeypatch, fake)
    injected = {"palette_id": "core.rgb_primary", "stops": ["#FF1744", "#00E676"]}

    with p1_templates():
        assert await _live(tmp_path) == 0
        payload = json.loads(_live_plans(tmp_path).read_text(encoding="utf-8"))
        (record,) = payload.values()
        assert record["palettes"] == {}  # no macro plan in this run
        record["palettes"] = {"intro": injected, "chorus": injected}
        _live_plans(tmp_path).write_text(json.dumps(payload), encoding="utf-8")
        assert await _live(tmp_path, section_id="chorus") == 0, capsys.readouterr().out
        (record,) = json.loads(_live_plans(tmp_path).read_text(encoding="utf-8")).values()
        assert record["palettes"] == {"intro": injected}  # the re-planned one: this run's

        payload = json.loads(_live_plans(tmp_path).read_text(encoding="utf-8"))
        for entry in payload.values():
            del entry["palettes"]
        _live_plans(tmp_path).write_text(json.dumps(payload), encoding="utf-8")
        capsys.readouterr()
        assert await _live(tmp_path, section_id="chorus") == 1
    refused = " ".join(capsys.readouterr().out.split())
    assert "invalid record" in refused and "palettes" in refused and "delete it" in refused


@pytest.mark.anyio
@pytest.mark.parametrize("content", ["{not json", "[]"])
async def test_a_corrupt_live_plans_file_is_named_on_regenerate_and_on_inject(
    tmp_path, monkeypatch, capsys, content
) -> None:
    """Regenerate refuses naming the file and what to do; inject completes and says the
    plan was not recorded, without a traceback."""
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    _live_cli(monkeypatch, fake)

    with p1_templates():
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
async def test_live_injection_names_a_fixture_the_live_layout_lacks(
    tmp_path, monkeypatch, capsys
) -> None:
    """A fixture whose model the open layout does not have is named with what to do;
    the renderer never suggests the old renderer."""
    fake = FakeLiveXLights(models=("Dmx MH1",))
    captured = _live_cli(monkeypatch, fake)

    with p1_templates():
        exit_code = await _live(tmp_path)
    output = " ".join(capsys.readouterr().out.split())

    assert exit_code == 1
    assert captured["build_calls"] == 0
    assert "MH2 ('Dmx MH2')" in output and "moving_heads.initial_states" in output
    assert "legacy_v1" not in output


@pytest.mark.anyio
async def test_live_injection_refuses_a_rig_without_profiles_without_suggesting_legacy(
    tmp_path, monkeypatch, capsys
) -> None:
    rig = unprofiled_rig()
    fake = FakeLiveXLights(models=tuple(f.xlights_model_name for f in rig.expand_fixtures()))
    captured = _live_cli(monkeypatch, fake)
    monkeypatch.setattr(cli_main, "load_fixture_group", lambda _: rig)

    exit_code = await _live(tmp_path)
    output = " ".join(capsys.readouterr().out.split())

    assert exit_code == 1
    assert captured["build_calls"] == 0
    assert "MH1: physical_profile is missing" in output
    assert "legacy_v1" not in output


@pytest.mark.anyio
async def test_a_dry_run_prints_a_summary_and_writes_every_command_to_a_file(
    tmp_path, monkeypatch, capsys
) -> None:
    fake = FakeLiveXLights(models=("Dmx MH1", "Dmx MH2"))
    _live_cli(monkeypatch, fake)

    with p1_templates():
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
async def test_run_refuses_a_rig_without_profiles_before_planning(
    tmp_path, monkeypatch, capsys
) -> None:
    """`twinklr run` checks a job against the loaded rig before any analysis
    or provider request, naming each fixture and the missing item."""
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setattr(cli_main, "load_app_config", lambda _: AppConfig(llm_api_key="k"))
    monkeypatch.setattr(cli_main, "load_job_config", lambda _: JobConfig())
    monkeypatch.setattr(cli_main, "load_fixture_group", lambda _: unprofiled_rig())
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


def _prepared_run(monkeypatch, job, rig) -> list[dict]:
    """Patch `twinklr run` up to the pipeline build; return the captured build calls."""
    calls: list[dict] = []

    def capture(**kwargs):
        calls.append(kwargs)
        raise AssertionError("stop at the pipeline build")

    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setattr(cli_main, "load_app_config", lambda _: AppConfig(llm_api_key="k"))
    monkeypatch.setattr(cli_main, "load_job_config", lambda _: job)
    monkeypatch.setattr(cli_main, "load_fixture_group", lambda _: rig)
    monkeypatch.setattr(cli_main, "build_run_pipeline", capture)
    return calls


@pytest.mark.anyio
async def test_run_offers_the_planner_the_loaded_templates(tmp_path, monkeypatch) -> None:
    calls = _prepared_run(monkeypatch, p1_job(), p1_rig())

    with p1_templates(), pytest.raises(AssertionError, match="stop at"):
        await cli_main.run_pipeline_async(
            audio_path=tmp_path / "song.wav",
            output_dir=tmp_path,
            app_config_path=tmp_path / "config.json",
            job_config_path=tmp_path / "job.json",
        )

    (call,) = calls
    assert sorted(call["available_templates"]) == sorted(
        [TEMPLATE_ID, SUBSET_TEMPLATE_ID, *ALL_CATALOG_IDS]
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
async def test_run_refuses_a_model_the_layout_says_cannot_take_the_mapping(
    tmp_path, monkeypatch, capsys
) -> None:
    layout = tmp_path / "xlights_rgbeffects.xml"
    layout.write_text(p1_layout_xml({"Dmx MH2": {"DmxChannelCount": "16"}}), encoding="utf-8")
    captured = _captured_run(monkeypatch, p1_job(), p1_rig())

    with p1_templates():
        exit_code = await _run_with(tmp_path, layout)

    output = " ".join(capsys.readouterr().out.split())
    assert exit_code == 1
    assert captured["build_calls"] == 0
    assert "MH2: model 'Dmx MH2' has 16 channels by DmxChannelCount" in output


@pytest.mark.anyio
async def test_run_checks_the_rig_against_its_layout_and_hands_it_on(
    tmp_path, monkeypatch, capsys
) -> None:
    layout = tmp_path / "xlights_rgbeffects.xml"
    layout.write_text(p1_layout_xml(), encoding="utf-8")
    captured = _captured_run(monkeypatch, p1_job(), p1_rig())

    with p1_templates():
        await _run_with(tmp_path, layout)

    output = " ".join(capsys.readouterr().out.split())
    assert "model check was not performed" not in output
    state = captured["state"]
    assert [model.name for model in state["layout_models"]] == ["Dmx MH1", "Dmx MH2"]
    assert state["layout_sha256"] == hash_file_content(layout)


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
    """A job on a rig with a shared or blank model name stops before analysis."""
    payload = p1_rig().model_dump(mode="json")
    for fixture, name in zip(payload["fixtures"], names, strict=True):
        fixture["xlights_model_name"] = name
    rig = FixtureGroup.model_validate(payload)

    captured = _captured_run(monkeypatch, p1_job(), rig)
    with p1_templates():
        assert await _run_with(tmp_path, None) == 1
    assert captured["build_calls"] == 0
    assert message in " ".join(capsys.readouterr().out.split())


@pytest.mark.anyio
async def test_run_notes_untagged_wheel_states_once_and_writes_the_paste_ready_tags(
    tmp_path, monkeypatch, capsys
) -> None:
    """Before analysis, `twinklr run` says in one line which fixtures have wheel states
    the planner's colour, gobo and strobe choices cannot use, and where the paste-ready
    tags are; a colour the layout's model declares for a slot is suggested for MH1."""
    layout = tmp_path / "xlights_rgbeffects.xml"
    layout.write_text(
        p1_layout_xml({"Dmx MH1": {"DmxColorWheelColor0": "#E01010", "DmxColorWheelDMX0": "14"}}),
        encoding="utf-8",
    )
    _captured_run(monkeypatch, p1_job(), p1_rig())

    with p1_templates():
        await _run_with(tmp_path, layout)

    output = capsys.readouterr().out
    (note,) = [line for line in output.splitlines() if "NOTE:" in line]
    (tags,) = (tmp_path / "out").rglob(PROFILE_TAGS_FILENAME)
    assert note.startswith("NOTE: MH1, MH2: wheel or shutter states without a meaning tag")
    assert note.endswith(f"paste-ready tags to confirm: {tags}")
    assert '"pattern": "stars"' not in output  # the snippet is in the file, not inline
    text = tags.read_text(encoding="utf-8")
    assert "MH1 (profile 'synthetic_spot'): 6 wheel or shutter states do not say" in text
    assert "MH2 (profile 'synthetic_spot'): 6 wheel or shutter states do not say" in text
    assert "  color.red: hex \"#E01010\" (suggested from xLights model 'Dmx MH1')" in text
    assert (
        '    "star": {"range_min": 16, "range_max": 23, "value": 20, "settle_ms": 160, "pattern": "stars"}'
        in text
    )


@pytest.mark.anyio
async def test_run_on_a_fully_tagged_rig_prints_no_note_and_removes_stale_tags(
    tmp_path, monkeypatch, capsys
) -> None:
    _captured_run(monkeypatch, p1_job(), p1_rig())
    with p1_templates():
        await _run_with(tmp_path, None)
    (stale,) = (tmp_path / "out").rglob(PROFILE_TAGS_FILENAME)
    capsys.readouterr()

    _captured_run(monkeypatch, p1_job(), tagged_p1_rig())
    with p1_templates():
        await _run_with(tmp_path, None)

    assert "NOTE:" not in capsys.readouterr().out
    assert not stale.exists()


def test_profile_tags_fall_back_to_printing_in_full_when_the_file_cannot_be_written(
    tmp_path, capsys
) -> None:
    """A run never fails for the note: an unwritable directory prints the tags inline."""
    missing = tmp_path / "no-such-dir"

    report_profile_tags(Console(), p1_rig().expand_fixtures(), (), missing)

    output = capsys.readouterr().out
    assert "could not be written" in output
    assert "MH1, MH2 (profile 'synthetic_spot'): 6 wheel or shutter states" in output


def test_an_injected_plan_is_normalised_on_load(tmp_path: Path) -> None:
    """The code-owned motif relations of an injected plan are derived again on load: an
    injected RESOLVE (no macro thread is at hand here) and a stale source are not kept."""
    from tests.support import moving_heads as m
    from twinklr.cli.main import LIVE_PLAN_IDENTITY, _load_live_plan

    plan = ChoreographyPlan(
        sections=[
            m.plan_section("a", 1, 2, "mirror_wings", motif_id="mo"),
            m.plan_section(
                "b",
                3,
                4,
                "mirror_wings",
                motif_id="mo",
                motif_relation="RESOLVE",
                motif_source_id="zzz",
            ),
        ],
        overall_strategy="",
    )
    sequence = tmp_path / "song.xsq"
    path = tmp_path / ".twinklr-live-plans.json"
    path.write_text(
        json.dumps(
            {
                str(sequence): {
                    "plan": plan.model_dump(mode="json"),
                    "palettes": {},
                    **dict.fromkeys(LIVE_PLAN_IDENTITY, "x"),
                }
            }
        ),
        encoding="utf-8",
    )

    loaded = _load_live_plan(path, sequence)

    assert loaded is not None
    b = loaded[0].sections[1]
    assert (b.motif_relation, b.motif_source_id) == ("RESTATE", "a")
