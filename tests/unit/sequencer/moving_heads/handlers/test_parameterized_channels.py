"""Discriminating tests for schema-v2 parameterized channels."""

from __future__ import annotations

import pytest

from twinklr.core.config.fixtures.dmx import DmxMapping, ShutterMap
from twinklr.core.config.fixtures.instances import FixtureConfig
from twinklr.core.curves.dmx_conversion import dimmer_curve_to_dmx
from twinklr.core.sequencer.moving_heads.handlers.wheels import (
    DefaultColorHandler,
    DefaultGoboHandler,
    DefaultShutterHandler,
)


def _calibration(mapping: DmxMapping) -> dict[str, object]:
    return {"fixture_config": FixtureConfig(fixture_id="MH1", dmx_mapping=mapping)}


@pytest.mark.parametrize(
    ("handler", "params", "expected"),
    [
        (DefaultColorHandler(), {"preset": "red"}, 18),
        (DefaultShutterHandler(), {"pattern": "closed"}, 0),
        (DefaultShutterHandler(), {"pattern": "open"}, 255),
        (DefaultShutterHandler(), {"pattern": "strobe_slow"}, 64),
        (DefaultShutterHandler(), {"pattern": "strobe_medium"}, 127),
        (DefaultShutterHandler(), {"pattern": "strobe_fast"}, 190),
        (DefaultGoboHandler(), {"pattern": "circles"}, 20),
    ],
)
def test_handlers_resolve_fixture_maps(
    handler: object, params: dict[str, str], expected: int
) -> None:
    mapping = DmxMapping(
        pan_channel=1,
        tilt_channel=2,
        dimmer_channel=3,
        color_channel=4,
        shutter_channel=5,
        gobo_channel=6,
        gobo_map={"open": 0, "circles": 20},
    )
    result = handler.generate({**params, "calibration": _calibration(mapping)}, 8)

    assert result.static_dmx == expected
    assert result.curve is None
    assert result.trace.startswith("resolved:")


@pytest.mark.parametrize(
    ("handler", "params", "expected"),
    [
        (DefaultColorHandler(), {"preset": "uv"}, 7),
        (DefaultGoboHandler(), {"pattern": "stars"}, 9),
    ],
)
def test_unmappable_wheel_preset_falls_back_to_declared_open(
    handler: object, params: dict[str, str], expected: int
) -> None:
    mapping = DmxMapping(
        pan_channel=1,
        tilt_channel=2,
        dimmer_channel=3,
        color_channel=4,
        gobo_channel=6,
        color_map={"open": 7, "red": 18},
        gobo_map={"open": 9, "gobo1": 10},
    )
    result = handler.generate({**params, "calibration": _calibration(mapping)}, 8)

    assert result.static_dmx == expected
    assert result.trace.startswith("fallback:")


def test_unmapped_shutter_channel_uses_declared_default_in_traceable_result() -> None:
    mapping = DmxMapping(
        pan_channel=1,
        tilt_channel=2,
        dimmer_channel=3,
        shutter_channel=None,
        shutter_default=211,
    )
    result = DefaultShutterHandler().generate(
        {
            "pattern": "strobe_fast",
            "calibration": _calibration(mapping),
        },
        8,
    )

    assert result.static_dmx == 211
    assert result.trace == "fallback:shutter channel unavailable; default=211"


def test_shutter_pulse_is_the_only_new_axis_curve() -> None:
    mapping = DmxMapping(
        pan_channel=1,
        tilt_channel=2,
        dimmer_channel=3,
        shutter_channel=5,
    )
    result = DefaultShutterHandler().generate(
        {"pattern": "pulse", "calibration": _calibration(mapping)}, 8
    )

    assert result.static_dmx is None
    assert result.curve is not None
    assert {point.v for point in result.curve} == {0.0, 1.0}


@pytest.mark.parametrize(
    ("closed", "opened", "expected_values"),
    [
        (10, 200, [0.0, 1.0, 0.0, 1.0]),
        (200, 10, [1.0, 0.0, 1.0, 0.0]),
    ],
)
def test_shutter_pulse_follows_declared_closed_to_open_direction(
    closed: int, opened: int, expected_values: list[float]
) -> None:
    mapping = DmxMapping(
        pan_channel=1,
        tilt_channel=2,
        dimmer_channel=3,
        shutter_channel=5,
        shutter_map=ShutterMap(closed=closed, open=opened),
    )

    result = DefaultShutterHandler().generate(
        {"pattern": "pulse", "calibration": _calibration(mapping)}, 4
    )

    assert result.curve is not None
    assert [point.v for point in result.curve] == expected_values
    assert result.clamp_min_dmx == min(closed, opened)
    assert result.clamp_max_dmx == max(closed, opened)
    emitted = dimmer_curve_to_dmx(
        result.curve,
        clamp_min=result.clamp_min_dmx,
        clamp_max=result.clamp_max_dmx,
    )
    assert [round(point.v * 255) for point in emitted] == [closed, opened, closed, opened]
