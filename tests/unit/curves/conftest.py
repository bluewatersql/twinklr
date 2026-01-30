"""Shared pytest fixtures for curve tests."""

from __future__ import annotations

import pytest

from twinklr.core.curves.models import CurvePoint


@pytest.fixture
def simple_linear_points() -> list[CurvePoint]:
    """Create simple linear curve points from 0 to 1."""
    return [
        CurvePoint(t=0.0, v=0.0),
        CurvePoint(t=0.5, v=0.5),
        CurvePoint(t=1.0, v=1.0),
    ]


@pytest.fixture
def simple_hold_points() -> list[CurvePoint]:
    """Create simple hold curve points at 0.5."""
    return [
        CurvePoint(t=0.0, v=0.5),
        CurvePoint(t=0.5, v=0.5),
        CurvePoint(t=1.0, v=0.5),
    ]


@pytest.fixture
def sine_wave_points() -> list[CurvePoint]:
    """Create a simple sine-like wave pattern."""
    return [
        CurvePoint(t=0.0, v=0.5),
        CurvePoint(t=0.25, v=1.0),
        CurvePoint(t=0.5, v=0.5),
        CurvePoint(t=0.75, v=0.0),
        CurvePoint(t=1.0, v=0.5),
    ]


@pytest.fixture
def ramp_up_points() -> list[CurvePoint]:
    """Create ascending ramp points."""
    return [
        CurvePoint(t=0.0, v=0.0),
        CurvePoint(t=1.0, v=1.0),
    ]


@pytest.fixture
def ramp_down_points() -> list[CurvePoint]:
    """Create descending ramp points."""
    return [
        CurvePoint(t=0.0, v=1.0),
        CurvePoint(t=1.0, v=0.0),
    ]


@pytest.fixture
def loop_ready_points() -> list[CurvePoint]:
    """Create points with matching start/end values."""
    return [
        CurvePoint(t=0.0, v=0.5),
        CurvePoint(t=0.5, v=1.0),
        CurvePoint(t=1.0, v=0.5),
    ]


@pytest.fixture
def non_loop_ready_points() -> list[CurvePoint]:
    """Create points with non-matching start/end values."""
    return [
        CurvePoint(t=0.0, v=0.0),
        CurvePoint(t=0.5, v=0.5),
        CurvePoint(t=0.9, v=1.0),
    ]


@pytest.fixture
def dense_linear_points() -> list[CurvePoint]:
    """Create a dense linear curve for simplification tests."""
    n = 10
    return [CurvePoint(t=i / (n - 1), v=i / (n - 1)) for i in range(n)]


@pytest.fixture
def curved_points() -> list[CurvePoint]:
    """Create curved points that should not be simplified much."""
    return [
        CurvePoint(t=0.0, v=0.0),
        CurvePoint(t=0.25, v=0.1),
        CurvePoint(t=0.5, v=0.5),
        CurvePoint(t=0.75, v=0.9),
        CurvePoint(t=1.0, v=1.0),
    ]
