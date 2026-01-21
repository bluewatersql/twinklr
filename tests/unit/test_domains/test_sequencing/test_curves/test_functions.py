"""Tests for curve generation functions.

Tests pure mathematical functions extracted from CustomCurveProvider.
"""

import numpy as np

from blinkb0t.core.domains.sequencing.infrastructure.curves.functions import (
    anticipate,
    bezier,
    bounce_in,
    bounce_out,
    cosine,
    ease_in_cubic,
    ease_in_out_cubic,
    ease_in_out_quad,
    ease_in_out_sine,
    ease_in_quad,
    ease_in_sine,
    ease_out_cubic,
    ease_out_quad,
    ease_out_sine,
    elastic_in,
    elastic_out,
    lissajous,
    overshoot,
    perlin_noise,
    s_curve,
    smooth_step,
    smoother_step,
    square,
    triangle,
)


def test_cosine():
    """Test cosine wave generation."""
    t = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    result = cosine(t)

    # Cosine starts at 1, dips to 0 at middle, returns to 1
    assert np.isclose(result[0], 1.0)  # t=0
    assert np.isclose(result[2], 0.0)  # t=0.5 (middle)
    assert np.isclose(result[4], 1.0)  # t=1.0
    assert all(0.0 <= v <= 1.0 for v in result)


def test_triangle():
    """Test triangle wave generation."""
    t = np.array([0.0, 0.5, 1.0])
    result = triangle(t)

    assert np.isclose(result[0], 0.0)  # starts at 0
    assert np.isclose(result[1], 1.0)  # peaks at 0.5
    assert np.isclose(result[2], 0.0)  # returns to 0
    assert all(0.0 <= v <= 1.0 for v in result)


def test_s_curve():
    """Test S-curve (sigmoid) generation."""
    t = np.array([0.0, 0.5, 1.0])
    result = s_curve(t)

    assert np.isclose(result[0], 0.0, atol=0.01)  # starts near 0
    assert np.isclose(result[1], 0.5, atol=0.01)  # middle at 0.5
    assert np.isclose(result[2], 1.0, atol=0.01)  # ends near 1
    assert all(0.0 <= v <= 1.0 for v in result)


def test_ease_in_sine():
    """Test ease-in sine function."""
    t = np.array([0.0, 0.5, 1.0])
    result = ease_in_sine(t)

    assert np.isclose(result[0], 0.0)  # starts at 0
    assert np.isclose(result[2], 1.0)  # ends at 1
    assert 0.0 < result[1] < 1.0  # smooth in between
    assert all(0.0 <= v <= 1.0 for v in result)


def test_ease_out_sine():
    """Test ease-out sine function."""
    t = np.array([0.0, 0.5, 1.0])
    result = ease_out_sine(t)

    assert np.isclose(result[0], 0.0)  # starts at 0
    assert np.isclose(result[2], 1.0)  # ends at 1
    assert 0.0 < result[1] < 1.0  # smooth in between
    assert all(0.0 <= v <= 1.0 for v in result)


def test_ease_in_quad():
    """Test ease-in quadratic function."""
    t = np.array([0.0, 0.5, 1.0])
    result = ease_in_quad(t)

    assert np.isclose(result[0], 0.0)  # t²: 0² = 0
    assert np.isclose(result[1], 0.25)  # 0.5² = 0.25
    assert np.isclose(result[2], 1.0)  # 1² = 1
    assert all(0.0 <= v <= 1.0 for v in result)


def test_smooth_step():
    """Test smooth-step function."""
    t = np.array([0.0, 0.5, 1.0])
    result = smooth_step(t)

    assert np.isclose(result[0], 0.0)  # starts at 0
    assert np.isclose(result[1], 0.5)  # middle at 0.5
    assert np.isclose(result[2], 1.0)  # ends at 1
    assert all(0.0 <= v <= 1.0 for v in result)


def test_bounce_out():
    """Test bounce-out function."""
    t = np.linspace(0, 1, 50)
    result = bounce_out(t)

    assert np.isclose(result[0], 0.0, atol=0.1)  # starts near 0
    assert np.isclose(result[-1], 1.0, atol=0.01)  # ends at 1
    # Should have some values that dip below the linear interpolation (bouncing)
    assert all(0.0 <= v <= 1.1 for v in result)  # Allow slight overshoot


def test_elastic_out():
    """Test elastic-out function."""
    t = np.linspace(0, 1, 50)
    result = elastic_out(t)

    assert np.isclose(result[0], 0.0)  # starts at 0
    assert np.isclose(result[-1], 1.0)  # ends at 1
    # Elastic allows overshoot
    assert any(v > 1.0 for v in result[1:-1])  # Should overshoot in middle


def test_all_functions_return_correct_shape():
    """Test that all functions return arrays of the same shape as input."""
    t = np.linspace(0, 1, 20)

    functions = [
        cosine,
        triangle,
        s_curve,
        square,
        smooth_step,
        smoother_step,
        ease_in_sine,
        ease_out_sine,
        ease_in_out_sine,
        ease_in_quad,
        ease_out_quad,
        ease_in_out_quad,
        ease_in_cubic,
        ease_out_cubic,
        ease_in_out_cubic,
        bounce_in,
        bounce_out,
        elastic_in,
        elastic_out,
        anticipate,
        overshoot,
        perlin_noise,
        lissajous,
        bezier,
    ]

    for func in functions:
        result = func(t)
        assert result.shape == t.shape, f"{func.__name__} returned wrong shape"
        assert len(result) == len(t), f"{func.__name__} returned wrong length"


def test_functions_bounded():
    """Test that most functions stay within [0, 1] bounds (except elastic which overshoots)."""
    t = np.linspace(0, 1, 100)

    bounded_functions = [
        cosine,
        triangle,
        s_curve,
        square,
        smooth_step,
        smoother_step,
        ease_in_sine,
        ease_out_sine,
        ease_in_out_sine,
        ease_in_quad,
        ease_out_quad,
        ease_in_out_quad,
        ease_in_cubic,
        ease_out_cubic,
        ease_in_out_cubic,
        anticipate,
        overshoot,
        perlin_noise,
        lissajous,
        bezier,
    ]

    for func in bounded_functions:
        result = func(t)
        assert np.all(result >= 0.0), f"{func.__name__} has values < 0"
        assert np.all(result <= 1.0), f"{func.__name__} has values > 1"
