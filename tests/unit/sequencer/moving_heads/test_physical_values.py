"""Typed physical channel values: an additive alternative to legacy DMX/curve values."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
import pytest

from tests.golden.harness import RIGS, build_fixture_group
from tests.support.mh_physical import profile_payload
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup
from twinklr.core.curves.generator import CurveGenerator
from twinklr.core.curves.models import CurvePoint, PointsCurve
from twinklr.core.sequencer.models.enum import BlendMode, ChannelName, TransitionMode
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
from twinklr.core.sequencer.models.transition import (
    Boundary,
    BoundaryType,
    TransitionHint,
    TransitionPlan,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.channel_blender import ChannelBlender
from twinklr.core.sequencer.moving_heads.compile.transition_segment_compiler import (
    TransitionSegmentCompiler,
)
from twinklr.core.sequencer.moving_heads.export.dmx_settings_builder import DmxSettingsBuilder
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts


def _pan(*points: tuple[int, float]) -> ContinuousTrajectory:
    return ContinuousTrajectory(
        unit="degree",
        points=tuple(PhysicalPoint(t_ms=t, value=v) for t, v in points),
        interpolation="linear",
    )


def _shutter(*events: tuple[int, str]) -> DiscreteTrajectory:
    return DiscreteTrajectory(events=tuple(DiscretePoint(t_ms=t, state=s) for t, s in events))


_CURVE = PointsCurve(points=[CurvePoint(t=0.0, v=0.0), CurvePoint(t=1.0, v=1.0)])


def test_physical_values_cannot_mix_with_legacy_curve() -> None:
    trajectory = _pan((0, 0.0), (1000, 90.0))

    value = ChannelValue(channel=ChannelName.PAN, physical=trajectory)
    assert value.physical == trajectory
    assert (value.static_dmx, value.curve) == (None, None)

    with pytest.raises(ValidationError, match="physical"):
        ChannelValue(channel=ChannelName.PAN, static_dmx=1, physical=trajectory)
    with pytest.raises(ValidationError, match="physical"):
        ChannelValue(channel=ChannelName.PAN, curve=_CURVE, physical=trajectory)


@pytest.mark.parametrize(
    "legacy",
    [
        pytest.param({"value_points": [CurvePoint(t=0.0, v=0.5)]}, id="value-points"),
        pytest.param({"base_dmx": 128}, id="base"),
        pytest.param({"amplitude_dmx": 64}, id="amplitude"),
        pytest.param({"offset_centered": True}, id="offset-centered"),
        pytest.param({"clamp_min": 10}, id="clamp-min"),
        pytest.param({"clamp_max": 200}, id="clamp-max"),
        pytest.param({"blend_mode": BlendMode.ADD}, id="blend-mode"),
    ],
)
def test_physical_value_rejects_legacy_composition_fields(legacy: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="legacy"):
        ChannelValue(channel=ChannelName.PAN, physical=_pan((0, 0.0)), **legacy)


def test_legacy_values_are_unchanged() -> None:
    """Exactly one of static_dmx or curve remains the legacy rule, with its messages."""
    assert ChannelValue(channel=ChannelName.DIMMER, static_dmx=255).physical is None
    assert (
        ChannelValue(
            channel=ChannelName.PAN,
            curve=_CURVE,
            value_points=[CurvePoint(t=0.0, v=0.5)],
            base_dmx=128,
            amplitude_dmx=64,
            offset_centered=True,
            clamp_min=10,
            clamp_max=200,
        ).curve
        == _CURVE
    )

    with pytest.raises(ValidationError, match="must set either static_dmx or curve"):
        ChannelValue(channel=ChannelName.PAN)
    with pytest.raises(ValidationError, match="cannot set both static_dmx and curve"):
        ChannelValue(channel=ChannelName.PAN, static_dmx=1, curve=_CURVE)


@pytest.mark.parametrize(
    ("channel", "value"),
    [
        pytest.param(ChannelName.PAN, _shutter((0, "open")), id="discrete-pan"),
        pytest.param(ChannelName.DIMMER, _pan((0, 0.0)), id="degree-dimmer"),
        pytest.param(
            ChannelName.TILT,
            ContinuousTrajectory(
                unit="normalized", points=(PhysicalPoint(t_ms=0, value=0.5),), interpolation="hold"
            ),
            id="normalized-tilt",
        ),
        pytest.param(ChannelName.SHUTTER, _pan((0, 0.0)), id="continuous-shutter"),
    ],
)
def test_physical_value_kind_and_unit_match_the_channel(
    channel: ChannelName, value: ContinuousTrajectory | DiscreteTrajectory
) -> None:
    with pytest.raises(ValidationError, match=str(channel.value)):
        ChannelValue(channel=channel, physical=value)


def test_trajectories_require_strictly_increasing_finite_times_and_values() -> None:
    with pytest.raises(ValidationError, match="strictly increasing"):
        _pan((0, 0.0), (0, 10.0))
    with pytest.raises(ValidationError, match="strictly increasing"):
        _shutter((40, "open"), (20, "closed"))
    with pytest.raises(ValidationError):
        PhysicalPoint(t_ms=0, value=float("nan"))
    with pytest.raises(ValidationError):
        PhysicalPoint(t_ms=-20, value=0.0)
    with pytest.raises(ValidationError, match="normalized"):
        ContinuousTrajectory(
            unit="normalized", points=(PhysicalPoint(t_ms=0, value=1.5),), interpolation="hold"
        )
    with pytest.raises(ValidationError):
        ContinuousTrajectory(unit="degree", points=(), interpolation="hold")


def test_segment_carries_physical_values() -> None:
    segment = FixtureSegment(
        section_id="s",
        segment_id="seg",
        step_id="step",
        template_id="t",
        fixture_id="MH1",
        t0_ms=0,
        t1_ms=1000,
        channels={
            ChannelName.PAN: ChannelValue(
                channel=ChannelName.PAN, physical=_pan((0, 0.0), (1000, 90.0))
            ),
            ChannelName.SHUTTER: ChannelValue(
                channel=ChannelName.SHUTTER, physical=_shutter((0, "closed"), (980, "open"))
            ),
        },
    )

    restored = FixtureSegment.model_validate(segment.model_dump(mode="json"))
    assert restored == segment


def test_render_lock_is_a_half_open_nonempty_span() -> None:
    lock = RenderLock(
        start_ms=0,
        end_ms=4000,
        fixture_ids=("MH1",),
        channels=(ChannelName.PAN, ChannelName.TILT),
    )
    assert lock.end_ms == 4000

    with pytest.raises(ValidationError, match="end_ms"):
        RenderLock(start_ms=40, end_ms=40, fixture_ids=("MH1",), channels=(ChannelName.PAN,))
    with pytest.raises(ValidationError):
        RenderLock(start_ms=0, end_ms=40, fixture_ids=(), channels=(ChannelName.PAN,))
    with pytest.raises(ValidationError):
        RenderLock(start_ms=0, end_ms=40, fixture_ids=("MH1",), channels=())


def test_profile_unsupported_values_raise_a_typed_error() -> None:
    profile = FixtureCapabilities.model_validate(profile_payload())
    narrowed = profile.model_copy(
        update={
            "axes": {
                **profile.axes,
                "pan": profile.axes["pan"].model_copy(update={"allowed_max": 90.0}),
            }
        }
    )

    check_physical_value("MH1", ChannelName.PAN, _pan((0, 0.0), (1000, 180.0)), profile)
    check_physical_value("MH1", ChannelName.SHUTTER, _shutter((0, "closed")), profile)

    with pytest.raises(PhysicalChannelError) as raised:
        check_physical_value("MH1", ChannelName.PAN, _pan((0, 0.0), (1000, 180.0)), narrowed)
    assert (raised.value.fixture_id, raised.value.channel, raised.value.time_ms) == (
        "MH1",
        ChannelName.PAN,
        1000,
    )
    assert "180.0" in raised.value.reason

    with pytest.raises(PhysicalChannelError, match="strobe") as raised:
        check_physical_value(
            "MH1", ChannelName.SHUTTER, _shutter((0, "closed"), (500, "strobe")), profile
        )
    assert raised.value.time_ms == 500

    with pytest.raises(PhysicalChannelError, match="gobo"):
        check_physical_value("MH1", ChannelName.GOBO, _shutter((0, "open")), profile)


def test_fixture_contexts_carry_the_physical_profile() -> None:
    payload = build_fixture_group(RIGS["mh4_minimal"]).model_dump(mode="python")
    payload["fixtures"][0]["config"]["physical_profile"] = profile_payload()
    group = FixtureGroup.model_validate(payload)

    contexts = {
        context.fixture_id: context
        for context in build_fixture_contexts(rig_profile_from_fixture_group(group), group)
    }

    assert contexts["MH1"].physical_profile == FixtureCapabilities.model_validate(profile_payload())
    assert contexts["MH2"].physical_profile is None


def _segment(fixture_id: str, channels: dict[ChannelName, ChannelValue]) -> FixtureSegment:
    return FixtureSegment(
        section_id="s",
        segment_id="seg",
        step_id="step",
        template_id="t",
        fixture_id=fixture_id,
        t0_ms=2000,
        t1_ms=3000,
        channels=channels,
    )


def _physical_pan() -> ChannelValue:
    return ChannelValue(channel=ChannelName.PAN, physical=_pan((2000, 0.0), (3000, 90.0)))


def test_legacy_exporter_refuses_a_physical_value() -> None:
    """The legacy settings builder would otherwise write nothing for the channel."""
    fixture = build_fixture_group(RIGS["mh4_minimal"]).expand_fixtures()[0]
    builder = DmxSettingsBuilder(fixture)
    legacy = ChannelValue(channel=ChannelName.DIMMER, static_dmx=200)
    assert "E_SLIDER_DMX" in builder.build_settings_string(
        _segment("MH1", {ChannelName.DIMMER: legacy})
    )

    with pytest.raises(PhysicalChannelError, match="legacy") as raised:
        builder.build_settings_string(
            _segment("MH1", {ChannelName.DIMMER: legacy, ChannelName.PAN: _physical_pan()})
        )
    assert (raised.value.fixture_id, raised.value.channel, raised.value.time_ms) == (
        "MH1",
        ChannelName.PAN,
        2000,
    )


@pytest.mark.parametrize("side", ["source", "target"])
def test_legacy_transition_blend_refuses_a_physical_value(side: str) -> None:
    """The legacy blender would otherwise read a physical value as DMX 128."""
    plan = TransitionPlan(
        transition_id="a_to_b",
        boundary=Boundary(
            type=BoundaryType.SECTION_BOUNDARY,
            source_id="a",
            target_id="b",
            time_ms=3000,
            bar_position=2.0,
        ),
        hint=TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=1.0),
        overlap_start_ms=2500,
        overlap_end_ms=3500,
        overlap_duration_ms=1000,
        fixtures=["MH1"],
    )
    legacy = [
        _segment("MH1", {ChannelName.PAN: ChannelValue(channel=ChannelName.PAN, static_dmx=1)})
    ]
    physical = [_segment("MH1", {ChannelName.PAN: _physical_pan()})]
    source, target = (physical, legacy) if side == "source" else (legacy, physical)
    compiler = TransitionSegmentCompiler(ChannelBlender(CurveGenerator()))
    assert compiler.compile_transition(plan, legacy, legacy)

    with pytest.raises(PhysicalChannelError, match="legacy") as raised:
        compiler.compile_transition(plan, source, target)
    assert (raised.value.fixture_id, raised.value.channel, raised.value.time_ms) == (
        "MH1",
        ChannelName.PAN,
        2500,
    )
