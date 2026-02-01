"""Tests for curve-specific intensity parameters."""

from twinklr.core.curves.library import CurveLibrary
from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.libraries.movement import (
    MovementCategoricalParams,
    get_curve_categorical_params,
)


class TestGetCurveCategoricalParams:
    """Tests for get_curve_categorical_params helper function."""

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
        triangle_slow = get_curve_categorical_params(CurveLibrary.MOVEMENT_TRIANGLE, Intensity.SLOW)
        pulse_smooth = get_curve_categorical_params(CurveLibrary.MOVEMENT_PULSE, Intensity.SMOOTH)
        cosine_smooth = get_curve_categorical_params(CurveLibrary.MOVEMENT_COSINE, Intensity.SMOOTH)

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

    def test_all_entries_have_all_intensities(self):
        """Test that each curve has all intensity levels defined."""
        from twinklr.core.sequencer.moving_heads.libraries.movement import (
            CURVE_INTENSITY_PARAMS,
        )

        for curve_id, intensity_map in CURVE_INTENSITY_PARAMS.items():
            for intensity in Intensity:
                assert intensity in intensity_map, f"{curve_id} missing {intensity}"
                params = intensity_map[intensity]
                assert isinstance(params, MovementCategoricalParams)

    def test_all_params_in_valid_range(self):
        """Test that all params are in valid ranges."""
        from twinklr.core.sequencer.moving_heads.libraries.movement import (
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
