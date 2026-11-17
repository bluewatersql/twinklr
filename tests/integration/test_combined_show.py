"""`twinklr show` on the moving-head renderer (C1.1a), offline.

The real combined pipeline definition runs with recorded planner stages in place of
the provider-backed ones, on a synthetic two-head rig, a synthetic layout and a
synthetic 120 BPM grid moved 15 ms off the frame grid. Moving-head frames are decoded
from the DMX effects in the combined sequence itself, so every assertion is on the
encoded bytes the `.xsq` carries.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import replace
from itertools import pairwise
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.support.moving_heads import (
    assert_honest_transactions,
    family_catalog,
    hold_step,
    loop_template_doc,
    p1_job,
    plan_section,
    registered_templates,
    sine_step,
    topology_rig,
)
from tests.unit.cli.test_live_injection_command import _audio_profile
from twinklr.cli.show_cmd import export_show_artifacts, run_show_pipeline_async
from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.agents.sequencer.moving_heads.orchestrator import MovingHeadPlannerOrchestrator
from twinklr.core.agents.sequencer.moving_heads.rendering_stage import MovingHeadRenderingStage
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage
from twinklr.core.agents.shared.judge.controller import IterationContext, IterationResult
from twinklr.core.agents.shared.judge.models import IterationState
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.formats.xlights.sequence.models.xsq import XSequence
from twinklr.core.formats.xlights.sequence.parser import XSQParser
from twinklr.core.pipeline import PipelineContext, PipelineExecutor
from twinklr.core.pipeline.definition import PipelineDefinition
from twinklr.core.pipeline.result import PipelineResult, success_result
from twinklr.core.pipeline.show_wiring import CombinedShowWiring, prepare_combined_show_pipeline
from twinklr.core.reporting.evaluation.collect import extract_plan, recorded_render
from twinklr.core.reporting.evaluation.extract import physical_channel_values
from twinklr.core.reporting.evaluation.generator import generate_evaluation_report
from twinklr.core.reporting.evaluation.models import EvaluationReport
from twinklr.core.reporting.evaluation.rerender import rerender_plan
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    TRANSACTION_METADATA_KEY,
    plan_prepositions,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    OutputError,
    frame_times,
)
from twinklr.core.sequencer.moving_heads.identity import RENDERER_REVISION
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline, TemplateAdmission
from twinklr.core.sequencer.planning.group_plan import LanePlan, SectionCoordinationPlan
from twinklr.core.sequencer.planning.models import (
    CallResponsePair,
    FocalAssignment,
    FocalRole,
    FocalRoleKind,
    MacroPlan,
    MacroSection,
    PaletteRef,
    PaletteRoleRef,
    PaletteStop,
    PaletteTransition,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationPlan,
    GroupPlacement,
    PlanTarget,
)
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import (
    ChoreographyStyle,
    CoordinationMode,
    EffectDuration,
    EnergyTarget,
    IntensityLevel,
    LaneKind,
    MotionDensity,
    PlanningTimeRef,
    StepUnit,
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType
from twinklr.core.session import TwinklrSession
from twinklr.core.utils.formatting import clean_audio_filename

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_IDS = ("MH1", "MH2")
SECTION_MS = (15, 8_015)
"""The one macro section: four bars of 500 ms beats from the first detected beat."""
SONG = "combined_show"

ARCH_GROUP, ARCH_ID = "Yard Arches", "YARD_ARCHES"
"""The arch group's layout name and the choreography id it derives."""

_TEMPLATES = [
    loop_template_doc("show_swing", [sine_step("swing", 0.0, 30.0)]),
    loop_template_doc("show_hold", [hold_step("hold", 45.0)]),
    *(
        loop_template_doc(
            f"show_swing_{mode}",
            [sine_step("swing", 0.0, 30.0, reposition_fallback=mode)],
        )
        for mode in ("drop_accent", "preserve_aim")
    ),
]
"""`show_swing`: pan swings 30 degrees either side of centre once a bar, lit throughout;
`show_hold`: a lit hold at 45 degrees; and the swing opting into each fallback."""

type Frames = dict[tuple[str, int], dict[int, int]]
type MacroSpec = Sequence[tuple[str, int, int, bool]]
"""Macro sections: `(section_id, start_ms, end_ms, the heads answer the tree's calls)`."""
type MovingHeadSpec = Sequence[tuple[str, int, int, str]]
"""Moving-head plan sections: `(section_id, first_bar, last_bar, template_id)`."""

UNIFIED: MacroSpec = [("drop", *SECTION_MS, False)]
CALL_RESPONSE: MacroSpec = [("drop", *SECTION_MS, True)]
SWING: MovingHeadSpec = [("drop", 1, 4, "show_swing")]
CALLS = [(15 + 1_000 * beat, 515 + 1_000 * beat) for beat in range(8)]
"""The tree's call beats under `CALL_RESPONSE`: beats 1, 3, 5, ..."""


@pytest.fixture(autouse=True)
def _templates() -> Iterator[None]:
    # The command admits the shipped family catalog itself; the registry is restored.
    with family_catalog(admit=False), registered_templates(*_TEMPLATES):
        yield


class _Recorded:
    """A recorded planner stage: returns its output and notes that it ran."""

    def __init__(self, name: str, output: object, calls: list[str]) -> None:
        self.name = name
        self.output = output
        self.calls = calls

    async def execute(self, input: Any, context: PipelineContext):
        self.calls.append(self.name)
        if isinstance(self.output, MacroPlan):
            context.set_state("macro_plan", self.output)
            return success_result(self.output.sections, stage_name=self.name)
        if self.name == "groups":  # one display plan for the macro section it is given
            return success_result(_section_plan(input.section), stage_name=self.name)
        return success_result(input if self.output is None else self.output, stage_name=self.name)


def _rig() -> FixtureGroup:
    return topology_rig(FIXTURE_IDS)


def _job(**policy: Any) -> JobConfig:
    return p1_job(**policy)


def _layout_xml(rig: FixtureGroup) -> str:
    heads = "".join(
        f'    <model name="{fixture.xlights_model_name}" DisplayAs="DmxMovingHeadAdv" '
        'StringType="Single Color White" DmxChannelCount="18" />\n'
        for fixture in rig.expand_fixtures()
    )
    members = ",".join(fixture.xlights_model_name for fixture in rig.expand_fixtures())
    return (
        "<xrgb>\n  <models>\n"
        f"{heads}"
        '    <model name="Mega Tree" DisplayAs="Tree 360" parm1="16" parm2="50" />\n'
        '    <model name="Arch 1" DisplayAs="Arches" parm1="1" parm2="50" />\n'
        "  </models>\n  <modelGroups>\n"
        f'    <modelGroup name="{rig.xlights_group}" models="{members}" />\n'
        f'    <modelGroup name="{ARCH_GROUP}" models="Arch 1" />\n'
        "  </modelGroups>\n</xrgb>\n"
    )


def _bundle() -> SimpleNamespace:
    beats = [(15 + 500 * index) / 1000 for index in range(17)]
    features = {
        "tempo_bpm": 120.0,
        "beats_s": beats,
        "bars_s": beats[::4],
        "duration_s": 8.03,
        "assumptions": {"beats_per_bar": 4},
    }
    return SimpleNamespace(
        features=features,
        timing=SimpleNamespace(duration_ms=8_030),
        lyrics=None,
        phonemes=None,
        audio_path="combined-show.wav",
        metadata=None,
    )


def _target(group_id: str) -> PlanTarget:
    return PlanTarget(type=TargetType.GROUP, id=group_id)


def _macro(mh_id: str, sections: MacroSpec) -> MacroPlan:
    """The macro sections; in one where the heads answer, the tree calls and the moving
    heads respond on alternate beats, so the heads rest through every call beat."""
    tree, heads = _target("MEGA_TREE"), _target(mh_id)
    return MacroPlan(
        sections=[
            MacroSection(
                section=SongSectionRef(
                    section_id=section_id, name=section_id, start_ms=start, end_ms=end
                ),
                energy_target=EnergyTarget.PEAK,
                motion_density=MotionDensity.BUSY,
                choreography_style=ChoreographyStyle.HYBRID,
                palette_role=PaletteRoleRef(
                    stop_id="drop", override=PaletteRef(palette_id="core.ice_neon")
                ),
                theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
                motif_ids=[],
                focal_roles=[
                    FocalRole(target=tree, role=FocalRoleKind.LEAD),
                    FocalRole(target=_target(ARCH_ID), role=FocalRoleKind.SUPPORT),
                    FocalRole(target=heads, role=FocalRoleKind.SUPPORT),
                ],
                call_response_pairs=(
                    [
                        CallResponsePair(
                            call=tree, response=heads, step_unit=StepUnit.BEAT, step_duration=1
                        )
                    ]
                    if respond
                    else []
                ),
                coordination_intent=(
                    CoordinationMode.CALL_RESPONSE if respond else CoordinationMode.UNIFIED
                ),
                notes="One macro plan drives both deterministic renderers.",
            )
            for section_id, start, end, respond in sections
        ],
        palette_arc=[
            PaletteStop(
                stop_id="drop",
                palette=PaletteRef(palette_id="core.christmas_traditional"),
                applies_from_section_id=sections[0][0],
                transition=PaletteTransition.CUT,
            )
        ],
        motif_continuity=[],
        focal_arc=[
            FocalAssignment(section_id=section_id, lead_target=tree) for section_id, *_ in sections
        ],
    )


def _section_plan(section: SongSectionRef) -> SectionCoordinationPlan:
    placements = [
        GroupPlacement(
            placement_id="tree-spirals",
            target=_target("MEGA_TREE"),
            template_id="gtpl_base_megatree_spirals",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,
            intensity=IntensityLevel.STRONG,
        ),
        GroupPlacement(
            placement_id="arch-chase",
            target=_target(ARCH_ID),
            template_id="gtpl_rhythm_chase_single",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,
            intensity=IntensityLevel.MED,
        ),
    ]
    return SectionCoordinationPlan(
        section_id=section.section_id,
        theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
        palette=PaletteRef(palette_id="core.christmas_traditional"),
        start_ms=section.start_ms,
        end_ms=section.end_ms,
        lane_plans=[
            LanePlan(
                lane=LaneKind.BASE,
                target_roles=["MEGA_TREE", ARCH_ID],
                coordination_plans=[
                    CoordinationPlan(
                        coordination_mode=CoordinationMode.UNIFIED,
                        targets=[_target("MEGA_TREE"), _target(ARCH_ID)],
                        placements=placements,
                    )
                ],
            )
        ],
    )


def _mh_plan(sections: MovingHeadSpec = SWING) -> ChoreographyPlan:
    return ChoreographyPlan(
        sections=[
            plan_section(name, first, last, template_id)
            for name, first, last, template_id in sections
        ],
        overall_strategy="",
    )


def _recorded(
    wiring: CombinedShowWiring,
    *,
    macro: MacroSpec,
    moving_heads: MovingHeadSpec = SWING,
    calls: list[str],
    planning_stage: bool = False,
) -> CombinedShowWiring:
    """The wiring with every provider-backed stage replaced by a recorded one; with
    `planning_stage`, the real moving-head planning stage is kept (its provider call is
    the caller's to answer), which reads a real audio profile and writes the plan
    checkpoint."""
    mh_id = next(iter(wiring.moving_head_target_ids))
    outputs: dict[str, object] = {
        "profile": _audio_profile() if planning_stage else object(),
        "lyrics": None if planning_stage else object(),
        "macro": _macro(mh_id, macro),
        "groups": None,
        "holistic": None,
        "holistic_corrector": None,
    }
    if not planning_stage:
        outputs["moving_heads"] = _mh_plan(moving_heads)
    pipeline = PipelineDefinition(
        name=wiring.pipeline.name,
        stages=[
            replace(stage, stage=_Recorded(stage.id, outputs[stage.id], calls))
            if stage.id in outputs
            else stage
            for stage in wiring.pipeline.stages
        ],
    )
    return replace(wiring, pipeline=pipeline)


def _write_inputs(tmp_path: Path, rig: FixtureGroup) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    layout_path = tmp_path / "xlights_rgbeffects.xml"
    layout_path.write_text(_layout_xml(rig), encoding="utf-8")
    fixture_path = tmp_path / "fixture_config.json"
    fixture_path.write_text(rig.model_dump_json(), encoding="utf-8")
    return layout_path, fixture_path


def _analyzer() -> MagicMock:
    analyzer = MagicMock()
    analyzer.analyze = AsyncMock(return_value=_bundle())
    analyzer.aclose = AsyncMock()
    return analyzer


async def _run(
    tmp_path: Path,
    *,
    rig: FixtureGroup | None = None,
    job: JobConfig | None = None,
    macro: MacroSpec = UNIFIED,
    moving_heads: MovingHeadSpec = SWING,
    calls: list[str] | None = None,
) -> tuple[PipelineResult, PipelineContext]:
    """Run the combined pipeline as `twinklr show` wires it, with recorded planners."""
    rig = rig or _rig()
    job = job or _job()
    layout_path, fixture_path = _write_inputs(tmp_path, rig)
    wiring = _recorded(
        prepare_combined_show_pipeline(
            layout_path=layout_path,
            fixture_group=rig,
            job_config=job,
            available_templates=sorted({template for *_, template in moving_heads}),
            song_name=SONG,
            catalog_dir=REPO_ROOT / "catalog" / "templates",
            fixture_config_path=fixture_path,
        ),
        macro=macro,
        moving_heads=moving_heads,
        calls=[] if calls is None else calls,
    )
    session = MagicMock()
    session.app_config = AppConfig()
    session.job_config = job
    context = PipelineContext(session=session)
    context.set_state("layout_models", wiring.layout_models)
    with patch("twinklr.core.audio.analyzer.AudioAnalyzer", return_value=_analyzer()):
        result = await PipelineExecutor().execute(wiring.pipeline, "combined-show.wav", context)
    return result, context


def _profiles(rig: FixtureGroup) -> dict[str, FixtureCapabilities]:
    profiles = {}
    for fixture in rig.expand_fixtures():
        assert fixture.config.physical_profile is not None
        profiles[fixture.fixture_id] = fixture.config.physical_profile
    return profiles


def _sequence_frames(sequence: XSequence, rig: FixtureGroup) -> Frames:
    """Every moving head's 20 ms frames, decoded from the sequence's DMX effects."""
    fixture_by_model = {f.xlights_model_name: f.fixture_id for f in rig.expand_fixtures()}
    frames: Frames = {}
    for element in sequence.element_effects:
        fixture_id = fixture_by_model.get(element.element_name)
        if fixture_id is None:
            continue
        for layer in element.layers:
            for effect in layer.effects:
                assert effect.effect_type == "DMX" and effect.ref is not None
                settings = dict(
                    item.split("=", 1) for item in sequence.effect_db.entries[effect.ref].split(",")
                )
                frame = {
                    int(key.removeprefix("E_SLIDER_DMX")): int(value)
                    for key, value in settings.items()
                    if key.startswith("E_SLIDER_DMX")
                }
                for time_ms in range(effect.start_time_ms, effect.end_time_ms, EFFECT_GRID_MS):
                    assert (fixture_id, time_ms) not in frames
                    frames[(fixture_id, time_ms)] = frame
    return frames


def _standalone(
    context: PipelineContext,
    rig: FixtureGroup,
    job: JobConfig,
    moving_heads: MovingHeadSpec = SWING,
) -> RenderingPipeline:
    """The same plan rendered by the standalone path, `twinklr run`'s."""
    admission = context.get_state("template_admission")
    assert isinstance(admission, TemplateAdmission)
    pipeline = RenderingPipeline(
        choreography_plan=_mh_plan(moving_heads),
        beat_grid=context.get_state("beat_grid"),
        fixture_group=rig,
        job_config=job,
        admission=admission,
    )
    pipeline.render()
    return pipeline


def _dark(frame: dict[int, int], profile: FixtureCapabilities) -> bool:
    dimmer = profile.axes["dimmer"]
    word = frame[dimmer.coarse_offset]
    if dimmer.fine_offset is not None:
        word = word << 8 | frame[dimmer.fine_offset]
    if profile.visibility.dimmer_zero_extinguishes and word == dimmer.dmx_word(0):
        return True
    shutter = profile.discrete["shutter"]
    state = next(n for n, s in shutter.states.items() if s.value == frame[shutter.offset])
    return state in profile.visibility.extinguishing_shutter_states


def _effect_types(sequence: XSequence) -> dict[str, set[str]]:
    return {
        element.element_name: {
            effect.effect_type for layer in element.layers for effect in layer.effects
        }
        for element in sequence.element_effects
        if any(layer.effects for layer in element.layers)
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_gate_refuses_a_rig_without_a_profile_before_any_planner(tmp_path: Path) -> None:
    payload = _rig().model_dump(mode="json")
    payload["fixtures"][1]["config"]["physical_profile"] = None
    rig = FixtureGroup.model_validate(payload)
    calls: list[str] = []

    result, _ = await _run(tmp_path, rig=rig, calls=calls)

    assert not result.success
    assert result.failed_stages == ["render_preflight"]
    error = result.stage_results["render_preflight"].error or ""
    assert "the moving-head renderer cannot render this rig" in error
    assert "MH2: physical_profile is missing" in error
    assert calls == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unified_show_renders_the_heads_as_the_standalone_render(
    tmp_path: Path,
) -> None:
    rig, job = _rig(), _job()

    result, context = await _run(tmp_path, rig=rig, job=job)

    assert result.success, result.failed_stages
    output = result.outputs["show_render"]
    sequence = output["sequence"]
    standalone = _standalone(context, rig, job)
    frames = _sequence_frames(sequence, rig)
    assert frames == {(f.fixture_id, f.time_ms): dict(f.channels) for f in standalone.frames}
    record = output["render_record"]
    assert "dark_spans" not in record
    assert record["render_fingerprint"] == standalone.fingerprint()
    assert record["layout_check"] == "performed"
    # The macro palette and focal role are not projected onto the heads: said, not done.
    projected = [d for d in record["diagnostics"] if "macro palette" in d["message"]]
    assert [(d["section_id"], d["severity"], d["action"]) for d in projected] == [
        ("drop", "warning", "unchanged")
    ]
    assert _effect_types(sequence) == {
        "Dmx MH1": {"DMX"},
        "Dmx MH2": {"DMX"},
        "Mega Tree": {"Spirals"},
        ARCH_GROUP: {"SingleStrand"},
    }


def _assert_rests(
    output: dict[str, Any],
    context: PipelineContext,
    rig: FixtureGroup,
    job: JobConfig,
    calls: Sequence[tuple[int, int]],
    moving_heads: MovingHeadSpec = SWING,
) -> None:
    """Asserted on the frames the combined sequence carries, against the same plan
    rendered alone: the heads rest dark in every call, snapped outward to the frame
    grid, moving there only along their cues' authored paths (only the dimmer differs);
    outside the calls every lit frame is the plain render's, none of its lit frames is
    lost, and every head answers in every response beat; replanning the render's own
    cues gives its segments, and no head is lit while it moves or before it settles."""
    frames = _sequence_frames(output["sequence"], rig)
    plain = {
        (f.fixture_id, f.time_ms): dict(f.channels)
        for f in _standalone(context, rig, job, moving_heads).frames
    }
    spans = [[start // 20 * 20, -(-end // 20) * 20] for start, end in calls]
    assert output["render_record"]["dark_spans"] == spans
    profiles = _profiles(rig)
    assert frames.keys() == plain.keys()
    lit: set[tuple[str, int]] = set()
    for (fixture_id, time_ms), frame in frames.items():
        profile = profiles[fixture_id]
        before = plain[(fixture_id, time_ms)]
        if any(start <= time_ms < end for start, end in spans):
            assert _dark(frame, profile), f"{fixture_id} lit at {time_ms} ms in a call beat"
            dimmer = profile.axes["dimmer"]
            assert {o for o in frame if frame[o] != before[o]} <= {
                dimmer.coarse_offset,
                dimmer.fine_offset,
            }, f"{fixture_id} left its authored path at {time_ms} ms"
        elif not _dark(frame, profile):
            assert frame == before, f"{fixture_id} differs at {time_ms} ms"
            lit.add((fixture_id, time_ms))
        else:
            assert _dark(before, profile), f"{fixture_id} lost a lit frame at {time_ms} ms"
    responses = [(end, start) for (_, end), (start, _) in pairwise(spans)]
    for fixture_id in FIXTURE_IDS:
        for start, end in responses:
            assert any((fixture_id, t) in lit for t in range(start, end, EFFECT_GRID_MS)), (
                f"{fixture_id} stays dark in the response beat {start}-{end} ms"
            )

    segments = list(output["moving_head_segments"])
    cues = [s for s in segments if TRANSACTION_METADATA_KEY not in s.metadata]
    grid = context.get_state("beat_grid")
    assert isinstance(grid, BeatGrid)
    replanned = plan_prepositions(
        cues,
        profiles,
        initial_states=job.moving_heads.initial_states,
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=len(frame_times(int(grid.duration_ms))) * EFFECT_GRID_MS,
        failure_mode=job.moving_heads.reposition_fallback,
    )
    assert list(replanned.segments) == segments
    for fixture_id, profile in profiles.items():
        initial = job.moving_heads.initial_states[fixture_id]
        assert_honest_transactions(replanned, cues, profile, initial, fixture_id=fixture_id)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", ["error", "drop_accent", "preserve_aim"])
async def test_call_response_rests_the_heads_dark_on_their_authored_paths(
    tmp_path: Path, fallback: str
) -> None:
    """Under every reposition fallback the job and its cues may declare."""
    rig, job = _rig(), _job(reposition_fallback=fallback)
    template = "show_swing" if fallback == "error" else f"show_swing_{fallback}"
    moving_heads = [("drop", 1, 4, template)]

    result, context = await _run(
        tmp_path, rig=rig, job=job, macro=CALL_RESPONSE, moving_heads=moving_heads
    )

    assert result.success, result.failed_stages
    _assert_rests(result.outputs["show_render"], context, rig, job, CALLS, moving_heads)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_spans_follow_the_coordination_of_each_section(tmp_path: Path) -> None:
    """A verse where the heads answer the tree, then a unified chorus on another
    template: the heads rest only on the verse's call beats, and the chorus renders as
    the same plan renders alone."""
    rig, job = _rig(), _job()
    # The verse ends on the detected downbeat, 4014 ms.
    macro: MacroSpec = [("verse", 15, 4_014, True), ("chorus", 4_014, 8_015, False)]
    moving_heads: MovingHeadSpec = [
        ("verse", 1, 2, "show_swing"),
        ("chorus", 3, 4, "show_hold"),
    ]

    result, context = await _run(tmp_path, rig=rig, job=job, macro=macro, moving_heads=moving_heads)

    assert result.success, result.failed_stages
    _assert_rests(result.outputs["show_render"], context, rig, job, CALLS[:4], moving_heads)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_export_writes_one_show_with_the_moving_head_trace_of_twinklr_run(
    tmp_path: Path,
) -> None:
    rig, job = _rig(), _job()
    result, context = await _run(tmp_path, rig=rig, job=job)
    assert result.success, result.failed_stages

    xsq_path, trace_path = export_show_artifacts(
        result.outputs["show_render"],
        artifact_dir=tmp_path / "show",
        song_name=SONG,
        policy=job.moving_heads,
    )

    written = XSQParser().parse(xsq_path)
    assert _effect_types(written) == {
        "Dmx MH1": {"DMX"},
        "Dmx MH2": {"DMX"},
        "Mega Tree": {"Spirals"},
        ARCH_GROUP: {"SingleStrand"},
    }
    assert _sequence_frames(written, rig) == _sequence_frames(
        result.outputs["show_render"]["sequence"], rig
    )
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert {entry["backend"] for entry in trace["entries"]} == {"display", "moving_head"}
    standalone = _standalone(context, rig, job)
    run_trace_path = tmp_path / "run" / "run.xsq"
    RenderingPipeline(
        choreography_plan=_mh_plan(),
        beat_grid=context.get_state("beat_grid"),
        fixture_group=rig,
        job_config=job,
        admission=context.get_state("template_admission"),
        layout_models=context.get_state("layout_models"),
        output_path=run_trace_path,
    ).render()
    run_trace = json.loads(Path(f"{run_trace_path}.trace.json").read_text(encoding="utf-8"))
    assert trace["render"].keys() == run_trace["render"].keys()
    assert trace["render"]["render_fingerprint"] == standalone.fingerprint()
    assert (
        trace["render"]["output"]["effect_count"] == run_trace["render"]["output"]["effect_count"]
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_show_is_deterministic(tmp_path: Path) -> None:
    written = []
    for attempt in ("first", "second"):
        result, _ = await _run(tmp_path / attempt, macro=CALL_RESPONSE)
        assert result.success, result.failed_stages
        xsq_path, trace_path = export_show_artifacts(
            result.outputs["show_render"],
            artifact_dir=tmp_path / attempt / "show",
            song_name=SONG,
            policy=_job().moving_heads,
        )
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        trace["render"]["output"].pop("serialization_ms")
        trace["render"].pop("layout_sha256", None)
        written.append((xsq_path.read_bytes(), trace))

    assert written[0] == written[1]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_output_budget_refuses_the_show_and_writes_nothing(tmp_path: Path) -> None:
    job = _job(max_effects=10)
    result, _ = await _run(tmp_path, job=job)
    assert result.success, result.failed_stages
    artifact_dir = tmp_path / "show"

    with pytest.raises(OutputError, match="exceed max_effects 10"):
        export_show_artifacts(
            result.outputs["show_render"],
            artifact_dir=artifact_dir,
            song_name=SONG,
            policy=job.moving_heads,
        )

    assert not artifact_dir.exists() or list(artifact_dir.iterdir()) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_export_publishes_the_sequence_and_its_trace_together(tmp_path: Path) -> None:
    """A failure before both files are in place leaves the earlier show as it was: no new
    `.xsq` beside an old trace, and nothing staged left behind."""
    job = _job()
    result, _ = await _run(tmp_path, job=job)
    assert result.success, result.failed_stages
    artifact_dir = tmp_path / "show"
    artifact_dir.mkdir()
    earlier = {
        f"{SONG}_twinklr_show.xsq": b"earlier sequence",
        f"{SONG}_twinklr_show.xsq.trace.json": b"earlier trace",
    }
    for name, content in earlier.items():
        (artifact_dir / name).write_bytes(content)

    with (
        patch("twinklr.cli.show_cmd.write_xsq_trace_sidecar", side_effect=OSError("disk full")),
        pytest.raises(OSError, match="disk full"),
    ):
        export_show_artifacts(
            result.outputs["show_render"],
            artifact_dir=artifact_dir,
            song_name=SONG,
            policy=job.moving_heads,
        )

    assert {path.name: path.read_bytes() for path in artifact_dir.iterdir()} == earlier


@pytest.mark.integration
@pytest.mark.asyncio
async def test_twinklr_show_writes_one_show_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The command end to end: catalog, gate, recorded planners, render, export, manifest."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    rig = _rig()
    layout_path, fixture_path = _write_inputs(tmp_path, rig)
    job_path = tmp_path / "job_config.json"
    job_path.write_text(_job().model_dump_json(), encoding="utf-8")
    audio_path = tmp_path / "combined-show.wav"
    audio_path.write_bytes(b"synthetic audio")
    local = AppConfig(
        llm_provider="ollama", llm_base_url="http://127.0.0.1:11434/v1", llm_api_key=""
    )
    calls: list[str] = []

    def recorded(**kwargs: Any) -> CombinedShowWiring:
        return _recorded(prepare_combined_show_pipeline(**kwargs), macro=CALL_RESPONSE, calls=calls)

    with (
        patch("twinklr.cli.show_cmd.load_app_config", return_value=local),
        patch("twinklr.cli.show_cmd.prepare_combined_show_pipeline", side_effect=recorded),
        patch("twinklr.core.audio.analyzer.AudioAnalyzer", return_value=_analyzer()),
    ):
        exit_code = await run_show_pipeline_async(
            audio_path=audio_path,
            layout_path=layout_path,
            fixture_config_path=fixture_path,
            output_dir=tmp_path / "out",
            app_config_path=None,
            job_config_path=job_path,
        )

    assert exit_code == 0
    song_name = clean_audio_filename(audio_path.stem)
    xsq_path = tmp_path / "out" / song_name / f"{song_name}_twinklr_show.xsq"
    trace = json.loads(Path(f"{xsq_path}.trace.json").read_text(encoding="utf-8"))
    assert trace["render"]["renderer_revision"] == RENDERER_REVISION
    assert trace["render"]["layout_check"] == "performed"
    assert trace["render"]["layout_sha256"]
    assert Path(f"{xsq_path}.evaluation.json").is_file()
    assert set(_effect_types(XSQParser().parse(xsq_path))) == {
        "Dmx MH1",
        "Dmx MH2",
        "Mega Tree",
        ARCH_GROUP,
    }
    assert "moving_heads" in calls


class _SongMetadataOnly:
    """The audio analysis `eval-report` runs, which a report reads only for the
    song's metadata."""

    def __init__(self, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> _SongMetadataOnly:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def analyze(self, path: str) -> SimpleNamespace:
        return SimpleNamespace(features={"tempo": {"bpm": 120.0}})


def _plan_through_json(moving_heads: MovingHeadSpec = SWING) -> ChoreographyPlan:
    """The plan as a planner states it, every intent field present, as the checkpoint
    carries it."""
    return ChoreographyPlan.model_validate(_mh_plan(moving_heads).model_dump(mode="json"))


async def _show_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    macro: MacroSpec = CALL_RESPONSE,
    job: JobConfig | None = None,
    exit_code: int = 0,
) -> tuple[Path, Path, Path]:
    """`twinklr show` end to end, offline, with the real moving-head planning stage (its
    provider answered by a recorded plan), which writes the plan checkpoint; it must exit
    with `exit_code`. Returns the artifact directory, the fixture config and the audio."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    layout_path, fixture_path = _write_inputs(tmp_path, _rig())
    job_path = tmp_path / "job_config.json"
    job_path.write_text((job or _job()).model_dump_json(), encoding="utf-8")
    audio_path = tmp_path / "combined-show.wav"
    audio_path.write_bytes(b"synthetic audio")
    local = AppConfig(
        llm_provider="ollama", llm_base_url="http://127.0.0.1:11434/v1", llm_api_key=""
    )

    def recorded(**kwargs: Any) -> CombinedShowWiring:
        return _recorded(
            prepare_combined_show_pipeline(**kwargs), macro=macro, calls=[], planning_stage=True
        )

    async def planner(self: object, planning_context: object) -> IterationResult:
        return IterationResult(
            success=True,
            plan=_plan_through_json(),
            context=IterationContext(current_iteration=1, state=IterationState.COMPLETE),
        )

    async def cache_key(self: object, planning_context: object) -> str:
        return "show-evaluation"

    monkeypatch.setattr(MovingHeadPlannerOrchestrator, "run", planner)
    monkeypatch.setattr(MovingHeadPlannerOrchestrator, "get_cache_key", cache_key)
    with (
        patch("twinklr.cli.show_cmd.load_app_config", return_value=local),
        patch("twinklr.cli.show_cmd.prepare_combined_show_pipeline", side_effect=recorded),
        patch("twinklr.core.audio.analyzer.AudioAnalyzer", return_value=_analyzer()),
    ):
        exited = await run_show_pipeline_async(
            audio_path=audio_path,
            layout_path=layout_path,
            fixture_config_path=fixture_path,
            output_dir=tmp_path / "out",
            app_config_path=None,
            job_config_path=job_path,
        )
    assert exited == exit_code
    return tmp_path / "out" / clean_audio_filename(audio_path.stem), fixture_path, audio_path


async def _evaluate(
    checkpoint: Path, fixture_path: Path, audio_path: Path, out: Path
) -> EvaluationReport:
    with patch("twinklr.core.audio.analyzer.AudioAnalyzer", _SongMetadataOnly):
        return await generate_evaluation_report(
            checkpoint_path=checkpoint,
            audio_path=audio_path,
            fixture_config_path=fixture_path,
            output_dir=out,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_eval_report_reproduces_a_show_render_with_its_dark_spans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`twinklr show` records its render in the plan checkpoint as `twinklr run` does,
    the coordination's dark spans included, and `eval-report` re-renders exactly it."""
    artifact_dir, fixture_path, audio_path = await _show_command(tmp_path, monkeypatch)
    trace = json.loads(
        (artifact_dir / f"{artifact_dir.name}_twinklr_show.xsq.trace.json").read_text()
    )["render"]
    checkpoint = artifact_dir / "checkpoints" / "plans" / "final.json"
    data = json.loads(checkpoint.read_text(encoding="utf-8"))
    spans = trace["dark_spans"]
    assert len(spans) == len(CALLS)  # the heads rest on each of the tree's calls
    assert data["render"]["render_fingerprint"] == trace["render_fingerprint"]
    assert data["render"]["dark_spans"] == spans
    assert data["render"]["inputs"]["dark_spans"] == spans

    report = await _evaluate(checkpoint, fixture_path, audio_path, tmp_path / "report")

    summary = report.render
    assert summary is not None
    assert summary.fingerprint_matches is True, summary.mismatched_inputs
    assert summary.rerender_fingerprint == summary.run_fingerprint == trace["render_fingerprint"]
    assert summary.dark_spans == spans
    assert summary.dark_span_ms == sum(end - start for start, end in spans)
    markdown = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    assert f"**Dark spans**: {len(spans)}, {summary.dark_span_ms} ms in all" in markdown
    written = json.loads((tmp_path / "report" / "report.json").read_text(encoding="utf-8"))
    assert written["render"]["dark_spans"] == spans

    # Lit-only figures leave the spans out by construction: in every frame of every span
    # each head emits nothing, and lit means emitted intensity above 0.
    with patch("twinklr.core.audio.analyzer.AudioAnalyzer", _SongMetadataOnly):
        rerendered = await rerender_plan(
            plan=extract_plan(data),
            audio_path=audio_path,
            fixture_config_path=fixture_path,
            recorded=recorded_render(data),
        )
    assert rerendered.output is not None
    values = physical_channel_values(
        rerendered.output.frames, rerendered.output.profiles, (0, sys.maxsize)
    )
    for fixture_id in FIXTURE_IDS:
        intensity = values[fixture_id]["dimmer"]
        for start, end in spans:
            assert not any(intensity[start // EFFECT_GRID_MS : end // EFFECT_GRID_MS])
        assert any(intensity)  # lit outside the spans
    for curve in (c for section in report.sections for c in section.curves):
        if curve.channel != "dimmer":
            assert curve.lit_range is not None and curve.lit_range <= curve.stats.range


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dark_spans_that_are_not_the_shows_are_named_as_what_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record whose spans were changed or lost re-renders another render, and the
    report names the dark spans instead of nothing."""
    artifact_dir, fixture_path, audio_path = await _show_command(tmp_path, monkeypatch)
    checkpoint = artifact_dir / "checkpoints" / "plans" / "final.json"
    data = json.loads(checkpoint.read_text(encoding="utf-8"))

    for change in ("tampered", "missing"):
        changed = json.loads(json.dumps(data))
        if change == "tampered":
            changed["render"]["dark_spans"] = changed["render"]["dark_spans"][1:]
        else:
            del changed["render"]["dark_spans"]
        path = tmp_path / f"{change}.json"
        path.write_text(json.dumps(changed), encoding="utf-8")

        report = await _evaluate(path, fixture_path, audio_path, tmp_path / change)

        assert report.render is not None
        assert report.render.fingerprint_matches is False, change
        assert report.render.mismatched_inputs == ["dark spans"], change


@pytest.mark.integration
@pytest.mark.asyncio
async def test_show_and_run_record_their_render_in_one_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One writer: the show's record has the run's keys, and the dark spans besides."""
    artifact_dir, fixture_path, _ = await _show_command(tmp_path, monkeypatch)
    show = json.loads((artifact_dir / "checkpoints" / "plans" / "final.json").read_text())

    run_dir = tmp_path / "run"
    job = _job()
    session = TwinklrSession(job_config=job, session_id="run", project_root=run_dir)
    context = PipelineContext(session=session, output_dir=run_dir)
    context.set_state("beat_grid", BeatGrid.model_validate(show["render"]["beat_grid"]))
    plan = _plan_through_json()
    MovingHeadStage(fixture_count=2, available_templates=["show_swing"])._handle_state(
        {"plan": plan.model_dump(mode="json")}, context
    )
    rendered = await MovingHeadRenderingStage(
        xsq_output_path=run_dir / "run.xsq", fixture_config_path=fixture_path
    ).execute({"moving_heads": plan}, context)
    assert rendered.success, rendered.error
    run = json.loads((run_dir / "checkpoints" / "plans" / "final.json").read_text())

    assert show.keys() == run.keys()
    assert run["render"].keys() == show["render"].keys() - {"dark_spans"}
    assert run["render"]["inputs"].keys() == show["render"]["inputs"].keys() - {"dark_spans"}
    # The same rig, the same identity.
    assert run["render"]["inputs"]["rig"] == show["render"]["inputs"]["rig"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_show_whose_export_is_refused_records_no_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record follows the delivery, as `twinklr run`'s does: a show the output budget
    refuses writes no sequence, and its plan checkpoint records no render."""
    artifact_dir, _, _ = await _show_command(
        tmp_path, monkeypatch, job=_job(max_effects=10), exit_code=1
    )

    data = json.loads((artifact_dir / "checkpoints" / "plans" / "final.json").read_text())
    assert set(data) == {"run_id", "plan"}
    assert not list(artifact_dir.glob("*.xsq"))
