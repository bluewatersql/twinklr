"""Tests for curve library."""

from __future__ import annotations

import pytest

from twinklr.core.curves.library import CurveLibrary, build_default_registry

# Skip trivial enum value tests - Python guarantees enum behavior


class TestBuildDefaultRegistry:
    """Tests for build_default_registry function."""

    def test_default_samples_is_64(self) -> None:
        """Default samples is 64."""
        registry = build_default_registry()
        defn = registry.get(CurveLibrary.SINE.value)
        assert defn.default_samples == 64

    @pytest.mark.parametrize(
        "curve_id",
        [
            CurveLibrary.LINEAR.value,
            CurveLibrary.SINE.value,
            CurveLibrary.EASE_IN_OUT_CUBIC.value,
            CurveLibrary.BOUNCE_OUT.value,
        ],
    )
    def test_curves_can_generate_points(self, curve_id: str) -> None:
        """Curves can generate valid points."""
        registry = build_default_registry()
        defn = registry.get(curve_id)
        points = registry.resolve(defn)
        assert len(points) == 64
        for p in points:
            assert 0.0 <= p.t <= 1.0
            assert 0.0 <= p.v <= 1.0
