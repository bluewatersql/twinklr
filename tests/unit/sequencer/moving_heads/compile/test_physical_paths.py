"""Relative physical paths and finite motion (P2.3).

`circle`, `lissajous` and `sweep` move about a resolved base aim: the centered
displacement is rotated by the template's `transform.rotation_deg`, then each axis is
scaled by its own extent (the maximum signed displacement) and the aim is added. The
pan component after rotation and scaling is what a mirrored wing negates. The path
parameter is the fixture's phase (step phase minus its distribution offset) plus
`transform.phase_cycles`, reflected to `1 - u` by `transform.reverse`; pulses never see
either. `RepeatMode.ONCE` plays one cycle at its nominal rate: `HOLD_LAST_POSE` extends
the closing cues to the section end and `TRUNCATE` leaves the remainder to the dark
transaction pass.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
import copy
from fractions import Fraction
import json
import math
import random
from typing import Any, Literal

from pydantic import ValidationError
import pytest

from tests.config_effects_registry import CONFIG_EFFECTS, ConfigDispositionKind
from tests.support.mh_physical import (
    assert_honest_transactions,
    hold_step,
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
from twinklr.core.agents.sequencer.moving_heads.context import MovingHeadPlanningContext
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.fixtures.presets import PoseDegrees
from twinklr.core.config.render_policy import UnsupportedRenderModeError
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.context import TemplateCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    PhysicalChannelError,
)
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.models.moving_heads.topology import rig_topology
from twinklr.core.sequencer.models.template import (
    PhysicalMovementSpec,
    RemainderPolicy,
    RepeatContract,
    RepeatMode,
    Template,
    TemplateDoc,
    TemplatePreset,
    TemplateStep,
)
from twinklr.core.sequencer.moving_heads import pipeline as pipeline_module
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.physical import (
    PhysicalCompileError,
    evaluate_physical_path,
)
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    TRANSACTION_METADATA_KEY,
    plan_prepositions,
)
from twinklr.core.sequencer.moving_heads.compile.scheduler import schedule_repeats
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    compile_physical_template,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import frame_times
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    check_physical_templates,
    physical_cue_limits,
)
from twinklr.core.sequencer.moving_heads.templates.library import (
    REGISTRY,
    validate_repeat_contract,
    validate_template_document,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import (
    build_musical_phase_map,
    musical_phase_fraction,
)

_GRID = BeatGrid.from_tempo(tempo_bpm=120, total_bars=6)
"""500 ms beats from time zero: a 4-beat period puts quarter phases on 500 ms frames."""
_PHASE_MAP = build_musical_phase_map(_GRID)
_PAN, _TILT, _DIMMER, _SHUTTER = (
    ChannelName.PAN,
    ChannelName.TILT,
    ChannelName.DIMMER,
    ChannelName.SHUTTER,
)
_ROOT_HALF = math.sqrt(2) / 2
_ROOT_THREE_HALF = math.sqrt(3) / 2


def _spec(shape: str, **fields: Any) -> PhysicalMovementSpec:
    return PhysicalMovementSpec.model_validate(
        {
            "shape": shape,
            "mode": "periodic",
            "start_pan_deg": 0.0,
            "start_tilt_deg": 0.0,
            "pan_extent_deg": 20.0,
            "tilt_extent_deg": 0.0 if shape == "sweep" else 10.0,
            "period_beats": 4.0,
            **fields,
        }
    )


def _at(spec: PhysicalMovementSpec, phase: Fraction, **kwargs: Any) -> tuple[float, float]:
    pose = kwargs.pop("pose", PoseDegrees(pan_deg=0.0, tilt_deg=0.0))
    return evaluate_physical_path(spec, pose, phase.numerator, phase.denominator, **kwargs)


def _template(*steps: dict[str, Any], **fields: Any) -> Template:
    return physical_template_doc("p23_probe", steps, **fields).template


def _context(
    template: Template, rig: FixtureGroup, *, duration_bars: int, start_bar: int = 1
) -> TemplateCompileContext:
    return TemplateCompileContext(
        section_id="verse",
        template_id=template.template_id,
        fixtures=build_fixture_contexts(rig_profile_from_fixture_group(rig), rig),
        beat_grid=_GRID,
        start_bar=start_bar,
        duration_bars=duration_bars,
        presets=rig.presets,
        topology=rig_topology(rig),
        fixture_group_id=rig.group_id,
    )


def _compile(
    template: Template,
    rig: FixtureGroup | None = None,
    *,
    duration_bars: int = 1,
    end_limit_ms: int | None = None,
    preset: TemplatePreset | None = None,
) -> list[FixtureSegment]:
    rig = rig or physical_rig()
    start_limit, end_limit = physical_cue_limits(_PHASE_MAP, int(_GRID.duration_ms))
    return compile_physical_template(
        template,
        _context(template, rig, duration_bars=duration_bars),
        preset,
        phase_map=_PHASE_MAP,
        start_limit_ms=start_limit,
        end_limit_ms=end_limit if end_limit_ms is None else end_limit_ms,
    ).segments


def _by_fixture(segments: list[FixtureSegment]) -> dict[str, FixtureSegment]:
    first: dict[str, FixtureSegment] = {}
    for segment in segments:
        first.setdefault(segment.fixture_id, segment)
    return first


def _values(segment: FixtureSegment, channel: ChannelName) -> dict[int, float]:
    physical = segment.channels[channel].physical
    assert isinstance(physical, ContinuousTrajectory)
    return {point.t_ms: point.value for point in physical.points}


def _ids(count: int) -> tuple[str, ...]:
    return tuple(f"MH{index}" for index in range(1, count + 1))


def _topology_rig(count: int) -> FixtureGroup:
    ids = _ids(count)
    return topology_rig(ids, topology=topology_payload(ids))


def _render(
    *sections: tuple[str, int, int], docs: tuple[Any, ...], rig: FixtureGroup | None = None
) -> tuple[RenderingPipeline, list[FixtureSegment]]:
    """Gate, render and check every fixture's transactions from its bytes."""
    rig = rig or physical_rig()
    job = physical_job(
        initial_states=dict.fromkeys(
            [f.fixture_id for f in rig.expand_fixtures()],
            physical_job().moving_heads.initial_states["MH1"].model_dump(mode="json"),
        )
    )
    policy = job.moving_heads
    with registered_templates(*docs):
        check_physical_templates(
            sorted({template_id for template_id, _, _ in sections}),
            beat_grid=_GRID,
            fixture_group=rig,
            initial_states=policy.initial_states,
            failure_mode=policy.reposition_fallback,
        )
        pipeline = RenderingPipeline(
            choreography_plan=physical_sections(*sections),
            beat_grid=_GRID,
            fixture_group=rig,
            job_config=job,
            output_path=None,
        )
        segments = pipeline.render()
    cues = [s for s in segments if TRANSACTION_METADATA_KEY not in s.metadata]
    profiles = {f.fixture_id: f.config.physical_profile for f in rig.expand_fixtures()}
    replanned = plan_prepositions(
        cues,
        profiles,  # type: ignore[arg-type]
        initial_states=policy.initial_states,
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=len(frame_times(int(_GRID.duration_ms))) * EFFECT_GRID_MS,
        failure_mode=policy.reposition_fallback,
    )
    assert list(replanned.segments) == segments
    for fixture_id, profile in profiles.items():
        assert profile is not None
        initial = policy.initial_states[fixture_id]
        assert_honest_transactions(replanned, cues, profile, initial, fixture_id=fixture_id)
    return pipeline, cues


# --- Path formulas, pinned with hand-computed values ---------------------------------


@pytest.mark.parametrize(
    ("shape", "fields", "phase", "expected"),
    [
        # circle: (cos 2πu, sin 2πu)
        ("circle", {}, Fraction(0), (20.0, 0.0)),
        ("circle", {}, Fraction(1, 8), (20 * _ROOT_HALF, 10 * _ROOT_HALF)),
        ("circle", {}, Fraction(1, 4), (0.0, 10.0)),
        ("circle", {}, Fraction(1, 2), (-20.0, 0.0)),
        # lissajous (a, b), default 1:2: (sin 2πau, sin 2πbu)
        ("lissajous", {}, Fraction(0), (0.0, 0.0)),
        ("lissajous", {}, Fraction(1, 8), (20 * _ROOT_HALF, 10.0)),
        ("lissajous", {"lissajous_ratio": [3, 2]}, Fraction(1, 12), (20.0, 10 * _ROOT_THREE_HALF)),
        # periodic sweep: (-cos 2πu, 0), edge to edge and back
        ("sweep", {}, Fraction(0), (-20.0, 0.0)),
        ("sweep", {}, Fraction(1, 4), (0.0, 0.0)),
        ("sweep", {}, Fraction(1, 2), (20.0, 0.0)),
        ("sweep", {}, Fraction(1), (-20.0, 0.0)),
        # finite sweep: (-cos π·clamp(u, 0, 1), 0), one way, held at both ends
        ("sweep", {"mode": "finite"}, Fraction(-1, 4), (-20.0, 0.0)),
        ("sweep", {"mode": "finite"}, Fraction(1, 2), (0.0, 0.0)),
        ("sweep", {"mode": "finite"}, Fraction(1), (20.0, 0.0)),
        ("sweep", {"mode": "finite"}, Fraction(3, 2), (20.0, 0.0)),
    ],
)
def test_each_relative_shape_follows_its_stated_formula(
    shape: str, fields: dict[str, Any], phase: Fraction, expected: tuple[float, float]
) -> None:
    """Pan extent 20, tilt extent 10, about a zero aim: each axis's displacement is its
    extent times that component of the centered path, never a full width."""
    assert _at(_spec(shape, **fields), phase) == pytest.approx(expected, abs=1e-12)


def test_ninety_degree_rotation_turns_the_normalized_path_before_scaling() -> None:
    """Asymmetric extents (pan 30, tilt 10): a 90-degree turn maps the path's x onto
    tilt, so a circle's start (1, 0) becomes (0, 1), scaled to tilt +10 (turning after
    scaling would give +30), and a pan sweep becomes a sweep of +/-10 on tilt. Quarter
    turns are exact."""
    rotated: dict[str, Any] = {
        "pan_extent_deg": 30.0,
        "tilt_extent_deg": 10.0,
        "transform": {"rotation_deg": 90.0},
    }
    sweep = _spec("sweep", mode="finite", **{**rotated, "pan_extent_deg": 0.0})
    assert _at(sweep, Fraction(0)) == (0.0, -10.0)
    assert _at(sweep, Fraction(1)) == (0.0, 10.0)
    assert _at(_spec("sweep", mode="finite", pan_extent_deg=30.0), Fraction(0)) == (-30.0, 0.0)

    circle = _spec("circle", **rotated)
    quarter = [value for k in range(4) for value in _at(circle, Fraction(k, 4))]
    assert quarter == pytest.approx([0, 10, -30, 0, 0, -10, 30, 0], abs=1e-12)

    # Any other angle uses cos and sin of the angle: 30 degrees turns (1, 0) to
    # (cos 30, sin 30) before the extents scale it.
    thirty = _spec("circle", pan_extent_deg=30.0, transform={"rotation_deg": 30.0})
    assert _at(thirty, Fraction(0)) == pytest.approx((30 * _ROOT_THREE_HALF, 5.0), abs=1e-12)


@pytest.mark.parametrize(
    ("rotation", "expected"),
    [(180.0, (-20.0, 0.0)), (270.0, (0.0, -10.0)), (-90.0, (0.0, -10.0)), (450.0, (0.0, 10.0))],
)
def test_every_quarter_turn_is_exact(rotation: float, expected: tuple[float, float]) -> None:
    """A circle's start (1, 0) turned by each quarter, with no float residue."""
    assert _at(_spec("circle", transform={"rotation_deg": rotation}), Fraction(0)) == expected


def test_a_turned_lissajous_can_exceed_its_unrotated_extents_and_is_still_bounded() -> None:
    """Extents bound the unrotated path. A 1:2 lissajous turned 45 degrees reaches about
    1.24 times its extents (never more than sqrt 2); the per-frame bounds check still
    refuses one that leaves the pan range only once turned."""
    spec = _spec("lissajous", transform={"rotation_deg": 45.0})
    points = [_at(spec, Fraction(k, 4800)) for k in range(4800)]
    pan = max(abs(p) for p, _ in points)
    tilt = max(abs(t) for _, t in points)
    assert pan == pytest.approx(24.8926, abs=1e-3) and tilt == pytest.approx(12.4463, abs=1e-3)
    assert 20.0 < pan <= 20 * math.sqrt(2) and 10.0 < tilt <= 10 * math.sqrt(2)

    upright = path_step("o", "lissajous", pan=248.0)
    assert _compile(_template(upright))
    turned = path_step("o", "lissajous", pan=248.0, transform={"rotation_deg": 45.0})
    with pytest.raises(PhysicalChannelError, match="pan"):
        _compile(_template(turned))


def test_extents_are_maximum_signed_displacement_and_stay_asymmetric() -> None:
    """Over a dense cycle, each axis reaches exactly its own extent and no more; a
    negative extent flips that axis; nothing is normalized to a common radius."""
    for shape in ("circle", "lissajous", "sweep"):
        tilt = 0.0 if shape == "sweep" else 10.0
        spec = _spec(shape, pan_extent_deg=-30.0, tilt_extent_deg=tilt)
        points = [_at(spec, Fraction(k, 480)) for k in range(480)]
        pans, tilts = [p for p, _ in points], [t for _, t in points]
        assert max(abs(p) for p in pans) == pytest.approx(30.0, abs=1e-9)
        if shape != "sweep":
            assert max(abs(t) for t in tilts) == pytest.approx(10.0, abs=1e-9)
    assert _at(_spec("circle", pan_extent_deg=-30.0), Fraction(0)) == (-30.0, 0.0)


def test_a_resolved_pose_is_the_only_base_and_the_terminal_point_is_not_closed() -> None:
    """The aim is added once. A circle over 1.25 periods ends a quarter turn on, not
    back at its start: no loop closure."""
    spec = _spec("circle")
    pose = PoseDegrees(pan_deg=60.0, tilt_deg=30.0)
    assert _at(spec, Fraction(0), pose=pose) == (80.0, 30.0)

    step = path_step("orbit", "circle", period_beats=3.2)
    segment = _by_fixture(_compile(_template(step)))["MH1"]
    pan, tilt = _values(segment, _PAN), _values(segment, _TILT)
    assert (pan[0], tilt[0]) == (20.0, 0.0)
    assert (pan[2000], tilt[2000]) == pytest.approx((0.0, 10.0), abs=1e-9)


# --- Named aim, reverse, phase composition and the mirror sign -----------------------


def _referencing(step: dict[str, Any], **refs: Any) -> dict[str, Any]:
    physical = step["movement"]["physical"]
    for name in ("start_pan_deg", "start_tilt_deg"):
        physical.pop(name)
    physical.update(refs.pop("start", {}))
    step["component_refs"] = {"position_id": "side", **refs}
    return step


def test_rotated_orbit_uses_named_aim() -> None:
    """A 90-degree-rotated circle (pan extent 30, tilt 10) orbits each head's `side`
    preset aim (MH1 60/30, MH2 -60/30). A start angle set on the step replaces that
    axis of the aim; the two are never added."""
    orbit = path_step(
        "orbit", "circle", pan_extent=30.0, tilt_extent=10.0, transform={"rotation_deg": 90.0}
    )
    heads = _by_fixture(_compile(_template(_referencing(orbit)), physical_preset_rig()))
    times = (0, 500, 1000, 1500)
    expected = {
        "MH1": ([60, 30, 60, 90], [40, 30, 20, 30]),
        "MH2": ([-60, -90, -60, -30], [40, 30, 20, 30]),
    }
    for fixture_id, (pans, tilts) in expected.items():
        segment = heads[fixture_id]
        assert [_values(segment, _PAN)[t] for t in times] == pytest.approx(pans, abs=1e-9)
        assert [_values(segment, _TILT)[t] for t in times] == pytest.approx(tilts, abs=1e-9)

    override = path_step(
        "orbit", "circle", pan_extent=30.0, tilt_extent=10.0, transform={"rotation_deg": 90.0}
    )
    override = _referencing(override, start={"start_tilt_deg": 0.0})
    segment = _by_fixture(_compile(_template(override), physical_preset_rig()))["MH1"]
    assert [_values(segment, _TILT)[t] for t in times] == pytest.approx([10, 0, -10, 0], abs=1e-9)
    assert [_values(segment, _PAN)[t] for t in times] == pytest.approx([60, 30, 60, 90], abs=1e-9)


def test_reverse_changes_travel_not_visibility_phase() -> None:
    """Reversed, the circle runs clockwise (tilt displacement negated, pan unchanged);
    its dimmer and shutter pulses are identical, with or without a path phase shift."""
    pulses = {
        "dimmer": {"physical": {"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0}},
        "physical_shutter": {
            "period_beats": 2.0,
            "duty_cycle": 0.5,
            "low_state": "closed",
            "high_state": "open",
        },
    }

    def compiled(transform: dict[str, Any] | None) -> FixtureSegment:
        step = path_step("orbit", "circle", transform=transform, **pulses)
        step.pop("physical_shutter_state")  # the pulse replaces the held state
        return _by_fixture(_compile(_template(step)))["MH1"]

    forward = compiled(None)
    for transform in ({"reverse": True}, {"reverse": True, "phase_cycles": 0.25}):
        reverse = compiled(transform)
        assert reverse.channels[_DIMMER] == forward.channels[_DIMMER]
        assert reverse.channels[_SHUTTER] == forward.channels[_SHUTTER]
    reverse = compiled({"reverse": True})
    assert _values(reverse, _PAN) == pytest.approx(_values(forward, _PAN), abs=1e-9)
    tilt_forward, tilt_reverse = _values(forward, _TILT), _values(reverse, _TILT)
    assert [tilt_reverse[t] for t in tilt_forward] == pytest.approx(
        [-value for value in tilt_forward.values()], abs=1e-9
    )
    assert tilt_forward[500] == pytest.approx(10.0) and tilt_reverse[500] == pytest.approx(-10.0)


def test_phase_terms_compose_exactly() -> None:
    """Path parameter u = step phase - distribution offset + transform.phase_cycles,
    then 1 - u when reversed, all exact: 1/5 + 0.1 is 3/10 (the floats would give
    0.30000000000000004). Pulses use step phase - offset + their own phase_cycles."""
    shifted = _spec("circle", transform={"phase_cycles": 0.1})
    assert _at(shifted, Fraction(1, 5)) == _at(_spec("circle"), Fraction(3, 10))
    # The binary float nearest 0.1 would leave a residue at the start.
    assert _at(shifted, Fraction(-1, 10)) == (20.0, 0.0)
    reversed_shifted = _spec("circle", transform={"phase_cycles": 0.1, "reverse": True})
    assert _at(reversed_shifted, Fraction(1, 5)) == _at(_spec("circle"), Fraction(7, 10))

    # On the rig: MH2 lags half a cycle on pan and tilt; the dimmer is not distributed.
    distribution = [{"domains": ["pan", "tilt"], "spread_cycles": 0.5}]
    dimmer = {"physical": {"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0}}
    step = path_step(
        "orbit",
        "circle",
        transform={"phase_cycles": 0.1},
        physical_distribution=distribution,
        dimmer=dimmer,
    )
    heads = _by_fixture(_compile(_template(step), _topology_rig(2)))
    spec = TemplateStep.model_validate(step).movement.physical
    assert spec is not None
    for t in (0, 260, 740, 1500):
        phase = musical_phase_fraction(_PHASE_MAP, t, origin_ms=0, period_beats=4.0)
        expected = _at(spec, phase - Fraction(1, 2))
        assert (_values(heads["MH2"], _PAN)[t], _values(heads["MH2"], _TILT)[t]) == expected
    unshifted = path_step("orbit", "circle", physical_distribution=distribution, dimmer=dimmer)
    plain = _by_fixture(_compile(_template(unshifted), _topology_rig(2)))
    for fixture_id in ("MH1", "MH2"):
        assert plain[fixture_id].channels[_DIMMER] == heads[fixture_id].channels[_DIMMER]
        assert plain[fixture_id].channels[_PAN] != heads[fixture_id].channels[_PAN]


def test_mirror_sign_negates_the_pan_component_after_rotation() -> None:
    """Two wings over three heads (signs -1, 0, +1) on a 30-degree-rotated circle: the
    left head's pan displacement is the right head's negated, the center's is zero, and
    all three share the tilt. Negating x before the turn would also flip tilt."""
    distribution = [{"domains": ["pan", "tilt"], "wings": 2}]
    step = path_step(
        "orbit",
        "circle",
        pan_extent=30.0,
        transform={"rotation_deg": 30.0},
        physical_distribution=distribution,
    )
    heads = _by_fixture(_compile(_template(step), _topology_rig(3)))
    left, center, right = (heads[f] for f in _ids(3))
    assert _values(right, _PAN)[0] == pytest.approx(30 * _ROOT_THREE_HALF)
    assert _values(left, _PAN)[0] == pytest.approx(-30 * _ROOT_THREE_HALF)
    assert _values(right, _TILT)[0] == pytest.approx(5.0)
    for t in _values(right, _PAN):
        assert _values(left, _PAN)[t] == -_values(right, _PAN)[t]
        assert _values(center, _PAN)[t] == 0.0
        assert _values(left, _TILT)[t] == _values(center, _TILT)[t] == _values(right, _TILT)[t]
    turned = _spec("circle", transform={"rotation_deg": 30.0})
    pose = PoseDegrees(pan_deg=5.0, tilt_deg=0.0)
    for phase in (Fraction(0), Fraction(1, 7), Fraction(5, 8)):
        left = _at(turned, phase, pose=pose, pan_sign=-1)
        right = _at(turned, phase, pose=pose, pan_sign=1)
        assert left[0] - 5.0 == -(right[0] - 5.0) and left[1] == right[1]
    assert _at(turned, Fraction(0), pose=pose, pan_sign=-1)[0] == pytest.approx(
        5.0 - 20 * _ROOT_THREE_HALF
    )


# --- Finite motion --------------------------------------------------------------------


def test_finite_snap_does_not_wrap() -> None:
    """A one-beat finite sweep in a one-bar step reaches +20 at 500 ms and holds it to
    the terminal point; the periodic sweep of the same period swings back."""
    snap = path_step("snap", "sweep", mode="finite", period_beats=1.0)
    segment = _by_fixture(_compile(_template(snap)))["MH1"]
    pan = _values(segment, _PAN)
    assert pan[0] == -20.0
    assert all(value == 20.0 for t, value in pan.items() if t >= 500)
    assert pan[2000] == 20.0

    swing = path_step("swing", "sweep", period_beats=1.0)
    swung = _values(_by_fixture(_compile(_template(swing)))["MH1"], _PAN)
    assert max(swung.values()) > 19.0 and swung[500] == pytest.approx(-20.0)


def test_lagging_finite_sweep_holds_its_start_then_reaches_its_terminal() -> None:
    """P2.2's clamp applies to the finite sweep: a head lagging half a period holds its
    start until its phase reaches zero, and the reversed sweep starts at +extent."""
    distribution = [{"domains": ["pan"], "spread_cycles": 0.5}]
    step = path_step(
        "snap", "sweep", mode="finite", period_beats=2.0, physical_distribution=distribution
    )
    heads = _by_fixture(_compile(_template(step), _topology_rig(2)))
    lagging = _values(heads["MH2"], _PAN)
    assert all(lagging[t] == -20.0 for t in range(0, 520, 20))
    assert lagging[1500] == 20.0 and lagging[2000] == 20.0
    reverse = path_step("back", "sweep", mode="finite", transform={"reverse": True})
    assert _values(_by_fixture(_compile(_template(reverse)))["MH1"], _PAN)[0] == 20.0


# --- Everything downstream sees the real path ----------------------------------------


def test_a_path_beyond_an_axis_limit_or_the_rate_is_refused_before_planning() -> None:
    """A circle whose start and end are in range but whose top (tilt 140) exceeds 135,
    and a 1:2 lissajous whose tilt (the doubled component) travels about 1000
    degrees/s on a 720 degrees/s head, are both refused by the gate."""
    high = physical_template_doc(
        "p23_high", [path_step("o", "circle", tilt=100.0, tilt_extent=40.0)]
    )
    fast = physical_template_doc(
        "p23_fast", [path_step("o", "lissajous", tilt_extent=40.0, period_beats=1.0)]
    )
    job = physical_job()
    for document, match in ((high, "tilt.*135"), (fast, "tilt.*travels")):
        template_id = document.template.template_id
        with registered_templates(document), pytest.raises(UnsupportedRenderModeError) as error:
            check_physical_templates(
                [template_id],
                beat_grid=_GRID,
                fixture_group=physical_rig(),
                initial_states=job.moving_heads.initial_states,
                failure_mode="error",
            )
        assert template_id in str(error.value)
        with pytest.raises(PhysicalChannelError, match=match):
            _compile(document.template)


def test_a_path_finer_than_its_axis_can_follow_is_refused() -> None:
    """A 0.55-degree circle every 0.16 beat on an 8-bit 45.5 degrees/s head, centered
    on a pan word boundary: within the speed limit, but the head falls ever further
    behind its commands (P2.4a's `follow_lag`)."""
    payload = physical_rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for name in ("pan", "tilt"):
            axis = fixture["config"]["physical_profile"]["axes"][name]
            axis.pop("fine_offset")
            axis.update(travel_speed_per_s=45.5, latency_ms=0, settle_ms=0)
    rig = FixtureGroup.model_validate(payload)
    profile = rig.expand_fixtures()[0].config.physical_profile
    assert profile is not None
    axis = profile.axes["pan"]
    low, high = 0.0, 5.0
    while high - low > 1e-9:
        middle = (low + high) / 2
        low, high = (middle, high) if axis.dmx_word(middle) == axis.dmx_word(0.0) else (low, middle)
    shake = path_step("s", "circle", pan=low, pan_extent=0.55, tilt_extent=0.55, period_beats=0.16)
    with pytest.raises(PhysicalChannelError, match="trails its commands"):
        _compile(_template(shake), rig)


def test_entry_window_opens_an_orbit_on_its_real_path() -> None:
    """After a hold at pan -90 the orbit cannot start as authored: each head waits dark
    for its window, then enters the circle where the path is at that time, with the
    phase origin kept; every head's transactions check out from its bytes."""
    left = physical_template_doc("p23_left", [hold_step("l", -90.0)])
    orbit = physical_template_doc("p23_orbit", [path_step("o", "circle")])
    pipeline, cues = _render(("p23_left", 1, 1), ("p23_orbit", 2, 3), docs=(left, orbit))
    assert pipeline.render_record is not None
    windows = [w for w in pipeline.render_record["entry_windows"] if w["section_id"] == "s2"]
    assert {w["action"] for w in windows} == {"cut"} and len(windows) == 2
    spec = PhysicalMovementSpec.model_validate(path_step("o", "circle")["movement"]["physical"])
    for window in windows:
        cue = min(
            (c for c in cues if c.section_id == "s2" and c.fixture_id == window["fixture_id"]),
            key=lambda c: c.t0_ms,
        )
        assert cue.t0_ms == window["first_cue_ms"] > 2000
        assert int(cue.metadata["phase_origin_ms"]) == 2000
        phase = musical_phase_fraction(_PHASE_MAP, cue.t0_ms, origin_ms=2000, period_beats=4.0)
        pan, tilt = _at(spec, phase)
        assert (_values(cue, _PAN)[cue.t0_ms], _values(cue, _TILT)[cue.t0_ms]) == pytest.approx(
            (pan, tilt), abs=1e-9
        )
        assert (pan, tilt) != pytest.approx((20.0, 0.0))


def test_gate_groups_heads_by_their_real_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate plans heads with identical trajectories once: a plain circle is one
    plan; mirrored wings over four heads are two (left and right), at every placement."""
    planned: dict[str, set[int]] = defaultdict(set)
    real = pipeline_module.plan_prepositions

    def recording(segments: Any, *args: Any, **kwargs: Any) -> Any:
        templates = {segment.template_id for segment in segments}
        planned[templates.pop()].add(len({segment.fixture_id for segment in segments}))
        return real(segments, *args, **kwargs)

    monkeypatch.setattr(pipeline_module, "plan_prepositions", recording)
    wings = [{"domains": ["pan", "tilt"], "wings": 2}]
    documents = (
        physical_template_doc("p23_plain", [path_step("o", "circle")]),
        physical_template_doc("p23_wings", [path_step("o", "circle", physical_distribution=wings)]),
    )
    ids = _ids(4)
    initial = physical_job().moving_heads.initial_states["MH1"]
    with registered_templates(*documents):
        check_physical_templates(
            ["p23_plain", "p23_wings"],
            beat_grid=_GRID,
            fixture_group=_topology_rig(4),
            initial_states=dict.fromkeys(ids, initial),
            failure_mode="error",
        )
    assert planned == {"p23_plain": {1}, "p23_wings": {2}}


# --- RepeatMode.ONCE ------------------------------------------------------------------


def _contract(mode: RepeatMode, policy: RemainderPolicy) -> RepeatContract:
    return RepeatContract(
        mode=mode, cycle_bars=2.0, loop_step_ids=["a", "b"], remainder_policy=policy
    )


def _spans(mode: RepeatMode, policy: RemainderPolicy, duration: float) -> list[tuple[Any, ...]]:
    result = schedule_repeats(
        _contract(mode, policy),
        duration,
        step_durations={"a": 1.0, "b": 1.0},
        step_offsets={"a": 0.0, "b": 1.0},
    )
    return [(i.step_id, i.start_bars, i.end_bars, i.cycle_number) for i in result.instances]


def test_once_schedules_one_cycle_at_its_nominal_rate() -> None:
    """ONCE never repeats or compresses its cycle: TRUNCATE schedules nothing after it,
    HOLD_LAST_POSE extends the closing step to the window end, and a window shorter
    than the cycle keeps the cycle's own placements (the compile refuses the cut)."""
    once, hold, cut = RepeatMode.ONCE, RemainderPolicy.HOLD_LAST_POSE, RemainderPolicy.TRUNCATE
    assert _spans(once, cut, 7.0) == [("a", 0.0, 1.0, 0), ("b", 1.0, 2.0, 0)]
    assert _spans(once, hold, 7.0) == [("a", 0.0, 1.0, 0), ("b", 1.0, 7.0, 0)]
    assert _spans(once, hold, 2.0) == [("a", 0.0, 1.0, 0), ("b", 1.0, 2.0, 0)]
    short = schedule_repeats(
        _contract(once, hold),
        1.5,
        step_durations={"a": 1.0, "b": 1.0},
        step_offsets={"a": 0.0, "b": 1.0},
    )
    assert short.num_complete_cycles == 0
    assert [(i.start_bars, i.end_bars) for i in short.instances] == [(0.0, 1.0), (1.0, 2.0)]


def test_every_other_mode_keeps_its_remainder_scheduling() -> None:
    """JOINER TRUNCATE still renders the head of the next cycle and HOLD_LAST_POSE
    still appends a new instance at the remainder start."""
    joiner = RepeatMode.JOINER
    assert _spans(joiner, RemainderPolicy.TRUNCATE, 7.0)[-1] == ("a", 6.0, 7.0, 3)
    assert _spans(joiner, RemainderPolicy.HOLD_LAST_POSE, 7.0)[-2:] == [
        ("b", 5.0, 6.0, 2),
        ("b", 6.0, 7.0, 3),
    ]
    assert len(_spans(RepeatMode.PING_PONG, RemainderPolicy.TRUNCATE, 7.0)) == 7


def _once(policy: str = "HOLD_LAST_POSE", *, cycle_bars: float = 1.0) -> Template:
    step = path_step(
        "fly", "sweep", mode="finite", pan_extent=30.0, period_beats=4.0, duration=cycle_bars
    )
    return physical_template_doc(
        "p23_once", [step], cycle_bars=cycle_bars, mode="ONCE", remainder_policy=policy
    ).template


def test_once_hold_extends_one_cue_and_holds_the_terminal_pose_lit() -> None:
    """One cue per fixture from the section start to its end, one phase origin; from
    the cycle end on, every frame holds the terminal pose (+30), lit and open."""
    segments = _compile(_once(), duration_bars=3)
    assert sorted(s.fixture_id for s in segments) == ["MH1", "MH2"]
    for segment in segments:
        assert (segment.t0_ms, segment.t1_ms) == (0, 6000)
        assert int(segment.metadata["phase_origin_ms"]) == 0
        assert all(v == 30.0 for t, v in _values(segment, _PAN).items() if t >= 2000)

    held = physical_template_doc(
        "p23_once_hold",
        [path_step("fly", "sweep", mode="finite", pan_extent=30.0)],
        mode="ONCE",
    )
    rig = physical_rig()
    pipeline, _ = _render(("p23_once_hold", 1, 3), docs=(held,), rig=rig)
    profiles = {f.fixture_id: f.config.physical_profile for f in rig.expand_fixtures()}
    remainder = [f for f in pipeline.frames if 2000 <= f.time_ms < 6000]
    assert len(remainder) == 2 * 200
    for frame in remainder:
        profile = profiles[frame.fixture_id]
        assert profile is not None
        pan, channels = profile.axes["pan"], dict(frame.channels)
        assert channels[1] << 8 | channels[2] == pan.dmx_word(30.0)
        assert channels[5] == 255 and channels[17] == 8


def test_once_truncate_leaves_the_remainder_dark() -> None:
    """TRUNCATE schedules nothing after the cycle: each head's only cue ends at the
    cycle end, and the transaction pass holds it dark to the next section."""
    segments = _compile(_once("TRUNCATE"), duration_bars=3)
    assert {(s.t0_ms, s.t1_ms) for s in segments} == {(0, 2000)}

    cut = physical_template_doc(
        "p23_once_cut",
        [path_step("fly", "sweep", mode="finite", pan_extent=30.0)],
        mode="ONCE",
        remainder_policy="TRUNCATE",
    )
    left = physical_template_doc("p23_left", [hold_step("l", -30.0)])
    pipeline, _ = _render(("p23_once_cut", 1, 3), ("p23_left", 4, 4), docs=(cut, left))
    remainder = [dict(f.channels) for f in pipeline.frames if 2000 <= f.time_ms < 6000]
    assert len(remainder) == 2 * 200
    assert all(channels[5] == 0 or channels[17] == 64 for channels in remainder)


def test_short_section_rejects_a_once_cycle_it_cuts() -> None:
    """A two-bar ONCE cycle in a one-bar section fails naming the cycle and section;
    the same cycle cut by the song's end (the cue limit) is cut without error."""
    with pytest.raises(PhysicalCompileError, match=r"ONCE.*2\.0 bars.*1 bar"):
        _compile(_once(cycle_bars=2.0), duration_bars=1)
    segments = _compile(_once(cycle_bars=2.0), duration_bars=2, end_limit_ms=3000)
    assert {(s.t0_ms, s.t1_ms) for s in segments} == {(0, 3000)}


def test_once_template_passes_validate_repeat_contract() -> None:
    """One cycle is an exact, hole-free span, so the unchanged contract accepts ONCE
    templates of one step and of two steps; registration leaves the registry as it was."""
    two = physical_template_doc(
        "p23_once_two",
        [
            sweep_step("out", 0.0, 30.0, duration=0.5, period_beats=2.0),
            sweep_step("back", 30.0, -30.0, start=0.5, duration=0.5, period_beats=2.0),
        ],
        mode="ONCE",
    )
    one = physical_template_doc("p23_once_one", [_once().steps[0].model_dump()], mode="ONCE")
    for document in (one, two):
        validate_repeat_contract(document.template)
        validate_template_document(document)
    before = len(REGISTRY.list_all())
    with registered_templates(two):
        assert len(REGISTRY.list_all()) == before + 1
    assert len(REGISTRY.list_all()) == before


def test_once_needs_finite_steps() -> None:
    """A ONCE step must declare finite motion and no periodic pulse; a preset that
    patches a step back to periodic motion is refused when the compile applies it."""
    periodic = path_step("o", "circle")
    with pytest.raises(ValidationError, match=r"ONCE.*finite"):
        physical_template_doc("p23_bad", [periodic], mode="ONCE")
    pulsing = path_step(
        "o",
        "sweep",
        mode="finite",
        dimmer={"physical": {"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0}},
    )
    with pytest.raises(ValidationError, match=r"ONCE.*duty_cycle"):
        physical_template_doc("p23_bad", [pulsing], mode="ONCE")
    preset = TemplatePreset(
        preset_id="loop",
        name="loop",
        step_patches={"fly": {"movement": {"physical": {"mode": "periodic"}}}},
    )
    with pytest.raises(ValidationError, match=r"ONCE.*finite"):
        _compile(_once(), duration_bars=1, preset=preset)


def test_once_fade_out_stays_refused() -> None:
    with pytest.raises(PhysicalCompileError, match="FADE_OUT"):
        _compile(_once("FADE_OUT"), duration_bars=2)


def test_a_once_move_longer_than_its_step_is_refused() -> None:
    """An 8-beat finite move in a one-bar (4-beat) ONCE step would still be moving at
    the cycle end, so it is refused; the same step under JOINER compiles."""
    slow = path_step("fly", "sweep", mode="finite", period_beats=8.0)
    with pytest.raises(PhysicalCompileError, match=r"8\.0 beats from phase 0\.0 in a 4-beat step"):
        _compile(_template(slow, mode="ONCE"), duration_bars=2)
    assert _compile(_template(slow), duration_bars=2)


def test_a_lagging_head_finishes_in_the_hold_and_is_cut_where_it_is_by_truncate() -> None:
    """MH2 lags half a period. Under HOLD_LAST_POSE it completes its move inside the
    extended cue (+20 by 3000 ms, then held); under TRUNCATE its cue ends at the cycle
    end mid-travel (at the path's centre) and the transaction pass holds it dark."""
    distribution = [{"domains": ["pan"], "spread_cycles": 0.5}]
    step = path_step("fly", "sweep", mode="finite", physical_distribution=distribution)
    held = _by_fixture(_compile(_template(step, mode="ONCE"), _topology_rig(2), duration_bars=3))
    lagging = _values(held["MH2"], _PAN)
    assert lagging[2000] == pytest.approx(0.0, abs=1e-12) and lagging[2500] != 20.0
    assert all(value == 20.0 for t, value in lagging.items() if t >= 3000)
    assert all(value == 20.0 for t, value in _values(held["MH1"], _PAN).items() if t >= 2000)

    cut = _template(step, mode="ONCE", remainder_policy="TRUNCATE")
    segments = _by_fixture(_compile(cut, _topology_rig(2), duration_bars=3))
    assert segments["MH2"].t1_ms == 2000
    assert _values(segments["MH2"], _PAN)[2000] == pytest.approx(0.0, abs=1e-12)
    document = physical_template_doc(
        "p23_once_lag", [step], mode="ONCE", remainder_policy="TRUNCATE"
    )
    pipeline, _ = _render(("p23_once_lag", 1, 3), docs=(document,), rig=_topology_rig(2))
    after = [dict(f.channels) for f in pipeline.frames if f.time_ms >= 2000]
    assert after and all(channels[5] == 0 or channels[17] == 64 for channels in after)


def _speed_rig(speed: float, rig: FixtureGroup | None = None) -> FixtureGroup:
    payload = (rig or physical_rig()).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for axis in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = speed
    return FixtureGroup.model_validate(payload)


def test_the_gate_checks_a_once_cycle_at_every_start_bar() -> None:
    """A ONCE finite sweep peaking at 0.75 of a 90 degrees/s head at 500 ms beats runs
    at 1.5 times it in the 250 ms-beat third bar. The gate refuses it, naming that bar,
    as the render at bar 3 does; at bar 1 it renders."""
    grid = physical_bars_grid(500.0, 500.0, 250.0, 500.0)
    rig = _speed_rig(90.0)
    extent = 0.75 * 90.0 * 2.0 / math.pi
    document = physical_template_doc(
        "p23_once_fast",
        [path_step("f", "sweep", mode="finite", pan_extent=extent)],
        mode="ONCE",
    )
    job = physical_job(on_unplayable="error")

    def render(start_bar: int) -> None:
        RenderingPipeline(
            choreography_plan=physical_sections(("p23_once_fast", start_bar, start_bar)),
            beat_grid=grid,
            fixture_group=rig,
            job_config=job,
            output_path=None,
        ).render()

    with registered_templates(document):
        with pytest.raises(UnsupportedRenderModeError, match=r"placed at bar 3.*travels"):
            check_physical_templates(
                ["p23_once_fast"],
                beat_grid=grid,
                fixture_group=rig,
                initial_states=job.moving_heads.initial_states,
                failure_mode="error",
            )
        render(1)
        with pytest.raises(PhysicalChannelError, match="travels"):
            render(3)


def test_the_gate_compiles_each_distinct_once_placement_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On a steady 12-bar song every start bar looks alike until the song end shortens
    the window, so the gate compiles bar 1, then only the placements near the end."""
    calls: list[int] = []
    real = pipeline_module.compile_physical_template

    def recording(template: Any, context: Any, *args: Any, **kwargs: Any) -> Any:
        calls.append(context.start_bar)
        return real(template, context, *args, **kwargs)

    monkeypatch.setattr(pipeline_module, "compile_physical_template", recording)
    document = physical_template_doc(
        "p23_once_steady", [path_step("f", "sweep", mode="finite")], mode="ONCE"
    )
    with registered_templates(document):
        check_physical_templates(
            ["p23_once_steady"],
            beat_grid=BeatGrid.from_tempo(tempo_bpm=120, total_bars=12),
            fixture_group=physical_rig(),
            initial_states=physical_job().moving_heads.initial_states,
            failure_mode="error",
        )
    assert calls[0] == 1 and len(calls) < 6, calls


def test_a_once_move_must_end_within_its_step_from_its_path_phase() -> None:
    """The move from transform.phase_cycles c to the terminal pose takes
    period * (1 - c) beats: a 4-beat move from phase -0.5 overruns a 4-beat step; an
    8-beat move from phase 0.5 fits exactly, from 0.49 it does not."""

    def once(period: float, phase: float) -> Template:
        step = path_step(
            "fly", "sweep", mode="finite", period_beats=period, transform={"phase_cycles": phase}
        )
        return _template(step, mode="ONCE")

    assert _compile(once(4.0, 0.0), duration_bars=2)
    assert _compile(once(8.0, 0.5), duration_bars=2)
    for period, phase in ((4.0, -0.5), (8.0, 0.49)):
        with pytest.raises(PhysicalCompileError, match=f"from phase {phase}"):
            _compile(once(period, phase), duration_bars=2)


def test_the_once_window_covers_a_head_lagging_past_the_cycle() -> None:
    """A three-bar cycle whose MH2 lags three periods: it is still moving three bars
    after the cycle, through the song's 250 ms-beat last bar, where it is too fast for
    a 90 degrees/s head. A window of the cycle alone would never see it."""
    rig = _speed_rig(90.0, _topology_rig(2))
    grid = physical_bars_grid(500.0, 500.0, 500.0, 500.0, 500.0, 250.0)
    step = path_step(
        "f",
        "sweep",
        mode="finite",
        pan_extent=0.75 * 90.0 * 2.0 / math.pi,
        duration=3.0,
        physical_distribution=[{"domains": ["pan"], "spread_cycles": 3.0}],
    )
    document = physical_template_doc("p23_lag_window", [step], cycle_bars=3.0, mode="ONCE")
    initial = dict.fromkeys(_ids(2), physical_job().moving_heads.initial_states["MH1"])
    with (
        registered_templates(document),
        pytest.raises(UnsupportedRenderModeError, match=r"MH2.*placed at bar 3.*travels"),
    ):
        check_physical_templates(
            ["p23_lag_window"],
            beat_grid=grid,
            fixture_group=rig,
            initial_states=initial,
            failure_mode="error",
        )


def test_the_once_window_is_the_cycle_or_the_last_motion_plus_a_bar() -> None:
    """The window spans the cycle, or the last motion when a lagging head moves on past
    it, in whole bars, plus one bar for frame quantization."""
    plain = path_step("f", "sweep", mode="finite")
    segments = _compile(_template(plain, mode="ONCE"), duration_bars=6)
    window = pipeline_module._once_window_bars(
        segments, _PHASE_MAP, section_start_ms=0, cycle_bars=1.0, beats_per_bar=4
    )
    assert window == 2
    lagging = path_step(
        "f",
        "sweep",
        mode="finite",
        physical_distribution=[{"domains": ["pan"], "spread_cycles": 3.0}],
    )
    segments = _compile(_template(lagging, mode="ONCE"), _topology_rig(2), duration_bars=6)
    window = pipeline_module._once_window_bars(
        segments, _PHASE_MAP, section_start_ms=0, cycle_bars=1.0, beats_per_bar=4
    )
    assert window == 5  # MH2 moves until bar 4 ends (1 + 3 periods of one bar)


def test_bar_ones_entry_does_not_stand_for_a_later_bar_with_its_key() -> None:
    """At bar 1 the head enters from its initial state at the song start, so its window
    drops the first step and the jump between the steps never plays; from bar 2 on, an
    equal key, the head reaches the first step in time and the jump is refused. The
    gate enters every placement with its first step revealed, so it names that entry
    at bar 1, not the initial state's."""
    template = _jump_template().model_copy(update={"template_id": "p23_jump"})
    document = TemplateDoc(template=template)
    with (
        registered_templates(document),
        pytest.raises(
            UnsupportedRenderModeError,
            match=r"'p23_jump': dark repositioning between its own cues cannot be planned: "
            r"\(entered at cue 1 of its first cycle\) MH1 cue at 2020 ms: infeasible_transition",
        ),
    ):
        check_physical_templates(
            ["p23_jump"],
            beat_grid=physical_bars_grid(*[500.0] * 8),
            fixture_group=_speed_rig(45.0),
            initial_states=physical_job().moving_heads.initial_states,
            failure_mode="error",
        )


def _placement(
    template: Template,
    rig: FixtureGroup,
    grid: BeatGrid,
    start_bar: int,
    duration_bars: int,
    limits: tuple[int, int] | None = None,
) -> tuple[tuple[Any, ...], Any]:
    """A placement's gate key and what the gate concludes from it: the compiled cues
    relative to the section start, and the reposition errors, or the compile error."""
    phase_map = build_musical_phase_map(grid)
    start_limit, end_limit = limits or physical_cue_limits(phase_map, int(grid.duration_ms))
    context = TemplateCompileContext(
        section_id="placement",
        template_id=template.template_id,
        fixtures=build_fixture_contexts(rig_profile_from_fixture_group(rig), rig),
        beat_grid=grid,
        start_bar=start_bar,
        duration_bars=duration_bars,
        presets=rig.presets,
        topology=rig_topology(rig),
        fixture_group_id=rig.group_id,
    )
    key = pipeline_module._placement_key(context, phase_map, start_limit, end_limit)
    origin = context.start_ms
    try:
        compiled = compile_physical_template(
            template,
            context,
            phase_map=phase_map,
            start_limit_ms=start_limit,
            end_limit_ms=end_limit,
        )
    except (PhysicalCompileError, PhysicalChannelError, ValueError) as error:
        return key, type(error).__name__
    cues = []
    for segment in compiled.segments:
        channels = []
        for channel, value in sorted(segment.channels.items()):
            physical = value.physical
            if isinstance(physical, ContinuousTrajectory):
                channels.append((channel, [(p.t_ms - origin, p.value) for p in physical.points]))
            else:
                assert physical is not None and hasattr(physical, "events")
                channels.append((channel, [(e.t_ms - origin, e.state) for e in physical.events]))
        cues.append((segment.fixture_id, segment.t0_ms - origin, segment.t1_ms - origin, channels))
    profiles = {f.fixture_id: f.config.physical_profile for f in rig.expand_fixtures()}
    initial = dict.fromkeys(profiles, physical_job().moving_heads.initial_states["MH1"])
    entered, _, _ = pipeline_module._enter_section(
        compiled.segments,
        {},
        profiles,  # type: ignore[arg-type]
        initial,
        section_start_ms=origin,
        phase_map=phase_map,
        failure_mode="error",
    )
    result = plan_prepositions(
        entered,
        profiles,  # type: ignore[arg-type]
        initial_states=initial,
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=len(frame_times(int(grid.duration_ms))) * EFFECT_GRID_MS,
        failure_mode="error",
    )
    errors = sorted(
        (d.fixture_id, d.cue_ms - origin, d.code) for d in result.diagnostics if d.status == "error"
    )
    return key, (sorted(cues), errors)


def _jump_template() -> Template:
    first = sweep_step("a", 75.0, -20.0, period_beats=2.0)
    second = hold_step("b", 60.0, start=1.0)
    for step in (first, second):
        step["movement"]["physical"]["mode"] = "finite"
    return _template(first, second, cycle_bars=2.0, mode="ONCE", remainder_policy="TRUNCATE")


def test_equal_placement_keys_give_equal_compiles_and_verdicts() -> None:
    """From bar 2 on, placements with equal keys compile to the same cues shifted by
    whole frames and reposition alike: a plain move, a lagging head and an infeasible
    jump, on a steady grid off the frame grid and on one alternating frame alignment."""
    lagging = path_step(
        "f",
        "sweep",
        mode="finite",
        physical_distribution=[{"domains": ["pan"], "spread_cycles": 1.0}],
    )
    cases = (
        (_template(path_step("f", "sweep", mode="finite"), mode="ONCE"), physical_rig()),
        (_template(lagging, mode="ONCE"), _topology_rig(2)),
        (_jump_template(), _speed_rig(45.0)),
    )
    merged = 0
    for grid in (physical_bars_grid(*[500.0] * 8), physical_bars_grid(*[502.5] * 8)):
        for template, rig in cases:
            by_key: dict[tuple[Any, ...], Any] = {}
            for start_bar in range(2, 8):
                key, outcome = _placement(template, rig, grid, start_bar, min(9 - start_bar, 3))
                if key in by_key:
                    merged += 1
                    assert outcome == by_key[key], (template.template_id, start_bar)
                by_key.setdefault(key, outcome)
    assert merged >= 12


_KEY_ALIGNMENT, _KEY_BARS, _KEY_KNOTS, _KEY_START_LIMIT, _KEY_END_LIMIT = range(5)


def _uneven_bars_grid() -> BeatGrid:
    """500 ms beats on the frame grid, bars of 4, 3, 5, 5 and 3 beats."""
    beats = [float(500 * index) for index in range(25)]
    return BeatGrid(
        bar_boundaries=[0.0, 2000.0, 3500.0, 6000.0, 8500.0, 10000.0, 12000.0],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=12000.0,
    )


def _uneven_beats_grid() -> BeatGrid:
    """Four-beat bars of 2000 ms on the frame grid; bar 2's beats are uneven."""
    beats = [0.0, 500.0, 1000.0, 1500.0, 2000.0, 2400.0, 3000.0, 3500.0]
    beats += [4000.0 + 500.0 * index for index in range(13)]
    return BeatGrid(
        bar_boundaries=beats[::4],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=10000.0,
    )


@pytest.mark.parametrize(
    "component", [_KEY_ALIGNMENT, _KEY_BARS, _KEY_KNOTS, _KEY_START_LIMIT, _KEY_END_LIMIT]
)
def test_each_placement_key_entry_separates_placements_that_compile_differently(
    component: int,
) -> None:
    """For each key entry, two placements whose keys differ in that entry alone compile
    differently, so a key without it would merge them."""
    two_steps = _template(
        path_step("a", "sweep", mode="finite", period_beats=1.0, duration=1.0),
        path_step("b", "sweep", mode="finite", pan=20.0, period_beats=1.0, start=1.0),
        cycle_bars=2.0,
        mode="ONCE",
    )
    one = _template(path_step("f", "sweep", mode="finite"), mode="ONCE")
    rig = physical_rig()
    if component == _KEY_ALIGNMENT:  # 2010 ms bars: starts alternate 10 ms off the grid
        grid = physical_bars_grid(*[502.5] * 8)
        first = _placement(one, rig, grid, 2, 2)
        second = _placement(one, rig, grid, 3, 2)
    elif component == _KEY_BARS:  # bars of 3 then 5 beats against 5 then 3
        first = _placement(two_steps, rig, _uneven_bars_grid(), 2, 2)
        second = _placement(two_steps, rig, _uneven_bars_grid(), 4, 2)
    elif component == _KEY_KNOTS:
        first = _placement(one, rig, _uneven_beats_grid(), 2, 1)
        second = _placement(one, rig, _uneven_beats_grid(), 3, 1)
    elif component == _KEY_START_LIMIT:
        first = _placement(one, rig, _GRID, 2, 2, limits=(0, 12000))
        second = _placement(one, rig, _GRID, 2, 2, limits=(2500, 12000))
    else:
        first = _placement(one, rig, _GRID, 2, 2, limits=(0, 12000))
        second = _placement(one, rig, _GRID, 2, 2, limits=(0, 3000))
    (first_key, first_outcome), (second_key, second_outcome) = first, second
    differing = [
        index for index, (a, b) in enumerate(zip(first_key, second_key, strict=True)) if a != b
    ]
    assert differing == [component]
    assert first_outcome != second_outcome


def _once_reference(template_id: str, grid: BeatGrid, rig: FixtureGroup) -> bool:
    """Whether a ONCE template compiles and repositions at every start bar it fits,
    each section running to the song end (no window, no deduplication)."""
    template = REGISTRY.get(template_id).template
    phase_map = build_musical_phase_map(grid)
    start, end = physical_cue_limits(phase_map, int(grid.duration_ms))
    bars = sum(1 for bar in grid.bar_boundaries if bar < grid.duration_ms)
    profiles = {f.fixture_id: f.config.physical_profile for f in rig.expand_fixtures()}
    initial = dict.fromkeys(profiles, physical_job().moving_heads.initial_states["MH1"])
    for start_bar in range(1, bars + 1):
        if bars - start_bar + 1 < template.repeat.cycle_bars:
            continue
        context = TemplateCompileContext(
            section_id="reference",
            template_id=template_id,
            fixtures=build_fixture_contexts(rig_profile_from_fixture_group(rig), rig),
            beat_grid=grid,
            start_bar=start_bar,
            duration_bars=bars - start_bar + 1,
            presets=rig.presets,
            topology=rig_topology(rig),
            fixture_group_id=rig.group_id,
        )
        try:
            compiled = compile_physical_template(
                template, context, phase_map=phase_map, start_limit_ms=start, end_limit_ms=end
            )
        except (PhysicalChannelError, ValueError):
            return False
        cues, _, _ = pipeline_module._enter_section(
            compiled.segments,
            {},
            profiles,  # type: ignore[arg-type]
            initial,
            section_start_ms=context.start_ms,
            phase_map=phase_map,
            failure_mode="error",
        )
        result = plan_prepositions(
            cues,
            profiles,  # type: ignore[arg-type]
            initial_states=initial,
            locks=(),
            frame_ms=EFFECT_GRID_MS,
            sequence_end_ms=len(frame_times(int(grid.duration_ms))) * EFFECT_GRID_MS,
            failure_mode="error",
        )
        if result.has_errors:
            return False
    return True


def test_the_gate_agrees_with_every_once_placement_on_variable_tempo() -> None:
    """Differential fuzz: random variable-tempo grids, head speeds, ONCE templates (one
    or two finite steps, HOLD or TRUNCATE, with or without a lagging head). The gate
    admits exactly when every start-bar placement compiles and repositions, and an
    admitted template renders at a random start bar."""
    verdicts: set[bool] = set()
    for seed in range(24):
        rng = random.Random(seed)
        grid = physical_bars_grid(*(rng.choice((250.0, 350.0, 500.0, 700.0)) for _ in range(6)))
        lagging = rng.random() < 0.4
        rig = _speed_rig(rng.choice((90.0, 180.0, 720.0)), _topology_rig(2) if lagging else None)
        fields: dict[str, Any] = {}
        if lagging:
            fields["physical_distribution"] = [{"domains": ["pan"], "spread_cycles": 0.5}]
        extent = rng.uniform(10.0, 80.0)
        if rng.random() < 0.5:
            steps = [path_step("f", "sweep", mode="finite", pan_extent=extent, **fields)]
            cycle = 1.0
        else:
            steps = [
                sweep_step("out", 0.0, extent, period_beats=4.0, **fields),
                sweep_step("back", extent, -extent, period_beats=4.0, start=1.0, **fields),
            ]
            cycle = 2.0
        document = physical_template_doc(
            f"p23_fuzz_{seed}",
            steps,
            cycle_bars=cycle,
            mode="ONCE",
            remainder_policy=rng.choice(("HOLD_LAST_POSE", "TRUNCATE")),
        )
        initial = dict.fromkeys(
            [f.fixture_id for f in rig.expand_fixtures()],
            physical_job().moving_heads.initial_states["MH1"],
        )
        with registered_templates(document):
            template_id = document.template.template_id
            try:
                check_physical_templates(
                    [template_id],
                    beat_grid=grid,
                    fixture_group=rig,
                    initial_states=initial,
                    failure_mode="error",
                )
                admitted = True
            except UnsupportedRenderModeError:
                admitted = False
            assert admitted == _once_reference(template_id, grid, rig), seed
            verdicts.add(admitted)
            if admitted:
                start_bar = rng.randint(1, 7 - math.ceil(cycle))
                RenderingPipeline(
                    choreography_plan=physical_sections((template_id, start_bar, 6)),
                    beat_grid=grid,
                    fixture_group=rig,
                    job_config=physical_job(
                        initial_states={k: v.model_dump(mode="json") for k, v in initial.items()}
                    ),
                    output_path=None,
                ).render()
    assert verdicts == {True, False}


# --- Validation, dumps and the planner's view ---------------------------------------


@pytest.mark.parametrize(
    ("movement", "match"),
    [
        ({"shape": "circle", "mode": "finite"}, "circle is periodic"),
        ({"shape": "lissajous", "mode": "finite"}, "lissajous is periodic"),
        ({"shape": "circle", "lissajous_ratio": [1, 2]}, "lissajous_ratio"),
        ({"shape": "lissajous", "lissajous_ratio": [0, 2]}, "greater than 0"),
        ({"shape": "sine_pan", "tilt_extent_deg": 0.0, "transform": {}}, "transform"),
        ({"shape": "linear", "mode": "finite", "transform": {"reverse": True}}, "transform"),
        ({"shape": "circle", "transform": {"rotation_deg": math.inf}}, "finite"),
        ({"shape": "sweep", "tilt_extent_deg": 0.0, "transform": {"reverse": True}}, "reverse"),
        ({"shape": "sweep", "tilt_extent_deg": 5.0}, "tilt_extent_deg"),
        ({"shape": "sweep", "transform": {"rotation_deg": 90.0}}, "pan_extent_deg"),
    ],
)
def test_unsupported_path_variants_are_rejected(movement: dict[str, Any], match: str) -> None:
    payload = {
        "mode": "periodic",
        "start_pan_deg": 0.0,
        "start_tilt_deg": 0.0,
        "pan_extent_deg": 10.0,
        "tilt_extent_deg": 10.0,
        "period_beats": 1.0,
        **movement,
    }
    with pytest.raises(ValidationError, match=match):
        PhysicalMovementSpec.model_validate(payload)


def test_new_fields_stay_out_of_dumps_and_out_of_the_planner_surfaces() -> None:
    """Absent transform and ratio are left out of dumps; neither the planner's response
    schema nor its context schema exposes the repeat mode, so ONCE is invisible there."""
    dumped = _spec("circle").model_dump(mode="json")
    assert "transform" not in dumped and "lissajous_ratio" not in dumped
    for model in (ChoreographyPlan, MovingHeadPlanningContext):
        schema = json.dumps(model.model_json_schema())
        assert "RepeatMode" not in schema and "ONCE" not in schema


# --- Registry evidence for the new config paths ---------------------------------------

Component = Literal["rejected", "compiled"]

_COMPONENT_NOTES: dict[Component, str] = {
    "rejected": "exact path's alternative is rejected by physical validation or compile",
    "compiled": "exact path changes the physical compile result",
}

_PHYSICAL = "template.template.steps.movement.physical"


def _evidence_step() -> dict[str, Any]:
    """A 1:2 lissajous turned 30 degrees, every path field set."""
    step = path_step(
        "o", "lissajous", transform={"rotation_deg": 30.0, "reverse": False, "phase_cycles": 0.0}
    )
    step["movement"]["physical"]["lissajous_ratio"] = [1, 2]
    return step


def _transform(step: dict[str, Any]) -> dict[str, Any]:
    transform: dict[str, Any] = step["movement"]["physical"]["transform"]
    return transform


_MUTATIONS: dict[str, tuple[Component, Callable[[dict[str, Any]], Any]]] = {
    f"{_PHYSICAL}.transform": ("compiled", lambda s: s["movement"]["physical"].pop("transform")),
    f"{_PHYSICAL}.transform.rotation_deg": (
        "compiled",
        lambda s: _transform(s).update(rotation_deg=60.0),
    ),
    f"{_PHYSICAL}.transform.reverse": ("compiled", lambda s: _transform(s).update(reverse=True)),
    f"{_PHYSICAL}.transform.phase_cycles": (
        "compiled",
        lambda s: _transform(s).update(phase_cycles=0.25),
    ),
    f"{_PHYSICAL}.lissajous_ratio": (
        "compiled",
        lambda s: s["movement"]["physical"].update(lissajous_ratio=[3, 2]),
    ),
}
"""Per config path: the one component its alternative must change."""

PATH_PATHS = tuple(
    path
    for path, disposition in CONFIG_EFFECTS.items()
    if disposition.kind is ConfigDispositionKind.EFFECT_TEST
    and disposition.test_nodeid is not None
    and "::test_path_field_changes_compile[" in disposition.test_nodeid
)


def _compile_snapshot(step: dict[str, Any]) -> dict[str, Any]:
    try:
        segments = _compile(_template(step))
    except (ValidationError, PhysicalCompileError, PhysicalChannelError) as error:
        return {"rejected": f"{type(error).__name__}: {error}"}
    return {"compiled": [segment.model_dump(mode="json") for segment in segments]}


def test_path_evidence_paths_cover_every_mutation() -> None:
    """The registry, its notes and the mutation table describe the same evidence."""
    assert set(PATH_PATHS) == set(_MUTATIONS)
    for path, (component, _) in _MUTATIONS.items():
        assert CONFIG_EFFECTS[path].note == _COMPONENT_NOTES[component], path


@pytest.mark.parametrize("config_path", PATH_PATHS, ids=PATH_PATHS)
def test_path_field_changes_compile(config_path: str) -> None:
    """Each path field changes the compiled pan and tilt values."""
    component, mutate = _MUTATIONS[config_path]
    step = copy.deepcopy(_evidence_step())
    mutate(step)

    base = _compile_snapshot(_evidence_step())
    changed = _compile_snapshot(step)

    assert "rejected" not in base, base
    if component == "rejected":
        assert "rejected" in changed, changed
        return
    assert "rejected" not in changed, changed
    assert [s["channels"] for s in changed["compiled"]] != [s["channels"] for s in base["compiled"]]
