"""Tests for curve semantics helpers."""

from __future__ import annotations

import pytest

from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.semantics import center_curve, ensure_loop_ready

# Skip trivial enum tests


class TestCenterCurve:
    """Tests for center_curve function."""

    def test_center_translates_midpoint_to_half(self) -> None:
        """Shifts values so the midpoint sits at 0.5, leaving the span alone."""
        points = [
            CurvePoint(t=0.0, v=0.2),
            CurvePoint(t=0.5, v=0.6),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = center_curve(points)
        # min=0.2, max=1.0, midpoint=0.6 -> shift by -0.1. The 0.8 span is preserved.
        assert result[0].v == pytest.approx(0.1)
        assert result[1].v == pytest.approx(0.5)
        assert result[2].v == pytest.approx(0.9)

    def test_center_preserves_span_regardless_of_how_much_is_traversed(self) -> None:
        """P4-M6: centering must not turn a narrow arc into a full-range swing.

        Rescaling to full range made physical excursion a function of frequency —
        a window holding less than a full oscillation was stretched back out to
        [0, 1], so lowering the frequency *widened* the movement and inverted the
        SLOW/SMOOTH intent. Translation keeps excursion the amplitude's business.
        """
        narrow = [CurvePoint(t=0.0, v=0.5), CurvePoint(t=0.5, v=0.6), CurvePoint(t=1.0, v=0.55)]
        wide = [CurvePoint(t=0.0, v=0.0), CurvePoint(t=0.5, v=1.0), CurvePoint(t=1.0, v=0.5)]

        def span(points: list[CurvePoint]) -> float:
            return max(p.v for p in points) - min(p.v for p in points)

        assert span(center_curve(narrow)) == pytest.approx(span(narrow))
        assert span(center_curve(wide)) == pytest.approx(span(wide))
        assert span(center_curve(narrow)) < span(center_curve(wide))

    def test_center_constant_curve_maps_to_half(self) -> None:
        """Constant curve values all map to 0.5."""
        points = [
            CurvePoint(t=0.0, v=0.3),
            CurvePoint(t=0.5, v=0.3),
            CurvePoint(t=1.0, v=0.3),
        ]
        result = center_curve(points)
        for p in result:
            assert p.v == pytest.approx(0.5)

    def test_center_empty_raises(self) -> None:
        """Empty list raises ValueError."""
        with pytest.raises(ValueError, match="points cannot be empty"):
            center_curve([])

    def test_empty_raises(self) -> None:
        """Empty list raises ValueError."""
        with pytest.raises(ValueError, match="points cannot be empty"):
            ensure_loop_ready([])

    def test_invalid_mode_raises(self, non_loop_ready_points: list[CurvePoint]) -> None:
        """Invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="mode must be"):
            ensure_loop_ready(non_loop_ready_points, mode="invalid")

    def test_tolerance_parameter(self) -> None:
        """Tolerance parameter controls alignment check."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=0.0001),
        ]
        result_strict = ensure_loop_ready(points, tolerance=1e-6)
        result_relaxed = ensure_loop_ready(points, tolerance=1e-3)
        # Strict tolerance adjusts value, relaxed tolerance keeps original
        assert result_strict[-1].v == pytest.approx(0.0)
        assert result_relaxed[-1].v == pytest.approx(0.0001)

    def test_append_when_last_t_near_one(self) -> None:
        """When last t is near 1.0, replaces last point instead of adding."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=0.9999, v=1.0),  # Very close to 1.0
        ]
        result = ensure_loop_ready(points, mode="append", tolerance=1e-3)
        # Should replace last point, not add new one
        assert len(result) == 3
        assert result[-1].v == pytest.approx(0.0)

    def test_extend_continues_the_motion_instead_of_snapping_back(self) -> None:
        """P4-M5: the t=1.0 anchor carries the curve on, not back to the start.

        Curves are sampled on [0, 1), so the last sample sits short of 1.0 and the
        anchor decides what the final inter-sample step does. "append" writes the
        start value there, which on a physical head is a full-excursion snap inside
        the last 1/n of the segment.
        """
        points = [
            CurvePoint(t=0.0, v=0.2),
            CurvePoint(t=0.25, v=0.4),
            CurvePoint(t=0.5, v=0.6),
            CurvePoint(t=0.75, v=0.8),
        ]
        snapped = ensure_loop_ready(points, mode="append")
        extended = ensure_loop_ready(points, mode="extend")

        assert snapped[-1].v == pytest.approx(0.2)  # the defect: jumps back
        assert extended[-1].v == pytest.approx(1.0)  # carries on at the same slope
        assert extended[-1].t == pytest.approx(1.0)  # anchor still present for chases
        assert len(extended) == len(points) + 1

    def test_extend_keeps_the_final_step_no_larger_than_the_others(self) -> None:
        """The acceptance property behind P4-M5, stated directly."""
        points = [CurvePoint(t=i / 8, v=0.5 + 0.4 * (i / 8)) for i in range(8)]
        result = ensure_loop_ready(points, mode="extend")
        deltas = [abs(result[i + 1].v - result[i].v) for i in range(len(result) - 1)]
        assert deltas[-1] <= max(deltas[:-1]) + 1e-9

    def test_extend_clamps_extrapolation_into_range(self) -> None:
        """A steep final slope cannot push the anchor outside [0, 1]."""
        points = [CurvePoint(t=0.0, v=0.0), CurvePoint(t=0.5, v=0.5), CurvePoint(t=0.75, v=0.99)]
        result = ensure_loop_ready(points, mode="extend")
        assert result[-1].v == pytest.approx(1.0)

    def test_extend_adds_no_point_when_curve_already_reaches_one(self) -> None:
        """Nothing to anchor when the last sample is already at t=1.0."""
        points = [CurvePoint(t=0.0, v=0.2), CurvePoint(t=1.0, v=0.8)]
        assert ensure_loop_ready(points, mode="extend") == points
