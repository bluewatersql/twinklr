"""Tests for curve modifiers."""

from __future__ import annotations

import pytest

from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.modifiers import (
    CurveModifier,
    bounce_curve,
    mirror_curve,
    ping_pong_curve,
    repeat_curve,
    reverse_curve,
)


class TestCurveModifierEnum:
    """Tests for CurveModifier enum."""

    def test_enum_values(self) -> None:
        """All expected modifier values exist."""
        assert CurveModifier.REVERSE.value == "reverse"
        assert CurveModifier.BOUNCE.value == "bounce"
        assert CurveModifier.MIRROR.value == "mirror"
        assert CurveModifier.REPEAT.value == "repeat"
        assert CurveModifier.PINGPONG.value == "pingpong"

    def test_enum_is_string(self) -> None:
        """CurveModifier is a string enum."""
        assert isinstance(CurveModifier.REVERSE, str)
        assert CurveModifier.REVERSE == "reverse"


class TestReverseCurve:
    """Tests for reverse_curve function."""

    def test_reverses_time_values(self, ramp_up_points: list[CurvePoint]) -> None:
        """Reverses t values (1 - t) while preserving values."""
        result = reverse_curve(ramp_up_points)
        # Original ramp goes from (t=0,v=0) to (t=1,v=1)
        # After reverse: time flips but values stay, so (t=0,v=1) to (t=1,v=0)
        assert result[0].t == pytest.approx(0.0)
        assert result[0].v == pytest.approx(1.0)
        assert result[1].t == pytest.approx(1.0)
        assert result[1].v == pytest.approx(0.0)

    def test_reverse_maintains_length(self, simple_linear_points: list[CurvePoint]) -> None:
        """Output has same length as input."""
        result = reverse_curve(simple_linear_points)
        assert len(result) == len(simple_linear_points)

    def test_double_reverse_restores_original(self, simple_linear_points: list[CurvePoint]) -> None:
        """Reversing twice restores original curve."""
        reversed_once = reverse_curve(simple_linear_points)
        reversed_twice = reverse_curve(reversed_once)
        for orig, restored in zip(simple_linear_points, reversed_twice, strict=True):
            assert orig.t == pytest.approx(restored.t)
            assert orig.v == pytest.approx(restored.v)

    def test_reverse_empty_list(self) -> None:
        """Empty list returns empty list."""
        result = reverse_curve([])
        assert result == []


class TestMirrorCurve:
    """Tests for mirror_curve function."""

    def test_mirrors_values_vertically(self, ramp_up_points: list[CurvePoint]) -> None:
        """Mirrors v values (1 - v) while preserving time."""
        result = mirror_curve(ramp_up_points)
        # Original ramp goes from (t=0,v=0) to (t=1,v=1)
        # After mirror: values flip but time stays, so (t=0,v=1) to (t=1,v=0)
        assert result[0].t == pytest.approx(0.0)
        assert result[0].v == pytest.approx(1.0)
        assert result[1].t == pytest.approx(1.0)
        assert result[1].v == pytest.approx(0.0)

    def test_mirror_maintains_length(self, simple_linear_points: list[CurvePoint]) -> None:
        """Output has same length as input."""
        result = mirror_curve(simple_linear_points)
        assert len(result) == len(simple_linear_points)

    def test_double_mirror_restores_original(self, simple_linear_points: list[CurvePoint]) -> None:
        """Mirroring twice restores original curve."""
        mirrored_once = mirror_curve(simple_linear_points)
        mirrored_twice = mirror_curve(mirrored_once)
        for orig, restored in zip(simple_linear_points, mirrored_twice, strict=True):
            assert orig.t == pytest.approx(restored.t)
            assert orig.v == pytest.approx(restored.v)

    def test_mirror_preserves_time(self, sine_wave_points: list[CurvePoint]) -> None:
        """Mirror preserves time values."""
        result = mirror_curve(sine_wave_points)
        for orig, mirrored in zip(sine_wave_points, result, strict=True):
            assert orig.t == mirrored.t


class TestBounceCurve:
    """Tests for bounce_curve function."""

    def test_bounce_transformation(self) -> None:
        """Bounce applies 1 - abs(v - 0.5) * 2 transformation."""
        points = [
            CurvePoint(t=0.0, v=0.0),  # 1 - abs(0-0.5)*2 = 1 - 1 = 0
            CurvePoint(t=0.5, v=0.5),  # 1 - abs(0.5-0.5)*2 = 1 - 0 = 1
            CurvePoint(t=1.0, v=1.0),  # 1 - abs(1-0.5)*2 = 1 - 1 = 0
        ]
        result = bounce_curve(points)
        assert result[0].v == pytest.approx(0.0)
        assert result[1].v == pytest.approx(1.0)
        assert result[2].v == pytest.approx(0.0)

    def test_bounce_maintains_length(self, simple_linear_points: list[CurvePoint]) -> None:
        """Output has same length as input."""
        result = bounce_curve(simple_linear_points)
        assert len(result) == len(simple_linear_points)

    def test_bounce_preserves_time(self, simple_linear_points: list[CurvePoint]) -> None:
        """Bounce preserves time values."""
        result = bounce_curve(simple_linear_points)
        for orig, bounced in zip(simple_linear_points, result, strict=True):
            assert orig.t == bounced.t


class TestPingPongCurve:
    """Tests for ping_pong_curve function."""

    def test_ping_pong_doubles_length(self, simple_linear_points: list[CurvePoint]) -> None:
        """Ping pong returns reversed + original (doubles length)."""
        result = ping_pong_curve(simple_linear_points)
        assert len(result) == len(simple_linear_points) * 2

    def test_ping_pong_structure(self, ramp_up_points: list[CurvePoint]) -> None:
        """First half is reversed, second half is original."""
        result = ping_pong_curve(ramp_up_points)
        # Ping pong creates reversed version followed by original
        n = len(ramp_up_points)
        # First half is reversed
        assert result[0] == ramp_up_points[-1]
        # Second half is original
        assert result[n] == ramp_up_points[0]

    def test_ping_pong_empty_list(self) -> None:
        """Empty list returns empty list."""
        result = ping_pong_curve([])
        assert result == []


class TestRepeatCurve:
    """Tests for repeat_curve function."""

    def test_repeat_doubles_length(self, simple_linear_points: list[CurvePoint]) -> None:
        """Repeat returns original * 2 (doubles length)."""
        result = repeat_curve(simple_linear_points)
        assert len(result) == len(simple_linear_points) * 2

    def test_repeat_structure(self, ramp_up_points: list[CurvePoint]) -> None:
        """Both halves are identical to original."""
        result = repeat_curve(ramp_up_points)
        n = len(ramp_up_points)
        # First half equals original
        assert result[:n] == ramp_up_points
        # Second half equals original
        assert result[n:] == ramp_up_points

    def test_repeat_empty_list(self) -> None:
        """Empty list returns empty list."""
        result = repeat_curve([])
        assert result == []
