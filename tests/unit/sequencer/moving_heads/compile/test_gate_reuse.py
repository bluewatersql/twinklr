"""The pre-planning gate's reuse and exact shortcuts never change what it or the render decides.

The gate time cut (Phase 3) reuses work where the inputs are the same: a step instance's
sampled channels across heads that share a channel's phase (`compile_step`'s
`shared`), the rest of a fixture's plan from a cue an earlier section entry reached in
the same state (`plan_prepositions`' `memo`), and plan groups keyed only for heads alike
in their cheap features (`_plan_groups`); and it evaluates paths, pulses, DMX words and
head motion in integers instead of fractions. Each test compares with the same work done
without the shortcut (or with the fraction formula), on inputs built so that a key missing
an input would return a stale value; a reuse test also checks that the reuse happened, so
its equality is not vacuous. Synthetic inputs only.
"""

from __future__ import annotations

from fractions import Fraction
import gc
import math
import random
from typing import Any
import weakref

import pytest

from tests.support.moving_heads import (
    FAMILY_IDS,
    bars_grid,
    family_catalog,
    family_job,
    family_rig,
    fixture_segment,
    loop_template_doc,
    p1_grid,
    path_step,
    preposition_profile_payload,
    topology_payload,
    topology_rig,
    zoom_pilot_profile_payload,
)
from twinklr.core.config.fixtures import (
    AxisCapability,
    FixtureCapabilities,
    FixtureGroup,
    InitialFixtureState,
)
from twinklr.core.config.fixtures.presets import PoseDegrees
from twinklr.core.sequencer.models.context import TemplateCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalChannelError,
    PhysicalPoint,
    RenderLock,
    check_physical_value,
)
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.models.moving_heads.topology import resolve_distribution, rig_topology
from twinklr.core.sequencer.models.template import (
    Movement,
    PulseSpec,
    Template,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile import preposition, template_compiler
from twinklr.core.sequencer.moving_heads.compile import step as step_module
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    FALLBACK_METADATA_KEY,
    PrepositionMemo,
    PrepositionResult,
    plan_prepositions,
)
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
from twinklr.core.sequencer.moving_heads.pipeline import (
    TemplateAdmission,
    _plan_groups,
    _plan_key,
    admit_templates,
    cue_limits,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import (
    build_musical_phase_map,
    musical_phase_fraction,
)

_PAN, _TILT, _DIMMER, _ZOOM = (
    ChannelName.PAN,
    ChannelName.TILT,
    ChannelName.DIMMER,
    ChannelName.ZOOM,
)
_SHUTTER, _COLOR = ChannelName.SHUTTER, ChannelName.COLOR
_IDS = ("MH1", "MH2", "MH3", "MH4")


# --- Channels shared across heads -----------------------------------------------------


_WINGS = [
    {"domains": ["pan"], "wings": 2, "spread_cycles": 0.5},
    {"domains": ["tilt"], "wings": 2, "spread_cycles": 0.25},
]
"""Pan over two mirrored wings, tilt over two wings on another phase: MH1/MH4 share
their tilt, and MH2/MH3's tilt phase is not their pan phase."""


def _wings_template(*, zoom: bool = False, dimmer_spread: float | None = None) -> Template:
    """A circle on `_WINGS` whose dimmer pulses on one phase for all heads (or spread
    `dimmer_spread` cycles over the rig), and, with `zoom`, a zoom wave on each head's
    pan phase."""
    fields: dict[str, Any] = {}
    if zoom:
        fields["zoom"] = {"shape": "sine", "start_deg": 25.0, "extent_deg": 10.0}
    distribution = list(_WINGS)
    if dimmer_spread is not None:
        distribution.append({"domains": ["dimmer"], "spread_cycles": dimmer_spread})
    step = path_step(
        "wings",
        "circle",
        pan_extent=20.0,
        tilt_extent=10.0,
        period_beats=2.0,
        dimmer={"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0},
        distribution=distribution,
        **fields,
    )
    return loop_template_doc("reuse_wings", [step], cycle_bars=1.0).template


def _mixed_rig(edit_mh3: Any, *, zoom: bool = False) -> FixtureGroup:
    """Four heads on one profile (the zoom pilot's with `zoom`) but MH3, which `edit_mh3`
    changes."""
    payload = topology_rig(_IDS, topology=topology_payload(_IDS)).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        if zoom:
            fixture["config"]["physical_profile"] = zoom_pilot_profile_payload()
        if fixture["fixture_id"] == "MH3":
            edit_mh3(fixture["config"]["physical_profile"])
    return FixtureGroup.model_validate(payload)


def _compile(template: Template, rig: FixtureGroup) -> list[FixtureSegment]:
    grid = p1_grid()
    phase_map = build_musical_phase_map(grid)
    context = TemplateCompileContext(
        section_id="verse",
        template_id=template.template_id,
        fixtures=build_fixture_contexts(rig_profile_from_fixture_group(rig), rig),
        beat_grid=grid,
        start_bar=1,
        duration_bars=3,
        presets=rig.presets,
        topology=rig_topology(rig),
        fixture_group_id=rig.group_id,
    )
    start_limit, end_limit = cue_limits(phase_map, int(grid.duration_ms))
    segments: list[FixtureSegment] = template_compiler.compile_template(
        template, context, phase_map=phase_map, start_limit_ms=start_limit, end_limit_ms=end_limit
    ).segments
    return segments


def _compile_unshared(
    template: Template, rig: FixtureGroup, monkeypatch: pytest.MonkeyPatch
) -> list[FixtureSegment]:
    """`_compile` with every head's channels made by its own compile."""

    def alone(*args: Any, shared: Any = None, **kwargs: Any) -> FixtureSegment:
        return step_module.compile_step(*args, **kwargs)

    with monkeypatch.context() as patched:
        patched.setattr(template_compiler, "compile_step", alone)
        segments: list[FixtureSegment] = _compile(template, rig)
    return segments


def _invert_pan(profile: dict[str, Any]) -> None:
    profile["axes"]["pan"]["inverted"] = not profile["axes"]["pan"].get("inverted", False)


@pytest.mark.parametrize("zoom", [False, True], ids=["zoomless", "zoom"])
def test_shared_channels_are_each_heads_own_on_every_profile(
    zoom: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every head's cues equal its own compile's, MH3 on another profile included; heads
    alike in a channel's phase hold that channel's very trajectory; and each head's pan,
    tilt and zoom are the path at that channel's own phase."""
    template, rig = _wings_template(zoom=zoom), _mixed_rig(_invert_pan, zoom=zoom)
    shared = _compile(template, rig)
    alone = _compile_unshared(template, rig, monkeypatch)

    assert [s.model_dump(mode="json") for s in shared] == [s.model_dump(mode="json") for s in alone]
    first: dict[str, FixtureSegment] = {}
    for segment in shared:
        first.setdefault(segment.fixture_id, segment)
    mh1, mh2, mh3, mh4 = (first[fixture_id] for fixture_id in _IDS)
    # The wings mirror MH1/MH4: pan differs, tilt is one object, as is every dimmer.
    assert mh1.channels[_PAN].physical != mh4.channels[_PAN].physical
    assert mh1.channels[_TILT].physical is mh4.channels[_TILT].physical
    assert mh1.channels[_DIMMER].physical is mh2.channels[_DIMMER].physical
    # MH3's profile differs, so it holds its own channels, equal in value to MH2's tilt.
    assert mh3.channels[_TILT].physical is not mh2.channels[_TILT].physical
    assert mh3.channels[_TILT].physical == mh2.channels[_TILT].physical
    # Each channel at its own phase: pan and zoom at the pan phase, tilt at the tilt one.
    distribution = resolve_distribution(rig_topology(rig), template.steps[0].distribution, _IDS)
    movement = template.steps[0].movement
    assert movement is not None
    pose = PoseDegrees(pan_deg=0.0, tilt_deg=0.0)
    phase_map = build_musical_phase_map(p1_grid())
    for segment in (mh1, mh2):
        phases = distribution[segment.fixture_id]
        channels = [_PAN, _TILT, *([_ZOOM] if zoom else [])]
        for channel in channels:
            trajectory = segment.channels[channel].physical
            assert isinstance(trajectory, ContinuousTrajectory)
            domain = _TILT if channel is _TILT else _PAN
            for point in trajectory.points[::7]:
                phase = (
                    musical_phase_fraction(
                        phase_map, point.t_ms, origin_ms=segment.t0_ms, period_beats=2.0
                    )
                    - phases.phase_by_channel[domain]
                )
                if channel is _ZOOM:
                    expected = 25.0 + 10.0 * math.sin(2 * math.pi * float(phase))
                else:
                    at = step_module.evaluate_path(
                        movement, pose, phase.numerator, phase.denominator, phases.pan_sign
                    )
                    expected = at[0] if channel is _PAN else at[1]
                assert point.value == expected, (segment.fixture_id, channel, point.t_ms)


def test_a_head_whose_profile_refuses_a_shared_channel_is_still_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MH3 allows less tilt than the path reaches: its compile refuses it, naming MH3, as
    a compile without sharing does, though MH2 made the same tilt trajectory first."""

    def narrow_tilt(profile: dict[str, Any]) -> None:
        profile["axes"]["tilt"]["allowed_max"] = 5.0

    template, rig = _wings_template(), _mixed_rig(narrow_tilt)
    with pytest.raises(PhysicalChannelError) as shared:
        _compile(template, rig)
    with pytest.raises(PhysicalChannelError) as alone:
        _compile_unshared(template, rig, monkeypatch)
    assert shared.value.fixture_id == "MH3"
    assert str(shared.value) == str(alone.value)
    assert shared.value.__notes__ == alone.value.__notes__


def test_heads_on_distinct_dimmer_phases_each_pulse_on_their_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dimmer pulse spread over four heads on one profile: every head's cues equal its
    own compile's, and no two heads hold the same dimmer."""
    template = _wings_template(dimmer_spread=0.5)
    rig = topology_rig(_IDS, topology=topology_payload(_IDS))
    shared = _compile(template, rig)

    assert [s.model_dump(mode="json") for s in shared] == [
        s.model_dump(mode="json") for s in _compile_unshared(template, rig, monkeypatch)
    ]
    first: dict[str, FixtureSegment] = {}
    for segment in shared:
        first.setdefault(segment.fixture_id, segment)
    dimmers = [first[fixture_id].channels[_DIMMER].physical for fixture_id in _IDS]
    assert all(a != b for i, a in enumerate(dimmers) for b in dimmers[i + 1 :])


# --- The planner's memo ----------------------------------------------------------------


def _profile(
    *, red_settle_ms: int = 0, close_latency_ms: int = 0, **pan: Any
) -> FixtureCapabilities:
    payload = preposition_profile_payload()
    payload["axes"]["pan"].update(pan)
    payload["discrete"]["color"]["states"]["red"]["settle_ms"] = red_settle_ms
    payload["visibility"]["close_latency_ms"] = close_latency_ms
    return FixtureCapabilities.model_validate(payload)


def _cue(
    name: str,
    t0: int,
    t1: int,
    pan: tuple[float, float],
    colors: tuple[tuple[int, str], ...] | None = None,
) -> FixtureSegment:
    """A lit cue panning linearly between `pan` over its span, white unless `colors`."""
    trajectories = {
        _PAN: ContinuousTrajectory(
            unit="degree",
            points=(PhysicalPoint(t_ms=t0, value=pan[0]), PhysicalPoint(t_ms=t1, value=pan[1])),
            interpolation="linear",
        ),
        _TILT: ContinuousTrajectory(
            unit="degree",
            points=(PhysicalPoint(t_ms=t0, value=0.0), PhysicalPoint(t_ms=t1, value=0.0)),
            interpolation="linear",
        ),
        _DIMMER: ContinuousTrajectory(
            unit="normalized", points=(PhysicalPoint(t_ms=t0, value=1.0),), interpolation="hold"
        ),
        _SHUTTER: DiscreteTrajectory(events=(DiscretePoint(t_ms=t0, state="open"),)),
        _COLOR: DiscreteTrajectory(
            events=tuple(
                DiscretePoint(t_ms=t, state=state) for t, state in colors or ((t0, "white"),)
            )
        ),
    }
    return fixture_segment(trajectories, t0_ms=t0, t1_ms=t1, segment_id=name, section_id=name)


_CUES = (
    _cue("a", 1000, 2000, (0.0, 40.0)),
    _cue("b", 2000, 3000, (40.0, 0.0)),  # continues a
    _cue("c", 4000, 5000, (90.0, 90.0)),  # a dark move of 90° first
    _cue("d", 6000, 7000, (-30.0, 30.0)),
)


def _initial(pan: float, color: str = "white", *, dark: bool = True) -> InitialFixtureState:
    """A settled head at `pan`, dimmer zero and shutter closed, evidenced dark or not."""
    return InitialFixtureState.model_validate(
        {
            "pan_deg": pan,
            "tilt_deg": 0.0,
            "dimmer": 0.0,
            "discrete_states": {"shutter": "closed", "color": color},
            "settled": True,
            "dark": dark,
        }
    )


def _plan(
    cues: tuple[FixtureSegment, ...],
    profile: FixtureCapabilities,
    initial: InitialFixtureState,
    memo: PrepositionMemo | None,
    *,
    end_ms: int = 8000,
    locks: tuple[RenderLock, ...] = (),
    **policy: Any,
) -> PrepositionResult:
    """Plan MH1's `cues`; `policy` is `failure_mode` and `on_unplayable`."""
    return plan_prepositions(
        list(cues),
        {"MH1": profile},
        initial_states={"MH1": initial},
        locks=locks,
        frame_ms=20,
        sequence_end_ms=end_ms,
        memo=memo,
        **policy,
    )


def _counting_follows(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Count the planner's cue follows (`_end_state`)."""
    calls = [0]
    end_state = preposition._FixturePlanner._end_state

    def counted(self: Any, *args: Any) -> Any:
        calls[0] += 1
        return end_state(self, *args)

    monkeypatch.setattr(preposition._FixturePlanner, "_end_state", counted)
    return calls


def test_a_later_entry_reuses_the_rest_of_an_earlier_plan_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entered at its second cue from a dark head already at its pose, the plan rejoins
    the song-start plan's state by the third cue and reuses the rest; its result is the
    one planned without the memo."""
    profile = _profile(travel_speed_per_s=360.0, settle_ms=40)
    fresh = _plan(_CUES[1:], profile, _initial(40.0), None)
    memo: PrepositionMemo = {}
    _plan(_CUES, profile, _initial(0.0), memo)
    calls = _counting_follows(monkeypatch)
    reused = _plan(_CUES[1:], profile, _initial(40.0), memo)

    assert reused == fresh
    assert not reused.has_errors
    assert calls[0] < len(_CUES) - 1  # the cues after the rejoin were not followed again


@pytest.mark.parametrize(
    ("change", "value"),
    [
        pytest.param("profile", _profile(travel_speed_per_s=60.0, settle_ms=40), id="slow_profile"),
        pytest.param("profile", _profile(travel_speed_per_s=360.0, settle_ms=400), id="settle"),
        pytest.param("end_ms", 9000, id="sequence_end"),
        pytest.param(
            "locks",
            (RenderLock(start_ms=3000, end_ms=4000, fixture_ids=("MH1",), channels=(_PAN,)),),
            id="lock",
        ),
    ],
)
def test_the_memo_never_reuses_a_plan_made_with_another_profile_or_end(
    change: str, value: Any
) -> None:
    """The same cue objects planned on another profile, to another end, or with a lock on
    the pan over cue c's dark move, after the memo holds their plan: each result is its
    own memo-free plan, and differs from the one in the memo (a stale reuse would return
    that)."""
    profile = _profile(travel_speed_per_s=360.0, settle_ms=40)
    memo: PrepositionMemo = {}
    remembered = _plan(_CUES, profile, _initial(0.0), memo)
    kwargs: dict[str, Any] = {} if change == "profile" else {change: value}
    other = value if change == "profile" else profile
    with_memo = _plan(_CUES, other, _initial(0.0), memo, **kwargs)
    fresh = _plan(_CUES, other, _initial(0.0), None, **kwargs)

    assert with_memo == fresh
    assert fresh != remembered


@pytest.mark.parametrize(
    ("reach", "red_settle_ms"),
    [pytest.param(120.0, 0, id="head_trails"), pytest.param(90.0, 500, id="wheel_settles")],
)
def test_motion_or_a_wheel_still_settling_at_a_cue_is_planned_again(
    reach: float, red_settle_ms: int
) -> None:
    """From the song start the head pans `reach` degrees over cue v at 100°/s (trailing it
    at 120°) and its color turns red late in v, so the pan or the wheel is still settling
    while cues w and x hold the pose; entered at w, from a head already there, nothing
    is. Cue y waits for what still settles after x, so the entries differ there; with a
    memo each is its memo-free plan."""
    profile = _profile(travel_speed_per_s=100.0, settle_ms=40, red_settle_ms=red_settle_ms)
    last = reach * 980 / 1000  # v's pan on its last frame
    v = _cue("v", 1000, 2000, (0.0, reach), colors=((1000, "white"), (1940, "red")))
    w = _cue("w", 2000, 2100, (last, last), colors=((2000, "red"),))
    x = _cue("x", 2100, 2200, (last, last), colors=((2100, "red"),))
    y = _cue("y", 2600, 3600, (last, last), colors=((2600, "red"),))
    memo: PrepositionMemo = {}
    song = _plan((v, w, x, y), profile, _initial(0.0), memo)
    entered = _plan((w, x, y), profile, _initial(last, "red"), memo)

    assert song == _plan((v, w, x, y), profile, _initial(0.0), None)
    assert entered == _plan((w, x, y), profile, _initial(last, "red"), None)
    assert not song.has_errors and not entered.has_errors
    at_y = [[d.reason for d in plan.diagnostics if d.cue_ms == 2600] for plan in (song, entered)]
    assert at_y[0] != at_y[1]  # the rest of the song-start plan is not the entry's


@pytest.mark.parametrize(
    "later",
    [
        pytest.param((), id="fewer_cues"),
        pytest.param((_cue("d2", 6000, 7000, (30.0, -30.0)),), id="another_last_cue"),
    ],
)
def test_a_plan_whose_later_cues_differ_is_never_given_an_earlier_plans_rest(
    later: tuple[FixtureSegment, ...],
) -> None:
    """The head reaches cue c in the same state planning a to d and planning b, c and
    then nothing or another cue: each later plan is its own memo-free plan."""
    profile = _profile(travel_speed_per_s=360.0, settle_ms=40)
    memo: PrepositionMemo = {}
    _plan(_CUES, profile, _initial(0.0), memo)
    cues = (*_CUES[1:3], *later)
    assert _plan(cues, profile, _initial(40.0), memo) == _plan(cues, profile, _initial(40.0), None)


def test_every_entry_with_a_memo_is_its_memo_free_plan() -> None:
    """Every suffix of the cues from several dark starting poses, on a slow head with a
    long settle, planned with one memo in turn."""
    profile = _profile(travel_speed_per_s=90.0, settle_ms=900)
    memo: PrepositionMemo = {}
    for start in range(len(_CUES)):
        for pan in (0.0, 40.0, -60.0):
            cues = _CUES[start:]
            assert _plan(cues, profile, _initial(pan), memo) == _plan(
                cues, profile, _initial(pan), None
            )


_Run = tuple[tuple[FixtureSegment, ...], InitialFixtureState, dict[str, Any]]
"""Cues, initial state and policy (`failure_mode`, `on_unplayable`) of one plan."""


def _each_its_own(profile: FixtureCapabilities, *runs: _Run) -> list[PrepositionResult]:
    """Plan `runs` in turn with one memo; each must be its memo-free plan."""
    memo: PrepositionMemo = {}
    results = []
    for cues, initial, policy in runs:
        result = _plan(cues, profile, initial, memo, **policy)
        assert result == _plan(cues, profile, initial, None, **policy)
        results.append(result)
    return results


def test_a_head_known_dark_is_never_given_the_plan_of_one_that_is_not() -> None:
    """Two initial states with the same pose, dimmer zero and shutter closed, one evidenced
    dark: it moves for cue x at once, the other waits out the 60 ms close latency first.
    Each state reaches x alike in everything but that evidence."""
    profile = _profile(travel_speed_per_s=360.0, close_latency_ms=60)
    x = _cue("x", 1000, 1200, (90.0, 90.0))
    dark, lit = _each_its_own(
        profile, ((x,), _initial(0.0), {}), ((x,), _initial(0.0, dark=False), {})
    )

    assert [d.reason for d in dark.diagnostics] != [d.reason for d in lit.diagnostics]


def test_a_cue_reached_from_another_predecessor_reports_its_own_source() -> None:
    """Cues s1 and s2 differ only in their section: the head reaches cue x in the same
    state after either, and x's dependency names the section it came from."""
    profile = _profile(travel_speed_per_s=360.0)
    s1 = _cue("s1", 1000, 2000, (0.0, 0.0))
    s2 = s1.model_copy(update={"section_id": "other"})
    x = _cue("x", 3000, 4000, (40.0, 40.0))
    after_s1, after_s2 = _each_its_own(
        profile, ((s1, x), _initial(0.0), {}), ((s2, x), _initial(0.0), {})
    )

    sources = [
        [d.source_section_id for d in plan.dependencies if d.target_section_id == "x"]
        for plan in (after_s1, after_s2)
    ]
    assert sources == [["s1"], ["other"]]


def test_a_cue_after_a_substitution_is_never_given_the_plan_after_the_cue_itself() -> None:
    """Cue p cannot reach 180° and is played as `preserve_aim`; cue q right after it moves
    half a degree, which may continue a cue played as authored but not a substitution.
    The cue p was played as (planned again, as authored) leaves the head in the same
    state but for that substitution."""
    profile = _profile(travel_speed_per_s=360.0)
    p = _cue("p", 100, 1000, (180.0, 180.0))
    q = _cue("q", 1000, 2000, (0.5, 0.5))
    for cue in (p, q):
        cue.metadata[FALLBACK_METADATA_KEY] = "preserve_aim"
    policy: dict[str, Any] = {"failure_mode": "preserve_aim"}
    played = _plan((p, q), profile, _initial(0.0), None, **policy)
    held = next(s for s in played.segments if s.segment_id == "p" and s.t0_ms == p.t0_ms)
    substituted, authored = _each_its_own(
        profile, ((p, q), _initial(0.0), policy), ((held, q), _initial(0.0), policy)
    )

    statuses = [[d.status for d in plan.diagnostics] for plan in (substituted, authored)]
    assert statuses == [["preserve_aim", "preserve_aim"], ["feasible", "feasible"]]


def test_motion_settling_within_a_frame_of_a_cue_end_is_planned_again() -> None:
    """From the song start the pan settles under 1 ms after one-frame cue w ends, so cue x
    waits a frame; entered at w, from a head already there, it waits for nothing."""
    profile = _profile(travel_speed_per_s=100.0, settle_ms=39)
    last = 10.0 * 980 / 1000  # v's pan on its last frame
    v = _cue("v", 1000, 2000, (0.0, 10.0))
    w = _cue("w", 2000, 2020, (last, last))
    x = _cue("x", 2600, 3600, (last, last))
    song, entered = _each_its_own(
        profile, ((v, w, x), _initial(0.0), {}), ((w, x), _initial(last), {})
    )

    at_x = [
        [d.required_ms for d in plan.diagnostics if d.cue_ms == 2600] for plan in (song, entered)
    ]
    assert at_x == [[20], [0]]


def test_a_replan_with_cues_kept_dark_is_never_given_the_plan_it_replaces() -> None:
    """Under `on_unplayable="dark"`, cue b closes the shutter for one frame, less than the
    60 ms close latency: the fixture is replanned with b kept dark, and then c, and the
    result has no error, as without a memo."""
    profile = _profile(close_latency_ms=60)
    a = _cue("a", 1000, 1100, (0.0, 0.0))
    b = _cue("b", 1100, 1120, (0.0, 0.0))
    b.channels[_SHUTTER] = ChannelValue(
        channel=_SHUTTER,
        physical=DiscreteTrajectory(events=(DiscretePoint(t_ms=1100, state="closed"),)),
    )
    c = _cue("c", 1120, 1300, (0.0, 0.0))
    (replanned,) = _each_its_own(profile, ((a, b, c), _initial(0.0), {"on_unplayable": "dark"}))

    assert not replanned.has_errors
    assert [record["start_ms"] for record in replanned.unplayable] == [1100, 1120]


@pytest.mark.parametrize(
    "policy",
    [
        pytest.param({"failure_mode": "drop_accent"}, id="failure_mode"),
        pytest.param({"on_unplayable": "dark"}, id="on_unplayable"),
    ],
)
def test_the_memo_never_reuses_a_plan_made_under_another_policy(policy: dict[str, Any]) -> None:
    """Cue `far` cannot be reached in time: kept dark under `policy`, refused by default.
    Planned under `policy` (a plan the memo keeps), then by default, with one memo, each
    is its own plan."""
    profile = _profile(travel_speed_per_s=90.0)
    far = _cue("far", 200, 1000, (180.0, 180.0))
    far.metadata[FALLBACK_METADATA_KEY] = "drop_accent"
    kept_dark, refused = _each_its_own(
        profile, ((far,), _initial(0.0), policy), ((far,), _initial(0.0), {})
    )

    assert not kept_dark.has_errors and refused.has_errors


def test_the_memo_keeps_every_profile_it_was_filled_with() -> None:
    """The memo knows a profile by its identity, so it holds the profile: one made after
    another is dropped never takes the dropped one's identity, and its plans."""
    memo: PrepositionMemo = {}
    fast = _profile(travel_speed_per_s=360.0, settle_ms=40)
    _plan(_CUES, fast, _initial(0.0), memo)
    kept = weakref.ref(fast)
    del fast
    gc.collect()

    assert kept() is not None
    slow = _profile(travel_speed_per_s=60.0, settle_ms=40)
    assert _plan(_CUES, slow, _initial(0.0), memo) == _plan(_CUES, slow, _initial(0.0), None)


def _counting_reuses(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Count the cues at which a plan took the rest of an earlier plan."""
    hits = [0]
    continues = preposition._Reached.continues

    def counted(self: Any, *args: Any) -> bool:
        reused: bool = continues(self, *args)
        hits[0] += reused
        return reused

    monkeypatch.setattr(preposition._Reached, "continues", counted)
    return hits


def _random_profile(rng: random.Random) -> FixtureCapabilities:
    """Random pan/tilt speed, latency and settle, 8-bit or inverted axes, wheel settles,
    close and open latencies, and sometimes a shutter-only visibility."""
    payload = preposition_profile_payload()
    for name in ("pan", "tilt"):
        axis = payload["axes"][name]
        axis["travel_speed_per_s"] = rng.choice([45.0, 90.0, 333.0, 720.0])
        axis["latency_ms"] = rng.choice([0, 0, 13, 45])
        axis["settle_ms"] = rng.choice([0, 40, 250, 900])
        if rng.random() < 0.2:
            axis.pop("fine_offset")
        if rng.random() < 0.2:
            axis["inverted"] = True
    for state in payload["discrete"]["color"]["states"].values():
        state["settle_ms"] = rng.choice([0, 30, 300, 700])
    visibility = payload["visibility"]
    visibility["close_latency_ms"] = rng.choice([0, 20, 60])
    visibility["open_latency_ms"] = rng.choice([0, 20])
    if rng.random() < 0.25:
        visibility["dimmer_zero_extinguishes"] = False
        payload["discrete"]["shutter"]["states"]["closed"]["settle_ms"] = rng.choice([0, 30])
    return FixtureCapabilities.model_validate(payload)


def _random_initial(rng: random.Random) -> InitialFixtureState:
    """A random settled state, dark four times in five, else lit or not."""
    dark = rng.random() < 0.8
    return InitialFixtureState.model_validate(
        {
            "pan_deg": rng.choice([0.0, 40.0, -60.0, rng.uniform(-200, 200)]),
            "tilt_deg": rng.choice([0.0, 20.0]),
            "dimmer": 0.0 if dark or rng.random() < 0.5 else 1.0,
            "discrete_states": {
                "shutter": "closed" if dark else rng.choice(["open", "closed"]),
                "color": rng.choice(["white", "red"]),
            },
            "settled": True,
            "dark": dark,
        }
    )


def _random_cues(rng: random.Random) -> list[FixtureSegment]:
    """Two to nine cues, often adjacent, with random pans held or ramped, dimmer levels
    (dark at zero), shutter states, a late color change and fallback metadata."""
    cues: list[FixtureSegment] = []
    t = rng.choice([0, 0, 20, 400])
    for index in range(rng.randint(2, 9)):
        if not (rng.random() < 0.6 and cues):
            t += 20 * rng.randint(1, 60)
        duration = 20 * rng.randint(1, 60)
        t0, t1 = t, t + duration
        count = rng.randint(1, 4)
        times = sorted({t0, *(t0 + 20 * rng.randint(0, duration // 20) for _ in range(count))})
        pan = tuple(
            PhysicalPoint(
                t_ms=time_ms,
                value=rng.choice([0.0, 40.0, 90.0, -30.0, rng.uniform(-260, 260)]),
            )
            for time_ms in times
        )
        tilt = (PhysicalPoint(t_ms=t0, value=rng.choice([0.0, 30.0])),)
        level = rng.choice([1.0, 1.0, 0.0, 0.5])
        colors = [(t0, rng.choice(["white", "red"]))]
        if rng.random() < 0.3 and duration > 40:
            later = t0 + 20 * rng.randint(1, duration // 20 - 1)
            colors.append((later, rng.choice(["white", "red"])))
        trajectories = {
            _PAN: ContinuousTrajectory(
                unit="degree", points=pan, interpolation=rng.choice(["linear", "hold"])
            ),
            _TILT: ContinuousTrajectory(unit="degree", points=tilt, interpolation="hold"),
            _DIMMER: ContinuousTrajectory(
                unit="normalized",
                points=(PhysicalPoint(t_ms=t0, value=level),),
                interpolation="hold",
            ),
            _SHUTTER: DiscreteTrajectory(
                events=(DiscretePoint(t_ms=t0, state=rng.choice(["open", "open", "closed"])),)
            ),
            _COLOR: DiscreteTrajectory(
                events=tuple(DiscretePoint(t_ms=at, state=state) for at, state in colors)
            ),
        }
        cue = fixture_segment(
            trajectories,
            t0_ms=t0,
            t1_ms=t1,
            segment_id=f"c{index}",
            section_id=f"s{index % 3}",
        )
        if rng.random() < 0.5:
            cue.metadata[FALLBACK_METADATA_KEY] = rng.choice(["preserve_aim", "drop_accent"])
        cues.append(cue)
        t = t1
    return cues


def _outcome(
    cues: list[FixtureSegment],
    profile: FixtureCapabilities,
    initial: InitialFixtureState,
    memo: PrepositionMemo | None,
    **policy: Any,
) -> PrepositionResult | tuple[str, str]:
    """`plan_prepositions`' result, or the refusal it raises."""
    try:
        return plan_prepositions(
            cues,
            {"MH1": profile},
            initial_states={"MH1": initial},
            locks=(),
            frame_ms=20,
            memo=memo,
            **policy,
        )
    except Exception as error:  # the refusal is the outcome compared
        return type(error).__name__, str(error)


def test_random_entries_with_a_memo_are_their_memo_free_plans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Random profiles and cue chains under every policy: every suffix of a chain, from
    three random initial states (dark and lit), planned in random order with one memo, is
    its memo-free plan or the same refusal; and plans do take earlier plans' rest. Seed
    108 is a witness that `_plan_view` must keep `known_dark`, 104 and 121 its motion."""
    hits = _counting_reuses(monkeypatch)
    plans = 0
    for seed in range(150):
        rng = random.Random(seed)
        profile = _random_profile(rng)
        cues = _random_cues(rng)
        end_ms = cues[-1].t1_ms + 20 * rng.choice([0, 1, 50])
        policy: dict[str, Any] = {
            "sequence_end_ms": end_ms,
            "failure_mode": rng.choice(["error", "preserve_aim", "drop_accent"]),
            "on_unplayable": rng.choice(["error", "dark"]),
        }
        memo: PrepositionMemo = {}
        initials = [_random_initial(rng) for _ in range(3)]
        entries = [(start, initial) for start in range(len(cues)) for initial in initials]
        rng.shuffle(entries)
        for start, initial in entries:
            with_memo = _outcome(cues[start:], profile, initial, memo, **policy)
            assert with_memo == _outcome(cues[start:], profile, initial, None, **policy), seed
            plans += 1

    assert hits[0] > plans // 4


# --- Plan groups -----------------------------------------------------------------------


def _held(fixture_id: str, values: tuple[float, ...]) -> FixtureSegment:
    """A cue whose pan passes through `values`, one per frame."""
    t0 = 1000
    points = tuple(PhysicalPoint(t_ms=t0 + 20 * i, value=v) for i, v in enumerate(values))
    trajectories = {
        _PAN: ContinuousTrajectory(unit="degree", points=points, interpolation="linear"),
        _TILT: ContinuousTrajectory(
            unit="degree",
            points=(
                PhysicalPoint(t_ms=t0, value=0.0),
                points[-1].model_copy(update={"value": 0.0}),
            ),
            interpolation="linear",
        ),
    }
    return fixture_segment(
        trajectories, t0_ms=t0, t1_ms=points[-1].t_ms, fixture_id=fixture_id, segment_id="s"
    )


def test_plan_groups_are_the_groups_of_equal_plan_keys() -> None:
    """MH2 and MH4 equal MH1 in their first and last pans but MH2 differs in between:
    only MH1 and MH4 are planned as one, as grouping every head by its full key does, in
    the same order; MH3, on another profile, is its own."""
    cues = [
        _held("MH1", (0.0, 5.0, 10.0)),
        _held("MH2", (0.0, 6.0, 10.0)),
        _held("MH3", (0.0, 5.0, 10.0)),
        _held("MH4", (0.0, 5.0, 10.0)),
    ]
    profile = _profile()
    profiles = {"MH1": profile, "MH2": profile, "MH3": _profile(inverted=True), "MH4": profile}
    states = dict.fromkeys(profiles, _initial(0.0))

    groups = _plan_groups(cues, profiles, states)

    eager: dict[Any, list[str]] = {}
    for fixture_id, fixture_profile in profiles.items():
        own = [cue for cue in cues if cue.fixture_id == fixture_id]
        eager.setdefault(_plan_key(own, fixture_profile, states[fixture_id]), []).append(fixture_id)
    assert groups == {group[0]: group for group in eager.values()}
    assert groups == {"MH1": ["MH1", "MH4"], "MH2": ["MH2"], "MH3": ["MH3"]}


# --- The gate across runs --------------------------------------------------------------


def _gate(rig: FixtureGroup, grid: Any, heads: tuple[str, ...]) -> TemplateAdmission:
    job = family_job(heads)
    return admit_templates(
        list(FAMILY_IDS),
        beat_grid=grid,
        fixture_group=rig,
        initial_states=job.moving_heads.initial_states,
        failure_mode=job.moving_heads.reposition_fallback,
        on_unplayable=job.moving_heads.on_unplayable,
        excludable=list(FAMILY_IDS),
    )


def _slow(rig: FixtureGroup) -> FixtureGroup:
    payload = rig.model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for axis in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = 200.0
    return FixtureGroup.model_validate(payload)


def test_gate_runs_in_one_process_give_each_runs_own_result() -> None:
    """A gate after another on a slower rig and another tempo admits, excludes and dips
    exactly as it does before it: nothing one run keeps reaches the next."""
    heads = _IDS[:3]
    fast = (family_rig(heads), bars_grid(*([500.0] * 5)))
    slow = (_slow(family_rig(heads)), bars_grid(430.0, 500.0, 340.0, 580.0, 470.0))
    with family_catalog():
        first_fast = _gate(*fast, heads)
        first_slow = _gate(*slow, heads)
        again_fast = _gate(*fast, heads)
        again_slow = _gate(*slow, heads)

    assert again_fast == first_fast and again_slow == first_slow
    assert first_fast != first_slow  # the slow rig is refused or dips differently


# --- Exact arithmetic ------------------------------------------------------------------


def _reference_word(axis: AxisCapability, value: Fraction) -> int:
    """`dmx_word` as the fraction formula: scale, round half up, invert."""
    low = Fraction(axis.physical_min)
    word_min, word_max = axis.word_range
    scaled = (value - low) * (word_max - word_min) / (Fraction(axis.physical_max) - low)
    word: int = word_min + math.floor(scaled + Fraction(1, 2))
    return word_min + word_max - word if axis.inverted else word


def test_dmx_words_round_exactly_as_the_fraction_formula() -> None:
    """Random calibrations, subranges and inversions, at random values, range ends and
    exact half-word ties."""
    rng = random.Random(7)
    for _ in range(300):
        low = rng.choice([-270.0, -135.0, 0.0, 10.0, rng.uniform(-400, 400)])
        high = low + rng.choice([540.0, 30.0, 1.0, rng.uniform(0.01, 600)])
        fine = rng.random() < 0.5
        full = 65535 if fine else 255
        dmx_min = rng.choice([0, 20, rng.randint(0, full - 2)])
        dmx_max = rng.choice([None, rng.randint(dmx_min + 1, full)])
        axis = AxisCapability(
            unit="degree",
            physical_min=low,
            physical_max=high,
            coarse_offset=1,
            fine_offset=2 if fine else None,
            inverted=rng.random() < 0.5,
            dmx_min=dmx_min,
            dmx_max=dmx_max,
        )
        word_min, word_max = axis.word_range
        tie = rng.randint(word_min, word_max - 1)
        values = [
            Fraction(rng.uniform(low, high)),
            Fraction(low),
            Fraction(high),
            Fraction(low)
            + (Fraction(high) - Fraction(low))
            * Fraction(2 * (tie - word_min) + 1, 2 * (word_max - word_min)),
        ]
        for value in values:
            assert axis.dmx_word(value) == _reference_word(axis, value), (axis, value)


def test_head_motion_follows_exactly_as_in_fractions() -> None:
    """`_follow`'s integer arrival against the fraction recurrence, from random motion
    under way, over random word commands, on profiles with odd speeds."""
    rng = random.Random(11)
    for speed in (90.0, 333.0, 720.0, 47.5):
        profile = _profile(
            travel_speed_per_s=speed, latency_ms=rng.choice([0, 7, 30]), settle_ms=40
        )
        planner = preposition._FixturePlanner("MH1", profile, None, (), 20, 10_000, "error")
        axis = profile.axes["pan"]
        per_word = Fraction(axis.physical_max) - Fraction(axis.physical_min)
        per_word = per_word / (axis.word_range[1] - axis.word_range[0]) * 1000 / Fraction(speed)
        for _ in range(50):
            start = Fraction(rng.randint(0, 4000), rng.choice([1, 3, 7, 4369]))
            motion = (start, start + 40)
            word = rng.randint(0, 65535)
            commands = [(t, rng.choice([word, rng.randint(0, 65535)])) for t in range(0, 2000, 20)]
            expected, held = motion, word
            for time_ms, commanded in commands:
                if commanded != held:
                    arrival = max(expected[0], Fraction(time_ms + axis.latency_ms)) + (
                        abs(commanded - held) * per_word
                    )
                    expected, held = (arrival, arrival + 40), commanded
            assert planner._follow(_PAN, motion, word, commands) == (expected, held)


def test_paths_and_pulses_evaluate_as_from_the_fraction_phase() -> None:
    """Every path shape, transform and pulse, at random exact phases: the floats are
    those of the fraction formulas."""
    rng = random.Random(13)
    pose = PoseDegrees(pan_deg=10.0, tilt_deg=-5.0)
    shapes = [
        ("circle", "periodic"),
        ("lissajous", "periodic"),
        ("sweep", "periodic"),
        ("sweep", "finite"),
        ("linear", "finite"),
        ("sine_pan", "periodic"),
    ]
    for shape, mode in shapes:
        for transform in (
            None,
            {"rotation_deg": 30.0, "phase_cycles": 0.3},
            {"rotation_deg": 180.0, "reverse": True},
        ):
            if transform and (shape, mode) == ("sweep", "periodic") and "reverse" in transform:
                continue  # a periodic sweep refuses `reverse`
            fields: dict[str, Any] = {
                "shape": shape,
                "mode": mode,
                "start_pan_deg": 10.0,
                "start_tilt_deg": -5.0,
                "pan_extent_deg": 20.0,
                "tilt_extent_deg": 0.0 if shape in ("sweep", "sine_pan") else 10.0,
                "period_beats": 2.0,
            }
            if transform and shape in ("circle", "lissajous", "sweep"):
                fields["transform"] = transform
            spec = Movement.model_validate(fields)
            for _ in range(40):
                phase = Fraction(rng.randint(-500, 5000), rng.choice([1, 3, 28, 4369]))
                sign = rng.choice([-1, 0, 1])
                n, d = phase.numerator, phase.denominator
                assert step_module.evaluate_path(spec, pose, n, d, sign) == _reference_path(
                    spec, pose, phase, sign
                )

    grid = p1_grid()
    phase_map = build_musical_phase_map(grid)
    for _ in range(200):
        pulse = PulseSpec.model_validate(
            {
                "period_beats": rng.choice([0.5, 1.0, 4.0]),
                "duty_cycle": rng.choice([0.25, 0.5, 0.3]),
                "phase_cycles": rng.choice([0.0, 0.1, 0.75]),
            }
        )
        origin = 20 * rng.randint(1, 50)
        time_ms = origin + 20 * rng.randint(0, 100)
        offset = Fraction(rng.randint(0, 12), 12)
        phase = (
            musical_phase_fraction(
                phase_map, time_ms, origin_ms=origin, period_beats=pulse.period_beats
            )
            - offset
            + Fraction(repr(pulse.phase_cycles))
        )
        expected = phase - math.floor(phase) < Fraction(repr(pulse.duty_cycle))
        assert step_module._pulse_high(pulse, phase_map, time_ms, origin, offset=offset) == expected


@pytest.mark.parametrize(
    ("offset", "end_ms"),
    [
        pytest.param(Fraction(0), 500, id="in_phase"),
        pytest.param(Fraction(1, 4), 750, id="lagging"),
    ],
)
def test_a_pulse_is_low_from_the_exact_end_of_its_duty(offset: Fraction, end_ms: int) -> None:
    """A half-duty pulse over 1000 ms (two 500 ms beats) is high on `[0, duty)` of its
    cycle: high just before `end_ms`, where the phase's fractional part is exactly the
    duty, low at it, and high again a cycle on."""
    phase_map = build_musical_phase_map(BeatGrid.from_tempo(tempo_bpm=120, total_bars=2))
    pulse = PulseSpec.model_validate({"period_beats": 2.0, "duty_cycle": 0.5})
    start_ms = end_ms - 500
    high = [
        step_module._pulse_high(pulse, phase_map, time_ms, 0, offset=offset)
        for time_ms in (start_ms, end_ms - 1, end_ms, start_ms + 1000)
    ]
    assert high == [True, True, False, True]


@pytest.mark.parametrize(
    ("values", "refused"),
    [
        pytest.param((0.0, -300.0, 10.0), "-300.0", id="below_only"),
        pytest.param((0.0, 300.0, -10.0), "300.0", id="above_only"),
    ],
)
def test_a_trajectory_with_one_extreme_out_of_range_is_refused_at_it(
    values: tuple[float, ...], refused: str
) -> None:
    """Pan's operable range is [-270, 270]: a trajectory whose only point outside it is
    its lowest, or its highest, is refused at that point."""
    trajectory = ContinuousTrajectory(
        unit="degree",
        points=tuple(PhysicalPoint(t_ms=20 * i, value=v) for i, v in enumerate(values)),
        interpolation="linear",
    )
    with pytest.raises(PhysicalChannelError) as error:
        check_physical_value("MH1", _PAN, trajectory, _profile())
    assert str(error.value) == (
        f"MH1 pan at 20 ms: {refused} is outside the operable range (-270.0, 270.0)"
    )


def test_a_refused_float_reads_as_its_exact_fraction() -> None:
    """The planner encodes a float outside the operable range as its exact fraction, so the
    refusal names the value as it always has."""
    axis = _profile().axes["pan"]
    with pytest.raises(ValueError) as error:
        preposition._encoded(axis, 300.5)
    assert str(error.value) == "601/2 is outside the operable range (-270.0, 270.0)"


def _reference_path(
    spec: Movement, pose: PoseDegrees, phase: Fraction, sign: int
) -> tuple[float, float]:
    """`evaluate_path` with every float taken of a `Fraction`."""
    pan_extent = sign * spec.pan_extent_deg
    if spec.shape in ("circle", "lissajous", "sweep"):
        transform = spec.transform
        travel = phase + (Fraction(repr(transform.phase_cycles)) if transform else 0)
        u = float(1 - travel if transform and transform.reverse else travel)
        if spec.shape == "circle":
            x, y = math.cos(2 * math.pi * u), math.sin(2 * math.pi * u)
        elif spec.shape == "lissajous":
            a, b = spec.lissajous_ratio or (1, 2)
            x, y = math.sin(2 * math.pi * a * u), math.sin(2 * math.pi * b * u)
        elif spec.mode == "finite":
            x, y = -math.cos(math.pi * min(max(u, 0.0), 1.0)), 0.0
        else:
            x, y = -math.cos(2 * math.pi * u), 0.0
        if transform and transform.rotation_deg:
            quarters, rest = divmod(transform.rotation_deg, 90)
            if rest == 0:
                cos, sin = ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))[int(quarters) % 4]
            else:
                angle = math.radians(transform.rotation_deg)
                cos, sin = math.cos(angle), math.sin(angle)
            x, y = x * cos - y * sin, x * sin + y * cos
        return pose.pan_deg + pan_extent * x, pose.tilt_deg + spec.tilt_extent_deg * y
    fraction = float(phase)
    if spec.shape == "linear":
        progress = min(max(fraction, 0.0), 1.0)
    else:
        progress = math.sin(2 * math.pi * fraction)
    return pose.pan_deg + pan_extent * progress, pose.tilt_deg + spec.tilt_extent_deg * progress
