"""Tests for curve modifier system.

Tests the modifier registry and individual modifier functions.
"""

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveModifier
from blinkb0t.core.domains.sequencing.infrastructure.curves.modifiers import (
    apply_modifiers,
    reverse,
)
from blinkb0t.core.domains.sequencing.models.curves import CurvePoint


@pytest.fixture
def sample_points():
    """Create sample curve points for testing."""
    return [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=0.25, value=0.25),
        CurvePoint(time=0.5, value=0.5),
        CurvePoint(time=0.75, value=0.75),
        CurvePoint(time=1.0, value=1.0),
    ]


def test_reverse_modifier(sample_points):
    """Test reverse modifier inverts values."""
    result = reverse(sample_points)

    # Time should stay the same
    assert all(r.time == s.time for r, s in zip(result, sample_points, strict=False))

    # Values should be inverted (1.0 - value)
    assert result[0].value == pytest.approx(1.0)  # 1.0 - 0.0
    assert result[1].value == pytest.approx(0.75)  # 1.0 - 0.25
    assert result[2].value == pytest.approx(0.5)  # 1.0 - 0.5
    assert result[3].value == pytest.approx(0.25)  # 1.0 - 0.75
    assert result[4].value == pytest.approx(0.0)  # 1.0 - 1.0


def test_reverse_modifier_empty_list():
    """Test reverse modifier with empty list."""
    result = reverse([])
    assert result == []


def test_apply_modifiers_single(sample_points):
    """Test applying a single modifier."""
    result = apply_modifiers(sample_points, ["reverse"])

    # Should match reverse() output
    expected = reverse(sample_points)
    assert len(result) == len(expected)
    for r, e in zip(result, expected, strict=False):
        assert r.time == e.time
        assert r.value == pytest.approx(e.value)


def test_apply_modifiers_multiple(sample_points):
    """Test applying multiple modifiers in sequence."""
    # Reverse twice should return to original
    result = apply_modifiers(sample_points, ["reverse", "reverse"])

    assert len(result) == len(sample_points)
    for r, s in zip(result, sample_points, strict=False):
        assert r.time == s.time
        assert r.value == pytest.approx(s.value)


def test_apply_modifiers_empty_list(sample_points):
    """Test applying no modifiers returns original points."""
    result = apply_modifiers(sample_points, [])

    assert len(result) == len(sample_points)
    for r, s in zip(result, sample_points, strict=False):
        assert r.time == s.time
        assert r.value == s.value


def test_apply_modifiers_unknown_modifier_skipped(sample_points):
    """Test unknown modifiers are skipped gracefully."""
    result = apply_modifiers(sample_points, ["unknown", "reverse", "invalid"])

    # Should only apply reverse (unknown and invalid skipped)
    expected = reverse(sample_points)
    assert len(result) == len(expected)
    for r, e in zip(result, expected, strict=False):
        assert r.time == e.time
        assert r.value == pytest.approx(e.value)


def test_apply_modifiers_with_enum():
    """Test applying modifiers using CurveModifier enum."""
    points = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=1.0, value=1.0),
    ]

    # Use enum value directly
    result = apply_modifiers(points, [CurveModifier.REVERSE.value])

    assert result[0].value == pytest.approx(1.0)
    assert result[1].value == pytest.approx(0.0)


def test_modifier_preserves_point_count(sample_points):
    """Test modifiers don't change number of points."""
    result = apply_modifiers(sample_points, ["reverse"])
    assert len(result) == len(sample_points)


def test_modifier_preserves_time_values(sample_points):
    """Test modifiers don't modify time values."""
    result = apply_modifiers(sample_points, ["reverse"])

    for original, modified in zip(sample_points, result, strict=False):
        assert original.time == modified.time
