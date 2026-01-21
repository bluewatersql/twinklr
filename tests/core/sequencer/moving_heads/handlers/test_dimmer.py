"""Tests for Dimmer Handlers.

Tests FADE_IN, FADE_OUT, PULSE, and HOLD dimmer handlers.
Validates absolute curves and min/max range handling.
"""

from blinkb0t.core.sequencer.moving_heads.handlers.dimmer import (
    FadeInHandler,
    FadeOutHandler,
    HoldHandler,
    PulseHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.protocols import DimmerResult


class TestFadeInHandler:
    """Tests for FadeInHandler."""

    def test_handler_has_correct_id(self) -> None:
        """Test handler has correct handler_id."""
        handler = FadeInHandler()
        assert handler.handler_id == "FADE_IN"

    def test_generate_returns_dimmer_result(self) -> None:
        """Test generate returns DimmerResult."""
        handler = FadeInHandler()
        result = handler.generate(
            params={},
            n_samples=8,
            cycles=1.0,
            intensity="SMOOTH",
            min_norm=0.0,
            max_norm=1.0,
        )

        assert isinstance(result, DimmerResult)
        assert len(result.dimmer_curve) == 8

    def test_generate_starts_at_min(self) -> None:
        """Test fade-in starts at min_norm."""
        handler = FadeInHandler()
        result = handler.generate(
            params={},
            n_samples=8,
            cycles=1.0,
            intensity="SMOOTH",
            min_norm=0.2,
            max_norm=0.8,
        )

        # First point should be at min_norm
        assert result.dimmer_curve[0].v == 0.2

    def test_generate_ends_near_max(self) -> None:
        """Test fade-in ends near max_norm."""
        handler = FadeInHandler()
        result = handler.generate(
            params={},
            n_samples=8,
            cycles=1.0,
            intensity="SMOOTH",
            min_norm=0.2,
            max_norm=0.8,
        )

        # Last point should approach max_norm
        assert result.dimmer_curve[-1].v > 0.7

    def test_generate_is_monotonic(self) -> None:
        """Test fade-in values are monotonically increasing."""
        handler = FadeInHandler()
        result = handler.generate(
            params={},
            n_samples=16,
            cycles=1.0,
            intensity="SMOOTH",
            min_norm=0.0,
            max_norm=1.0,
        )

        for i in range(len(result.dimmer_curve) - 1):
            assert result.dimmer_curve[i].v <= result.dimmer_curve[i + 1].v

    def test_generate_values_in_range(self) -> None:
        """Test all values are within [min_norm, max_norm]."""
        handler = FadeInHandler()
        result = handler.generate(
            params={},
            n_samples=16,
            cycles=1.0,
            intensity="SMOOTH",
            min_norm=0.3,
            max_norm=0.7,
        )

        for point in result.dimmer_curve:
            assert 0.3 <= point.v <= 0.7


class TestFadeOutHandler:
    """Tests for FadeOutHandler."""

    def test_handler_has_correct_id(self) -> None:
        """Test handler has correct handler_id."""
        handler = FadeOutHandler()
        assert handler.handler_id == "FADE_OUT"

    def test_generate_starts_at_max(self) -> None:
        """Test fade-out starts at max_norm."""
        handler = FadeOutHandler()
        result = handler.generate(
            params={},
            n_samples=8,
            cycles=1.0,
            intensity="SMOOTH",
            min_norm=0.2,
            max_norm=0.8,
        )

        # First point should be at max_norm
        assert result.dimmer_curve[0].v == 0.8

    def test_generate_ends_near_min(self) -> None:
        """Test fade-out ends near min_norm."""
        handler = FadeOutHandler()
        result = handler.generate(
            params={},
            n_samples=8,
            cycles=1.0,
            intensity="SMOOTH",
            min_norm=0.2,
            max_norm=0.8,
        )

        # Last point should approach min_norm
        assert result.dimmer_curve[-1].v < 0.3

    def test_generate_is_monotonic_decreasing(self) -> None:
        """Test fade-out values are monotonically decreasing."""
        handler = FadeOutHandler()
        result = handler.generate(
            params={},
            n_samples=16,
            cycles=1.0,
            intensity="SMOOTH",
            min_norm=0.0,
            max_norm=1.0,
        )

        for i in range(len(result.dimmer_curve) - 1):
            assert result.dimmer_curve[i].v >= result.dimmer_curve[i + 1].v


class TestPulseHandler:
    """Tests for PulseHandler."""

    def test_handler_has_correct_id(self) -> None:
        """Test handler has correct handler_id."""
        handler = PulseHandler()
        assert handler.handler_id == "PULSE"

    def test_generate_returns_dimmer_result(self) -> None:
        """Test generate returns DimmerResult."""
        handler = PulseHandler()
        result = handler.generate(
            params={},
            n_samples=32,
            cycles=2.0,
            intensity="SMOOTH",
            min_norm=0.0,
            max_norm=1.0,
        )

        assert isinstance(result, DimmerResult)
        assert len(result.dimmer_curve) == 32

    def test_generate_values_in_range(self) -> None:
        """Test all values are within [min_norm, max_norm]."""
        handler = PulseHandler()
        result = handler.generate(
            params={},
            n_samples=64,
            cycles=4.0,
            intensity="DRAMATIC",
            min_norm=0.2,
            max_norm=0.8,
        )

        for point in result.dimmer_curve:
            assert 0.2 <= point.v <= 0.8

    def test_generate_has_oscillation(self) -> None:
        """Test pulse has oscillation (not constant)."""
        handler = PulseHandler()
        result = handler.generate(
            params={},
            n_samples=64,
            cycles=2.0,
            intensity="SMOOTH",
            min_norm=0.0,
            max_norm=1.0,
        )

        values = [p.v for p in result.dimmer_curve]
        # Should have variance (not constant)
        assert max(values) - min(values) > 0.1

    def test_generate_respects_cycles(self) -> None:
        """Test pulse respects cycles parameter."""
        handler = PulseHandler()

        result_1cycle = handler.generate(
            params={}, n_samples=64, cycles=1.0, intensity="SMOOTH", min_norm=0.0, max_norm=1.0
        )
        result_2cycles = handler.generate(
            params={}, n_samples=64, cycles=2.0, intensity="SMOOTH", min_norm=0.0, max_norm=1.0
        )

        # Count peaks
        def count_peaks(values: list[float]) -> int:
            peaks = 0
            for i in range(1, len(values) - 1):
                if (
                    values[i] > values[i - 1] and values[i] > values[i + 1] and values[i] > 0.7
                ):  # Only count significant peaks
                    peaks += 1
            return peaks

        values_1 = [p.v for p in result_1cycle.dimmer_curve]
        values_2 = [p.v for p in result_2cycles.dimmer_curve]

        # 2 cycles should have ~2x the peaks
        assert count_peaks(values_2) >= count_peaks(values_1)


class TestHoldHandler:
    """Tests for HoldHandler (constant dimmer)."""

    def test_handler_has_correct_id(self) -> None:
        """Test handler has correct handler_id."""
        handler = HoldHandler()
        assert handler.handler_id == "HOLD"

    def test_generate_returns_constant(self) -> None:
        """Test hold returns constant value at max_norm."""
        handler = HoldHandler()
        result = handler.generate(
            params={},
            n_samples=8,
            cycles=1.0,
            intensity="SMOOTH",
            min_norm=0.3,
            max_norm=0.8,
        )

        # All values should be at max_norm
        for point in result.dimmer_curve:
            assert point.v == 0.8

    def test_generate_with_hold_value_param(self) -> None:
        """Test hold_value param overrides max_norm."""
        handler = HoldHandler()
        result = handler.generate(
            params={"hold_value": 0.5},
            n_samples=8,
            cycles=1.0,
            intensity="SMOOTH",
            min_norm=0.0,
            max_norm=1.0,
        )

        # All values should be at hold_value
        for point in result.dimmer_curve:
            assert point.v == 0.5


class TestDimmerHandlerDeterminism:
    """Tests for handler determinism."""

    def test_fade_in_deterministic(self) -> None:
        """Test FadeInHandler is deterministic."""
        handler = FadeInHandler()

        result1 = handler.generate(
            {}, n_samples=16, cycles=1.0, intensity="SMOOTH", min_norm=0.0, max_norm=1.0
        )
        result2 = handler.generate(
            {}, n_samples=16, cycles=1.0, intensity="SMOOTH", min_norm=0.0, max_norm=1.0
        )

        for p1, p2 in zip(result1.dimmer_curve, result2.dimmer_curve, strict=False):
            assert p1.t == p2.t
            assert p1.v == p2.v

    def test_pulse_deterministic(self) -> None:
        """Test PulseHandler is deterministic."""
        handler = PulseHandler()

        result1 = handler.generate(
            {}, n_samples=32, cycles=2.0, intensity="SMOOTH", min_norm=0.0, max_norm=1.0
        )
        result2 = handler.generate(
            {}, n_samples=32, cycles=2.0, intensity="SMOOTH", min_norm=0.0, max_norm=1.0
        )

        for p1, p2 in zip(result1.dimmer_curve, result2.dimmer_curve, strict=False):
            assert p1.t == p2.t
            assert p1.v == p2.v


class TestDimmerHandlerMonotonicTime:
    """Tests for monotonic time in output."""

    def test_fade_in_monotonic_time(self) -> None:
        """Test FadeInHandler has monotonic time."""
        handler = FadeInHandler()
        result = handler.generate(
            {}, n_samples=16, cycles=1.0, intensity="SMOOTH", min_norm=0.0, max_norm=1.0
        )

        for i in range(len(result.dimmer_curve) - 1):
            assert result.dimmer_curve[i].t < result.dimmer_curve[i + 1].t

    def test_pulse_monotonic_time(self) -> None:
        """Test PulseHandler has monotonic time."""
        handler = PulseHandler()
        result = handler.generate(
            {}, n_samples=32, cycles=2.0, intensity="SMOOTH", min_norm=0.0, max_norm=1.0
        )

        for i in range(len(result.dimmer_curve) - 1):
            assert result.dimmer_curve[i].t < result.dimmer_curve[i + 1].t
