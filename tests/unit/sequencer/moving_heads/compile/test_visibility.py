"""Visibility envelopes and masked attribute overlays (P2.4b).

A step's `physical_visibility` lights it only over part of each movement period, read at
the head's own movement phase (its pan/tilt distribution offset included, its path
transform not); the dark rest is left between cues for the transaction pass, which
performs every dark return. A template's `physical_overlays` split each cue they cross
into base, dark mask, overlay (the base with one wheel replaced), dark mask and base, and
the base resumed after release is whichever step is in force then. Neither authors dark
motion inside a cue.

Every render below is gated first (the gate must admit it), then replanned from its cues
and checked from its bytes on every fixture: frames outside the cues are dark through the
profile's declared mechanism and `assert_honest_transactions` passes: no wheel turns or
settles on a lit frame, inside a cue or not; no head is lit while a transaction moves it
or its earlier motion is still under way; each reveal is on its cue's own frame.

The fuzz runs 12 seeds by default; set `TWINKLR_P24B_FUZZ=full` to sweep 400.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import copy
from itertools import pairwise
import os
import random
from typing import Any

from pydantic import ValidationError
import pytest

from tests.config_effects_registry import CONFIG_EFFECTS, ConfigDispositionKind
from tests.support.mh_physical import (
    PHYSICAL_INITIAL_STATE,
    assert_honest_transactions,
    envelope_step,
    hold_step,
    overlay,
    path_step,
    physical_bars_grid,
    physical_job,
    physical_preset_rig,
    physical_rig,
    physical_sections,
    physical_template_doc,
    registered_templates,
    sweep_step,
    topology_payload,
    topology_rig,
)
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.config.render_policy import UnsupportedRenderModeError
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.context import TemplateCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscreteTrajectory,
    PhysicalChannelError,
    RenderLock,
)
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.models.moving_heads.topology import rig_topology
from twinklr.core.sequencer.models.template import Template, TemplateDoc, TemplateStep
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.physical import PhysicalCompileError
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    TRANSACTION_METADATA_KEY,
    plan_prepositions,
)
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    compile_physical_template,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import frame_times
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
from twinklr.core.sequencer.moving_heads.pipeline import (
    PhysicalRenderError,
    RenderingPipeline,
    check_physical_templates,
    physical_cue_limits,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import build_musical_phase_map

# Byte offsets of `physical_head_profile`.
_PAN, _DIMMER, _COLOR, _SHUTTER, _GOBO = 1, 5, 7, 17, 18
_WHITE, _RED, _BLUE = 0, 14, 26
_GOBO_OPEN, _DOTS, _STAR = 0, 10, 20


def _grid(*beat_ms: float) -> BeatGrid:
    """Four-beat bars from 15 ms (so steps quantize to 20 ms, 2020 ms, ...)."""
    return physical_bars_grid(*(beat_ms or (500.0,) * 8))


def _rig(edit: Callable[[dict[str, Any]], None] | None = None) -> FixtureGroup:
    """`physical_rig`, each head's profile passed through `edit`."""
    payload = physical_rig().model_dump(mode="json")
    if edit is not None:
        for fixture in payload["fixtures"]:
            edit(fixture["config"]["physical_profile"])
    return FixtureGroup.model_validate(payload)


def _speed(value: float) -> Callable[[dict[str, Any]], None]:
    def edit(profile: dict[str, Any]) -> None:
        for axis in ("pan", "tilt"):
            profile["axes"][axis]["travel_speed_per_s"] = value

    return edit


def _cues(
    segments: Sequence[FixtureSegment], fixture_id: str | None = None
) -> list[FixtureSegment]:
    return [
        s
        for s in segments
        if TRANSACTION_METADATA_KEY not in s.metadata
        and (fixture_id is None or s.fixture_id == fixture_id)
    ]


def _spans(segments: Sequence[FixtureSegment], fixture_id: str = "MH1") -> list[tuple[int, int]]:
    return [(s.t0_ms, s.t1_ms) for s in sorted(_cues(segments, fixture_id), key=lambda s: s.t0_ms)]


def _commanded_dark(frame: dict[int, int], profile: FixtureCapabilities) -> bool:
    """Dark through the profile's declared mechanism, judged from the bytes alone."""
    visibility = profile.visibility
    dimmer = profile.axes.get("dimmer")
    if (
        visibility.dimmer_zero_extinguishes
        and dimmer is not None
        and frame[dimmer.coarse_offset] == dimmer.dmx_word(0)
    ):
        return True
    shutter = profile.discrete.get("shutter")
    if shutter is None:
        return False
    state = next(name for name, s in shutter.states.items() if s.value == frame[shutter.offset])
    return state in visibility.extinguishing_shutter_states


def _frames(pipeline: RenderingPipeline, fixture_id: str = "MH1") -> dict[int, dict[int, int]]:
    return {f.time_ms: dict(f.channels) for f in pipeline.frames if f.fixture_id == fixture_id}


def _check_bytes(
    pipeline: RenderingPipeline,
    segments: Sequence[FixtureSegment],
    rig: FixtureGroup,
    job: JobConfig,
    *,
    locks: Sequence[RenderLock] = (),
) -> None:
    """Replan the render's cues, then check every fixture from its bytes: frames outside
    the cues are dark through the declared mechanism, and the transactions are honest."""
    policy = job.moving_heads
    cues = _cues(segments)
    profiles = {f.fixture_id: f.config.physical_profile for f in rig.expand_fixtures()}
    replanned = plan_prepositions(
        cues,
        profiles,  # type: ignore[arg-type]
        initial_states=policy.initial_states,
        locks=locks,
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=len(frame_times(int(pipeline.beat_grid.duration_ms))) * EFFECT_GRID_MS,
        failure_mode=policy.reposition_fallback,
    )
    assert list(replanned.segments) == list(segments)
    for fixture_id, profile in profiles.items():
        assert profile is not None
        covered = {
            t for c in _cues(cues, fixture_id) for t in range(c.t0_ms, c.t1_ms, EFFECT_GRID_MS)
        }
        frames = _frames(pipeline, fixture_id)
        for time_ms, frame in frames.items():
            if time_ms not in covered:
                assert _commanded_dark(frame, profile), (fixture_id, time_ms)
        if not covered:
            continue  # no cue to check against: every frame was dark above
        assert_honest_transactions(
            replanned,
            cues,
            profile,
            policy.initial_states[fixture_id],
            locks=locks,
            fixture_id=fixture_id,
        )


def _render(
    *sections: tuple[str, int, int],
    docs: Sequence[TemplateDoc],
    grid: BeatGrid | None = None,
    rig: FixtureGroup | None = None,
    job: JobConfig | None = None,
    locks: Sequence[RenderLock] = (),
) -> tuple[RenderingPipeline, list[FixtureSegment]]:
    """Gate the sections' templates, render them and check every fixture's bytes."""
    grid, rig, job = grid or _grid(), rig or physical_rig(), job or physical_job()
    with registered_templates(*docs):
        check_physical_templates(
            sorted({template_id for template_id, _, _ in sections}),
            beat_grid=grid,
            fixture_group=rig,
            initial_states=job.moving_heads.initial_states,
            failure_mode=job.moving_heads.reposition_fallback,
        )
        pipeline = RenderingPipeline(
            choreography_plan=physical_sections(*sections),
            beat_grid=grid,
            fixture_group=rig,
            job_config=job,
            output_path=None,
            locks=locks,
        )
        segments = pipeline.render()
    _check_bytes(pipeline, segments, rig, job, locks=locks)
    return pipeline, segments


def _gate_error(
    doc: TemplateDoc,
    *,
    rig: FixtureGroup | None = None,
    job: JobConfig | None = None,
    grid: BeatGrid | None = None,
) -> str:
    """The gate's refusal of `doc` (on the default grid unless given)."""
    rig, job = rig or physical_rig(), job or physical_job()
    with registered_templates(doc), pytest.raises(UnsupportedRenderModeError) as error:
        check_physical_templates(
            [doc.template.template_id],
            beat_grid=grid or _grid(),
            fixture_group=rig,
            initial_states=job.moving_heads.initial_states,
            failure_mode=job.moving_heads.reposition_fallback,
        )
    return str(error.value)


def _compile(
    template: Template,
    rig: FixtureGroup | None = None,
    *,
    bars: int = 1,
    grid: BeatGrid | None = None,
) -> list[FixtureSegment]:
    rig, grid = rig or physical_rig(), grid or _grid()
    phase_map = build_musical_phase_map(grid)
    start, end = physical_cue_limits(phase_map, int(grid.duration_ms))
    context = TemplateCompileContext(
        section_id="verse",
        template_id=template.template_id,
        fixtures=build_fixture_contexts(rig_profile_from_fixture_group(rig), rig),
        beat_grid=grid,
        start_bar=1,
        duration_bars=bars,
        presets=rig.presets,
        topology=rig_topology(rig),
        fixture_group_id=rig.group_id,
    )
    return compile_physical_template(
        template, context, phase_map=phase_map, start_limit_ms=start, end_limit_ms=end
    ).segments


def _values(cue: FixtureSegment, channel: ChannelName) -> list[float]:
    trajectory = cue.channels[channel].physical
    assert isinstance(trajectory, ContinuousTrajectory)
    return [point.value for point in trajectory.points]


def _state(cue: FixtureSegment, channel: ChannelName) -> list[str]:
    trajectory = cue.channels[channel].physical
    assert isinstance(trajectory, DiscreteTrajectory)
    return [event.state for event in trajectory.events]


# --- Envelopes ---------------------------------------------------------------------------


_FLY_OUT = physical_template_doc("vis_fly_out", [envelope_step("out", 0.0, 60.0, lit=(0.0, 0.25))])
"""A sine pan swing, lit only while it travels from center to its right edge."""
_FLY_IN = physical_template_doc("vis_fly_in", [envelope_step("in", 0.0, 60.0, lit=(0.25, 0.5))])
"""The same swing, lit only on its way back from the edge to center."""


def test_an_envelope_lights_only_its_window_and_every_return_is_dark() -> None:
    """Lit while the movement phase is in [0, 0.25) of each 2000 ms period: one slice per
    cycle, the dimmer full on it; every other frame is commanded dark, and the head's
    return to center between slices is a transaction (checked from the bytes)."""
    pipeline, segments = _render(("vis_fly_out", 1, 4), docs=(_FLY_OUT,))
    for fixture_id in ("MH1", "MH2"):
        assert _spans(segments, fixture_id) == [(20 + 2000 * k, 520 + 2000 * k) for k in range(4)]
    frames = _frames(pipeline)
    for k in range(4):
        lit = [frames[t] for t in range(20 + 2000 * k, 520 + 2000 * k, EFFECT_GRID_MS)]
        assert {frame[_DIMMER] for frame in lit} == {255}
        assert {frame[_SHUTTER] for frame in lit} == {8}  # the step's open state


def test_fly_out_and_fly_in_light_opposite_directions_of_one_path() -> None:
    """Both share the path and its phase origin; fly-out is lit travelling out (pan rising
    from center), fly-in travelling back (pan falling to center), on every head."""
    _, out = _render(("vis_fly_out", 1, 2), docs=(_FLY_OUT,))
    _, back = _render(("vis_fly_in", 1, 2), docs=(_FLY_IN,))
    for fixture_id in ("MH1", "MH2"):
        for cue in _cues(out, fixture_id):
            pan = _values(cue, ChannelName.PAN)
            assert pan[0] == pytest.approx(0.0, abs=1e-9) and pan == sorted(pan)
        for cue in _cues(back, fixture_id):
            pan = _values(cue, ChannelName.PAN)
            assert pan[0] == pytest.approx(60.0) and pan == sorted(pan, reverse=True)
        assert _spans(back, fixture_id) == [(520, 1020), (2520, 3020)]


def test_the_lit_window_follows_each_heads_phase_offset() -> None:
    """MH2 lags a quarter cycle on pan and tilt, so its window opens 500 ms later, where its
    own path is at center: the window follows each head's path, not the step clock."""
    rig = topology_rig(("MH1", "MH2"), topology=topology_payload(("MH1", "MH2")))
    distribution = [{"domains": ["pan", "tilt"], "spread_cycles": 0.25}]
    doc = physical_template_doc(
        "vis_lag", [envelope_step("out", 0.0, 60.0, lit=(0.0, 0.25), distribution=distribution)]
    )
    _, segments = _render(("vis_lag", 1, 2), docs=(doc,), rig=rig)
    assert _spans(segments, "MH1") == [(20, 520), (2020, 2520)]
    assert _spans(segments, "MH2") == [(520, 1020), (2520, 3020)]
    for fixture_id in ("MH1", "MH2"):
        first = min(_cues(segments, fixture_id), key=lambda s: s.t0_ms)
        assert _values(first, ChannelName.PAN)[0] == pytest.approx(0.0, abs=1e-9)


def test_a_frame_is_lit_when_its_start_lies_in_the_window() -> None:
    """Phases [0.125, 0.375) of a 2000 ms period from 20 ms are 270-770 ms, off the frame
    grid: the frame at 260 ms starts before the window and stays dark, the one at 760 ms
    starts inside it and is lit."""
    doc = physical_template_doc("vis_off_grid", [envelope_step("o", 0.0, 60.0, lit=(0.125, 0.375))])
    assert _spans(_compile(doc.template)) == [(280, 780)]


@pytest.mark.parametrize(
    "transform", [{"phase_cycles": 0.25}, {"reverse": True}, {"reverse": True, "phase_cycles": 0.5}]
)
def test_a_path_transform_moves_the_path_but_not_the_lit_window(transform: dict[str, Any]) -> None:
    """Decision: the window reads the movement phase before the path's own transform, as
    pulses do (P2.3), so shifting or reversing a circle changes where it is while lit,
    never when it is lit."""

    def compiled(transform: dict[str, Any] | None) -> list[FixtureSegment]:
        step = path_step("orbit", "circle", transform=transform, physical_shutter_state="open")
        step["dimmer"] = {}
        step["physical_visibility"] = {"visible_phase_start": 0.25, "visible_phase_end": 0.5}
        return _compile(physical_template_doc("vis_orbit", [step]).template, bars=2)

    plain, moved = compiled(None), compiled(transform)
    assert _spans(moved) == _spans(plain) == [(520, 1020), (2520, 3020)]
    assert [_values(c, ChannelName.TILT) for c in _cues(moved, "MH1")] != [
        _values(c, ChannelName.TILT) for c in _cues(plain, "MH1")
    ]


def test_attack_and_release_ramps_sit_inside_the_lit_slice() -> None:
    """Lit over phases [0, 0.5) (two beats), up over one beat and down over half a beat:
    the dimmer is 0 on the slice's first frame, 0.48 up 0.48 beat in, full from one
    beat to the release, and still above zero on its last frame; every frame around the
    slice is dark."""
    doc = physical_template_doc(
        "vis_ramps", [envelope_step("r", 0.0, 60.0, lit=(0.0, 0.5), attack=1.0, release=0.5)]
    )
    pipeline, segments = _render(("vis_ramps", 1, 1), docs=(doc,))
    assert _spans(segments) == [(20, 1020)]
    frames = _frames(pipeline)
    expected = {20: 0, 260: 122, 520: 255, 760: 255, 1000: 20}  # 0.48 and 0.08 of 255
    assert {t: frames[t][_DIMMER] for t in expected} == expected
    assert frames[1020][_DIMMER] == 0 and frames[0][_DIMMER] == 0
    dimmer = [frames[t][_DIMMER] for t in range(20, 1020, EFFECT_GRID_MS)]
    rising, falling = dimmer[:25], dimmer[25:]
    assert rising == sorted(rising) and falling == sorted(falling, reverse=True)


def test_ramps_repeat_in_every_cycle_of_a_step() -> None:
    """A two-beat period lit over its first beat, up over half a beat: each of the step's
    two cycles ramps from 0, not only the one at its phase origin."""
    doc = physical_template_doc(
        "vis_cycles",
        [envelope_step("c", 0.0, 20.0, lit=(0.0, 0.5), attack=0.5, period_beats=2.0)],
    )
    pipeline, segments = _render(("vis_cycles", 1, 1), docs=(doc,))
    assert _spans(segments) == [(20, 520), (1020, 1520)]
    frames = _frames(pipeline)
    for start in (20, 1020):
        assert [frames[start + offset][_DIMMER] for offset in (0, 120, 240, 260)] == [
            0,
            122,
            245,
            255,
        ]


def test_level_sets_the_lit_dimmer() -> None:
    doc = physical_template_doc(
        "vis_half", [envelope_step("h", 0.0, 60.0, lit=(0.0, 0.25), level=0.5)]
    )
    pipeline, _ = _render(("vis_half", 1, 1), docs=(doc,))
    assert {_frames(pipeline)[t][_DIMMER] for t in range(20, 520, EFFECT_GRID_MS)} == {128}


@pytest.mark.parametrize(
    ("edit", "match"),
    [
        (
            lambda s: s.update(
                dimmer={
                    "physical": {"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0}
                }
            ),
            "replaces the dimmer",
        ),
        (
            lambda s: (
                s.pop("physical_shutter_state"),
                s.update(
                    physical_shutter={
                        "period_beats": 1.0,
                        "duty_cycle": 0.5,
                        "low_state": "closed",
                        "high_state": "open",
                    }
                ),
            ),
            "replaces the dimmer",
        ),
        (
            lambda s: s["movement"].update(
                physical={
                    "shape": "hold",
                    "mode": "periodic",
                    "start_pan_deg": 0.0,
                    "start_tilt_deg": 0.0,
                }
            ),
            "hold step",
        ),
        (
            lambda s: s["physical_visibility"].update(attack_beats=0.6, release_beats=0.5),
            "exceed the lit window",
        ),
        (
            lambda s: s.update(physical_distribution=[{"domains": ["pan"], "spread_cycles": 0.2}]),
            "pan and tilt must be distributed together",
        ),
        (
            lambda s: s.update(
                physical_distribution=[
                    {"domains": ["pan", "tilt"], "spread_cycles": 0.2},
                    {"domains": ["dimmer"], "spread_cycles": 0.2},
                ]
            ),
            "would do nothing",
        ),
        (lambda s: s["physical_visibility"].update(visible_phase_end=0.1), "after visible"),
    ],
)
def test_an_envelope_owns_the_dimmer_and_reads_one_movement_phase(
    edit: Callable[[dict[str, Any]], Any], match: str
) -> None:
    """Refused at validation: an envelope plus a dimmer or shutter pulse, on a hold step,
    with ramps longer than its window (here 0.25 of 4 beats = 1 beat), with pan and tilt
    on different offsets, with the dimmer distributed, or with an empty window."""
    step = envelope_step("e", 0.0, 60.0, lit=(0.25, 0.5))
    edit(step)
    with pytest.raises(ValidationError, match=match):
        TemplateStep.model_validate(step)


def _no_dimmer(profile: dict[str, Any]) -> None:
    """A profile without a dimmer axis: only its shutter extinguishes."""
    profile["axes"].pop("dimmer")
    profile["visibility"]["dimmer_zero_extinguishes"] = False


def test_a_profile_without_a_dimmer_axis_needs_zero_ramps_and_full_level() -> None:
    """Without a dimmer the slice is lit by the shutter alone, so a ramp or a level below 1
    cannot be honored and is refused, never dropped."""
    rig = _rig(_no_dimmer)
    plain = physical_template_doc("vis_nod", [envelope_step("n", 0.0, 60.0, lit=(0.0, 0.25))])
    segments = _compile(plain.template, rig)
    assert all(ChannelName.DIMMER not in cue.channels for cue in segments)
    assert all(_state(cue, ChannelName.SHUTTER) == ["open"] for cue in segments)
    for fields in ({"attack": 0.5}, {"release": 0.5}, {"level": 0.5}):
        doc = physical_template_doc(
            "vis_nod_ramp", [envelope_step("n", 0.0, 60.0, lit=(0.0, 0.25), **fields)]
        )
        with pytest.raises(PhysicalChannelError, match="no dimmer axis"):
            _compile(doc.template, rig)


def _strobe(profile: dict[str, Any]) -> None:
    """A third, non-extinguishing shutter state."""
    profile["discrete"]["shutter"]["states"]["strobe"] = {
        "range_min": 32,
        "range_max": 59,
        "value": 40,
        "settle_ms": 0,
    }


def test_the_lit_shutter_is_the_steps_state_else_the_profiles_open_state() -> None:
    """A step without a static shutter state is lit through the profile's `open_state`;
    one with a state keeps it; with neither the step is refused."""
    unset = envelope_step("s", 0.0, 60.0, lit=(0.0, 0.25))
    unset.pop("physical_shutter_state")
    strobe = {**copy.deepcopy(unset), "physical_shutter_state": "strobe"}

    def shutters(step: dict[str, Any], rig: FixtureGroup) -> set[str]:
        doc = physical_template_doc("vis_shutter", [step])
        return {s for cue in _compile(doc.template, rig) for s in _state(cue, ChannelName.SHUTTER)}

    assert shutters(unset, _rig(_strobe)) == {"open"}
    assert shutters(strobe, _rig(_strobe)) == {"strobe"}

    def open_strobe(profile: dict[str, Any]) -> None:
        _strobe(profile)
        profile["discrete"]["shutter"]["open_state"] = "strobe"

    assert shutters(unset, _rig(open_strobe)) == {"strobe"}

    def no_open(profile: dict[str, Any]) -> None:
        profile["discrete"]["shutter"]["open_state"] = None

    with pytest.raises(PhysicalChannelError, match="open_state"):
        shutters(unset, _rig(no_open))


@pytest.mark.parametrize(
    ("lit", "period", "what"),
    [((0.5, 0.504), 4.0, "lit window"), ((0.0, 0.97), 1.0, "dark interval")],
)
def test_a_window_or_gap_shorter_than_a_frame_is_refused(
    lit: tuple[float, float], period: float, what: str
) -> None:
    """0.004 of a 2000 ms period, or 0.03 of a 500 ms one, is under a frame: a lit window
    or a dark interval that short inside a step is refused by the compile, and so by the
    gate before planning, never dropped."""
    doc = physical_template_doc(
        "vis_short", [envelope_step("s", 0.0, 20.0, lit=lit, period_beats=period)]
    )
    with pytest.raises(PhysicalChannelError, match=f"{what} .* shorter than one 20 ms frame"):
        _compile(doc.template, bars=2)
    assert what in _gate_error(doc)


def _return_doc(fallback: str | None) -> TemplateDoc:
    """A linear pan out by 60 degrees over three beats, lit while it moves, then dark for
    the bar's last beat: 500 ms to return 60 degrees."""
    step = sweep_step("out", 0.0, 60.0, period_beats=3.0)
    step["dimmer"] = {}
    # Ending at 1 would light the hold too (the finite phase clamps); 0.99 ends at 1505 ms,
    # so the first frame left dark is 1520 ms.
    step["physical_visibility"] = {"visible_phase_start": 0.0, "visible_phase_end": 0.99}
    if fallback is not None:
        step["physical_reposition_fallback"] = fallback
    return physical_template_doc(f"vis_return_{fallback}", [step])


def test_a_dark_return_too_short_fails_and_a_declared_fallback_drops_the_slice() -> None:
    """At 45 degrees/s the return needs 1333 ms but has 500: the transaction's
    substitutable `infeasible_transition`. The gate refuses it under `error`; a step that
    declares `drop_accent` under that policy renders, each slice that cannot be reached
    kept dark."""
    slow = _rig(_speed(45.0))
    refused = _gate_error(_return_doc(None), rig=slow)
    assert "infeasible_transition" in refused and "needs" in refused
    job = physical_job(reposition_fallback="drop_accent")
    pipeline, _ = _render(
        ("vis_return_drop_accent", 1, 4), docs=(_return_doc("drop_accent"),), rig=slow, job=job
    )
    assert pipeline.render_record is not None
    statuses = {
        d["cue_ms"]: d["status"]
        for d in pipeline.render_record["transactions"]
        if d["fixture_id"] == "MH1"
    }
    # The section's entry is not played as authored (its second slice is unreachable), so
    # P2.4a's entry window drops the first slice; from there every other one is dropped.
    assert statuses == {2020: "feasible", 4020: "drop_accent", 6020: "feasible"}


# --- Overlays ----------------------------------------------------------------------------


_FLICK = physical_template_doc(
    "vis_flick", [hold_step("h", 0.0)], overlays=[overlay("gobo", 1.0, 3.0, 0.5, "dots")]
)
"""A lit hold (open gobo) with a gobo flick to `dots` over beats [1, 3) of each bar."""


def test_an_overlay_splits_each_cue_into_base_mask_flick_mask_base() -> None:
    """Beats 1-1.5 dark (the wheel turns in), 1.5-2.5 lit with `dots`, 2.5-3 dark (it
    turns back), then the base again: the wheel never moves on a lit frame."""
    pipeline, segments = _render(("vis_flick", 1, 2), docs=(_FLICK,))
    assert _spans(segments) == [
        (20, 520),
        (760, 1260),
        (1520, 2020),
        (2020, 2520),
        (2760, 3260),
        (3520, 4020),
    ]
    frames = _frames(pipeline)
    for start, end, gobo in ((20, 520, _GOBO_OPEN), (760, 1260, _DOTS), (1520, 2520, _GOBO_OPEN)):
        lit = [frames[t] for t in range(start, end, EFFECT_GRID_MS)]
        assert {(f[_GOBO], f[_DIMMER]) for f in lit} == {(gobo, 255)}
    for start, end in ((520, 760), (1260, 1520)):
        assert {frames[t][_DIMMER] for t in range(start, end, EFFECT_GRID_MS)} == {0}


_TWO_BARS = _grid(500.0, 500.0)
"""A two-bar song: one cycle of the two-step templates below, so the gate never sees B
run into a second cycle's A (a lit change from blue to red)."""


def _base_change_doc(channel: str, state: str, *, overlays: bool = True) -> TemplateDoc:
    """Step A red on bar 1, step B blue on bar 2, both aimed alike; an overlay over beats
    [3, 5): from bar 0.75 to 1.25."""
    steps = [
        hold_step("a", 0.0, physical_color="red"),
        hold_step("b", 0.0, start=1.0, physical_color="blue"),
    ]
    return physical_template_doc(
        f"vis_base_{channel}_{overlays}",
        steps,
        cycle_bars=2.0,
        overlays=[overlay(channel, 3.0, 5.0, 0.5, state)] if overlays else [],
    )


def test_after_release_the_base_step_in_force_resumes() -> None:
    """The base changes from A (red) to B (blue) during the overlay: what resumes after
    release is B's slice with blue, never a stale red. A color overlay hides the base's
    own wheel change under the flick, which on its own is refused (a lit wheel change)."""
    doc = _base_change_doc("color", "white")
    pipeline, segments = _render((doc.template.template_id, 1, 2), docs=(doc,), grid=_TWO_BARS)
    frames = _frames(pipeline)
    assert {frames[t][_COLOR] for t in range(20, 1520, EFFECT_GRID_MS)} == {_RED}
    assert {frames[t][_COLOR] for t in range(1760, 2260, EFFECT_GRID_MS)} == {_WHITE}
    assert {frames[t][_COLOR] for t in range(2520, 4020, EFFECT_GRID_MS)} == {_BLUE}
    resumed = min((c for c in _cues(segments, "MH1") if c.t0_ms >= 2520), key=lambda c: c.t0_ms)
    assert resumed.step_id == "b" and _state(resumed, ChannelName.COLOR) == ["blue"]
    alone = _base_change_doc("color", "white", overlays=False)
    assert "color changes at the cue" in _gate_error(alone, grid=_TWO_BARS)


def test_an_overlay_never_smuggles_a_lit_wheel_change_through_its_flick() -> None:
    """The plan's literal case: a gobo flick across the same base change. The color still
    changes at the step boundary inside the lit flick, so it is refused, as the base alone
    is: the overlay masks only its own channel's turns."""
    message = _gate_error(_base_change_doc("gobo", "dots"), grid=_TWO_BARS)
    assert "color changes at the cue" in message and "2020 ms" in message


def _short_mask_doc(fallback: str | None) -> TemplateDoc:
    """A gobo flick whose masks last a quarter beat (120 ms), under the 150 ms settle."""
    step = hold_step("h", 0.0, **({"physical_reposition_fallback": fallback} if fallback else {}))
    return physical_template_doc(
        f"vis_short_mask_{fallback}", [step], overlays=[overlay("gobo", 1.0, 3.0, 0.25, "dots")]
    )


def test_a_mask_too_short_for_the_wheel_fails_and_a_declared_fallback_drops_the_flick() -> None:
    refused = _gate_error(_short_mask_doc(None))
    assert "infeasible_transition" in refused and "needs 160 ms" in refused
    job = physical_job(reposition_fallback="drop_accent")
    pipeline, _ = _render(
        ("vis_short_mask_drop_accent", 1, 1), docs=(_short_mask_doc("drop_accent"),), job=job
    )
    assert pipeline.render_record is not None
    statuses = [
        d["status"] for d in pipeline.render_record["transactions"] if d["fixture_id"] == "MH1"
    ]
    # The entry window drops the first base slice (its flick is unreachable from it); the
    # flick is entered from the dark, and the base after its 120 ms release mask is dropped.
    assert statuses == ["feasible", "drop_accent"]


def test_a_lock_on_the_masked_wheel_fails_before_emission() -> None:
    """A lock over the first mask leaves the wheel no frame to turn: the transaction's
    `lock_conflict`, and the render delivers nothing."""
    lock = RenderLock(start_ms=520, end_ms=760, fixture_ids=("MH1",), channels=(ChannelName.GOBO,))
    with registered_templates(_FLICK), pytest.raises(PhysicalRenderError, match="lock_conflict"):
        RenderingPipeline(
            choreography_plan=physical_sections(("vis_flick", 1, 1)),
            beat_grid=_grid(),
            fixture_group=physical_rig(),
            job_config=physical_job(),
            output_path=None,
            locks=(lock,),
        ).render()


def test_overlays_on_different_channels_compose_and_on_one_channel_may_not_overlap() -> None:
    """A color flick over beats [1, 3) and a gobo flick over [2, 4): each splits what the
    other left, so the color flick shows on beats 1.5-2 and the gobo flick on 3-3.5 over
    the base color; between them both wheels turn in the dark."""
    doc = physical_template_doc(
        "vis_two",
        [hold_step("h", 0.0)],
        overlays=[overlay("color", 1.0, 3.0, 0.5, "blue"), overlay("gobo", 2.0, 4.0, 0.5, "star")],
    )
    pipeline, segments = _render(("vis_two", 1, 1), docs=(doc,))
    assert _spans(segments) == [(20, 520), (760, 1020), (1520, 1760)]
    frames = _frames(pipeline)
    for start, end, color, gobo in (
        (20, 520, _WHITE, _GOBO_OPEN),
        (760, 1020, _BLUE, _GOBO_OPEN),
        (1520, 1760, _WHITE, _STAR),
    ):
        assert {
            (frames[t][_COLOR], frames[t][_GOBO]) for t in range(start, end, EFFECT_GRID_MS)
        } == {(color, gobo)}
    with pytest.raises(ValidationError, match="overlap at beat 2"):
        physical_template_doc(
            "vis_overlap",
            [hold_step("h", 0.0)],
            overlays=[
                overlay("gobo", 1.0, 3.0, 0.5, "dots"),
                overlay("gobo", 2.0, 4.0, 0.5, "star"),
            ],
        )


def _remainder_doc(policy: str = "HOLD_LAST_POSE") -> TemplateDoc:
    """The review's repro: step a lit only on beat 1 of bar 1, step b a lit hold on bar 2,
    and a gobo flick on beats 1.5-3.5, inside a's dark part, so no full cycle shows it."""
    a = envelope_step("a", 0.0, 30.0, lit=(0.0, 0.25))
    b = hold_step("b", 0.0, start=1.0)
    return physical_template_doc(
        f"vis_rem_{policy.lower()}",
        [a, b],
        cycle_bars=2.0,
        remainder_policy=policy,
        overlays=[overlay("gobo", 1.5, 3.5, 0.25, "dots")],
    )


def test_an_overlay_takes_no_hold_last_pose_remainder() -> None:
    """A three-bar section of a two-bar cycle holds step b over bar 3 from a new phase
    origin, where no authored cycle plays it: the overlay is not applied there (it was,
    with a 140 ms mask the gate never planned, and the render failed after admission)."""
    doc = _remainder_doc()
    pipeline, segments = _render(
        (doc.template.template_id, 1, 3),
        (doc.template.template_id, 4, 4),
        docs=(doc,),
        grid=_grid(*[500.0] * 4),
    )
    assert (4020, 6020) in _spans(segments)
    frames = _frames(pipeline)
    assert {frames[t][_GOBO] for t in range(4020, 6020, EFFECT_GRID_MS)} == {_GOBO_OPEN}


def _cycle_head_doc(policy: str) -> TemplateDoc:
    """Holds a (bar 1) and b (bar 2) at one aim, with a gobo flick on beats 1-3 of bar 1."""
    return physical_template_doc(
        f"vis_head_{policy.lower()}",
        [hold_step("a", 0.0), hold_step("b", 0.0, start=1.0)],
        cycle_bars=2.0,
        remainder_policy=policy,
        overlays=[overlay("gobo", 1.0, 3.0, 0.5, "dots")],
    )


@pytest.mark.parametrize(
    ("policy", "bar_three"),
    [
        ("HOLD_LAST_POSE", [(4020, 6020)]),
        ("TRUNCATE", [(4020, 4520), (4760, 5260), (5520, 6020)]),
    ],
)
def test_an_odd_length_section_flicks_only_where_a_cycle_plays(
    policy: str, bar_three: list[tuple[int, int]]
) -> None:
    """In a three-bar section, TRUNCATE plays the head of a second cycle over bar 3 (step
    a, with its flick); HOLD_LAST_POSE holds step b there, unflicked."""
    doc = _cycle_head_doc(policy)
    _, segments = _render((doc.template.template_id, 1, 3), docs=(doc,), grid=_grid(*[500.0] * 3))
    assert [span for span in _spans(segments) if span[0] >= 4020] == bar_three


def test_an_overlay_the_base_already_holds_is_a_no_op() -> None:
    """A flick to the state a cue already holds would only dip it dark twice: that cue is
    kept whole and records the channel. Over a base change only the cue that differs is
    masked."""
    same = physical_template_doc(
        "vis_same", [hold_step("h", 0.0)], overlays=[overlay("gobo", 1.0, 3.0, 0.5, "open")]
    )
    _, segments = _render(("vis_same", 1, 1), docs=(same,))
    assert _spans(segments) == [(20, 2020)]
    assert {c.metadata["overlay_unchanged"] for c in _cues(segments)} == {"gobo"}
    steps = [
        hold_step("a", 0.0, physical_color="red"),
        hold_step("b", 0.0, start=1.0, physical_color="white"),
    ]
    mixed = physical_template_doc(
        "vis_mixed", steps, cycle_bars=2.0, overlays=[overlay("color", 3.0, 5.0, 0.5, "white")]
    )
    _, segments = _render(("vis_mixed", 1, 2), docs=(mixed,), grid=_TWO_BARS)
    # A's red needs a dark wheel turn from the white initial state: its entry is cut to 520.
    assert _spans(segments) == [(520, 1520), (1760, 2020), (2020, 4020)]
    b = next(c for c in _cues(segments, "MH1") if c.step_id == "b")
    assert b.metadata["overlay_unchanged"] == "color"


def test_an_entry_window_drop_records_the_slice_it_dropped() -> None:
    """The fly-out's first lit slice falls inside its section's entry window: the record
    names that slice's frames, not the whole step instance, whose later slices render."""
    far = physical_template_doc("vis_far", [hold_step("h", 150.0)])
    fly = physical_template_doc(
        "vis_fly", [envelope_step("o", -100.0, 40.0, lit=(0.0, 0.25), period_beats=2.0)]
    )
    pipeline, segments = _render(
        ("vis_far", 1, 1), ("vis_fly", 2, 3), docs=(far, fly), grid=_grid(*[500.0] * 4)
    )
    assert pipeline.render_record is not None
    dropped = [
        d
        for d in pipeline.render_record["dropped_cues"]
        if d["fixture_id"] == "MH1" and d["reason"] == "entry_window"
    ]
    assert dropped and all(d["end_ms"] - d["start_ms"] < 2000 for d in dropped)
    kept = {c.t0_ms for c in _cues(segments, "MH1")}
    for record in dropped:
        assert record["start_ms"] not in kept
        assert record["requested_start_ms"] < record["start_ms"] + 20


def _once_doc(lit_end: float, **fields: Any) -> TemplateDoc:
    """ONCE with HOLD_LAST_POSE: a finite sweep from 0 to 40 degrees over the cycle's bar."""
    step = path_step("f", "sweep", pan=20.0, mode="finite", period_beats=4.0)
    step["dimmer"] = {}
    step["physical_visibility"] = {
        "visible_phase_start": 0.0,
        "visible_phase_end": lit_end,
        **fields,
    }
    return physical_template_doc(f"vis_once_{lit_end:g}", [step], mode="ONCE")


@pytest.mark.parametrize(("lit_end", "spans"), [(1.0, [(20, 6020)]), (0.75, [(20, 1520)])])
def test_a_finite_window_ending_at_one_stays_lit_through_the_once_hold(
    lit_end: float, spans: list[tuple[int, int]]
) -> None:
    """The finite phase clamps to [0, 1] as the motion does: a window ending at 1 lights the
    terminal hold to the section end at its level; one ending before 1 leaves it dark, so
    HOLD_LAST_POSE and TRUNCATE differ again. Release on a window ending at 1 is refused."""
    doc = _once_doc(lit_end)
    pipeline, segments = _render(
        (doc.template.template_id, 1, 3), docs=(doc,), grid=_grid(*[500.0] * 3)
    )
    assert _spans(segments) == spans
    assert _frames(pipeline)[spans[0][1] - 20][_DIMMER] == 255
    with pytest.raises(ValidationError, match="takes no release_beats"):
        _once_doc(1.0, release_beats=0.5)


def test_an_overlay_state_is_named_never_a_byte() -> None:
    """A state the wheel does not declare is refused, never replaced by an open slot or a
    zero byte; an attribute preset supplies each fixture's own state."""
    bad = physical_template_doc(
        "vis_bad", [hold_step("h", 0.0)], overlays=[overlay("gobo", 1.0, 3.0, 0.5, "0")]
    )
    with pytest.raises(PhysicalChannelError, match="state '0' is not declared"):
        _compile(bad.template)
    rig = physical_preset_rig()
    doc = physical_template_doc(
        "vis_preset",
        [hold_step("h", 0.0)],
        overlays=[overlay("gobo", 1.0, 3.0, 0.5, attribute_preset_id="wash")],
    )
    flicks = {
        cue.fixture_id: _state(cue, ChannelName.GOBO)
        for cue in _compile(doc.template, rig)
        if cue.t0_ms == 760
    }
    assert flicks == {"MH1": ["dots"], "MH2": ["star"]}  # MH2 through wash's fallback
    no_gobo = physical_template_doc(
        "vis_no_gobo",
        [hold_step("h", 0.0)],
        overlays=[overlay("gobo", 1.0, 3.0, 0.5, attribute_preset_id="cool")],
    )
    with pytest.raises(PhysicalCompileError, match="'cool' sets no gobo for fixture 'MH1'"):
        _compile(no_gobo.template, rig)


def test_overlay_shape_is_refused_where_it_cannot_follow_the_cycle() -> None:
    """Under PING_PONG (which mirrors every other cycle), past the end of a cycle whose
    steps do not each span it (one they span grows to hold the overlay instead:
    `whole_period_cycle`), with both or neither state source, or with masks that leave
    no flick."""
    with pytest.raises(ValidationError, match="PING_PONG"):
        physical_template_doc(
            "vis_pp",
            [hold_step("h", 0.0)],
            mode="PING_PONG",
            overlays=[overlay("gobo", 1, 3, 0.5, "dots")],
        )
    late = physical_template_doc(
        "vis_late",
        [hold_step("h", 0.0, duration=0.5), hold_step("k", 0.0, start=0.5, duration=0.5)],
        overlays=[overlay("gobo", 3.0, 5.0, 0.5, "dots")],
    )
    with pytest.raises(PhysicalCompileError, match="ends after its 4-beat cycle"):
        _compile(late.template)
    for fields in ({"state": "dots", "attribute_preset_id": "wash"}, {}):
        with pytest.raises(ValidationError, match="exactly one"):
            physical_template_doc(
                "vis_src",
                [hold_step("h", 0.0)],
                overlays=[overlay("gobo", 1.0, 3.0, 0.5, **fields)],
            )
    with pytest.raises(ValidationError, match="outlast its two masks"):
        physical_template_doc(
            "vis_masks", [hold_step("h", 0.0)], overlays=[overlay("gobo", 1.0, 2.0, 0.5, "dots")]
        )


def test_envelopes_and_overlays_are_physical_only_and_absent_from_dumps() -> None:
    """At their defaults neither appears in a dump, so every existing template dumps and
    fingerprints as before."""
    legacy_step = {
        "step_id": "s",
        "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 1}},
        "geometry": {},
        "movement": {},
        "dimmer": {},
    }
    dumped = TemplateStep.model_validate(legacy_step).model_dump(mode="json")
    assert "physical_visibility" not in dumped
    assert (
        "physical_overlays"
        not in physical_template_doc("vis_dump", [hold_step("h", 0.0)]).model_dump(mode="json")[
            "template"
        ]
    )


# --- Repeated runs, missing heads and the gate ------------------------------------------


def _rig_of(fixture_ids: Sequence[str], full_ids: Sequence[str], speed: float) -> FixtureGroup:
    """`len(fixture_ids)` heads at `speed`, placed by the full rig's declared topology."""
    payload = topology_rig(fixture_ids, topology=topology_payload(full_ids)).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        _speed(speed)(fixture["config"]["physical_profile"])
    return FixtureGroup.model_validate(payload)


def _job_of(fixture_ids: Sequence[str], policy: str = "error") -> JobConfig:
    states = dict.fromkeys(fixture_ids, PHYSICAL_INITIAL_STATE)
    if policy == "error":
        return physical_job(initial_states=states)
    return physical_job(initial_states=states, reposition_fallback=policy)


def _encoded(
    sections: Sequence[tuple[str, int, int]], grid: BeatGrid, rig: FixtureGroup, job: JobConfig
) -> dict[str, list[tuple[int, tuple[tuple[int, int], ...]]]]:
    pipeline = RenderingPipeline(
        choreography_plan=physical_sections(*sections),
        beat_grid=grid,
        fixture_group=rig,
        job_config=job,
        output_path=None,
    )
    pipeline.render()
    frames: dict[str, list[tuple[int, tuple[tuple[int, int], ...]]]] = {}
    for frame in pipeline.frames:
        frames.setdefault(frame.fixture_id, []).append(
            (frame.time_ms, tuple(sorted(dict(frame.channels).items())))
        )
    return frames


def _assert_subset_stable(
    sections: Sequence[tuple[str, int, int]],
    grid: BeatGrid,
    *,
    heads: int,
    missing: Sequence[str],
    speed: float,
    policy: str = "error",
) -> None:
    """The gate admits the sections' templates on the full rig, and with any listed head
    removed (its topology slot kept) every remaining head's encoded frames equal the full
    rig's byte for byte."""
    full_ids = tuple(f"MH{index}" for index in range(1, heads + 1))
    rig, job = _rig_of(full_ids, full_ids, speed), _job_of(full_ids, policy)
    check_physical_templates(
        sorted({template_id for template_id, _, _ in sections}),
        beat_grid=grid,
        fixture_group=rig,
        initial_states=job.moving_heads.initial_states,
        failure_mode=job.moving_heads.reposition_fallback,
    )
    full = _encoded(sections, grid, rig, job)
    for gone in missing:
        present = tuple(fixture_id for fixture_id in full_ids if fixture_id != gone)
        subset = _encoded(
            sections, grid, _rig_of(present, full_ids, speed), _job_of(present, policy)
        )
        for fixture_id in present:
            assert subset[fixture_id] == full[fixture_id], (gone, fixture_id)


_WINGS = physical_template_doc(
    "vis_wings",
    [
        envelope_step(
            "w",
            0.0,
            40.0,
            lit=(0.0, 0.5),
            attack=0.5,
            distribution=[{"domains": ["pan", "tilt"], "wings": 2, "spread_cycles": 0.5}],
        )
    ],
    overlays=[overlay("gobo", 1.0, 4.0, 1.0, "dots")],
)
"""Mirrored wings lit over half of each head's own swing, the inner heads lagging, with a
gobo flick on beat 2 of every bar."""


def test_a_missing_head_leaves_every_other_heads_envelopes_and_overlays_unchanged() -> None:
    """Each head's lit window comes from its own canonical phase and the overlay splits
    each head's cues alone, so removing a head never changes another head's frames."""
    with registered_templates(_WINGS, _FLICK):
        _assert_subset_stable(
            (("vis_flick", 1, 1), ("vis_wings", 2, 4), ("vis_flick", 5, 5)),
            _grid(),
            heads=5,
            missing=("MH1", "MH3"),
            speed=180.0,
        )


def test_repeated_runs_encode_identical_frames() -> None:
    ids = ("MH1", "MH2", "MH3")
    rig, job = _rig_of(ids, ids, 180.0), _job_of(ids)
    sections = (("vis_wings", 1, 3), ("vis_flick", 4, 5))
    with registered_templates(_WINGS, _FLICK):
        assert _encoded(sections, _grid(), rig, job) == _encoded(sections, _grid(), rig, job)


_FUZZ_SEEDS = 400 if os.environ.get("TWINKLR_P24B_FUZZ") == "full" else 12
"""Seeds 0-11 catch an overlay or envelope applied only at render or only at the gate; 400
are swept in full."""
_FUZZ_KNOWN = (686, 21)
"""686 catches overlays applied to a HOLD_LAST_POSE remainder (the only one of 3,938 seeds);
21 catches a flick authored as a wheel change inside a cue (through the oracle)."""
_COLORS, _GOBOS = ("red", "blue"), ("dots", "star")


def _fuzz_step(rng: random.Random, step_id: str, start: float, duration: float) -> dict[str, Any]:
    """An envelope on a P2.3 shape (or P1's sine and linear), maybe distributed over pan and
    tilt (P2.2), maybe declaring a fallback."""
    shape = rng.choice(["sine_pan", "circle", "sweep", "linear"])
    period = rng.choice([2.0, 4.0])
    extent = round(rng.uniform(10.0, 50.0), 1)
    timing = {"start": start, "duration": duration}
    if shape == "sine_pan":
        step = sweep_step(step_id, 0.0, extent, period_beats=period, **timing)
        step["movement"]["physical"].update(shape="sine_pan", mode="periodic")
    elif shape == "linear":
        step = sweep_step(step_id, -extent / 2, extent, period_beats=period, **timing)
    else:
        transform = rng.choice([None, {"phase_cycles": 0.25}, {"reverse": True}])
        if shape == "sweep" and transform == {"reverse": True}:
            transform = None  # a periodic sweep refuses reverse
        step = path_step(
            step_id, shape, pan_extent=extent, period_beats=period, transform=transform, **timing
        )
    lit_start = rng.choice([0.0, 0.25, 0.5])
    lit_end = min(1.0, lit_start + rng.choice([0.25, 0.5]))
    release = rng.choice([0.0, 0.25])
    if shape == "linear" and lit_end == 1:
        release = 0.0  # a finite window ending at 1 stays lit through the hold
    step["dimmer"] = {}
    step["physical_visibility"] = {
        "visible_phase_start": lit_start,
        "visible_phase_end": lit_end,
        "attack_beats": rng.choice([0.0, 0.25]),
        "release_beats": release,
    }
    if rng.random() < 0.5:
        step["physical_distribution"] = [
            {
                "domains": ["pan", "tilt"],
                "spread_cycles": rng.choice([0.25, 0.5]),
                "wings": rng.choice([1, 2]),
            }
        ]
    fallback = rng.choice([None, "preserve_aim", "drop_accent"])
    if fallback is not None:
        step["physical_reposition_fallback"] = fallback
    return step


def _fuzz_doc(rng: random.Random, seed: int) -> TemplateDoc:
    """One or two envelope steps per one- or two-bar cycle, up to one overlay per wheel,
    and either remainder policy."""
    cycle = rng.choice([1.0, 2.0])
    if rng.random() < 0.6:
        steps = [_fuzz_step(rng, "a", 0.0, cycle)]
    else:
        half = cycle / 2
        steps = [_fuzz_step(rng, "a", 0.0, half), _fuzz_step(rng, "b", half, half)]
    overlays = []
    for channel, states in (("color", _COLORS), ("gobo", _GOBOS)):
        if rng.random() < 0.45:
            mask = rng.choice([0.25, 0.5])
            start = rng.choice([0.0, 0.5, 1.0, 1.5]) + (
                4.0 if cycle == 2 and rng.random() < 0.5 else 0.0
            )
            end = min(4 * cycle, start + 2 * mask + rng.choice([0.5, 1.0, 1.5]))
            overlays.append(overlay(channel, start, end, mask, rng.choice(states)))
    return physical_template_doc(
        f"vis_fuzz_{seed}",
        steps,
        cycle_bars=cycle,
        remainder_policy=rng.choice(["HOLD_LAST_POSE", "TRUNCATE"]),
        overlays=overlays,
    )


def _fuzz_grid(rng: random.Random, *, steady: bool) -> BeatGrid:
    """4-7 bars of four beats from 15 ms: one beat length throughout, or mostly 470-700 ms
    with an occasional fast beat."""
    if steady:
        return _grid(*[rng.choice([400.0, 500.0, 600.0])] * rng.randint(4, 7))
    beats = [15.0]
    for _ in range(4 * rng.randint(4, 7)):
        fast = rng.random() < 0.08
        beats.append(
            beats[-1] + rng.choice([320.0, 400.0] if fast else [470.0, 500.0, 610.0, 700.0])
        )
    return BeatGrid(
        bar_boundaries=beats[::4],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=beats[-1] + 15.0,
    )


def _reference_admits(template_id: str, grid: BeatGrid, rig: FixtureGroup, job: JobConfig) -> bool:
    """The whole song as one section from bar 1, as the render plays it, with no gate
    shortcut: compile, enter, plan."""
    from twinklr.core.sequencer.moving_heads.pipeline import _enter_section

    policy = job.moving_heads
    bars = sum(1 for bar in grid.bar_boundaries if bar < grid.duration_ms)
    pipeline = RenderingPipeline(
        choreography_plan=physical_sections((template_id, 1, bars)),
        beat_grid=grid,
        fixture_group=rig,
        job_config=job,
    )
    phase_map = build_musical_phase_map(grid)
    start, end = physical_cue_limits(phase_map, int(grid.duration_ms))
    profiles = {f.fixture_id: f.config.physical_profile for f in rig.expand_fixtures()}
    context = TemplateCompileContext(
        section_id="reference",
        template_id=template_id,
        fixtures=pipeline._build_fixture_contexts(),
        beat_grid=grid,
        start_bar=1,
        duration_bars=bars,
        presets=rig.presets,
        topology=rig_topology(rig),
        fixture_group_id=rig.group_id,
    )
    from twinklr.core.sequencer.moving_heads.templates import get_template

    try:
        compiled = compile_physical_template(
            get_template(template_id).template,
            context,
            phase_map=phase_map,
            start_limit_ms=start,
            end_limit_ms=end,
        )
    except (PhysicalCompileError, PhysicalChannelError, ValueError):
        return False
    cues, _, _ = _enter_section(
        compiled.segments,
        {},
        profiles,  # type: ignore[arg-type]
        policy.initial_states,
        section_start_ms=context.start_ms,
        phase_map=phase_map,
        failure_mode=policy.reposition_fallback,
    )
    result = plan_prepositions(
        cues,
        profiles,  # type: ignore[arg-type]
        initial_states=policy.initial_states,
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=len(frame_times(int(grid.duration_ms))) * EFFECT_GRID_MS,
        failure_mode=policy.reposition_fallback,
    )
    return not result.has_errors


def _fuzz_case(seed: int) -> bool:
    """One random template, grid, rig and policy. The gate admits exactly what the
    whole-song reference renders; an admitted template renders the whole song, and on a
    steady grid also split into sections of random lengths (remainders under either
    policy), honestly from its bytes, and a head removed
    leaves the others' frames unchanged. Returns whether it was admitted."""
    rng = random.Random(seed)
    document = _fuzz_doc(rng, seed)
    steady = rng.random() < 0.5
    grid = _fuzz_grid(rng, steady=steady)
    heads = rng.randint(2, 3)
    ids = tuple(f"MH{index}" for index in range(1, heads + 1))
    speed = rng.choice([90.0, 180.0, 720.0])
    policy = rng.choice(["error", "preserve_aim", "drop_accent"])
    rig, job = _rig_of(ids, ids, speed), _job_of(ids, policy)
    template_id = document.template.template_id
    bars = sum(1 for bar in grid.bar_boundaries if bar < grid.duration_ms)
    where = f"seed {seed}: {policy}, {speed} deg/s, {heads} heads, steady {steady}"
    with registered_templates(document):
        try:
            check_physical_templates(
                [template_id],
                beat_grid=grid,
                fixture_group=rig,
                initial_states=job.moving_heads.initial_states,
                failure_mode=job.moving_heads.reposition_fallback,
            )
            admitted = True
        except UnsupportedRenderModeError:
            admitted = False
        assert admitted == _reference_admits(template_id, grid, rig, job), where
        if not admitted:
            return False
        plans = [((template_id, 1, bars),)]
        if steady and bars >= 2:
            # Sections of random lengths, so most leave a remainder of the cycle.
            cuts = sorted(rng.sample(range(1, bars), min(bars - 1, rng.randint(1, 2))))
            bounds = [0, *cuts, bars]
            plans.append(tuple((template_id, first + 1, last) for first, last in pairwise(bounds)))
        for sections in plans:
            pipeline = RenderingPipeline(
                choreography_plan=physical_sections(*sections),
                beat_grid=grid,
                fixture_group=rig,
                job_config=job,
                output_path=None,
            )
            try:
                segments = pipeline.render()
            except (PhysicalRenderError, PhysicalChannelError) as error:
                raise AssertionError(
                    f"{where}: admitted, then {sections} failed: {error}"
                ) from error
            _check_bytes(pipeline, segments, rig, job)
        if heads == 3:
            _assert_subset_stable(
                plans[-1], grid, heads=3, missing=(rng.choice(ids),), speed=speed, policy=policy
            )
    return True


def test_gate_render_and_bytes_agree_over_envelopes_overlays_distributions_and_policies() -> None:
    """Random envelopes on every path shape, with and without distribution, overlays on
    either wheel and all three fallback policies, on variable and steady tempos: nothing
    the gate admits fails at render, every admitted render is honest from its bytes, and
    subsets are stable. Both verdicts must occur."""
    verdicts = {_fuzz_case(seed) for seed in (*_FUZZ_KNOWN, *range(_FUZZ_SEEDS))}
    assert verdicts == {True, False}


# --- Registry evidence -------------------------------------------------------------------


_COMPONENT_NOTES = {
    "rejected": "exact path's alternative is rejected by physical validation or compile",
    "compiled": "exact path changes the physical compile result",
}


def _evidence_payload() -> dict[str, Any]:
    """A fully lit envelope step with a gobo flick that names a rig preset, then a color
    flick; moving the preset flick onto the color wheel keeps them apart."""
    return physical_template_doc(
        "vis_evidence",
        [envelope_step("e", 0.0, 40.0, lit=(0.0, 1.0))],
        overlays=[
            overlay("color", 2.5, 3.75, 0.25, "blue"),
            overlay("gobo", 0.5, 2.5, 0.5, attribute_preset_id="wash"),
        ],
    ).model_dump(mode="json")


def _visibility(change: Callable[[dict[str, Any]], Any]) -> Callable[[dict[str, Any]], Any]:
    return lambda doc: change(doc["template"]["steps"][0]["physical_visibility"])


def _overlay(
    index: int, change: Callable[[dict[str, Any]], Any]
) -> Callable[[dict[str, Any]], Any]:
    return lambda doc: change(doc["template"]["physical_overlays"][index])


_STEP = "template.template.steps.physical_visibility"
_OVERLAYS = "template.template.physical_overlays"
_MUTATIONS: dict[str, tuple[str, Callable[[dict[str, Any]], Any]]] = {
    _STEP: ("compiled", lambda doc: doc["template"]["steps"][0].pop("physical_visibility")),
    f"{_STEP}.visible_phase_start": (
        "compiled",
        _visibility(lambda v: v.update(visible_phase_start=0.125)),
    ),
    f"{_STEP}.visible_phase_end": (
        "compiled",
        _visibility(lambda v: v.update(visible_phase_end=0.75)),
    ),
    f"{_STEP}.attack_beats": ("compiled", _visibility(lambda v: v.update(attack_beats=0.5))),
    f"{_STEP}.release_beats": ("compiled", _visibility(lambda v: v.update(release_beats=0.5))),
    f"{_STEP}.level": ("compiled", _visibility(lambda v: v.update(level=0.5))),
    _OVERLAYS: ("compiled", lambda doc: doc["template"].pop("physical_overlays")),
    f"{_OVERLAYS}.start_beats": ("compiled", _overlay(0, lambda o: o.update(start_beats=0.5))),
    f"{_OVERLAYS}.end_beats": ("compiled", _overlay(0, lambda o: o.update(end_beats=3.5))),
    f"{_OVERLAYS}.mask_beats": ("compiled", _overlay(1, lambda o: o.update(mask_beats=0.25))),
    f"{_OVERLAYS}.channel": ("compiled", _overlay(1, lambda o: o.update(channel="color"))),
    f"{_OVERLAYS}.state": ("compiled", _overlay(0, lambda o: o.update(state="red"))),
    f"{_OVERLAYS}.attribute_preset_id": (
        "compiled",
        _overlay(1, lambda o: o.update(attribute_preset_id="wash_all")),
    ),
    f"{_OVERLAYS}.release": ("rejected", _overlay(0, lambda o: o.update(release="hold"))),
}
"""Per config path: the component its alternative must change, and that alternative."""

VISIBILITY_PATHS = tuple(
    path
    for path, disposition in CONFIG_EFFECTS.items()
    if disposition.kind is ConfigDispositionKind.EFFECT_TEST
    and disposition.test_nodeid is not None
    and "::test_visibility_field_changes_compile[" in disposition.test_nodeid
)


def _evidence_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        template = TemplateDoc.model_validate(payload).template
        segments = _compile(template, physical_preset_rig())
    except (ValidationError, PhysicalCompileError, PhysicalChannelError) as error:
        return {"rejected": f"{type(error).__name__}: {error}"}
    return {"compiled": [s.model_dump(mode="json", exclude={"metadata"}) for s in segments]}


def test_visibility_evidence_paths_cover_every_mutation() -> None:
    assert set(VISIBILITY_PATHS) == set(_MUTATIONS)
    for path, (component, _) in _MUTATIONS.items():
        assert CONFIG_EFFECTS[path].note == _COMPONENT_NOTES[component], path


@pytest.mark.parametrize("config_path", VISIBILITY_PATHS, ids=VISIBILITY_PATHS)
def test_visibility_field_changes_compile(config_path: str) -> None:
    """Each envelope and overlay path changes the compiled cues, or is refused."""
    component, mutate = _MUTATIONS[config_path]
    payload = _evidence_payload()
    mutate(payload)
    base, changed = _evidence_snapshot(_evidence_payload()), _evidence_snapshot(payload)
    assert "rejected" not in base, base
    if component == "rejected":
        assert "rejected" in changed, changed
        return
    assert "rejected" not in changed, changed
    assert changed["compiled"] != base["compiled"]


_OPEN_STATE_ROOTS = {
    "fixture.fixtures[FixtureInstance].config.physical_profile.discrete.open_state": "instance",
    "fixture.base_config.physical_profile.discrete.open_state": "base_config",
}


def _open_state_rig(root: str, open_state: str) -> FixtureGroup:
    """`physical_rig` with a `strobe` shutter state and `open_state`, its profile on each
    fixture's config or on the group's shared base config."""
    payload = physical_rig().model_dump(mode="json")
    profile = payload["fixtures"][0]["config"]["physical_profile"]
    _strobe(profile)
    profile["discrete"]["shutter"]["open_state"] = open_state
    if root == "instance":
        for fixture in payload["fixtures"]:
            fixture["config"]["physical_profile"] = copy.deepcopy(profile)
        return FixtureGroup.model_validate(payload)
    base = {
        key: value
        for key, value in payload["fixtures"][0]["config"].items()
        if key not in {"fixture_id", "position"}
    }
    payload["base_config"] = base
    payload["fixtures"] = [
        {"fixture_id": f["fixture_id"], "xlights_model_name": f["xlights_model_name"]}
        for f in payload["fixtures"]
    ]
    return FixtureGroup.model_validate(payload)


@pytest.mark.parametrize("config_path", sorted(_OPEN_STATE_ROOTS), ids=sorted(_OPEN_STATE_ROOTS))
def test_open_state_changes_the_lit_shutter(config_path: str) -> None:
    """An envelope step without a static shutter state is lit through the profile's
    `open_state`: changing it changes every lit slice's shutter."""
    assert CONFIG_EFFECTS[config_path].test_nodeid.endswith(
        f"::test_open_state_changes_the_lit_shutter[{config_path}]"
    )
    step = envelope_step("s", 0.0, 60.0, lit=(0.0, 0.25))
    step.pop("physical_shutter_state")
    template = physical_template_doc("vis_open_state", [step]).template
    root = _OPEN_STATE_ROOTS[config_path]
    shutters = {
        state: {
            s
            for c in _compile(template, _open_state_rig(root, state))
            for s in _state(c, ChannelName.SHUTTER)
        }
        for state in ("open", "strobe")
    }
    assert shutters == {"open": {"open"}, "strobe": {"strobe"}}
