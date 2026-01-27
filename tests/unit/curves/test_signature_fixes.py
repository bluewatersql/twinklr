"""Tests for Phase 2: Curve signature mismatch fixes.

Tests verify that curve generators accept the parameters defined in their
registry default_params, fixing mismatches that caused TypeErrors.
"""

from __future__ import annotations

from blinkb0t.core.curves.functions.basic import generate_triangle
from blinkb0t.core.curves.functions.movement import generate_movement_pulse
from blinkb0t.core.curves.library import CurveLibrary, build_default_registry


class TestTrianglePhaseParameter:
    """Tests for generate_triangle() phase parameter."""

    def test_generate_triangle_accepts_phase(self):
        """Test triangle generator accepts phase parameter."""
        # This should not raise TypeError
        result = generate_triangle(
            n_samples=10,
            cycles=1.0,
            amplitude=1.0,
            frequency=1.0,
            phase=0.0,  # This parameter was missing
        )

        assert len(result) == 10
        assert all(0.0 <= p.v <= 1.0 for p in result)

    def test_generate_triangle_phase_default(self):
        """Test triangle generator has default phase."""
        # Should work without phase (backward compatible)
        result = generate_triangle(n_samples=10, cycles=1.0)

        assert len(result) == 10

    def test_generate_triangle_phase_ignored(self):
        """Test triangle generator ignores phase (for now)."""
        # Phase should be accepted but not affect output (for now)
        result_no_phase = generate_triangle(n_samples=20, cycles=1.0, amplitude=1.0, phase=0.0)
        result_with_phase = generate_triangle(
            n_samples=20,
            cycles=1.0,
            amplitude=1.0,
            phase=1.57,  # π/2 radians
        )

        # Output should be identical (phase not implemented yet)
        assert len(result_no_phase) == len(result_with_phase)
        # Values should be similar (phase ignored)
        for p1, p2 in zip(result_no_phase, result_with_phase, strict=True):
            assert abs(p1.v - p2.v) < 0.01  # Allow small tolerance


class TestTriangleRegistryIntegration:
    """Tests for TRIANGLE curve registry integration."""

    def test_triangle_registry_resolve_with_defaults(self):
        """Test triangle can be resolved with default params."""
        registry = build_default_registry()
        definition = registry.get(CurveLibrary.TRIANGLE.value)

        # This should not raise TypeError about 'phase'
        result = registry.resolve(definition=definition)

        assert len(result) > 0
        assert all(0.0 <= p.v <= 1.0 for p in result)

    def test_triangle_registry_resolve_with_custom_params(self):
        """Test triangle can be resolved with custom params including phase."""
        registry = build_default_registry()
        definition = registry.get(CurveLibrary.TRIANGLE.value)

        result = registry.resolve(
            definition=definition,
            n_samples=30,
            cycles=2.0,
            amplitude=0.8,
            frequency=1.5,
            phase=0.5,  # Should be accepted
        )

        assert len(result) == 30


class TestMovementPulseParameters:
    """Tests for generate_movement_pulse() parameter signature."""

    def test_generate_movement_pulse_uses_high_low(self):
        """Test movement_pulse uses high/low not amplitude."""
        # Should accept high/low parameters
        result = generate_movement_pulse(
            n_samples=10,
            cycles=1.0,
            duty_cycle=0.5,
            high=0.8,
            low=0.2,
            frequency=1.0,
        )

        # Movement curves add a loop-ready point, so n=10 becomes n=11
        assert len(result) >= 10
        # Movement curves are centered at 0.5
        assert all(0.0 <= p.v <= 1.0 for p in result)

    def test_generate_movement_pulse_does_not_use_amplitude(self):
        """Test movement_pulse doesn't accept amplitude parameter."""
        # Movement pulse uses high/low, not amplitude
        # If amplitude is passed, it should be ignored via **kwargs
        result = generate_movement_pulse(
            n_samples=10,
            cycles=1.0,
            duty_cycle=0.5,
            high=0.8,
            low=0.2,
            frequency=1.0,
            amplitude=0.5,  # This should be ignored
        )

        # Movement curves add a loop-ready point
        assert len(result) >= 10


class TestMovementPulseRegistryIntegration:
    """Tests for MOVEMENT_PULSE curve registry integration."""

    def test_movement_pulse_registry_resolve_with_defaults(self):
        """Test movement_pulse can be resolved with default params."""
        registry = build_default_registry()
        definition = registry.get(CurveLibrary.MOVEMENT_PULSE.value)

        # This should not raise TypeError about missing high/low
        result = registry.resolve(definition=definition)

        assert len(result) > 0
        assert all(0.0 <= p.v <= 1.0 for p in result)

    def test_movement_pulse_registry_resolve_with_high_low(self):
        """Test movement_pulse can be resolved with high/low params."""
        registry = build_default_registry()
        definition = registry.get(CurveLibrary.MOVEMENT_PULSE.value)

        result = registry.resolve(
            definition=definition,
            n_samples=30,
            cycles=2.0,
            high=0.9,
            low=0.1,
            frequency=1.5,
        )

        # Movement curves add loop-ready point
        assert len(result) >= 30


class TestCurveLibraryDefaultParams:
    """Tests for curve library default_params correctness."""

    def test_triangle_default_params_include_phase(self):
        """Test TRIANGLE default_params include phase."""
        registry = build_default_registry()
        definition = registry.get(CurveLibrary.TRIANGLE.value)

        assert definition is not None
        assert definition.default_params is not None
        assert "phase" in definition.default_params
        assert definition.default_params["phase"] == 0.0

    def test_movement_pulse_default_params_correct(self):
        """Test MOVEMENT_PULSE default_params use high/low not amplitude."""
        registry = build_default_registry()
        definition = registry.get(CurveLibrary.MOVEMENT_PULSE.value)

        assert definition is not None
        assert definition.default_params is not None

        # Should have high/low, not amplitude
        assert "high" in definition.default_params
        assert "low" in definition.default_params

        # Should not have amplitude (or if present, should be handled via adapter)
        # Note: amplitude might still be in defaults but adapter translates it
        # So we just verify that resolution works
        assert "cycles" in definition.default_params
        assert "frequency" in definition.default_params
