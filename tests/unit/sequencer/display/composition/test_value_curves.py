"""Tests for the value curve bridge utility."""

from __future__ import annotations

from twinklr.core.curves.library import CurveLibrary
from twinklr.core.curves.models import CurvePoint
from twinklr.core.sequencer.display.composition.value_curves import (
    build_value_curve_string,
    curve_points_to_xlights_string,
)


class TestCurvePointsToXlightsString:
    """Tests for curve_points_to_xlights_string."""

    def test_basic_two_point_curve(self) -> None:
        """Two anchored points produce a valid ValueCurve string."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = curve_points_to_xlights_string(
            points, param_id="Speed", min_val=0.0, max_val=100.0
        )
        assert result.startswith("Active=TRUE|")
        assert "Id=ID_VALUECURVE_Speed" in result
        assert "Type=Custom" in result
        assert "Min=0.00" in result
        assert "Max=100.00" in result
        assert "RV=FALSE" in result
        assert "Values=0.00:0.00;1.00:1.00" in result
        assert result.endswith("|")

    def test_multi_point_curve(self) -> None:
        """Multiple points are serialised in order."""
        points = [
            CurvePoint(t=0.0, v=0.2),
            CurvePoint(t=0.5, v=0.8),
            CurvePoint(t=1.0, v=0.2),
        ]
        result = curve_points_to_xlights_string(
            points, param_id="Twinkle_Count", min_val=0.0, max_val=25.0
        )
        assert "Values=0.00:0.20;0.50:0.80;1.00:0.20" in result
        assert "Max=25.00" in result

    def test_anchor_prepended_when_missing(self) -> None:
        """If first point t > 0.01, an anchor at t=0 is prepended."""
        points = [
            CurvePoint(t=0.1, v=0.5),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = curve_points_to_xlights_string(points, param_id="X", min_val=0.0, max_val=100.0)
        assert result.count("Values=") == 1
        values_part = result.split("Values=")[1].rstrip("|")
        pairs = values_part.split(";")
        assert pairs[0] == "0.00:0.50"

    def test_anchor_appended_when_missing(self) -> None:
        """If last point t < 0.99, an anchor at t=1 is appended."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.8, v=0.7),
        ]
        result = curve_points_to_xlights_string(points, param_id="Y", min_val=0.0, max_val=100.0)
        values_part = result.split("Values=")[1].rstrip("|")
        pairs = values_part.split(";")
        assert pairs[-1] == "1.00:0.70"

    def test_empty_points_returns_empty(self) -> None:
        """Empty point list produces empty string."""
        result = curve_points_to_xlights_string([], param_id="Z", min_val=0.0, max_val=100.0)
        assert result == ""

    def test_trailing_pipe(self) -> None:
        """xLights format requires trailing pipe."""
        points = [CurvePoint(t=0.0, v=0.5), CurvePoint(t=1.0, v=0.5)]
        result = curve_points_to_xlights_string(points, param_id="P", min_val=0.0, max_val=100.0)
        assert result.endswith("|")


class TestBuildValueCurveString:
    """Tests for build_value_curve_string (CurveLibrary integration)."""

    def test_sine_curve_produces_valid_string(self) -> None:
        """SINE curve generates a multi-point ValueCurve string."""
        result = build_value_curve_string(
            CurveLibrary.SINE,
            "ColorWash_Speed",
            min_val=0.0,
            max_val=100.0,
            num_points=10,
        )
        assert "Active=TRUE" in result
        assert "Id=ID_VALUECURVE_ColorWash_Speed" in result
        assert "Type=Custom" in result
        # Should have multiple value pairs
        values_part = result.split("Values=")[1].rstrip("|")
        pairs = values_part.split(";")
        assert len(pairs) >= 5

    def test_linear_curve(self) -> None:
        """LINEAR curve produces a ramp shape."""
        result = build_value_curve_string(
            CurveLibrary.LINEAR,
            "Fan_Revolutions",
            min_val=0.0,
            max_val=500.0,
            num_points=5,
        )
        assert "Max=500.00" in result
        assert "Active=TRUE" in result

    def test_amplitude_scaling(self) -> None:
        """Amplitude parameter is passed through to curve generation."""
        full = build_value_curve_string(
            CurveLibrary.SINE,
            "Test",
            amplitude=1.0,
            num_points=10,
        )
        half = build_value_curve_string(
            CurveLibrary.SINE,
            "Test",
            amplitude=0.5,
            num_points=10,
        )
        # Different amplitudes should produce different value strings
        assert full != half

    def test_invalid_curve_raises(self) -> None:
        """Unknown curve ID raises ValueError via the generator."""
        import pytest

        from twinklr.core.curves.generator import CurveGenerator

        gen = CurveGenerator()
        with pytest.raises(ValueError, match="not registered"):
            gen.generate_custom_points("nonexistent_curve_id_xyz")
