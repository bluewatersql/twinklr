"""`on_unplayable`: a cue the plan placed where it cannot play honestly is kept dark.

Under the default `dark`, after any fallback the cue and the job both declare, a cue the
transaction pass cannot play (or that a shutter state too short to take effect, or a
park, lies in), a step instance a fixture cannot compile at its section's placement and
a ONCE cycle a section is too short for are left dark: the fixture parks as over any gap,
each one is listed in the trace's `dropped_cues` and counted in `unplayable_totals`, and
the render logs one warning. `error` refuses the render as before. A refusal the
template shows at the gate's basic placement (bar 1 over the song) still raises.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
import math
from pathlib import Path
from typing import Any

import pytest

from tests.support.mh_physical import (
    PHYSICAL_INITIAL_STATE,
    assert_honest_transactions,
    hold_step,
    initial_state_payload,
    path_step,
    physical_bars_grid,
    physical_job,
    physical_rig,
    physical_sections,
    physical_segment,
    physical_template_doc,
    preposition_profile_payload,
    registered_templates,
    topology_rig,
)
from twinklr.core.caching.identity import RENDER_ONLY_CONFIG_KEYS
from twinklr.core.config.fixtures import (
    FixtureCapabilities,
    FixtureGroup,
    InitialFixtureState,
)
from twinklr.core.config.models import JobConfig
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalChannelError,
    PhysicalPoint,
)
from twinklr.core.sequencer.models.template import TemplateDoc
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.physical import PhysicalCompileError
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    TRANSACTION_METADATA_KEY,
    plan_prepositions,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import frame_times
from twinklr.core.sequencer.moving_heads.pipeline import (
    PhysicalRenderError,
    RenderingPipeline,
    check_physical_templates,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

_LOGGER = "twinklr.core.sequencer.moving_heads.pipeline"

# Back to back: a hold at -90 degrees for half a bar, then one at 90. The second cue can
# never follow the first (180 degrees in one frame), in every bar.
_JUMP = physical_template_doc(
    "un_jump",
    [hold_step("left", -90.0, duration=0.5), hold_step("right", 90.0, start=0.5, duration=0.5)],
)


def _render(
    docs: tuple[TemplateDoc, ...],
    sections: tuple[tuple[str, int, int], ...],
    *,
    grid: BeatGrid | None = None,
    rig: FixtureGroup | None = None,
    job: JobConfig | None = None,
) -> RenderingPipeline:
    pipeline = RenderingPipeline(
        choreography_plan=physical_sections(*sections),
        beat_grid=grid or physical_bars_grid(*[500.0] * 4),
        fixture_group=rig or physical_rig(),
        job_config=job or physical_job(),
        output_path=None,
    )
    with registered_templates(*docs):
        segments = pipeline.render()
    _check_honest(pipeline, segments)
    return pipeline


def _check_honest(pipeline: RenderingPipeline, segments: list[FixtureSegment]) -> None:
    """Replan the played cues and check every fixture from its bytes; every cue kept dark
    for being unplayable is commanded dark over its frames."""
    policy = pipeline.job_config.moving_heads
    profiles = {
        f.fixture_id: f.config.physical_profile for f in pipeline.fixture_group.expand_fixtures()
    }
    cues = [s for s in segments if TRANSACTION_METADATA_KEY not in s.metadata]
    replanned = plan_prepositions(
        cues,
        profiles,  # type: ignore[arg-type]
        initial_states=policy.initial_states,
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=len(frame_times(int(pipeline.beat_grid.duration_ms))) * EFFECT_GRID_MS,
        failure_mode=policy.reposition_fallback,
    )
    assert list(replanned.segments) == segments
    for fixture_id, profile in profiles.items():
        assert profile is not None
        if any(cue.fixture_id == fixture_id for cue in cues):
            initial = policy.initial_states[fixture_id]
            assert_honest_transactions(replanned, cues, profile, initial, fixture_id=fixture_id)
    assert pipeline.render_record is not None
    frames = {(f.fixture_id, f.time_ms): dict(f.channels) for f in pipeline.frames}
    for record in _unplayable(pipeline):
        profile = profiles[record["fixture_id"]]
        assert profile is not None
        for time_ms in range(record["start_ms"], record["end_ms"], EFFECT_GRID_MS):
            assert _commanded_dark(frames[record["fixture_id"], time_ms], profile), record
            assert not any(
                c.fixture_id == record["fixture_id"] and c.t0_ms <= time_ms < c.t1_ms for c in cues
            ), record


def _commanded_dark(frame: dict[int, int], profile: FixtureCapabilities) -> bool:
    dimmer = profile.axes.get("dimmer")
    dimmer_dark = profile.visibility.dimmer_zero_extinguishes and dimmer is not None
    if dimmer_dark and frame[dimmer.coarse_offset] == 0:  # type: ignore[union-attr]
        return True
    shutter = profile.discrete.get("shutter")
    if shutter is None:
        return False
    state = next(n for n, s in shutter.states.items() if s.value == frame[shutter.offset])
    return state in profile.visibility.extinguishing_shutter_states


def _unplayable(pipeline: RenderingPipeline) -> list[dict[str, Any]]:
    assert pipeline.render_record is not None
    return [r for r in pipeline.render_record["dropped_cues"] if r["reason"] == "unplayable"]


def test_on_unplayable_field_changes_the_render(caplog: pytest.LogCaptureFixture) -> None:
    """At the default every "right" cue is kept dark, recorded and counted, with one
    warning; under `error` the same plan is refused."""
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        pipeline = _render((_JUMP,), (("un_jump", 1, 4),))

    records = _unplayable(pipeline)
    assert {(r["fixture_id"], r["step_id"]) for r in records} == {
        ("MH1", "right"),
        ("MH2", "right"),
    }
    assert {r["code"] for r in records} == {"infeasible_transition"}
    assert all("jumps across" in r["detail"] for r in records)
    assert all(r["frames"] == (r["end_ms"] - r["start_ms"]) // EFFECT_GRID_MS for r in records)
    assert pipeline.render_record is not None
    assert pipeline.render_record["unplayable_totals"] == {
        "infeasible_transition": {
            "cues": len(records),
            "frames": sum(r["frames"] for r in records),
        }
    }
    warnings = [r for r in caplog.records if "cannot play honestly" in r.getMessage()]
    assert len(warnings) == 1
    assert pipeline.unplayable_warning == warnings[0].getMessage()
    assert f"{len(records)} cue(s)" in warnings[0].getMessage()
    kept_dark = [
        d for d in pipeline.render_record["transactions"] if "on_unplayable 'dark'" in d["reason"]
    ]
    assert len(kept_dark) == len(records)
    assert {d["status"] for d in kept_dark} == {"drop_accent"}

    with registered_templates(_JUMP), pytest.raises(PhysicalRenderError, match="jumps across"):
        RenderingPipeline(
            choreography_plan=physical_sections(("un_jump", 1, 4)),
            beat_grid=physical_bars_grid(*[500.0] * 4),
            fixture_group=physical_rig(),
            job_config=physical_job(on_unplayable="error"),
            output_path=None,
        ).render()


def test_on_unplayable_is_render_only_and_out_of_dumps_at_its_default() -> None:
    assert "moving_heads.on_unplayable" in RENDER_ONLY_CONFIG_KEYS
    assert "on_unplayable" not in physical_job().model_dump(mode="json")["moving_heads"]
    error = physical_job(on_unplayable="error")
    assert error.model_dump(mode="json")["moving_heads"]["on_unplayable"] == "error"

    def fingerprint(job: JobConfig) -> str:
        with registered_templates(_JUMP):
            return RenderingPipeline(
                choreography_plan=physical_sections(("un_jump", 1, 4)),
                beat_grid=physical_bars_grid(*[500.0] * 4),
                fixture_group=physical_rig(),
                job_config=job,
                output_path=None,
            ).fingerprint()

    assert fingerprint(physical_job()) == fingerprint(physical_job(on_unplayable="dark"))
    assert fingerprint(physical_job()) != fingerprint(error)


def test_a_render_with_nothing_unplayable_is_unchanged() -> None:
    """No cue kept dark: the same frames, transactions and no warning under both modes."""
    doc = physical_template_doc("un_hold", [hold_step("h", 10.0)])
    dark = _render((doc,), (("un_hold", 1, 4),))
    error = _render((doc,), (("un_hold", 1, 4),), job=physical_job(on_unplayable="error"))
    assert dark.frames == error.frames
    assert dark.unplayable_warning is None
    assert dark.render_record is not None and error.render_record is not None
    assert dark.render_record["transactions"] == error.render_record["transactions"]
    assert dark.render_record["unplayable_totals"] == {}


def _profile(edit: Callable[[dict[str, Any]], None] | None = None) -> FixtureCapabilities:
    payload = preposition_profile_payload()
    if edit is not None:
        edit(payload)
    return FixtureCapabilities.model_validate(payload)


def _cue(
    t0: int, t1: int, pan: float, shutter: str = "open", segment_id: str = "cue"
) -> FixtureSegment:
    pose = ContinuousTrajectory(
        unit="degree",
        points=(PhysicalPoint(t_ms=t0, value=pan), PhysicalPoint(t_ms=t1, value=pan)),
        interpolation="linear",
    )
    level = ContinuousTrajectory(
        unit="normalized", points=(PhysicalPoint(t_ms=t0, value=1.0),), interpolation="hold"
    )
    tilt = ContinuousTrajectory(
        unit="degree",
        points=(PhysicalPoint(t_ms=t0, value=0.0), PhysicalPoint(t_ms=t1, value=0.0)),
        interpolation="linear",
    )
    return physical_segment(
        {
            ChannelName.PAN: pose,
            ChannelName.TILT: tilt,
            ChannelName.DIMMER: level,
            ChannelName.SHUTTER: DiscreteTrajectory(
                events=(DiscretePoint(t_ms=t0, state=shutter),)
            ),
        },
        t0_ms=t0,
        t1_ms=t1,
        segment_id=segment_id,
    )


def test_a_shutter_state_too_short_before_the_park_is_kept_dark_until_it_plans() -> None:
    """A last cue cut to one frame at the song end opens the shutter, which needs 30 ms,
    for the 20 ms before the park closes it (review G2). Under `dark` that cue is kept
    dark and the fixture replanned: it parks after the first cue."""

    def slow_open(payload: dict[str, Any]) -> None:
        payload["discrete"]["shutter"]["states"]["open"]["settle_ms"] = 30

    profile = _profile(slow_open)
    initial = InitialFixtureState.model_validate(initial_state_payload())
    cues = [_cue(500, 1000, 0.0, segment_id="long"), _cue(2000, 2020, 0.0, segment_id="last")]
    arguments: dict[str, Any] = {
        "initial_states": {"MH1": initial},
        "locks": (),
        "frame_ms": EFFECT_GRID_MS,
        "sequence_end_ms": 2040,
    }

    refused = plan_prepositions(cues, {"MH1": profile}, **arguments)
    assert refused.has_errors
    assert any("holds 20 ms" in d.reason for d in refused.diagnostics)

    result = plan_prepositions(cues, {"MH1": profile}, on_unplayable="dark", **arguments)
    assert not result.has_errors
    assert [r["start_ms"] for r in result.unplayable] == [2000]
    assert "holds 20 ms" in str(result.unplayable[0]["detail"])
    assert [
        s.segment_id for s in result.segments if TRANSACTION_METADATA_KEY not in s.metadata
    ] == ["long"]
    assert_honest_transactions(result, cues, profile, initial)


def test_keeping_one_cue_dark_can_make_the_next_one_unplayable_too() -> None:
    """Three back-to-back cues each 120 degrees apart on a slow head: none after the first
    can follow its predecessor, and each kept dark leaves the next one no time either.
    The pass ends with the first cue played and the rest dark."""

    def slow(payload: dict[str, Any]) -> None:
        for axis in ("pan", "tilt"):
            payload["axes"][axis]["travel_speed_per_s"] = 90.0

    profile = _profile(slow)
    initial = InitialFixtureState.model_validate(initial_state_payload())
    cues = [
        _cue(500, 1000, 0.0, segment_id="a"),
        _cue(1000, 1500, 120.0, segment_id="b"),
        _cue(1500, 2000, -120.0, segment_id="c"),
    ]
    result = plan_prepositions(
        cues,
        {"MH1": profile},
        initial_states={"MH1": initial},
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=2000,
        on_unplayable="dark",
    )
    assert not result.has_errors
    assert [r["start_ms"] for r in result.unplayable] == [1000, 1500]
    assert_honest_transactions(result, cues, profile, initial)


def test_an_unknown_initial_state_or_a_lock_is_never_kept_dark() -> None:
    profile = _profile()
    result = plan_prepositions(
        [_cue(0, 500, 0.0)],
        {"MH1": profile},
        initial_states={},
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=500,
        on_unplayable="dark",
    )
    assert result.has_errors and result.unplayable == ()


def _speed_rig(speed: float, fixture_ids: tuple[str, ...] = ("MH1", "MH2")) -> FixtureGroup:
    payload = topology_rig(fixture_ids).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for axis in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = speed
    return FixtureGroup.model_validate(payload)


def _once_fast() -> TemplateDoc:
    """A ONCE finite sweep peaking at 0.75 of a 90 degrees/s head at 500 ms beats: 1.5
    times it in a 250 ms-beat bar."""
    extent = 0.75 * 90.0 * 2.0 / math.pi
    return physical_template_doc(
        "un_once_fast",
        [path_step("f", "sweep", mode="finite", pan_extent=extent)],
        mode="ONCE",
    )


def test_a_compile_refusal_only_this_placement_shows_is_kept_dark() -> None:
    """On the fast third bar the sweep outruns the head, which bar 1 never shows: the
    section's cues are kept dark per fixture; `error` refuses it."""
    grid = physical_bars_grid(500.0, 500.0, 250.0, 500.0)
    rig = _speed_rig(90.0)
    states = dict.fromkeys(("MH1", "MH2"), PHYSICAL_INITIAL_STATE)
    job = physical_job(initial_states=states)
    pipeline = _render(
        (_once_fast(),),
        (("un_once_fast", 1, 2), ("un_once_fast", 3, 3)),
        grid=grid,
        rig=rig,
        job=job,
    )
    records = _unplayable(pipeline)
    assert {(r["fixture_id"], r["section_id"], r["code"]) for r in records} == {
        ("MH1", "s2", "compile_refused"),
        ("MH2", "s2", "compile_refused"),
    }
    assert all("travels" in r["detail"] for r in records)

    with registered_templates(_once_fast()), pytest.raises(PhysicalChannelError, match="travels"):
        RenderingPipeline(
            choreography_plan=physical_sections(("un_once_fast", 1, 2), ("un_once_fast", 3, 3)),
            beat_grid=grid,
            fixture_group=rig,
            job_config=physical_job(initial_states=states, on_unplayable="error"),
            output_path=None,
        ).render()


def test_a_refusal_the_basic_placement_shows_still_raises() -> None:
    """At 30 degrees/s the sweep outruns the head from bar 1 too: that is the gate's to
    refuse, and a dark render never stands in for it."""
    rig = _speed_rig(30.0)
    states = dict.fromkeys(("MH1", "MH2"), PHYSICAL_INITIAL_STATE)
    with registered_templates(_once_fast()), pytest.raises(PhysicalChannelError, match="travels"):
        RenderingPipeline(
            choreography_plan=physical_sections(("un_once_fast", 1, 1), ("un_once_fast", 2, 4)),
            beat_grid=physical_bars_grid(*[500.0] * 4),
            fixture_group=rig,
            job_config=physical_job(initial_states=states),
            output_path=None,
        ).render()


def test_a_compile_refusal_on_one_head_leaves_the_others_unchanged() -> None:
    """Only MH2 is slow: its cues of the fast bar are kept dark, and MH1's frames are those
    of a rig without MH2 (a head missing from the rig changes no other head)."""
    grid = physical_bars_grid(500.0, 500.0, 250.0, 500.0)
    payload = _speed_rig(180.0).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        if fixture["fixture_id"] == "MH2":
            for axis in ("pan", "tilt"):
                fixture["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = 90.0
    both = FixtureGroup.model_validate(payload)
    alone = _speed_rig(180.0, ("MH1",))
    sections = (("un_once_fast", 1, 2), ("un_once_fast", 3, 3))
    states = dict.fromkeys(("MH1", "MH2"), PHYSICAL_INITIAL_STATE)
    pair = _render(
        (_once_fast(),), sections, grid=grid, rig=both, job=physical_job(initial_states=states)
    )
    single = _render(
        (_once_fast(),),
        sections,
        grid=grid,
        rig=alone,
        job=physical_job(initial_states={"MH1": PHYSICAL_INITIAL_STATE}),
    )
    assert {r["fixture_id"] for r in _unplayable(pair)} == {"MH2"}
    assert [f for f in pair.frames if f.fixture_id == "MH1"] == list(single.frames)


def test_a_once_cycle_a_section_is_too_short_for_is_kept_dark() -> None:
    """A 2-bar ONCE cycle in a 1-bar section: that section's cues are kept dark (review
    class (i)); `error` refuses it at compile."""
    doc = physical_template_doc(
        "un_once_long",
        [path_step("f", "sweep", mode="finite", pan_extent=20.0, period_beats=8.0, duration=2.0)],
        mode="ONCE",
        cycle_bars=2.0,
    )
    sections = (("un_once_long", 1, 3), ("un_once_long", 4, 4))
    grid = physical_bars_grid(*[500.0] * 4)
    pipeline = _render((doc,), sections, grid=grid)
    records = _unplayable(pipeline)
    assert {(r["fixture_id"], r["section_id"], r["code"]) for r in records} == {
        ("MH1", "s2", "once_section_too_short"),
        ("MH2", "s2", "once_section_too_short"),
    }
    assert all("may not cut it short" in r["detail"] for r in records)
    with registered_templates(doc), pytest.raises(PhysicalCompileError, match="cut it short"):
        RenderingPipeline(
            choreography_plan=physical_sections(*sections),
            beat_grid=grid,
            fixture_group=physical_rig(),
            job_config=physical_job(on_unplayable="error"),
            output_path=None,
        ).render()


# Review G1, fuzz seed 3942: one 16-bit head at 450 degrees/s with a 60 ms close latency
# on a jittered grid. Step `a` is lit for its first half beat and dark after; the section
# at bar 11 cuts it to a slice in that dark tail, whose darkness the next transaction
# counted only from the cut: it needed 260 ms and had 220. A cut that leaves only
# commanded darkness is dropped instead, so the cut cue ends as the whole one does.
_G1_BEATS = (
    11.0, 461.0, 911.0, 1321.0, 1731.0, 2181.0, 2591.0, 3041.0, 3491.0, 3971.0, 4451.0,
    4901.0, 5351.0, 5761.0, 6271.0, 6721.0, 7231.0, 7641.0, 8091.0, 8501.0, 8981.0, 9461.0,
    9911.0, 10361.0, 10811.0, 11261.0, 11711.0, 12161.0, 12611.0, 13061.0, 13511.0,
    13961.0, 14371.0, 14821.0, 15271.0, 15721.0, 16171.0, 16621.0, 17101.0, 17581.0,
    17991.0, 18401.0, 18851.0, 19301.0, 19781.0,
)  # fmt: skip
_G1_TEMPLATE = {
    "template_id": "un_g1",
    "version": 1,
    "name": "un_g1",
    "category": "low_energy",
    "repeat": {"mode": "JOINER", "cycle_bars": 1.0, "loop_step_ids": ["a", "b", "c"],
               "remainder_policy": "TRUNCATE"},
    "steps": [
        {"step_id": "a", "timing": {"base_timing": {"start_offset_bars": 0.0, "duration_bars": 0.25}},
         "geometry": {}, "movement": {"physical": {
             "shape": "linear", "mode": "finite", "start_pan_deg": 8.1, "start_tilt_deg": 9.6,
             "pan_extent_deg": -35.2, "period_beats": 2.0}},
         "dimmer": {"physical": {"period_beats": 2.0, "duty_cycle": 0.25, "low": 0.0, "high": 1.0}},
         "physical_shutter_state": "open", "physical_color": "blue",
         "physical_reposition_fallback": "drop_accent"},
        {"step_id": "b", "timing": {"base_timing": {"start_offset_bars": 0.25, "duration_bars": 0.5}},
         "geometry": {}, "movement": {"physical": {
             "shape": "hold", "mode": "periodic", "start_pan_deg": -33.6, "start_tilt_deg": 7.5}},
         "dimmer": {"physical": {"period_beats": 0.5, "duty_cycle": 0.75, "low": 0.0, "high": 1.0}},
         "physical_shutter_state": "open", "physical_color": "blue",
         "physical_reposition_fallback": "preserve_aim"},
        {"step_id": "c", "timing": {"base_timing": {"start_offset_bars": 0.75, "duration_bars": 0.25}},
         "geometry": {}, "movement": {"physical": {
             "shape": "circle", "mode": "periodic", "start_pan_deg": -6.4, "start_tilt_deg": 19.2,
             "pan_extent_deg": 45.4, "tilt_extent_deg": 10.0, "period_beats": 2.0}},
         "dimmer": {}, "physical_shutter_state": "open",
         "physical_reposition_fallback": "preserve_aim",
         "physical_visibility": {"visible_phase_start": 0.5, "visible_phase_end": 1.0}},
    ],
    "metadata": {"tags": ["test_only", "physical_v2"], "recommended_sections": ["verse"],
                 "energy_range": [0, 100], "description": "Review G1, fuzz seed 3942."},
    "physical_overlays": [{"start_beats": 1.0, "end_beats": 2.25, "mask_beats": 0.5,
                           "channel": "gobo", "state": "star"}],
}  # fmt: skip


def test_a_window_cut_into_a_cues_dark_tail_drops_the_slice() -> None:
    beats = list(_G1_BEATS)
    grid = BeatGrid(
        bar_boundaries=beats[::4],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=19796.0,
    )
    payload = topology_rig(("MH1",)).model_dump(mode="json")
    profile = payload["fixtures"][0]["config"]["physical_profile"]
    for axis in ("pan", "tilt"):
        profile["axes"][axis].update(travel_speed_per_s=450.0, latency_ms=0, settle_ms=0)
    profile["visibility"].update(close_latency_ms=60, open_latency_ms=0)
    for state in profile["discrete"]["shutter"]["states"].values():
        state["settle_ms"] = 0
    rig = FixtureGroup.model_validate(payload)
    doc = TemplateDoc.model_validate({"template": _G1_TEMPLATE})
    job = physical_job(
        initial_states={"MH1": PHYSICAL_INITIAL_STATE},
        reposition_fallback="drop_accent",
        on_unplayable="error",
    )
    with registered_templates(doc):
        check_physical_templates(
            ["un_g1"],
            beat_grid=grid,
            fixture_group=rig,
            initial_states=job.moving_heads.initial_states,
            failure_mode="drop_accent",
        )
    sections = (
        ("un_g1", 1, 3),
        ("un_g1", 4, 5),
        ("un_g1", 6, 6),
        ("un_g1", 7, 10),
        ("un_g1", 11, 12),
    )
    pipeline = _render((doc,), sections, grid=grid, rig=rig, job=job)
    assert pipeline.render_record is not None
    # Step `a` of s5 is cut at 18420 in its dark tail: the slice is dropped, not entered.
    s5 = [
        (r["step_id"], r["start_ms"], r["entry_window_end_ms"])
        for r in pipeline.render_record["dropped_cues"]
        if r["section_id"] == "s5" and r["reason"] == "entry_window"
    ]
    assert s5 == [("a", 18000, 18420)]
    assert not _unplayable(pipeline)


def test_the_trace_lists_unplayable_cues_in_the_written_file(tmp_path: Path) -> None:
    with registered_templates(_JUMP):
        pipeline = RenderingPipeline(
            choreography_plan=physical_sections(("un_jump", 1, 4)),
            beat_grid=physical_bars_grid(*[500.0] * 4),
            fixture_group=physical_rig(),
            job_config=physical_job(),
            output_path=tmp_path / "jump.xsq",
        )
        pipeline.render()
    assert pipeline.artifacts is not None
    trace = json.loads(pipeline.artifacts.trace_path.read_text())
    text = json.dumps(trace)
    assert '"reason": "unplayable"' in text and "unplayable_totals" in text


def test_a_too_short_shutter_state_in_a_transaction_keeps_its_cue_dark() -> None:
    """Darkness by shutter alone, closed needing 30 ms: the 20 ms transaction between the
    two cues closes the shutter for 20 ms before the second cue reveals. That cue, not
    the one before the transaction, is kept dark; the fixture parks after the first."""

    def shutter_only(payload: dict[str, Any]) -> None:
        payload["visibility"]["dimmer_zero_extinguishes"] = False
        payload["discrete"]["shutter"]["states"]["closed"]["settle_ms"] = 30

    profile = _profile(shutter_only)
    initial = InitialFixtureState.model_validate(initial_state_payload())
    cues = [_cue(500, 1000, 0.0, segment_id="a"), _cue(1020, 1500, 0.0, segment_id="b")]
    arguments: dict[str, Any] = {
        "initial_states": {"MH1": initial},
        "locks": (),
        "frame_ms": EFFECT_GRID_MS,
        "sequence_end_ms": 1500,
    }

    refused = plan_prepositions(cues, {"MH1": profile}, **arguments)
    assert [d.cue_ms for d in refused.diagnostics if d.status == "error"] == [1000]

    result = plan_prepositions(cues, {"MH1": profile}, on_unplayable="dark", **arguments)
    assert not result.has_errors
    assert [r["start_ms"] for r in result.unplayable] == [1020]
    played = [s.segment_id for s in result.segments if TRANSACTION_METADATA_KEY not in s.metadata]
    assert played == ["a"]
    assert_honest_transactions(result, cues, profile, initial)


@pytest.mark.parametrize("defect", ["ValueError", "ValidationError"])
def test_a_defect_at_a_sections_own_placement_is_never_kept_dark(
    defect: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a deliberate compile or channel refusal is kept dark. Any other error a step
    raises at a section's own placement (here injected into the second section only, so
    bar 1 over the song still compiles) is a defect and propagates under `dark`."""
    from twinklr.core.sequencer.moving_heads.compile import template_compiler

    compile_step = template_compiler.compile_physical_step

    def broken(step: Any, context: Any, **kwargs: Any) -> FixtureSegment:
        if context.section_id == "s2":
            if defect == "ValueError":
                raise ValueError("injected defect")
            InitialFixtureState.model_validate({})  # raises a pydantic ValidationError
        return compile_step(step, context, **kwargs)

    monkeypatch.setattr(template_compiler, "compile_physical_step", broken)
    doc = physical_template_doc("un_defect", [hold_step("h", 10.0)])
    with registered_templates(doc), pytest.raises(ValueError) as raised:
        RenderingPipeline(
            choreography_plan=physical_sections(("un_defect", 1, 2), ("un_defect", 3, 4)),
            beat_grid=physical_bars_grid(*[500.0] * 4),
            fixture_group=physical_rig(),
            job_config=physical_job(),
            output_path=None,
        ).render()
    assert type(raised.value).__name__ == defect
