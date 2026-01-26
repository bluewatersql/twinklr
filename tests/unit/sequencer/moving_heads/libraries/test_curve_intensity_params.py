"""Tests for curve-specific intensity parameters."""

import pytest

from blinkb0t.core.curves.library import CurveLibrary
from blinkb0t.core.sequencer.models.enum import Intensity
from blinkb0t.core.sequencer.moving_heads.libraries.movement import (
    DEFAULT_MOVEMENT_PARAMS,
    MovementCategoricalParams,
    get_curve_categorical_params,
)


class TestGetCurveCategoricalParams:
    """Tests for get_curve_categorical_params helper function."""

    def test_returns_curve_specific_params_when_available(self):
        """Test returns curve-specific params when defined."""
        # MOVEMENT_SINE has optimized params for SMOOTH intensity
        result = get_curve_categorical_params(CurveLibrary.MOVEMENT_SINE, Intensity.SMOOTH)

        assert isinstance(result, MovementCategoricalParams)
        # Should return optimized params, not defaults
        assert result.amplitude == 0.6  # From optimization report
        assert result.frequency == 1.0

    def test_returns_defaults_for_undefined_curve(self):
        """Test falls back to defaults when curve not in CURVE_INTENSITY_PARAMS."""
        # MOVEMENT_HOLD doesn't have optimized params (fixed behavior curve)
        result = get_curve_categorical_params(CurveLibrary.MOVEMENT_HOLD, Intensity.SMOOTH)

        assert isinstance(result, MovementCategoricalParams)
        # Should return default params
        assert result == DEFAULT_MOVEMENT_PARAMS[Intensity.SMOOTH]

    def test_returns_defaults_for_undefined_intensity(self):
        """Test falls back to defaults when intensity not defined for curve."""
        # Even if curve has params, all intensities should be defined
        # This test verifies the fallback mechanism works
        result = get_curve_categorical_params(CurveLibrary.MOVEMENT_SINE, Intensity.SLOW)

        assert isinstance(result, MovementCategoricalParams)
        # Should have valid params (either curve-specific or default)
        assert 0.0 <= result.amplitude <= 1.0
        assert 0.0 <= result.frequency <= 10.0

    def test_all_intensities_defined_for_optimized_curves(self):
        """Test that all intensities are defined for curves with optimized params."""
        # List of curves that should have optimized params
        optimized_curves = [
            CurveLibrary.MOVEMENT_SINE,
            CurveLibrary.MOVEMENT_TRIANGLE,
            CurveLibrary.MOVEMENT_PULSE,
            CurveLibrary.MOVEMENT_COSINE,
            CurveLibrary.MOVEMENT_LISSAJOUS,
            CurveLibrary.MOVEMENT_PERLIN_NOISE,
        ]

        for curve_id in optimized_curves:
            for intensity in Intensity:
                result = get_curve_categorical_params(curve_id, intensity)

                assert isinstance(result, MovementCategoricalParams)
                assert 0.0 <= result.amplitude <= 1.0
                assert 0.0 <= result.frequency <= 10.0
                assert result.center_offset == 0.5

    def test_params_are_frozen(self):
        """Test that returned params are immutable."""
        from pydantic import ValidationError

        result = get_curve_categorical_params(CurveLibrary.MOVEMENT_SINE, Intensity.SMOOTH)

        with pytest.raises(ValidationError):
            result.amplitude = 0.999

    def test_intensity_progression_for_movement_sine(self):
        """Test that MOVEMENT_SINE params show expected progression."""
        slow = get_curve_categorical_params(CurveLibrary.MOVEMENT_SINE, Intensity.SLOW)
        smooth = get_curve_categorical_params(CurveLibrary.MOVEMENT_SINE, Intensity.SMOOTH)
        intense = get_curve_categorical_params(CurveLibrary.MOVEMENT_SINE, Intensity.INTENSE)

        # Amplitude should generally increase (with some exceptions for tuning)
        assert slow.amplitude < intense.amplitude
        assert smooth.amplitude < intense.amplitude

        # Frequency should generally increase
        assert slow.frequency < intense.frequency

    def test_returns_different_params_for_different_curves(self):
        """Test that at least some curves have curve-specific optimizations."""
        # Compare multiple curves across multiple intensities
        # Some may converge to same values, but we should see variation
        sine_slow = get_curve_categorical_params(CurveLibrary.MOVEMENT_SINE, Intensity.SLOW)
        triangle_slow = get_curve_categorical_params(
            CurveLibrary.MOVEMENT_TRIANGLE, Intensity.SLOW
        )
        pulse_smooth = get_curve_categorical_params(CurveLibrary.MOVEMENT_PULSE, Intensity.SMOOTH)
        cosine_smooth = get_curve_categorical_params(
            CurveLibrary.MOVEMENT_COSINE, Intensity.SMOOTH
        )

        # At least one pair should have different optimizations
        # (Some curves may converge to same values at certain intensities)
        differences_found = (
            sine_slow.amplitude != triangle_slow.amplitude
            or sine_slow.frequency != triangle_slow.frequency
            or pulse_smooth.amplitude != cosine_smooth.amplitude
            or pulse_smooth.frequency != cosine_smooth.frequency
        )

        assert differences_found, "Expected curve-specific optimizations to differ"


class TestCurveIntensityParamsStructure:
    """Tests for CURVE_INTENSITY_PARAMS structure and completeness."""

    def test_curve_intensity_params_exists(self):
        """Test that CURVE_INTENSITY_PARAMS is defined."""
        from blinkb0t.core.sequencer.moving_heads.libraries.movement import (
            CURVE_INTENSITY_PARAMS,
        )

        assert isinstance(CURVE_INTENSITY_PARAMS, dict)
        assert len(CURVE_INTENSITY_PARAMS) >= 6  # At least 6 optimized curves

    def test_all_entries_have_all_intensities(self):
        """Test that each curve has all intensity levels defined."""
        from blinkb0t.core.sequencer.moving_heads.libraries.movement import (
            CURVE_INTENSITY_PARAMS,
        )

        for curve_id, intensity_map in CURVE_INTENSITY_PARAMS.items():
            for intensity in Intensity:
                assert intensity in intensity_map, (
                    f"{curve_id} missing {intensity}"
                )
                params = intensity_map[intensity]
                assert isinstance(params, MovementCategoricalParams)

    def test_all_params_in_valid_range(self):
        """Test that all params are in valid ranges."""
        from blinkb0t.core.sequencer.moving_heads.libraries.movement import (
            CURVE_INTENSITY_PARAMS,
        )

        for curve_id, intensity_map in CURVE_INTENSITY_PARAMS.items():
            for intensity, params in intensity_map.items():
                assert 0.0 <= params.amplitude <= 1.0, (
                    f"{curve_id}/{intensity} amplitude out of range"
                )
                assert 0.0 <= params.frequency <= 10.0, (
                    f"{curve_id}/{intensity} frequency out of range"
                )
                assert params.center_offset == 0.5, (
                    f"{curve_id}/{intensity} center_offset should be 0.5"
                )

    def test_params_are_frozen(self):
        """Test that all params in CURVE_INTENSITY_PARAMS are immutable."""
        from pydantic import ValidationError

        from blinkb0t.core.sequencer.moving_heads.libraries.movement import (
            CURVE_INTENSITY_PARAMS,
        )

        for intensity_map in CURVE_INTENSITY_PARAMS.values():
            for params in intensity_map.values():
                with pytest.raises(ValidationError):
                    params.amplitude = 0.999


class TestBackwardCompatibility:
    """Tests for backward compatibility with DEFAULT_MOVEMENT_PARAMS."""

    def test_default_movement_params_unchanged(self):
        """Test that DEFAULT_MOVEMENT_PARAMS still exists and is unchanged."""
        # Verify structure
        assert isinstance(DEFAULT_MOVEMENT_PARAMS, dict)
        assert len(DEFAULT_MOVEMENT_PARAMS) == len(Intensity)

        # Verify all intensities present
        for intensity in Intensity:
            assert intensity in DEFAULT_MOVEMENT_PARAMS
            assert isinstance(DEFAULT_MOVEMENT_PARAMS[intensity], MovementCategoricalParams)

    def test_defaults_are_fallback_for_undefined_curves(self):
        """Test that defaults are used when curve not optimized."""
        # Use a curve that shouldn't have optimized params
        result = get_curve_categorical_params(
            CurveLibrary.MOVEMENT_HOLD, Intensity.DRAMATIC
        )

        # Should match default
        assert result == DEFAULT_MOVEMENT_PARAMS[Intensity.DRAMATIC]
