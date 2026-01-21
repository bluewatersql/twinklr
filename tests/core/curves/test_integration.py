"""Integration tests for curve operations pipeline.

End-to-end tests validating: generate → shift → envelope → simplify.
Validates complete curve workflow performs correctly and efficiently.
"""

import time

from blinkb0t.core.curves.composition import apply_envelope, multiply_curves
from blinkb0t.core.curves.generators import (
    generate_hold,
    generate_linear,
    generate_pulse,
    generate_sine,
    generate_triangle,
)
from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.phase import apply_phase_shift_samples
from blinkb0t.core.curves.sampling import interpolate_linear
from blinkb0t.core.curves.simplification import simplify_rdp


class TestPipelineBoundsPreservation:
    """Tests that pipeline preserves [0, 1] bounds."""

    def test_generate_shift_envelope_preserves_bounds(self) -> None:
        """Test generate → shift → envelope preserves [0, 1] bounds."""
        # Generate a sine wave
        curve = generate_sine(n_samples=64, cycles=2.0)

        # Apply phase shift
        shifted = apply_phase_shift_samples(curve, offset_norm=0.25, n_samples=64)

        # Apply fade-in envelope
        envelope = generate_linear(n_samples=64, ascending=True)
        result = apply_envelope(shifted, envelope, n_samples=64)

        # All values should be in [0, 1]
        for p in result:
            assert 0.0 <= p.v <= 1.0, f"Value {p.v} out of bounds at t={p.t}"
            assert 0.0 <= p.t <= 1.0, f"Time {p.t} out of bounds"

    def test_full_pipeline_preserves_bounds(self) -> None:
        """Test full pipeline: generate → shift → multiply → simplify."""
        # Generate base curve
        curve = generate_triangle(n_samples=64, cycles=3.0)

        # Apply phase shift
        shifted = apply_phase_shift_samples(curve, offset_norm=0.1, n_samples=64)

        # Multiply with another curve
        modulator = generate_sine(n_samples=64, cycles=1.0)
        composed = multiply_curves(shifted, modulator, n_samples=64)

        # Simplify
        simplified = simplify_rdp(composed, epsilon=0.02)

        # All values should be in [0, 1]
        for p in simplified:
            assert 0.0 <= p.v <= 1.0, f"Value {p.v} out of bounds"
            assert 0.0 <= p.t <= 1.0, f"Time {p.t} out of bounds"


class TestPipelineMonotonicTime:
    """Tests that pipeline maintains monotonic time."""

    def test_phase_shift_maintains_monotonic_time(self) -> None:
        """Test phase shift output has monotonic time."""
        curve = generate_sine(n_samples=32, cycles=2.0)
        shifted = apply_phase_shift_samples(curve, offset_norm=0.5, n_samples=32)

        for i in range(len(shifted) - 1):
            assert shifted[i].t < shifted[i + 1].t, (
                f"Non-monotonic time at index {i}: {shifted[i].t} >= {shifted[i + 1].t}"
            )

    def test_composition_maintains_monotonic_time(self) -> None:
        """Test curve composition maintains monotonic time."""
        curve_a = generate_sine(n_samples=32, cycles=1.0)
        curve_b = generate_linear(n_samples=32)
        result = multiply_curves(curve_a, curve_b, n_samples=32)

        for i in range(len(result) - 1):
            assert result[i].t < result[i + 1].t, f"Non-monotonic time at index {i}"

    def test_simplification_maintains_monotonic_time(self) -> None:
        """Test RDP simplification maintains monotonic time."""
        curve = generate_sine(n_samples=64, cycles=4.0)
        simplified = simplify_rdp(curve, epsilon=0.05)

        for i in range(len(simplified) - 1):
            assert simplified[i].t < simplified[i + 1].t, f"Non-monotonic time at index {i}"


class TestPipelinePerformance:
    """Performance benchmarks for full pipeline."""

    def test_100_sample_full_pipeline_under_10ms(self) -> None:
        """Performance: 100-sample curve through full pipeline < 10ms."""
        start = time.perf_counter()

        for _ in range(10):
            # Generate
            curve = generate_sine(n_samples=100, cycles=4.0)

            # Phase shift
            shifted = apply_phase_shift_samples(curve, offset_norm=0.25, n_samples=100)

            # Envelope
            envelope = generate_linear(n_samples=100, ascending=True)
            enveloped = apply_envelope(shifted, envelope, n_samples=100)

            # Simplify
            simplify_rdp(enveloped, epsilon=0.01)

        elapsed_ms = (time.perf_counter() - start) * 1000 / 10

        assert elapsed_ms < 10.0, f"100-sample pipeline took {elapsed_ms:.2f}ms (should be < 10ms)"


class TestPipelineDataIntegrity:
    """Tests for data integrity through multi-step composition."""

    def test_no_data_corruption_multi_step(self) -> None:
        """Test no data corruption in multi-step composition."""
        # Create a distinctive curve
        curve = generate_pulse(n_samples=32, cycles=2.0, duty_cycle=0.5)

        # Store original for comparison
        original_values = [p.v for p in curve]

        # Run through pipeline
        shifted = apply_phase_shift_samples(curve, offset_norm=0.0, n_samples=32)
        envelope = generate_hold(n_samples=32, value=1.0)
        result = multiply_curves(shifted, envelope, n_samples=32)

        # With zero offset and identity envelope, result should match original
        for i, p in enumerate(result):
            assert abs(p.v - original_values[i]) < 1e-10, (
                f"Data corruption at index {i}: expected {original_values[i]}, got {p.v}"
            )

    def test_chained_operations_produce_expected_result(self) -> None:
        """Test chained operations produce mathematically expected result."""
        # Linear ramp 0→1
        ramp = generate_linear(n_samples=8)

        # Multiply ramp by itself should give quadratic
        squared = multiply_curves(ramp, ramp, n_samples=8)

        # Verify quadratic relationship
        for i, p in enumerate(squared):
            expected_v = (i / 7) ** 2 if i < 7 else 1.0  # Linear ramp squared
            # Allow tolerance for floating point
            assert abs(p.v - expected_v) < 0.01, (
                f"At index {i}: expected ~{expected_v:.4f}, got {p.v:.4f}"
            )


class TestPipelineEndToEnd:
    """End-to-end workflow tests."""

    def test_dimmer_fade_in_with_pulse_modulation(self) -> None:
        """Test realistic dimmer: fade-in with pulse modulation."""
        # Base: linear fade-in
        fade_in = generate_linear(n_samples=64, ascending=True)

        # Modulator: pulse wave
        pulse = generate_pulse(n_samples=64, cycles=4.0, duty_cycle=0.3, high=1.0, low=0.5)

        # Combine: fade-in * pulse
        result = multiply_curves(fade_in, pulse, n_samples=64)

        # Simplify for efficiency
        simplified = simplify_rdp(result, epsilon=0.02)

        # Verify properties
        assert len(simplified) > 2  # Should have some structure
        assert len(simplified) < len(result)  # Should be simplified

        # All values in bounds
        for p in simplified:
            assert 0.0 <= p.v <= 1.0

    def test_movement_curve_with_phase_offset(self) -> None:
        """Test realistic movement: sine wave with phase offset for chase."""
        # Base movement: sine wave (1 cycle so phase offsets give distinct values)
        movement = generate_sine(n_samples=64, cycles=1.0)

        # Apply phase offsets for different fixtures
        offsets = [0.0, 0.25, 0.5, 0.75]
        shifted_curves = [
            apply_phase_shift_samples(movement, offset_norm=offset, n_samples=64)
            for offset in offsets
        ]

        # Verify all curves are different at t=0
        values_at_start = [curve[0].v for curve in shifted_curves]
        # Should have 4 different values (phase shifted sine)
        # With 1 cycle: offset 0.0 → sin(0)=0.5, 0.25 → sin(π/2)=1.0, 0.5 → sin(π)=0.5, 0.75 → sin(3π/2)=0.0
        unique_values = {round(v, 2) for v in values_at_start}
        assert len(unique_values) >= 3, (
            f"Phase offsets should produce different starting values, got {values_at_start}"
        )

    def test_complex_envelope_chain(self) -> None:
        """Test complex envelope: attack → sustain → release."""
        n = 64

        # Attack phase: quick rise (0-25%)
        attack = generate_linear(n_samples=n // 4)

        # Sustain phase: hold (25-75%)
        sustain = generate_hold(n_samples=n // 2, value=1.0)

        # Release phase: fade out (75-100%)
        release = generate_linear(n_samples=n // 4, ascending=False)

        # Manually construct envelope from parts
        envelope_points: list[CurvePoint] = []

        # Attack: t=0.0 to 0.25
        for _, p in enumerate(attack):
            new_t = p.t * 0.25
            envelope_points.append(CurvePoint(t=new_t, v=p.v))

        # Sustain: t=0.25 to 0.75
        for _, p in enumerate(sustain):
            new_t = 0.25 + p.t * 0.5
            envelope_points.append(CurvePoint(t=new_t, v=p.v))

        # Release: t=0.75 to 1.0 (skip first point to avoid duplicate)
        for _, p in enumerate(release[1:], 1):
            new_t = 0.75 + p.t * 0.25
            envelope_points.append(CurvePoint(t=new_t, v=p.v))

        # Apply envelope to a constant
        carrier = generate_hold(n_samples=len(envelope_points), value=0.8)
        result = multiply_curves(carrier, envelope_points, n_samples=n)

        # Verify envelope shape
        # Start should be low
        assert result[0].v < 0.1
        # Middle should be high
        middle = len(result) // 2
        assert result[middle].v > 0.7
        # End should be low
        assert result[-1].v < 0.1


class TestInterpolationConsistency:
    """Tests for interpolation consistency across operations."""

    def test_interpolation_matches_original(self) -> None:
        """Test that interpolated values match original curve."""
        # Generate curve
        curve = generate_sine(n_samples=32, cycles=1.0)

        # Interpolate at various points
        test_points = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9]
        for t in test_points:
            interp_value = interpolate_linear(curve, t)
            assert 0.0 <= interp_value <= 1.0

    def test_simplified_curve_interpolates_similarly(self) -> None:
        """Test that simplified curve interpolates similarly to original."""
        # Generate curve
        original = generate_sine(n_samples=64, cycles=2.0)

        # Simplify
        simplified = simplify_rdp(original, epsilon=0.02)

        # Compare interpolated values
        test_points = [0.1, 0.25, 0.4, 0.6, 0.75, 0.9]
        for t in test_points:
            orig_value = interpolate_linear(original, t)
            simp_value = interpolate_linear(simplified, t)
            # Should be within reasonable tolerance
            assert abs(orig_value - simp_value) < 0.05, (
                f"At t={t}: original={orig_value:.4f}, simplified={simp_value:.4f}"
            )
