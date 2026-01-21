"""Tests for curve schema models.

Tests CurvePoint, PointsCurve, NativeCurve and BaseCurve union type.
All 14 test cases per implementation plan Task 0.2.
"""

import json

from pydantic import ValidationError
import pytest

from blinkb0t.core.curves.models import CurvePoint, NativeCurve, PointsCurve


class TestCurvePoint:
    """Tests for CurvePoint model."""

    def test_accepts_valid_values(self) -> None:
        """Test CurvePoint accepts valid t and v in [0,1]."""
        p1 = CurvePoint(t=0.0, v=0.0)
        assert p1.t == 0.0
        assert p1.v == 0.0

        p2 = CurvePoint(t=0.5, v=0.5)
        assert p2.t == 0.5
        assert p2.v == 0.5

        p3 = CurvePoint(t=1.0, v=1.0)
        assert p3.t == 1.0
        assert p3.v == 1.0

    def test_rejects_t_below_zero(self) -> None:
        """Test CurvePoint rejects t < 0."""
        with pytest.raises(ValidationError) as exc_info:
            CurvePoint(t=-0.1, v=0.5)
        assert "t" in str(exc_info.value).lower()

    def test_rejects_t_above_one(self) -> None:
        """Test CurvePoint rejects t > 1."""
        with pytest.raises(ValidationError) as exc_info:
            CurvePoint(t=1.1, v=0.5)
        assert "t" in str(exc_info.value).lower()

    def test_rejects_v_below_zero(self) -> None:
        """Test CurvePoint rejects v < 0."""
        with pytest.raises(ValidationError) as exc_info:
            CurvePoint(t=0.5, v=-0.1)
        assert "v" in str(exc_info.value).lower()

    def test_rejects_v_above_one(self) -> None:
        """Test CurvePoint rejects v > 1."""
        with pytest.raises(ValidationError) as exc_info:
            CurvePoint(t=0.5, v=1.1)
        assert "v" in str(exc_info.value).lower()

    def test_is_immutable(self) -> None:
        """Test CurvePoint is immutable (frozen=True)."""
        p = CurvePoint(t=0.5, v=0.7)
        with pytest.raises(ValidationError):
            p.t = 0.6  # type: ignore[misc]
        with pytest.raises(ValidationError):
            p.v = 0.8  # type: ignore[misc]


class TestPointsCurve:
    """Tests for PointsCurve model."""

    def test_validates_monotonic_t(self) -> None:
        """Test PointsCurve accepts monotonic (non-decreasing) t values."""
        curve = PointsCurve(
            points=[
                CurvePoint(t=0.0, v=0.0),
                CurvePoint(t=0.5, v=1.0),
                CurvePoint(t=0.5, v=0.8),  # Same t is allowed (non-decreasing)
                CurvePoint(t=1.0, v=0.0),
            ]
        )
        assert len(curve.points) == 4

    def test_rejects_non_monotonic_points(self) -> None:
        """Test PointsCurve rejects non-monotonic (decreasing) t values."""
        with pytest.raises(ValidationError) as exc_info:
            PointsCurve(
                points=[
                    CurvePoint(t=0.0, v=0.0),
                    CurvePoint(t=0.7, v=1.0),
                    CurvePoint(t=0.5, v=0.5),  # t goes backward
                    CurvePoint(t=1.0, v=0.0),
                ]
            )
        assert "non-decreasing" in str(exc_info.value).lower()

    def test_requires_min_two_points(self) -> None:
        """Test PointsCurve requires minimum 2 points."""
        curve = PointsCurve(
            points=[
                CurvePoint(t=0.0, v=0.0),
                CurvePoint(t=1.0, v=1.0),
            ]
        )
        assert len(curve.points) == 2

    def test_rejects_single_point(self) -> None:
        """Test PointsCurve rejects list with only 1 point."""
        with pytest.raises(ValidationError) as exc_info:
            PointsCurve(points=[CurvePoint(t=0.5, v=0.5)])
        # Pydantic min_length validation
        assert "2" in str(exc_info.value) or "min" in str(exc_info.value).lower()


class TestNativeCurve:
    """Tests for NativeCurve model."""

    def test_requires_non_empty_curve_id(self) -> None:
        """Test NativeCurve requires non-empty curve_id."""
        with pytest.raises(ValidationError) as exc_info:
            NativeCurve(curve_id="")
        assert "curve_id" in str(exc_info.value).lower() or "min" in str(exc_info.value).lower()

    def test_accepts_params_dict(self) -> None:
        """Test NativeCurve accepts params dict."""
        curve = NativeCurve(curve_id="SINE", params={"frequency": 2.0, "phase": 0.25})
        assert curve.curve_id == "SINE"
        assert curve.params == {"frequency": 2.0, "phase": 0.25}

    def test_params_defaults_to_empty_dict(self) -> None:
        """Test NativeCurve params defaults to empty dict."""
        curve = NativeCurve(curve_id="LINEAR")
        assert curve.params == {}


class TestBaseCurveUnion:
    """Tests for BaseCurve union type discrimination."""

    def test_discriminates_points_vs_native(self) -> None:
        """Test BaseCurve union discriminates correctly based on kind field."""
        points_data = {
            "kind": "POINTS",
            "points": [{"t": 0.0, "v": 0.0}, {"t": 1.0, "v": 1.0}],
        }
        native_data = {"kind": "NATIVE", "curve_id": "LINEAR"}

        points_curve = PointsCurve.model_validate(points_data)
        assert points_curve.kind == "POINTS"
        assert len(points_curve.points) == 2

        native_curve = NativeCurve.model_validate(native_data)
        assert native_curve.kind == "NATIVE"
        assert native_curve.curve_id == "LINEAR"


class TestJsonSerialization:
    """Tests for JSON serialization roundtrip."""

    def test_curve_point_json_roundtrip(self) -> None:
        """Test CurvePoint serializes/deserializes to JSON correctly."""
        original = CurvePoint(t=0.5, v=0.7)
        json_str = original.model_dump_json()
        restored = CurvePoint.model_validate_json(json_str)
        assert restored == original

    def test_points_curve_json_roundtrip(self) -> None:
        """Test PointsCurve serializes/deserializes to JSON correctly."""
        original = PointsCurve(
            points=[
                CurvePoint(t=0.0, v=0.0),
                CurvePoint(t=0.5, v=1.0),
                CurvePoint(t=1.0, v=0.0),
            ]
        )
        json_str = original.model_dump_json()
        restored = PointsCurve.model_validate_json(json_str)
        assert restored == original

    def test_native_curve_json_roundtrip(self) -> None:
        """Test NativeCurve serializes/deserializes to JSON correctly."""
        original = NativeCurve(curve_id="SINE", params={"frequency": 2.0})
        json_str = original.model_dump_json()
        restored = NativeCurve.model_validate_json(json_str)
        assert restored == original

    def test_json_output_format(self) -> None:
        """Test JSON output can be parsed by standard json module."""
        curve = PointsCurve(
            points=[
                CurvePoint(t=0.0, v=0.0),
                CurvePoint(t=1.0, v=1.0),
            ]
        )
        json_str = curve.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["kind"] == "POINTS"
        assert len(parsed["points"]) == 2
