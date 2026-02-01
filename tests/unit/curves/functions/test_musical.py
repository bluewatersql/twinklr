"""Tests for musical curve generators."""

from __future__ import annotations

import pytest

from twinklr.core.curves.functions.musical import (
    generate_beat_pulse,
    generate_musical_accent,
)


class TestGenerateMusicalAccent:
    """Tests for generate_musical_accent function."""

    def test_n_less_than_two_raises(self) -> None:
        """n < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_musical_accent(1)

    def test_cycles_zero_raises(self) -> None:
        """cycles <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="cycles must be > 0"):
            generate_musical_accent(10, cycles=0)

    def test_cycles_negative_raises(self) -> None:
        """Negative cycles raises ValueError."""
        with pytest.raises(ValueError, match="cycles must be > 0"):
            generate_musical_accent(10, cycles=-1)

    def test_beat_subdivision_zero_raises(self) -> None:
        """beat_subdivision <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="beat_subdivision must be > 0"):
            generate_beat_pulse(10, beat_subdivision=0)

    def test_beat_subdivision_negative_raises(self) -> None:
        """Negative beat_subdivision raises ValueError."""
        with pytest.raises(ValueError, match="beat_subdivision must be > 0"):
            generate_beat_pulse(10, beat_subdivision=-1)

    def test_phase_shifts_values(self) -> None:
        """Phase offset shifts the wave."""
        result_no_phase = generate_beat_pulse(20, phase=0.0)
        result_with_phase = generate_beat_pulse(20, phase=0.5)
        # Values should be different due to phase shift
        differences = [
            abs(a.v - b.v) for a, b in zip(result_no_phase, result_with_phase, strict=True)
        ]
        # At least some differences should be significant
        assert any(d > 0.1 for d in differences)
