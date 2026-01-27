"""Tests for curve parameter adapters.

Tests the adapter layer that translates categorical intensity parameters
to curve-specific parameters.
"""

from __future__ import annotations

import pytest

from blinkb0t.core.sequencer.moving_heads.libraries.movement import MovementCategoricalParams

# Import adapters (will be created)
# These imports will fail until we create the adapters module
try:
    from blinkb0t.core.curves.adapters import (
        ParameterAdapterRegistry,
        adapt_bezier_params,
        adapt_fixed_behavior,
        adapt_lissajous_params,
        adapt_movement_pulse_params,
        adapt_pulse_params,
        build_default_adapter_registry,
    )
except ImportError:
    # Module doesn't exist yet - tests will be skipped
    pytest.skip("Adapters module not yet implemented", allow_module_level=True)


class TestPulseAdapter:
    """Tests for pulse curve parameter adapter."""

    def test_converts_amplitude_to_high_low(self):
        """Test pulse adapter converts amplitude to high/low."""
        categorical = MovementCategoricalParams(
            amplitude=0.8,
            frequency=2.0,
            center_offset=0.5,
        )

        result = adapt_pulse_params(categorical, {"cycles": 2.0})

        assert result["high"] == pytest.approx(0.9)  # 0.5 + 0.8/2
        assert result["low"] == pytest.approx(0.1)  # 0.5 - 0.8/2
        assert result["frequency"] == 2.0
        assert result["duty_cycle"] == 0.5
        assert result["cycles"] == 2.0

    def test_respects_center_offset(self):
        """Test pulse adapter respects center_offset."""
        categorical = MovementCategoricalParams(
            amplitude=0.6,
            frequency=1.0,
            center_offset=0.3,  # Off-center
        )

        result = adapt_pulse_params(categorical, {})

        assert result["high"] == pytest.approx(0.6)  # 0.3 + 0.6/2
        assert result["low"] == pytest.approx(0.0)  # 0.3 - 0.6/2

    def test_preserves_custom_duty_cycle(self):
        """Test pulse adapter preserves custom duty_cycle."""
        categorical = MovementCategoricalParams(
            amplitude=0.5,
            frequency=1.0,
            center_offset=0.5,
        )

        result = adapt_pulse_params(categorical, {"duty_cycle": 0.7})

        assert result["duty_cycle"] == 0.7  # Preserved from base_params


class TestMovementPulseAdapter:
    """Tests for movement_pulse curve parameter adapter."""

    def test_uses_fixed_center(self):
        """Test movement_pulse adapter uses fixed 0.5 center."""
        categorical = MovementCategoricalParams(
            amplitude=0.6,
            frequency=1.5,
            center_offset=0.7,  # This should be ignored
        )

        result = adapt_movement_pulse_params(categorical, {"cycles": 1.0})

        # Movement curves always centered at 0.5
        assert result["high"] == pytest.approx(0.8)  # 0.5 + 0.6/2
        assert result["low"] == pytest.approx(0.2)  # 0.5 - 0.6/2
        assert result["frequency"] == 1.5
        assert result["cycles"] == 1.0

    def test_includes_required_params(self):
        """Test movement_pulse adapter includes all required params."""
        categorical = MovementCategoricalParams(
            amplitude=0.4,
            frequency=2.0,
            center_offset=0.5,
        )

        result = adapt_movement_pulse_params(categorical, {})

        assert "high" in result
        assert "low" in result
        assert "frequency" in result
        assert "cycles" in result
        assert "duty_cycle" in result


class TestBezierAdapter:
    """Tests for bezier curve parameter adapter."""

    def test_scales_control_points(self):
        """Test bezier adapter scales control point y-values."""
        categorical = MovementCategoricalParams(
            amplitude=0.5,
            frequency=1.0,
            center_offset=0.5,
        )

        result = adapt_bezier_params(
            categorical,
            {"control_points": [(0.0, 0.0), (0.5, 1.0), (1.0, 0.5)]},
        )

        # Y-values should be scaled by amplitude
        expected = [(0.0, 0.0), (0.5, 0.5), (1.0, 0.25)]
        assert result["control_points"] == expected

    def test_handles_empty_control_points(self):
        """Test bezier adapter handles missing control points."""
        categorical = MovementCategoricalParams(
            amplitude=0.8,
            frequency=1.0,
            center_offset=0.5,
        )

        result = adapt_bezier_params(categorical, {})

        # Should use default control points
        assert "control_points" in result
        assert len(result["control_points"]) == 2


class TestLissajousAdapter:
    """Tests for lissajous curve parameter adapter."""

    def test_scales_b_parameter(self):
        """Test lissajous adapter scales b parameter by frequency."""
        categorical = MovementCategoricalParams(
            amplitude=0.8,
            frequency=2.0,
            center_offset=0.5,
        )

        result = adapt_lissajous_params(categorical, {"b": 2, "delta": 0})

        assert result["amplitude"] == 0.8
        assert result["b"] == 4  # max(1, int(2 * 2.0))
        assert result["delta"] == 0

    def test_preserves_amplitude(self):
        """Test lissajous adapter preserves amplitude."""
        categorical = MovementCategoricalParams(
            amplitude=0.6,
            frequency=1.5,
            center_offset=0.5,
        )

        result = adapt_lissajous_params(categorical, {"b": 5, "delta": 90})

        assert result["amplitude"] == 0.6
        assert result["b"] == 7  # max(1, int(5 * 1.5))

    def test_enforces_minimum_b_value(self):
        """Test lissajous adapter enforces b >= 1 for low frequencies."""
        categorical = MovementCategoricalParams(
            amplitude=0.4,
            frequency=0.35,  # Very low frequency
            center_offset=0.5,
        )

        result = adapt_lissajous_params(categorical, {"b": 2, "delta": 0})

        # b should be at least 1, even though 2 * 0.35 = 0.7
        assert result["b"] >= 1
        assert result["b"] == 1


class TestFixedBehaviorAdapter:
    """Tests for fixed behavior curve adapter."""

    def test_returns_base_params_unchanged(self):
        """Test fixed behavior adapter returns params unchanged."""
        categorical = MovementCategoricalParams(
            amplitude=0.8,
            frequency=2.0,
            center_offset=0.5,
        )

        base_params = {"some_param": 42, "another": "value"}
        result = adapt_fixed_behavior(categorical, base_params)

        # Should return base params exactly as-is
        assert result == base_params
        assert result is not base_params  # Should be a copy

    def test_does_not_add_categorical_params(self):
        """Test fixed behavior adapter doesn't add amplitude/frequency."""
        categorical = MovementCategoricalParams(
            amplitude=0.8,
            frequency=2.0,
            center_offset=0.5,
        )

        result = adapt_fixed_behavior(categorical, {})

        # Should not include amplitude or frequency
        assert "amplitude" not in result
        assert "frequency" not in result


class TestParameterAdapterRegistry:
    """Tests for parameter adapter registry."""

    def test_registers_adapter(self):
        """Test registry can register an adapter."""
        registry = ParameterAdapterRegistry()

        def custom_adapter(cat, base):
            return {"custom": True}

        registry.register("test_curve", custom_adapter)

        categorical = MovementCategoricalParams(amplitude=0.5, frequency=1.0, center_offset=0.5)
        result = registry.adapt("test_curve", categorical, {})

        assert result["custom"] is True

    def test_uses_default_for_unregistered(self):
        """Test registry uses default adapter for unregistered curves."""
        registry = ParameterAdapterRegistry()

        categorical = MovementCategoricalParams(amplitude=0.7, frequency=1.5, center_offset=0.5)
        result = registry.adapt("unknown_curve", categorical, {"cycles": 2.0})

        # Should apply default mapping
        assert result["amplitude"] == 0.7
        assert result["frequency"] == 1.5
        assert result["cycles"] == 2.0

    def test_preserves_base_params(self):
        """Test adapter preserves base parameters."""
        registry = ParameterAdapterRegistry()

        categorical = MovementCategoricalParams(amplitude=0.5, frequency=1.0, center_offset=0.5)
        base_params = {"cycles": 3.0, "phase": 0.5}
        result = registry.adapt("unknown_curve", categorical, base_params)

        assert result["cycles"] == 3.0
        assert result["phase"] == 0.5


class TestDefaultAdapterRegistry:
    """Tests for default adapter registry."""

    def test_build_includes_pulse_adapters(self):
        """Test default registry includes pulse adapters."""
        registry = build_default_adapter_registry()

        categorical = MovementCategoricalParams(amplitude=0.8, frequency=2.0, center_offset=0.5)

        # Test pulse adapter
        pulse_result = registry.adapt("pulse", categorical, {})
        assert "high" in pulse_result
        assert "low" in pulse_result

        # Test movement_pulse adapter
        mov_pulse_result = registry.adapt("movement_pulse", categorical, {})
        assert "high" in mov_pulse_result
        assert "low" in mov_pulse_result

    def test_build_includes_parametric_adapters(self):
        """Test default registry includes parametric adapters."""
        registry = build_default_adapter_registry()

        categorical = MovementCategoricalParams(amplitude=0.6, frequency=1.5, center_offset=0.5)

        # Test bezier adapter
        bezier_result = registry.adapt("bezier", categorical, {"control_points": [(0, 0), (1, 1)]})
        assert "control_points" in bezier_result

        # Test lissajous adapter
        liss_result = registry.adapt("lissajous", categorical, {"a": 1, "b": 2})
        assert liss_result["b"] == 3  # 2 * 1.5

    def test_build_includes_fixed_behavior_adapters(self):
        """Test default registry includes fixed behavior adapters."""
        registry = build_default_adapter_registry()

        categorical = MovementCategoricalParams(amplitude=0.8, frequency=2.0, center_offset=0.5)

        # Test easing curves
        for curve in ["ease_in_sine", "ease_out_sine", "bounce_in", "elastic_out"]:
            result = registry.adapt(curve, categorical, {"some_param": 1})
            # Should return base params unchanged
            assert result == {"some_param": 1}
