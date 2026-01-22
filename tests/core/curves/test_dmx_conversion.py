"""Tests for DMX conversion helpers."""

from blinkb0t.core.curves.dmx_conversion import dimmer_curve_to_dmx, movement_curve_to_dmx
from blinkb0t.core.curves.models import CurvePoint


def test_movement_curve_to_dmx_example() -> None:
    points = [
        CurvePoint(t=0.0, v=0.5),
        CurvePoint(t=0.25, v=1.0),
        CurvePoint(t=0.5, v=0.5),
        CurvePoint(t=0.75, v=0.0),
    ]
    result = movement_curve_to_dmx(
        points,
        base_dmx=45.0,
        amplitude_dmx=30.0,
        clamp_min=-270.0,
        clamp_max=270.0,
    )
    assert [p.v for p in result] == [45.0, 60.0, 45.0, 30.0]


def test_movement_curve_to_dmx_clamps() -> None:
    points = [CurvePoint(t=0.0, v=1.0)]
    result = movement_curve_to_dmx(
        points,
        base_dmx=300.0,
        amplitude_dmx=50.0,
        clamp_min=0.0,
        clamp_max=255.0,
    )
    assert result[0].v == 255.0


def test_dimmer_curve_to_dmx_maps() -> None:
    points = [CurvePoint(t=0.0, v=0.0), CurvePoint(t=1.0, v=1.0)]
    result = dimmer_curve_to_dmx(points, clamp_min=10.0, clamp_max=110.0)
    assert result[0].v == 10.0
    assert result[1].v == 110.0


def test_dimmer_curve_to_dmx_clamps() -> None:
    points = [CurvePoint(t=0.0, v=2.0)]
    result = dimmer_curve_to_dmx(points, clamp_min=0.0, clamp_max=100.0)
    assert result[0].v == 100.0
