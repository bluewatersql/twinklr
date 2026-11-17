"""`eval-report` on a run's checkpoint (P3-C1.1b).

The run is real down to the render: the pre-planning gate admits the family
catalog on a four-head rig, the planning stage writes its checkpoint and the render
stage renders, delivers and records its render in that checkpoint. Only the audio
analysis is replaced: a re-render takes its beat grid from the checkpoint, and
the analysis supplies the report's song metadata alone. No provider, owner data or
xLights is touched.
"""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from click.testing import CliRunner
import pytest

from tests.support.moving_heads import (
    FAMILY_IDS,
    ZOOM_FAMILY_ID,
    bars_grid,
    family_catalog,
    family_job,
    family_rig,
    physical_head_profile,
    sections_plan,
    zoom_job,
    zoom_pilot_profile_payload,
    zoom_rig,
)
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    EventAction,
    PlanColor,
    PlanEvent,
    PlanRepair,
    RepairAction,
)
from twinklr.core.agents.sequencer.moving_heads.rendering_stage import (
    MovingHeadRenderingStage,
    RenderPreflightStage,
)
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage
from twinklr.core.config.fixtures import FixtureCapabilities
from twinklr.core.config.render_policy import UnsupportedRenderModeError
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.reporting.evaluation.cli import eval_report_cli
from twinklr.core.reporting.evaluation.generator import (
    _beyond_travel,
    _boundary_steps,
    _mismatched_inputs,
    _section_fact_flags,
    _section_facts,
    generate_evaluation_report,
)
from twinklr.core.reporting.evaluation.models import (
    EvaluationReport,
    LitStep,
    ReportFlagLevel,
    SectionRenderFacts,
)
from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.templates.library import REGISTRY
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.session import TwinklrSession

HEADS = ("MH1", "MH2", "MH3", "MH4")
GRID = bars_grid(500.0, 500.0, 430.0, 500.0)
FLICK = "masked_wheel_flick"  # left out: the rig declares no `flick` attribute preset


class _FakeAnalyzer:
    """Stands in for the audio analysis, which a report reads only for the
    song's metadata."""

    def __init__(self, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> _FakeAnalyzer:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def analyze(self, path: str) -> SimpleNamespace:
        return SimpleNamespace(features={"tempo": {"bpm": 120.0}})


def _plan(*sections: tuple[str, int, int]) -> ChoreographyPlan:
    # Through JSON, as a planner's plan arrives, with the reasons the validator requires.
    data = sections_plan(*sections).model_dump(mode="json")
    data["overall_strategy"] = "The heads follow the song's energy from section to section."
    for section in data["sections"]:
        section["reasoning"] = "Answers the section's energy with one fitting template."
    return ChoreographyPlan.model_validate(data)


PLAN = _plan(("target_orbit", 1, 2), ("mirror_wings", 3, 4))


def _grid(shift_ms: float, *beat_ms: float) -> BeatGrid:
    """`bars_grid(*beat_ms)` moved `shift_ms` (instead of 15 ms) off the frame
    grid."""
    grid = bars_grid(*beat_ms)
    move = shift_ms - grid.bar_boundaries[0]
    beats = [beat + move for beat in grid.beat_boundaries]
    return grid.model_copy(
        update={
            "bar_boundaries": [bar + move for bar in grid.bar_boundaries],
            "beat_boundaries": beats,
            "eighth_boundaries": BeatGrid._calculate_eighth_boundaries(beats),
            "sixteenth_boundaries": BeatGrid._calculate_sixteenth_boundaries(beats),
            "duration_ms": grid.duration_ms + move,
        }
    )


async def _run(
    tmp_path: Path,
    *,
    grid: BeatGrid = GRID,
    plan: ChoreographyPlan = PLAN,
    gate: bool = True,
    zoom: bool = False,
) -> tuple[Path, Path, dict[str, Any]]:
    """A run: gate (unless `gate` is false), plan checkpoint, render, on the
    family rig (with `zoom`, the zoom pilot rig and every family). Returns the
    checkpoint, the fixture config and the run's trace."""
    rig = zoom_rig(HEADS) if zoom else family_rig(HEADS, presets=False)
    job = zoom_job(HEADS) if zoom else family_job(HEADS)
    templates = [*FAMILY_IDS, ZOOM_FAMILY_ID] if zoom else list(FAMILY_IDS)
    fixture_path = tmp_path / "fixture_config.json"
    fixture_path.write_text(rig.model_dump_json(), encoding="utf-8")
    output_dir = tmp_path / "artifacts"
    session = TwinklrSession(job_config=job, session_id="family-eval", project_root=tmp_path)
    context = PipelineContext(session=session, output_dir=output_dir)
    context.set_state("beat_grid", grid)

    if gate:
        preflight = RenderPreflightStage(
            available_templates=templates, fixture_config_path=fixture_path
        )
        assert (await preflight.execute(object(), context)).success
    MovingHeadStage(fixture_count=len(HEADS), available_templates=templates)._handle_state(
        {"plan": plan.model_dump(mode="json")}, context
    )
    xsq = output_dir / "song_twinklr_mh.xsq"
    render = MovingHeadRenderingStage(xsq_output_path=xsq, fixture_config_path=fixture_path)
    result = await render.execute({"moving_heads": plan}, context)
    assert result.success, result.error
    trace = json.loads(Path(f"{xsq}.trace.json").read_text(encoding="utf-8"))
    return output_dir / "checkpoints" / "plans" / "final.json", fixture_path, trace


async def _report(
    tmp_path: Path, checkpoint: Path, fixture_path: Path, out: str
) -> EvaluationReport:
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"not analyzed")
    with patch("twinklr.core.audio.analyzer.AudioAnalyzer", _FakeAnalyzer):
        return await generate_evaluation_report(
            checkpoint_path=checkpoint,
            audio_path=audio,
            fixture_config_path=fixture_path,
            output_dir=tmp_path / out,
        )


@pytest.mark.asyncio
async def test_checkpoint_reports_the_render_the_run_made(tmp_path: Path) -> None:
    with family_catalog():
        checkpoint, fixture_path, trace = await _run(tmp_path)
        report = await _report(tmp_path, checkpoint, fixture_path, "report")
        again = await _report(tmp_path, checkpoint, fixture_path, "again")

    run = trace["render"]
    summary = report.render
    # The re-render is the run's render: its fingerprint, recorded in the trace, matches.
    assert summary.run_fingerprint == run["render_fingerprint"]
    assert summary.rerender_fingerprint == run["render_fingerprint"]
    assert summary.fingerprint_matches is True
    # The gate's facts, as the run's trace records them.
    assert [e["template_id"] for e in summary.admission_exclusions] == [FLICK]
    assert summary.admission_exclusions == run["admission_exclusions"]
    assert summary.admission_preset_exclusions == run.get("admission_preset_exclusions", [])
    assert summary.admission_effective_presets == run.get("admission_effective_presets", {})
    assert summary.unplayable_totals == run["unplayable_totals"]
    # A run renders no dark spans; its record and report say none.
    assert "dark_spans" not in json.loads(checkpoint.read_text())["render"]
    assert (summary.dark_spans, summary.dark_span_ms) == ([], 0)

    assert report.summary.sections == 2
    for section, (start_bar, end_bar) in zip(report.sections, ((1, 2), (3, 4)), strict=True):
        assert section.time_range_ms == (
            int(GRID.get_bar_start_ms(start_bar - 1)),
            int(GRID.get_bar_start_ms(end_bar)),
        )
        facts = section.render_facts
        assert facts.entry_windows == [
            w for w in run["entry_windows"] if w["section_id"] == section.section_id
        ]
        assert facts.dropped_cues == [
            c for c in run["dropped_cues"] if c["section_id"] == section.section_id
        ]
        assert facts.transactions == {"feasible": 4}  # one per head entering the section
        # Every head's largest step in each channel, and no lit step beyond travel speed.
        assert {(s.fixture_id, s.channel) for s in facts.lit_steps} == {
            (head, channel) for head in HEADS for channel in ("pan", "tilt", "dimmer")
        }
        assert all(s.lit for s in facts.lit_steps if s.channel != "dimmer")  # not repositioning
        assert not [f for f in section.flags if f.code == "LIT_STEP_EXCEEDS_TRAVEL"]
        assert {curve.channel for curve in section.curves} == {"pan", "tilt", "dimmer"}
        for curve in section.curves:
            assert curve.space == ("normalized" if curve.channel == "dimmer" else "degree")
            if curve.channel == "dimmer":
                assert (curve.lit_range, curve.lit_rate) == (None, None)
            else:
                assert curve.lit_range is not None and curve.lit_range <= curve.stats.range
            assert curve.plot_path is not None and curve.plot_path.exists()

    written = json.loads((tmp_path / "report" / "report.json").read_text(encoding="utf-8"))
    assert written["render"]["fingerprint_matches"] is True
    # The old renderer's metrics are not in the report at all.
    assert not {"physics_violations", "compliance_issues", "harsh_transitions"} & set(
        written["summary"]
    )
    assert "not_reported" not in written["render"]
    for section in written["sections"]:
        assert not {"template_compliance", "transition_to_next"} & set(section)
        assert "steps" not in section["selected_template"]
    for curve in (c for s in written["sections"] for c in s["curves"]):
        assert "clamp_pct" not in curve["stats"]
        assert not {
            "continuity",
            "physics_check",
            "curve_type",
            "handler",
            "base_position",
            "static_dmx",
        } & set(curve)
    markdown = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    assert "## Render\n" in markdown
    assert run["render_fingerprint"] in markdown
    assert "Not reported" not in markdown
    assert "clamp=" not in markdown and "loop=" not in markdown
    assert "Dark spans" not in markdown
    # Nothing is written beside the report but the report and its plots.
    assert not list((tmp_path / "report").rglob("*.xsq"))

    # Deterministic: the same checkpoint gives the same report, provenance aside.
    def content(r: EvaluationReport) -> dict[str, Any]:
        dumped = r.model_dump(mode="json", exclude={"run"})
        for section in dumped["sections"]:
            for curve in section["curves"]:
                curve["plot_path"] = Path(curve["plot_path"]).name
        return dumped

    assert content(again) == content(report)


def _rename_model(fixture_path: Path, checkpoint: Path) -> None:
    rig = json.loads(fixture_path.read_text(encoding="utf-8"))
    rig["fixtures"][0]["xlights_model_name"] = "Renamed MH1"
    fixture_path.write_text(json.dumps(rig), encoding="utf-8")


def _rename_profile(fixture_path: Path, checkpoint: Path) -> None:
    rig = json.loads(fixture_path.read_text(encoding="utf-8"))
    rig["fixtures"][1]["config"]["physical_profile"]["profile_id"] = "another_spot"
    fixture_path.write_text(json.dumps(rig), encoding="utf-8")


def _rename_group(fixture_path: Path, checkpoint: Path) -> None:
    """A group-level field the fixtures do not carry: the xLights group's name."""
    rig = json.loads(fixture_path.read_text(encoding="utf-8"))
    rig["xlights_group"] = "Renamed group"
    fixture_path.write_text(json.dumps(rig), encoding="utf-8")


def _forge_identity(fixture_path: Path, checkpoint: Path) -> None:
    data = json.loads(checkpoint.read_text(encoding="utf-8"))
    data["render"]["render_fingerprint"] = "0" * 64
    checkpoint.write_text(json.dumps(data), encoding="utf-8")


def _change_template(fixture_path: Path, checkpoint: Path) -> None:
    """The registered `mirror_wings` document changes after the run (its description)."""
    document = REGISTRY.get("mirror_wings")
    template = document.template.model_copy(
        update={
            "metadata": document.template.metadata.model_copy(update={"description": "changed"})
        }
    )
    REGISTRY.register_document(
        document.model_copy(update={"template": template}),
        source=REGISTRY.source("mirror_wings"),
        allow_override=True,
    )


@pytest.mark.asyncio
async def test_the_report_carries_each_sections_song_intent_and_the_plan_repairs(
    tmp_path: Path,
) -> None:
    """The planner's song intent is reported per section as planned, with what the render
    played of its colour and the fields the renderer does not render yet; the plan's
    repairs are reported from the trace."""
    accented = PLAN.sections[0].model_copy(
        update={
            "intensity": Intensity.DRAMATIC,
            "color": PlanColor.PALETTE_ACCENT,
            "events": [
                PlanEvent(
                    bar=2,
                    beat=3,
                    moment_cue_id=None,
                    action=EventAction.HIT,
                    color=None,
                    gobo=None,
                )
            ],
        }
    )
    repair = PlanRepair(
        section_id="s1",
        item="moment cue 'ghost'",
        action=RepairAction.DROPPED,
        reason="no lyric moment cue has id 'ghost'",
    )
    plan = PLAN.model_copy(update={"sections": [accented, PLAN.sections[1]], "repairs": [repair]})
    with family_catalog():
        checkpoint, fixture_path, _ = await _run(tmp_path, plan=plan)
        report = await _report(tmp_path, checkpoint, fixture_path, "report")

    first, second = (section.song_intent for section in report.sections)
    assert first is not None and second is not None
    assert (first.intensity, first.color, first.gobo) == ("DRAMATIC", "PALETTE_ACCENT", None)
    assert first.events == ["bar 2 beat 3: hit"]
    assert first.not_rendered == ["intensity", "events"]
    # The family rig's colour wheel carries no tags: the colour plays on no head.
    (played,) = first.played
    assert played.startswith("colour PALETTE_ACCENT (#FF00FF, fixed table (magenta: ")
    assert played.endswith("no head shows it; MH1, MH2, MH3, MH4 keep their authored colour")
    assert second.not_rendered == [] and second.intensity is None
    assert report.render.plan_repairs == [repair.model_dump(mode="json")]
    markdown = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    assert "**Song intent** (as planned):" in markdown
    assert "- intensity: DRAMATIC" in markdown and "- intensity: as authored" in markdown
    assert "not rendered yet (intensity, events): a known regression" in markdown
    assert f"- played: {played}" in markdown
    assert "**Plan repair** (section `s1`): moment cue 'ghost' dropped" in markdown


@pytest.mark.parametrize(
    ("change", "named"),
    [
        pytest.param(_forge_identity, [], id="recorded-identity"),
        pytest.param(
            _rename_model,
            ["fixture 'MH1': xLights model name", "rig (fixture group): fixtures"],
            id="model-name",
        ),
        pytest.param(
            _rename_profile,
            ["fixture 'MH2': physical profile", "rig (fixture group): fixtures"],
            id="profile",
        ),
        pytest.param(_rename_group, ["rig (fixture group): xlights_group"], id="rig-group"),
        pytest.param(_change_template, ["template 'mirror_wings'"], id="template"),
    ],
)
@pytest.mark.asyncio
async def test_a_fingerprint_mismatch_is_reported_with_the_input_that_differs(
    tmp_path: Path, change: Any, named: list[str]
) -> None:
    """A re-render that is not the run's render is reported as an error naming the
    recorded input that differs, and the report is still written."""
    with family_catalog():
        checkpoint, fixture_path, _ = await _run(tmp_path)
        change(fixture_path, checkpoint)
        run_fingerprint = json.loads(checkpoint.read_text())["render"]["render_fingerprint"]
        report = await _report(tmp_path, checkpoint, fixture_path, "report")

    assert report.render is not None
    assert report.render.fingerprint_matches is False
    assert report.render.run_fingerprint == run_fingerprint
    assert report.render.rerender_fingerprint != run_fingerprint
    assert report.render.mismatched_inputs == named
    [mismatch] = [f for f in report.sections[0].flags if f.code == "RENDER_FINGERPRINT_MISMATCH"]
    assert mismatch.level == ReportFlagLevel.ERROR
    for input_name in named:
        assert input_name in mismatch.message
    if not named:
        assert "no recorded input differs" in mismatch.message
        assert "plan or recorded policy" in mismatch.message
    assert report.summary.total_errors >= 1
    markdown = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    assert "does not match" in markdown
    for input_name in named:
        assert f"  - differs: {input_name}" in markdown


def test_the_command_prints_a_mismatch(tmp_path: Path) -> None:
    with family_catalog():
        checkpoint, fixture_path, _ = asyncio.run(_run(tmp_path))
        _rename_model(fixture_path, checkpoint)
        audio = tmp_path / "song.wav"
        audio.write_bytes(b"not analyzed")
        with patch("twinklr.core.audio.analyzer.AudioAnalyzer", _FakeAnalyzer):
            result = CliRunner().invoke(
                eval_report_cli,
                [
                    *("--checkpoint", str(checkpoint), "--audio", str(audio)),
                    *("--fixture", str(fixture_path), "--out", str(tmp_path / "out")),
                ],
            )

    assert result.exit_code == 0, result.output
    assert "does not match the run's" in result.output
    assert "fixture 'MH1': xLights model name" in result.output


@pytest.mark.asyncio
async def test_a_skipped_entry_reports_its_lit_step_across_the_boundary(tmp_path: Path) -> None:
    """MH1 plays from the target orbit (bars 5-8) into the mirror wings (bars 9-12)
    without a dark entry: lit at full intensity, its pan steps from the orbit's 25° at
    16000 ms to the wings' 35° at 16020 ms (bar 9 starts at 16015 ms, on frame 16020).
    That is within the 14.4° a 720°/s head travels in a frame (plus one 16-bit word)."""
    plan = _plan(("target_orbit", 1, 4), ("target_orbit", 5, 8), ("mirror_wings", 9, 12))
    with family_catalog():
        checkpoint, fixture_path, _ = await _run(tmp_path, grid=bars_grid(*[500.0] * 12), plan=plan)
        report = await _report(tmp_path, checkpoint, fixture_path, "report")

    wings = report.sections[2]
    assert wings.render_facts is not None
    entry = {w["fixture_id"]: w["action"] for w in wings.render_facts.entry_windows}
    assert entry["MH1"] == "skipped"
    steps = {(s.fixture_id, s.channel): s for s in wings.render_facts.boundary_steps}
    assert {fixture for fixture, _ in steps} == {f for f, a in entry.items() if a == "skipped"}
    pan, tilt, dimmer = (steps["MH1", channel] for channel in ("pan", "tilt", "dimmer"))
    assert (pan.from_ms, pan.to_ms, pan.lit) == (16000, 16020, True)
    # The orbit, a circle of 25° pan and 15° tilt about 30° tilt over 4 beats (2000 ms),
    # is one frame short of the top of its circle at 16000 ms; the wings start at 35°
    # pan and 30° tilt. Within a 16-bit word (0.01°).
    angle = 2 * math.pi * 20 / 2000
    assert pan.change == pytest.approx(35.0 - 25.0 * math.cos(angle), abs=0.01)
    assert tilt.change == pytest.approx(15.0 * math.sin(angle), abs=0.01)
    assert pan.allowed == pytest.approx(720 * 0.02 + 540 / 65535)
    assert dimmer.change == 0.0 and dimmer.allowed is None
    assert not [f for s in report.sections for f in s.flags if f.code == "LIT_STEP_EXCEEDS_TRAVEL"]


@pytest.mark.asyncio
async def test_a_zoom_axis_is_reported_like_pan_and_tilt(tmp_path: Path) -> None:
    """On the zoom pilot rig the zoom wave's zoom is read in degrees, within the axis'
    10°-40° beam angle, with its lit range and its largest lit step per head."""
    with family_catalog():
        checkpoint, fixture_path, _ = await _run(
            tmp_path, plan=_plan((ZOOM_FAMILY_ID, 1, 4)), zoom=True
        )
        report = await _report(tmp_path, checkpoint, fixture_path, "report")

    assert report.render is not None and report.render.fingerprint_matches
    [section] = report.sections
    zoom = next(c for c in section.curves if c.channel == "zoom")
    assert zoom.space == "degree"
    assert 10.0 <= zoom.stats.min < zoom.stats.max <= 40.0
    assert zoom.lit_range is not None and zoom.lit_range > 0
    assert section.render_facts is not None
    assert {s.fixture_id for s in section.render_facts.lit_steps if s.channel == "zoom"} == set(
        HEADS
    )
    assert not [f for f in section.flags if f.code == "LIT_STEP_EXCEEDS_TRAVEL"]
    assert "zoom (degree)" in (tmp_path / "report" / "report.md").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_sections_are_windowed_on_the_frames_their_cues_land_on(tmp_path: Path) -> None:
    """Bar 3 starts at 4005 ms, which a cue lands on as frame 4000: that frame and the
    entry transactions there belong to the wings, so the orbit's pan stays within its
    ±25° and each section counts its own four entries."""
    with family_catalog():
        checkpoint, fixture_path, _ = await _run(
            tmp_path, grid=_grid(5.0, 500.0, 500.0, 430.0, 500.0)
        )
        report = await _report(tmp_path, checkpoint, fixture_path, "report")

    orbit, wings = report.sections
    assert orbit.time_range_ms[1] == wings.time_range_ms[0] == 4005
    pan = next(c for c in orbit.curves if c.channel == "pan")
    assert pan.stats.max == pytest.approx(25.0, abs=0.01)
    assert orbit.render_facts is not None and wings.render_facts is not None
    assert orbit.render_facts.transactions == wings.render_facts.transactions == {"feasible": 4}


@pytest.mark.asyncio
async def test_a_plan_naming_a_template_eval_report_cannot_load_is_refused_early(
    tmp_path: Path,
) -> None:
    with family_catalog():
        checkpoint, fixture_path, _ = await _run(tmp_path)
    data = json.loads(checkpoint.read_text(encoding="utf-8"))
    data["plan"]["sections"][1]["parts"][0]["template_id"] = "my_user_template"
    checkpoint.write_text(json.dumps(data), encoding="utf-8")

    with (
        family_catalog(admit=False),
        patch("twinklr.core.audio.analyzer.AudioAnalyzer") as analyzer,
        pytest.raises(UnsupportedRenderModeError, match=r"my_user_template.*--template-dir"),
    ):
        await generate_evaluation_report(
            checkpoint_path=checkpoint,
            audio_path=tmp_path / "song.wav",
            fixture_config_path=fixture_path,
            output_dir=tmp_path / "report",
        )
    analyzer.assert_not_called()


@pytest.mark.asyncio
def _drop_beat_grid(render: dict[str, Any]) -> Any:
    del render["beat_grid"]
    return render


def _bad_fixture_hashes(render: dict[str, Any]) -> Any:
    render["inputs"]["fixtures"] = "MH1"
    return render


def _drop_rig(render: dict[str, Any]) -> Any:
    """A record written before the rig's identity was: refused, not read."""
    del render["inputs"]["rig"]
    return render


def _bad_template_hashes(render: dict[str, Any]) -> Any:
    render["inputs"]["template_sha256"] = ["mirror_wings"]
    render["render_fingerprint"] = "0" * 64  # a mismatch would compare them
    return render


@pytest.mark.parametrize(
    "damage",
    [_drop_beat_grid, _bad_fixture_hashes, _drop_rig, _bad_template_hashes, lambda render: []],
    ids=["no-beat-grid", "fixture-hashes", "no-rig", "template-hashes", "not-a-mapping"],
)
@pytest.mark.asyncio
async def test_a_malformed_render_record_is_refused_with_a_message(
    tmp_path: Path, damage: Any
) -> None:
    """Refused before any audio is analyzed, whichever part is damaged."""
    with family_catalog():
        checkpoint, fixture_path, _ = await _run(tmp_path)
        data = json.loads(checkpoint.read_text(encoding="utf-8"))
        data["render"] = damage(data["render"])
        checkpoint.write_text(json.dumps(data), encoding="utf-8")
        with (
            patch("twinklr.core.audio.analyzer.AudioAnalyzer") as analyzer,
            pytest.raises(UnsupportedRenderModeError, match="malformed"),
        ):
            await generate_evaluation_report(
                checkpoint_path=checkpoint,
                audio_path=tmp_path / "song.wav",
                fixture_config_path=fixture_path,
                output_dir=tmp_path / "report",
            )
    analyzer.assert_not_called()


@pytest.mark.asyncio
async def test_a_checkpoint_without_a_record_is_refused_with_what_is_true(
    tmp_path: Path,
) -> None:
    """`run`, `show`, `inject` and `regenerate` all plan, then record their render: a
    checkpoint without the record stopped before its render was delivered or could not
    record it, and re-running the command writes it. Refused before any analysis."""
    with family_catalog():
        checkpoint, fixture_path, _ = await _run(tmp_path)
        data = json.loads(checkpoint.read_text(encoding="utf-8"))
        del data["render"]
        checkpoint.write_text(json.dumps(data), encoding="utf-8")
        with (
            patch("twinklr.core.audio.analyzer.AudioAnalyzer") as analyzer,
            pytest.raises(UnsupportedRenderModeError) as refused,
        ):
            await generate_evaluation_report(
                checkpoint_path=checkpoint,
                audio_path=tmp_path / "song.wav",
                fixture_config_path=fixture_path,
                output_dir=tmp_path / "report",
            )
    analyzer.assert_not_called()
    message = " ".join(str(refused.value).split())
    assert "records none" in message
    assert "stopped before it delivered its moving-head render" in message
    assert "could not write the record" in message
    assert "re-running that command records it" in message
    assert "re-run the job through its render" not in message


@pytest.mark.asyncio
async def test_a_record_whose_policy_names_mode_is_refused_with_the_remedy(
    tmp_path: Path,
) -> None:
    """A record written before the cutover to one renderer has `policy.mode`; it is
    refused, not read, naming why and what to do."""
    with family_catalog():
        checkpoint, fixture_path, _ = await _run(tmp_path)
        data = json.loads(checkpoint.read_text(encoding="utf-8"))
        data["render"]["policy"]["mode"] = "physical_v2"
        checkpoint.write_text(json.dumps(data), encoding="utf-8")
        with (
            patch("twinklr.core.audio.analyzer.AudioAnalyzer") as analyzer,
            pytest.raises(UnsupportedRenderModeError) as refused,
        ):
            await generate_evaluation_report(
                checkpoint_path=checkpoint,
                audio_path=tmp_path / "song.wav",
                fixture_config_path=fixture_path,
                output_dir=tmp_path / "report",
            )
    analyzer.assert_not_called()
    message = " ".join(str(refused.value).split())
    assert "its policy names `mode`" in message
    assert "re-run the command that planned it to plan and record it again" in message


@pytest.mark.asyncio
async def test_a_run_without_a_gate_result_validates_against_the_catalog(tmp_path: Path) -> None:
    """With no recorded gate result, the plan is validated against the registry with the
    family catalog loaded, as the run loaded it."""
    with family_catalog():
        checkpoint, fixture_path, _ = await _run(tmp_path, gate=False)
    assert json.loads(checkpoint.read_text())["render"]["admission"] is None

    with family_catalog(admit=False):
        report = await _report(tmp_path, checkpoint, fixture_path, "report")

    assert report.summary.validation_errors == 0
    assert report.render is not None and report.render.fingerprint_matches


def test_section_facts_select_the_sections_records_and_flag_what_was_kept_dark() -> None:
    """A section's facts are the trace records naming it, and the transactions of cues
    starting in its window; cues kept dark raise one warning, each diagnostic a flag."""
    dropped = {"section_id": "s1", "fixture_id": "MH1", "reason": "unplayable", "code": "x"}
    window = {"section_id": "s1", "fixture_id": "MH1", "window_end_ms": 600, "action": "cut"}
    record = {
        "entry_windows": [window, {"section_id": "s2"}],
        "dropped_cues": [dropped, dropped | {"reason": "entry_window"}, {"section_id": "s2"}],
        "transactions": [
            {"cue_ms": 0, "status": "feasible"},
            {"cue_ms": 999, "status": "drop_accent"},
            {"cue_ms": 1000, "status": "feasible"},
        ],
        "diagnostics": [
            {"section_id": "s1", "severity": "warning", "message": "m", "code": "c"},
            {"section_id": None, "severity": "error", "message": "other", "code": "c"},
        ],
    }
    facts = _section_facts(record, "s1", (0, 1000))

    assert facts.entry_windows == [window]
    assert facts.dropped_cues == record["dropped_cues"][:2]
    assert facts.transactions == {"drop_accent": 1, "feasible": 1}
    assert facts.diagnostics == record["diagnostics"][:1]
    kept_dark, diagnostic = _section_fact_flags(facts, section_end_ms=1000)
    # A section that ends inside a head's entry window renders that head dark.
    assert [f.code for f in _section_fact_flags(facts, section_end_ms=600)] == [
        "CUES_KEPT_DARK",
        "SECTION_DARK_FOR_ENTRY",
        "RENDER_DIAGNOSTIC",
    ]
    assert (kept_dark.code, kept_dark.level) == ("CUES_KEPT_DARK", ReportFlagLevel.WARNING)
    assert kept_dark.message == "2 cue(s) kept dark (entry_window: 1, unplayable: 1)"
    assert (diagnostic.code, diagnostic.level, diagnostic.message) == (
        "RENDER_DIAGNOSTIC",
        ReportFlagLevel.WARNING,
        "m",
    )


def test_a_boundary_step_starts_at_the_last_lit_frame_before_the_section() -> None:
    """A skipped head dark in the frames before the section is compared from its last
    lit frame (20 ms), over 60 ms, which its 720°/s travel allows 43.2° (plus a word)."""
    profile = FixtureCapabilities.model_validate(physical_head_profile(inverted=False))
    song = {
        "MH1": {
            "pan": [0.0, 5.0, 9.0, 9.0, 30.0, 31.0],
            "dimmer": [1.0, 1.0, 0.0, 0.0, 1.0, 1.0],
        },
        "MH2": {"pan": [0.0] * 6, "dimmer": [1.0] * 6},
        # Skipped, but dark on the section's first frame: the change is not seen lit.
        "MH3": {"pan": [0.0, 0.0, 0.0, 0.0, 90.0, 90.0], "dimmer": [1.0] * 4 + [0.0] * 2},
    }
    windows = [
        {"fixture_id": "MH1", "action": "skipped"},
        {"fixture_id": "MH2", "action": "cut"},
        {"fixture_id": "MH3", "action": "skipped"},
    ]
    profiles = dict.fromkeys(("MH1", "MH2", "MH3"), profile)

    pan, dimmer, dark_pan, _ = _boundary_steps(song, profiles, windows, 80)
    assert (pan.fixture_id, pan.channel, pan.from_ms, pan.to_ms) == ("MH1", "pan", 20, 80)
    assert (pan.change, pan.lit, pan.beyond_travel) == (25.0, True, False)
    assert pan.allowed == pytest.approx(720 * 0.06 + 540 / 65535)
    assert (dimmer.channel, dimmer.change, dimmer.allowed) == ("dimmer", 0.0, None)
    assert (dark_pan.fixture_id, dark_pan.from_ms, dark_pan.change) == ("MH3", 60, 90.0)
    assert (dark_pan.lit, dark_pan.beyond_travel) == (False, True)
    assert not _section_fact_flags(
        SectionRenderFacts(boundary_steps=[dark_pan]), section_end_ms=1000
    )


def _rig(live_layout: bool = False, **fields: str) -> dict[str, Any]:
    hashes = {"fixtures": "f", "group_id": "i", "xlights_group": "g", **fields}
    return {"sha256": "".join(hashes.values()), "fields": hashes, "live_layout": live_layout}


def test_mismatched_inputs_name_each_recorded_input_that_differs() -> None:
    run = {
        "fixtures": [
            {"fixture_id": "MH1", "xlights_model_name": "Dmx MH1", "profile_sha256": "a"},
            {"fixture_id": "MH2", "xlights_model_name": "Dmx MH2", "profile_sha256": "b"},
        ],
        "template_sha256": {"t1": "x", "t2": "y"},
        "beat_grid_sha256": "g",
        "renderer_revision": "2",
        "encoder_version": "1",
        "rig": _rig(),
        "dark_spans": [[0, 520]],
    }
    rerender = {
        "fixtures": [
            {"fixture_id": "MH1", "xlights_model_name": "Dmx MH1", "profile_sha256": "a"},
            {"fixture_id": "MH3", "xlights_model_name": "Dmx MH3", "profile_sha256": "c"},
        ],
        "template_sha256": {"t1": "x", "t2": "z"},
        "beat_grid_sha256": "h",
        "renderer_revision": "3",
        "encoder_version": "2",
        "rig": _rig(fixtures="F", xlights_group="G"),
    }

    assert _mismatched_inputs(run, run) == []
    assert _mismatched_inputs(run, rerender) == [
        "fixture 'MH2': missing from the re-render's rig",
        "fixture 'MH3': missing from the run's rig",
        "rig (fixture group): fixtures, xlights_group",
        "template 't2'",
        "beat grid",
        "dark spans",
        "renderer revision",
        "encoder version",
    ]


def test_a_rig_reconciled_with_the_live_layout_is_named_so() -> None:
    """`inject` and `regenerate` render on the rig as the open layout leaves it, which no
    fixture config reproduces: the field that differs is named, with why."""
    inputs = {
        "fixtures": [],
        "template_sha256": {},
        "beat_grid_sha256": "g",
        "renderer_revision": "2",
        "encoder_version": "1",
    }
    run = {**inputs, "rig": _rig(live_layout=True, xlights_group="none")}

    assert _mismatched_inputs(run, {**inputs, "rig": _rig()}) == [
        "rig (fixture group): the run rendered on its rig as reconciled with the live "
        "xLights layout, which differs from this fixture config in xlights_group"
    ]
    assert _mismatched_inputs(run, {**inputs, "rig": _rig(xlights_group="none")}) == []


@pytest.mark.parametrize(
    ("words", "flagged"),
    [(12, False), (13, False), (14, True), (-14, True)],
    ids=["within", "exactly-at-the-bound", "one-word-beyond", "one-word-beyond-down"],
)
def test_beyond_travel_is_decided_exactly_in_words(words: int, flagged: bool) -> None:
    """The zoom pilot's 8-bit zoom: 30° over 200 words is 0.15° a word, and 90°/s is 12
    words a frame; with the one word of lag, 13 words are within the bound however the
    decoded degrees round, 14 are beyond it."""
    profile = FixtureCapabilities.model_validate(zoom_pilot_profile_payload())
    zoom = profile.axes["zoom"]
    # From every word the step fits in: decoded degrees round differently at each.
    for start in range(max(20, 20 - words), min(220, 220 - words) + 1):
        change = float(zoom.decode(start + words)) - float(zoom.decode(start))
        assert _beyond_travel(profile, "zoom", change, 20) is flagged, start
    assert _beyond_travel(profile, "dimmer", 1.0, 20) is False


@pytest.mark.parametrize(
    ("beyond", "lit", "flagged"),
    [(False, True, False), (True, True, True), (True, False, False)],
)
def test_a_lit_step_beyond_travel_speed_is_flagged(beyond: bool, lit: bool, flagged: bool) -> None:
    """A step between two lit frames larger than the head can travel between them is a
    warning; between a lit and a dark frame it is not visible motion."""
    step = LitStep(
        fixture_id="MH1",
        channel="pan",
        from_ms=0,
        to_ms=20,
        change=14.5 if beyond else 14.0,
        lit=lit,
        allowed=14.4,
        beyond_travel=beyond,
    )
    facts = SectionRenderFacts(lit_steps=[step])
    flags = _section_fact_flags(facts, section_end_ms=1000)
    assert [f.code for f in flags] == (["LIT_STEP_EXCEEDS_TRAVEL"] if flagged else [])
    if flagged:
        assert flags[0].level == ReportFlagLevel.WARNING
        assert "MH1 pan" in flags[0].message
