"""Test that tilt channel properly varies when movement pattern requires it."""

from __future__ import annotations

import pytest

from blinkb0t.core.curves.dmx_conversion import dimmer_curve_to_dmx
from blinkb0t.core.curves.models import CurvePoint


class TestTiltVariation:
    """Tests for tilt channel variation with boundary enforcement."""

    def test_tilt_with_variation_scales_to_boundaries(self) -> None:
        """Tilt curves with variation scale to full boundary range."""
        # Simulate a circle or bounce pattern with tilt variation
        tilt_curve = [
            CurvePoint(t=0.0, v=0.2),
            CurvePoint(t=0.25, v=0.5),
            CurvePoint(t=0.5, v=0.8),
            CurvePoint(t=0.75, v=0.5),
            CurvePoint(t=1.0, v=0.2),
        ]

        # Tilt boundaries from fixture config
        tilt_min = 5
        tilt_max = 125

        result = dimmer_curve_to_dmx(tilt_curve, clamp_min=tilt_min, clamp_max=tilt_max)

        # Check boundaries are respected
        dmx_values = [p.v * 255 for p in result]
        assert min(dmx_values) >= tilt_min
        assert max(dmx_values) <= tilt_max

        # Check we have actual variation (not flat)
        variation = max(dmx_values) - min(dmx_values)
        assert variation > 60  # Should have significant variation

        # Check specific values
        assert result[0].v * 255 == pytest.approx(29.0, abs=0.1)  # v=0.2 -> 29 DMX
        assert result[2].v * 255 == pytest.approx(101.0, abs=0.1)  # v=0.8 -> 101 DMX

    def test_tilt_hold_pattern_stays_constant(self) -> None:
        """Tilt with HOLD pattern stays constant (as expected for sweep_lr)."""
        # HOLD curve - constant value at 0.5
        tilt_curve = [CurvePoint(t=i / 10, v=0.5) for i in range(11)]

        tilt_min = 5
        tilt_max = 125

        result = dimmer_curve_to_dmx(tilt_curve, clamp_min=tilt_min, clamp_max=tilt_max)

        # All values should be the same
        dmx_values = [p.v * 255 for p in result]
        assert max(dmx_values) - min(dmx_values) < 0.1  # Effectively flat

        # Should be at midpoint of range
        expected_dmx = tilt_min + 0.5 * (tilt_max - tilt_min)
        assert dmx_values[0] == pytest.approx(expected_dmx, abs=0.1)

    def test_tilt_full_range_uses_all_boundaries(self) -> None:
        """Tilt curve using full [0,1] range maps to full boundary range."""
        tilt_curve = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=1.0, v=1.0),
        ]

        tilt_min = 5
        tilt_max = 125

        result = dimmer_curve_to_dmx(tilt_curve, clamp_min=tilt_min, clamp_max=tilt_max)

        # Should map to full boundary range
        dmx_values = [p.v * 255 for p in result]
        assert dmx_values[0] == pytest.approx(tilt_min, abs=0.1)
        assert dmx_values[1] == pytest.approx((tilt_min + tilt_max) / 2, abs=0.1)
        assert dmx_values[2] == pytest.approx(tilt_max, abs=0.1)

    def test_pan_and_tilt_use_same_scaling_formula(self) -> None:
        """Both pan and tilt use the same linear scaling formula."""
        curve = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]

        # Pan boundaries
        pan_result = dimmer_curve_to_dmx(curve, clamp_min=50, clamp_max=190)

        # Tilt boundaries
        tilt_result = dimmer_curve_to_dmx(curve, clamp_min=5, clamp_max=125)

        # Both should scale 0->min, 1->max
        assert pan_result[0].v * 255 == pytest.approx(50, abs=0.1)
        assert pan_result[1].v * 255 == pytest.approx(190, abs=0.1)

        assert tilt_result[0].v * 255 == pytest.approx(5, abs=0.1)
        assert tilt_result[1].v * 255 == pytest.approx(125, abs=0.1)
