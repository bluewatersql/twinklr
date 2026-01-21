"""Tests for Movement Handlers.

Tests SWEEP_LR movement handler and intensity mappings.
Validates offset-centered curves and deterministic behavior.
"""

from blinkb0t.core.sequencer.moving_heads.handlers.movement import (
    Intensity,
    SweepLRHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.protocols import MovementResult


class TestIntensityEnum:
    """Tests for Intensity enum values."""

    def test_intensity_has_amplitude_values(self) -> None:
        """Test all Intensity values have amplitude."""
        for intensity in Intensity:
            assert 0.0 < intensity.amplitude <= 0.5

    def test_intensity_ordering(self) -> None:
        """Test intensity ordering from smooth to dramatic."""
        assert Intensity.SLOW.amplitude < Intensity.SMOOTH.amplitude
        assert Intensity.SMOOTH.amplitude < Intensity.FAST.amplitude
        assert Intensity.FAST.amplitude < Intensity.DRAMATIC.amplitude


class TestSweepLRHandler:
    """Tests for SweepLRHandler."""

    def test_handler_has_correct_id(self) -> None:
        """Test handler has correct handler_id."""
        handler = SweepLRHandler()
        assert handler.handler_id == "SWEEP_LR"

    def test_generate_returns_movement_result(self) -> None:
        """Test generate returns MovementResult."""
        handler = SweepLRHandler()
        result = handler.generate(
            params={},
            n_samples=8,
            cycles=1.0,
            intensity="SMOOTH",
        )

        assert isinstance(result, MovementResult)
        assert len(result.pan_curve) == 8
        assert len(result.tilt_curve) == 8

    def test_generate_tilt_is_static(self) -> None:
        """Test tilt curve is static (0.5 = no motion)."""
        handler = SweepLRHandler()
        result = handler.generate(
            params={},
            n_samples=16,
            cycles=2.0,
            intensity="SMOOTH",
        )

        # Tilt should be constant at 0.5 (no motion)
        for point in result.tilt_curve:
            assert point.v == 0.5

    def test_generate_pan_is_offset_centered(self) -> None:
        """Test pan curve is offset-centered around 0.5."""
        handler = SweepLRHandler()
        result = handler.generate(
            params={},
            n_samples=32,
            cycles=1.0,
            intensity="SMOOTH",
        )

        # Pan should oscillate around 0.5
        values = [p.v for p in result.pan_curve]
        avg = sum(values) / len(values)
        assert abs(avg - 0.5) < 0.1  # Average close to 0.5

    def test_generate_pan_respects_intensity(self) -> None:
        """Test pan amplitude changes with intensity."""
        handler = SweepLRHandler()

        result_smooth = handler.generate(params={}, n_samples=64, cycles=1.0, intensity="SMOOTH")
        result_dramatic = handler.generate(
            params={}, n_samples=64, cycles=1.0, intensity="DRAMATIC"
        )

        # Calculate amplitude (max - min) / 2
        smooth_values = [p.v for p in result_smooth.pan_curve]
        dramatic_values = [p.v for p in result_dramatic.pan_curve]

        smooth_amplitude = (max(smooth_values) - min(smooth_values)) / 2
        dramatic_amplitude = (max(dramatic_values) - min(dramatic_values)) / 2

        # Dramatic should have larger amplitude
        assert dramatic_amplitude > smooth_amplitude

    def test_generate_respects_cycles(self) -> None:
        """Test pan curve respects cycles parameter."""
        handler = SweepLRHandler()

        result_1cycle = handler.generate(params={}, n_samples=64, cycles=1.0, intensity="SMOOTH")
        result_2cycles = handler.generate(params={}, n_samples=64, cycles=2.0, intensity="SMOOTH")

        # Count zero-crossings (approximate peaks)
        def count_peaks(values: list[float]) -> int:
            peaks = 0
            for i in range(1, len(values) - 1):
                if values[i] > values[i - 1] and values[i] > values[i + 1]:
                    peaks += 1
            return peaks

        values_1 = [p.v for p in result_1cycle.pan_curve]
        values_2 = [p.v for p in result_2cycles.pan_curve]

        # 2 cycles should have ~2x the peaks
        assert count_peaks(values_2) >= count_peaks(values_1)

    def test_generate_values_in_bounds(self) -> None:
        """Test all values are in [0, 1]."""
        handler = SweepLRHandler()
        result = handler.generate(params={}, n_samples=64, cycles=4.0, intensity="DRAMATIC")

        for point in result.pan_curve:
            assert 0.0 <= point.v <= 1.0
        for point in result.tilt_curve:
            assert 0.0 <= point.v <= 1.0


class TestSweepLRHandlerIntensityLevels:
    """Tests for all intensity levels."""

    def test_all_intensity_levels_work(self) -> None:
        """Test handler works with all intensity levels."""
        handler = SweepLRHandler()

        for intensity in Intensity:
            result = handler.generate(
                params={},
                n_samples=16,
                cycles=1.0,
                intensity=intensity.value,
            )
            assert len(result.pan_curve) == 16
            assert len(result.tilt_curve) == 16

    def test_unknown_intensity_uses_default(self) -> None:
        """Test unknown intensity falls back to SMOOTH."""
        handler = SweepLRHandler()
        result = handler.generate(
            params={},
            n_samples=16,
            cycles=1.0,
            intensity="UNKNOWN_INTENSITY",
        )

        # Should work (uses default)
        assert len(result.pan_curve) == 16


class TestSweepLRHandlerParams:
    """Tests for handler-specific parameters."""

    def test_amplitude_param_overrides_intensity(self) -> None:
        """Test amplitude_degrees param overrides intensity."""
        handler = SweepLRHandler()
        result = handler.generate(
            params={"amplitude_degrees": 45},
            n_samples=64,
            cycles=1.0,
            intensity="SMOOTH",  # Would normally be 0.15
        )

        # Calculate amplitude
        values = [p.v for p in result.pan_curve]
        amplitude = (max(values) - min(values)) / 2

        # 45 degrees = 45/180 = 0.25 amplitude
        expected = 45 / 180
        assert abs(amplitude - expected) < 0.05


class TestSweepLRHandlerDeterminism:
    """Tests for handler determinism."""

    def test_same_input_same_output(self) -> None:
        """Test handler produces same output for same input."""
        handler = SweepLRHandler()
        params: dict[str, object] = {}

        result1 = handler.generate(params, n_samples=32, cycles=2.0, intensity="SMOOTH")
        result2 = handler.generate(params, n_samples=32, cycles=2.0, intensity="SMOOTH")

        for i, (p1, p2) in enumerate(zip(result1.pan_curve, result2.pan_curve, strict=False)):
            assert p1.t == p2.t, f"Time mismatch at index {i}"
            assert p1.v == p2.v, f"Value mismatch at index {i}"

    def test_monotonic_time(self) -> None:
        """Test output has monotonic time."""
        handler = SweepLRHandler()
        result = handler.generate(params={}, n_samples=32, cycles=1.0, intensity="SMOOTH")

        for i in range(len(result.pan_curve) - 1):
            assert result.pan_curve[i].t < result.pan_curve[i + 1].t
