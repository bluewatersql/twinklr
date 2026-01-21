"""Tests for ValueCurveSpec hierarchy refactoring.

Tests the ValueCurveSpec model and CustomCurveSpec adapter.
Note: ValueCurveSpec is the native curve model, CustomCurveSpec is a separate dataclass.
"""

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import (
    CustomCurveSpec,
)
from blinkb0t.core.domains.sequencing.models.curves import CurvePoint, ValueCurveSpec


def test_valuecurvespec_creation():
    """Test creating a ValueCurveSpec (native curve)."""
    spec = ValueCurveSpec(
        type=NativeCurveType.SINE,
        p2=100.0,
        p4=128.0,
    )

    assert spec.type == NativeCurveType.SINE
    assert spec.p2 == 100.0
    assert spec.p4 == 128.0
    assert spec.p1 == 0.0  # Default
    assert spec.p3 == 0.0  # Default
    assert spec.reverse is False  # Default
    assert spec.min_val == 0  # Default
    assert spec.max_val == 255  # Default


def test_custom_spec_creation():
    """Test creating a CustomCurveSpec."""
    points = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=0.5, value=127.5),
        CurvePoint(time=1.0, value=255.0),
    ]

    spec = CustomCurveSpec(points=points)

    assert len(spec.points) == 3
    assert spec.points[0].time == 0.0
    assert spec.points[0].value == 0.0
    assert spec.points[2].time == 1.0
    assert spec.points[2].value == 255.0


def test_custom_spec_empty_points_list():
    """Test CustomCurveSpec validation rejects empty points list."""
    with pytest.raises(ValueError, match="Custom curve must have at least one point"):
        CustomCurveSpec(points=[])


def test_valuecurvespec_with_all_parameters():
    """Test ValueCurveSpec with all parameters set."""
    spec = ValueCurveSpec(
        type=NativeCurveType.PARABOLIC,
        p1=10.0,
        p2=50.0,
        p3=75.0,
        p4=100.0,
        reverse=True,
        min_val=50,
        max_val=200,
    )

    assert spec.type == NativeCurveType.PARABOLIC
    assert spec.p1 == 10.0
    assert spec.p2 == 50.0
    assert spec.p3 == 75.0
    assert spec.p4 == 100.0
    assert spec.reverse is True
    assert spec.min_val == 50
    assert spec.max_val == 200
