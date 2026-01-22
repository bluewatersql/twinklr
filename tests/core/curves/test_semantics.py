"""Tests for curve semantics helpers."""

import pytest

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.semantics import CurveKind, center_curve, ensure_loop_ready


def _points(values: list[float]) -> list[CurvePoint]:
    return [CurvePoint(t=i / (len(values) - 1), v=v) for i, v in enumerate(values)]


def test_curve_kind_enum() -> None:
    assert CurveKind.MOVEMENT_OFFSET.value == "movement_offset"
    assert CurveKind.DIMMER_ABSOLUTE.value == "dimmer_absolute"


def test_center_curve_normalizes_range() -> None:
    points = _points([2.0, 3.0, 4.0])
    centered = center_curve(points)
    values = [p.v for p in centered]
    assert values[0] == 0.0
    assert values[-1] == 1.0
    assert abs(values[1] - 0.5) < 1e-10


def test_center_curve_constant() -> None:
    points = _points([2.0, 2.0, 2.0])
    centered = center_curve(points)
    assert all(abs(p.v - 0.5) < 1e-10 for p in centered)


def test_center_curve_empty_raises() -> None:
    with pytest.raises(ValueError, match="points cannot be empty"):
        center_curve([])


def test_ensure_loop_ready_appends_endpoint() -> None:
    points = [
        CurvePoint(t=0.0, v=0.2),
        CurvePoint(t=0.5, v=0.8),
        CurvePoint(t=0.75, v=0.4),
    ]
    result = ensure_loop_ready(points, mode="append")
    assert result[-1].t == 1.0
    assert abs(result[-1].v - result[0].v) < 1e-10


def test_ensure_loop_ready_adjusts_last_value() -> None:
    points = [
        CurvePoint(t=0.0, v=0.2),
        CurvePoint(t=1.0, v=0.8),
    ]
    result = ensure_loop_ready(points, mode="adjust_last")
    assert result[-1].t == 1.0
    assert abs(result[-1].v - result[0].v) < 1e-10


def test_ensure_loop_ready_invalid_mode() -> None:
    points = [CurvePoint(t=0.0, v=0.1), CurvePoint(t=1.0, v=0.2)]
    with pytest.raises(ValueError, match="mode must be 'append' or 'adjust_last'"):
        ensure_loop_ready(points, mode="invalid")
