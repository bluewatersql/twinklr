"""Tests for native curve specification and tuning."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from twinklr.core.curves.native import (
    NativeCurveType,
    generate_native_spec,
    tune_native_spec,
    xLightsNativeCurve,
)


class TestNativeCurveType:
    """Tests for NativeCurveType enum."""

    def test_all_curve_types_exist(self) -> None:
        """All expected curve types are defined."""
        assert NativeCurveType.FLAT.value == "flat"
        assert NativeCurveType.RAMP.value == "ramp"
        assert NativeCurveType.SINE.value == "sine"
        assert NativeCurveType.ABS_SINE.value == "abs sine"
        assert NativeCurveType.PARABOLIC.value == "parabolic"
        assert NativeCurveType.LOGARITHMIC.value == "logarithmic"
        assert NativeCurveType.EXPONENTIAL.value == "exponential"
        assert NativeCurveType.SAW_TOOTH.value == "saw tooth"

    def test_enum_is_string(self) -> None:
        """NativeCurveType is a string enum."""
        assert isinstance(NativeCurveType.SINE, str)


class TestXLightsNativeCurve:
    """Tests for xLightsNativeCurve model."""

    def test_valid_curve_creation(self) -> None:
        """Valid curve is created with defaults."""
        curve = xLightsNativeCurve(type=NativeCurveType.SINE)
        assert curve.type == NativeCurveType.SINE
        assert curve.p1 == 0.0
        assert curve.p2 == 0.0
        assert curve.p3 == 0.0
        assert curve.p4 == 0.0
        assert curve.reverse is False
        assert curve.min_val == 0
        assert curve.max_val == 255

    def test_curve_with_parameters(self) -> None:
        """Curve is created with custom parameters."""
        curve = xLightsNativeCurve(
            type=NativeCurveType.SINE,
            p1=10.0,
            p2=100.0,
            p3=50.0,
            p4=128.0,
            reverse=True,
            min_val=10,
            max_val=200,
        )
        assert curve.p1 == 10.0
        assert curve.p2 == 100.0
        assert curve.p3 == 50.0
        assert curve.p4 == 128.0
        assert curve.reverse is True
        assert curve.min_val == 10
        assert curve.max_val == 200

    def test_min_val_must_be_less_than_max_val(self) -> None:
        """min_val >= max_val raises validation error."""
        with pytest.raises(ValidationError, match="min_val must be less than max_val"):
            xLightsNativeCurve(
                type=NativeCurveType.FLAT,
                min_val=255,
                max_val=100,
            )

    def test_equal_min_max_raises(self) -> None:
        """Equal min_val and max_val raises validation error."""
        with pytest.raises(ValidationError):
            xLightsNativeCurve(
                type=NativeCurveType.FLAT,
                min_val=128,
                max_val=128,
            )

    def test_to_xlights_string_basic(self) -> None:
        """to_xlights_string produces correct format."""
        curve = xLightsNativeCurve(type=NativeCurveType.SINE)
        result = curve.to_xlights_string(channel=1)
        assert "Active=TRUE" in result
        assert "Id=ID_VALUECURVE_DMX1" in result
        assert "Type=Sine" in result
        assert "Min=0" in result
        assert "Max=255" in result
        assert "RV=FALSE" in result

    def test_to_xlights_string_with_parameters(self) -> None:
        """to_xlights_string includes non-zero parameters."""
        curve = xLightsNativeCurve(
            type=NativeCurveType.SINE,
            p1=10.0,
            p2=100.0,
            reverse=True,
        )
        result = curve.to_xlights_string(channel=2)
        assert "P1=10.00" in result
        assert "P2=100.00" in result
        assert "RV=TRUE" in result
        assert "Id=ID_VALUECURVE_DMX2" in result

    def test_to_xlights_string_skips_zero_parameters(self) -> None:
        """to_xlights_string skips parameters that are 0."""
        curve = xLightsNativeCurve(type=NativeCurveType.FLAT, p1=0.0)
        result = curve.to_xlights_string(channel=1)
        assert "P1=" not in result

    def test_model_copy_update(self) -> None:
        """model_copy with update works correctly."""
        curve = xLightsNativeCurve(type=NativeCurveType.SINE, p1=10.0)
        updated = curve.model_copy(update={"p1": 20.0})
        assert updated.p1 == 20.0
        assert curve.p1 == 10.0  # Original unchanged


class TestGenerateNativeSpec:
    """Tests for generate_native_spec function."""

    def test_generate_sine_default(self) -> None:
        """Generate sine curve with defaults."""
        result = generate_native_spec(NativeCurveType.SINE)
        assert result.type == NativeCurveType.SINE
        assert result.p2 == 100.0  # Default amplitude
        assert result.p4 == 128.0  # Default center

    def test_generate_sine_custom_params(self) -> None:
        """Generate sine curve with custom params."""
        result = generate_native_spec(NativeCurveType.SINE, {"amplitude": 50.0, "center": 200.0})
        assert result.p2 == 50.0
        assert result.p4 == 200.0

    def test_generate_abs_sine(self) -> None:
        """Generate abs sine curve."""
        result = generate_native_spec(NativeCurveType.ABS_SINE)
        assert result.type == NativeCurveType.ABS_SINE
        assert result.p2 == 100.0
        assert result.p4 == 128.0

    def test_generate_parabolic(self) -> None:
        """Generate parabolic curve."""
        result = generate_native_spec(NativeCurveType.PARABOLIC)
        assert result.type == NativeCurveType.PARABOLIC

    def test_generate_ramp_default(self) -> None:
        """Generate ramp curve with defaults."""
        result = generate_native_spec(NativeCurveType.RAMP)
        assert result.type == NativeCurveType.RAMP
        assert result.p1 == 0.0  # Default min
        assert result.p2 == 255.0  # Default max

    def test_generate_ramp_custom_params(self) -> None:
        """Generate ramp curve with custom params."""
        result = generate_native_spec(NativeCurveType.RAMP, {"min": 50.0, "max": 200.0})
        assert result.p1 == 50.0
        assert result.p2 == 200.0

    def test_generate_saw_tooth(self) -> None:
        """Generate saw tooth curve."""
        result = generate_native_spec(NativeCurveType.SAW_TOOTH)
        assert result.type == NativeCurveType.SAW_TOOTH

    def test_generate_logarithmic(self) -> None:
        """Generate logarithmic curve."""
        result = generate_native_spec(NativeCurveType.LOGARITHMIC)
        assert result.type == NativeCurveType.LOGARITHMIC

    def test_generate_exponential(self) -> None:
        """Generate exponential curve."""
        result = generate_native_spec(NativeCurveType.EXPONENTIAL)
        assert result.type == NativeCurveType.EXPONENTIAL

    def test_generate_flat_default(self) -> None:
        """Generate flat curve with defaults."""
        result = generate_native_spec(NativeCurveType.FLAT)
        assert result.type == NativeCurveType.FLAT
        assert result.p1 == 128.0  # Default value

    def test_generate_flat_custom_value(self) -> None:
        """Generate flat curve with custom value."""
        result = generate_native_spec(NativeCurveType.FLAT, {"value": 64.0})
        assert result.p1 == 64.0


class TestTuneNativeSpec:
    """Tests for tune_native_spec function."""

    def test_tune_sine_within_limits_unchanged(self) -> None:
        """Sine curve within limits stays unchanged."""
        spec = xLightsNativeCurve(type=NativeCurveType.SINE, p2=50.0, p4=128.0)
        result = tune_native_spec(spec, 0.0, 255.0)
        assert result.p2 == 50.0
        assert result.p4 == 128.0

    def test_tune_sine_adjusts_to_limits(self) -> None:
        """Sine curve outside limits is adjusted."""
        spec = xLightsNativeCurve(type=NativeCurveType.SINE, p2=100.0, p4=128.0)
        # Current range: 28-228, limit to 50-200
        result = tune_native_spec(spec, 50.0, 200.0)
        # Should be centered at (50+200)/2 = 125 with amplitude (200-50)/2 = 75
        assert result.p4 == 125.0
        assert result.p2 == 75.0

    def test_tune_ramp_within_limits_unchanged(self) -> None:
        """Ramp curve within limits stays unchanged."""
        spec = xLightsNativeCurve(type=NativeCurveType.RAMP, p1=50.0, p2=200.0)
        result = tune_native_spec(spec, 0.0, 255.0)
        assert result.p1 == 50.0
        assert result.p2 == 200.0

    def test_tune_ramp_clamps_to_limits(self) -> None:
        """Ramp curve outside limits is clamped."""
        spec = xLightsNativeCurve(type=NativeCurveType.RAMP, p1=0.0, p2=255.0)
        result = tune_native_spec(spec, 50.0, 200.0)
        assert result.p1 == 50.0
        assert result.p2 == 200.0

    def test_tune_flat_within_limits_unchanged(self) -> None:
        """Flat curve within limits stays unchanged."""
        spec = xLightsNativeCurve(type=NativeCurveType.FLAT, p1=128.0)
        result = tune_native_spec(spec, 0.0, 255.0)
        assert result.p1 == 128.0

    def test_tune_flat_clamps_to_limits(self) -> None:
        """Flat curve outside limits is clamped."""
        spec = xLightsNativeCurve(type=NativeCurveType.FLAT, p1=255.0)
        result = tune_native_spec(spec, 50.0, 200.0)
        assert result.p1 == 200.0

    def test_tune_abs_sine(self) -> None:
        """Abs sine curve is tuned like sine."""
        spec = xLightsNativeCurve(type=NativeCurveType.ABS_SINE, p2=100.0, p4=128.0)
        result = tune_native_spec(spec, 50.0, 200.0)
        assert result.p4 == 125.0

    def test_tune_parabolic(self) -> None:
        """Parabolic curve is tuned like sine."""
        spec = xLightsNativeCurve(type=NativeCurveType.PARABOLIC, p2=100.0, p4=128.0)
        result = tune_native_spec(spec, 50.0, 200.0)
        assert result.p4 == 125.0

    def test_tune_saw_tooth(self) -> None:
        """Saw tooth curve is tuned like ramp."""
        spec = xLightsNativeCurve(type=NativeCurveType.SAW_TOOTH, p1=0.0, p2=255.0)
        result = tune_native_spec(spec, 50.0, 200.0)
        assert result.p1 == 50.0
        assert result.p2 == 200.0

    def test_tune_logarithmic(self) -> None:
        """Logarithmic curve is tuned like ramp."""
        spec = xLightsNativeCurve(type=NativeCurveType.LOGARITHMIC, p1=0.0, p2=255.0)
        result = tune_native_spec(spec, 50.0, 200.0)
        assert result.p1 == 50.0
        assert result.p2 == 200.0

    def test_tune_exponential(self) -> None:
        """Exponential curve is tuned like ramp."""
        spec = xLightsNativeCurve(type=NativeCurveType.EXPONENTIAL, p1=0.0, p2=255.0)
        result = tune_native_spec(spec, 50.0, 200.0)
        assert result.p1 == 50.0
        assert result.p2 == 200.0
