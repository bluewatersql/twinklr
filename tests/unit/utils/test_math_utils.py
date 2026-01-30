"""Tests for math utility functions."""

from __future__ import annotations

from twinklr.core.utils.math import clamp, lerp


def test_clamp_within_range():
    """Test clamping values within range."""
    assert clamp(5, 0, 10) == 5
    assert clamp(0, 0, 10) == 0
    assert clamp(10, 0, 10) == 10


def test_clamp_below_min():
    """Test clamping values below minimum."""
    assert clamp(-5, 0, 10) == 0
    assert clamp(-100, 0, 10) == 0


def test_clamp_above_max():
    """Test clamping values above maximum."""
    assert clamp(15, 0, 10) == 10
    assert clamp(100, 0, 10) == 10


def test_clamp_with_floats():
    """Test clamping with float values."""
    assert clamp(5.5, 0.0, 10.0) == 5.5
    assert clamp(-1.5, 0.0, 10.0) == 0.0
    assert clamp(11.5, 0.0, 10.0) == 10.0


def test_clamp_with_negative_range():
    """Test clamping with negative range."""
    assert clamp(-5, -10, -1) == -5
    assert clamp(-15, -10, -1) == -10
    assert clamp(0, -10, -1) == -1


def test_lerp_basic():
    """Test basic linear interpolation."""
    assert lerp(0.0, 10.0, 0.0) == 0.0
    assert lerp(0.0, 10.0, 1.0) == 10.0
    assert lerp(0.0, 10.0, 0.5) == 5.0


def test_lerp_with_negative_values():
    """Test lerp with negative values."""
    assert lerp(-10.0, 10.0, 0.5) == 0.0
    assert lerp(-5.0, 5.0, 0.0) == -5.0
    assert lerp(-5.0, 5.0, 1.0) == 5.0


def test_lerp_extrapolation():
    """Test lerp with t outside [0, 1] range."""
    # Below 0
    assert lerp(0.0, 10.0, -0.5) == -5.0

    # Above 1
    assert lerp(0.0, 10.0, 1.5) == 15.0


def test_clamp_integer_result():
    """Test that clamp preserves integer type when appropriate."""
    result = clamp(5, 0, 10)
    assert isinstance(result, int)


def test_clamp_float_result():
    """Test that clamp preserves float type."""
    result = clamp(5.5, 0.0, 10.0)
    assert isinstance(result, float)


def test_lerp_result_type():
    """Test that lerp returns float."""
    result = lerp(0.0, 10.0, 0.5)
    assert isinstance(result, float)
