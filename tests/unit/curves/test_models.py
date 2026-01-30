"""Tests for curve models."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from twinklr.core.curves.models import CurvePoint, NativeCurve, PointsCurve


class TestCurvePoint:
    """Tests for CurvePoint model."""

    def test_valid_point_creation(self) -> None:
        """Valid point with t and v in [0, 1] is created."""
        point = CurvePoint(t=0.5, v=0.7)
        assert point.t == 0.5
        assert point.v == 0.7

    def test_point_at_boundaries(self) -> None:
        """Points at boundary values 0 and 1 are valid."""
        p0 = CurvePoint(t=0.0, v=0.0)
        p1 = CurvePoint(t=1.0, v=1.0)
        assert p0.t == 0.0
        assert p1.v == 1.0

    def test_t_below_range_raises(self) -> None:
        """t value below 0 raises validation error."""
        with pytest.raises(ValidationError):
            CurvePoint(t=-0.1, v=0.5)

    def test_t_above_range_raises(self) -> None:
        """t value above 1 raises validation error."""
        with pytest.raises(ValidationError):
            CurvePoint(t=1.1, v=0.5)

    def test_v_below_range_raises(self) -> None:
        """v value below 0 raises validation error."""
        with pytest.raises(ValidationError):
            CurvePoint(t=0.5, v=-0.1)

    def test_v_above_range_raises(self) -> None:
        """v value above 1 raises validation error."""
        with pytest.raises(ValidationError):
            CurvePoint(t=0.5, v=1.1)

    def test_point_is_immutable(self) -> None:
        """CurvePoint is frozen (immutable)."""
        point = CurvePoint(t=0.5, v=0.5)
        with pytest.raises(ValidationError):
            point.t = 0.6  # type: ignore[misc]

    def test_extra_fields_forbidden(self) -> None:
        """Extra fields raise validation error."""
        with pytest.raises(ValidationError):
            CurvePoint(t=0.5, v=0.5, extra=1.0)  # type: ignore[call-arg]


class TestPointsCurve:
    """Tests for PointsCurve model."""

    def test_valid_points_curve(self, simple_linear_points: list[CurvePoint]) -> None:
        """Valid PointsCurve is created with monotonic points."""
        curve = PointsCurve(points=simple_linear_points)
        assert curve.kind == "POINTS"
        assert len(curve.points) == 3

    def test_minimum_two_points_required(self) -> None:
        """PointsCurve requires at least 2 points."""
        with pytest.raises(ValidationError):
            PointsCurve(points=[CurvePoint(t=0.0, v=0.0)])

    def test_empty_points_raises(self) -> None:
        """Empty points list raises validation error."""
        with pytest.raises(ValidationError):
            PointsCurve(points=[])

    def test_non_monotonic_t_raises(self) -> None:
        """Non-monotonic t values raise validation error."""
        with pytest.raises(ValidationError):
            PointsCurve(
                points=[
                    CurvePoint(t=0.0, v=0.0),
                    CurvePoint(t=0.8, v=0.5),
                    CurvePoint(t=0.5, v=1.0),  # Goes backwards
                ]
            )

    def test_equal_t_values_allowed(self) -> None:
        """Equal consecutive t values are allowed (non-decreasing)."""
        curve = PointsCurve(
            points=[
                CurvePoint(t=0.0, v=0.0),
                CurvePoint(t=0.5, v=0.3),
                CurvePoint(t=0.5, v=0.7),  # Same t is allowed
                CurvePoint(t=1.0, v=1.0),
            ]
        )
        assert len(curve.points) == 4

    def test_kind_discriminator_is_points(self) -> None:
        """Kind field is always 'POINTS'."""
        curve = PointsCurve(
            points=[
                CurvePoint(t=0.0, v=0.0),
                CurvePoint(t=1.0, v=1.0),
            ]
        )
        assert curve.kind == "POINTS"

    def test_extra_fields_forbidden(self) -> None:
        """Extra fields raise validation error."""
        with pytest.raises(ValidationError):
            PointsCurve(
                points=[
                    CurvePoint(t=0.0, v=0.0),
                    CurvePoint(t=1.0, v=1.0),
                ],
                extra="field",  # type: ignore[call-arg]
            )


class TestNativeCurve:
    """Tests for NativeCurve model."""

    def test_valid_native_curve(self) -> None:
        """Valid NativeCurve is created."""
        curve = NativeCurve(curve_id="SINE")
        assert curve.kind == "NATIVE"
        assert curve.curve_id == "SINE"
        assert curve.params == {}

    def test_native_curve_with_params(self) -> None:
        """NativeCurve with params is created."""
        curve = NativeCurve(curve_id="SINE", params={"frequency": 2.0, "phase": 0.5})
        assert curve.params["frequency"] == 2.0
        assert curve.params["phase"] == 0.5

    def test_curve_id_required(self) -> None:
        """curve_id is required."""
        with pytest.raises(ValidationError):
            NativeCurve()  # type: ignore[call-arg]

    def test_empty_curve_id_raises(self) -> None:
        """Empty curve_id raises validation error."""
        with pytest.raises(ValidationError):
            NativeCurve(curve_id="")

    def test_kind_discriminator_is_native(self) -> None:
        """Kind field is always 'NATIVE'."""
        curve = NativeCurve(curve_id="LINEAR")
        assert curve.kind == "NATIVE"

    def test_default_params_is_empty_dict(self) -> None:
        """Default params is empty dict."""
        curve = NativeCurve(curve_id="HOLD")
        assert curve.params == {}
        assert isinstance(curve.params, dict)

    def test_extra_fields_forbidden(self) -> None:
        """Extra fields raise validation error."""
        with pytest.raises(ValidationError):
            NativeCurve(curve_id="LINEAR", extra="field")  # type: ignore[call-arg]
