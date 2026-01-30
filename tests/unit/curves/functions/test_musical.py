"""Tests for musical curve generators."""

from __future__ import annotations

import pytest

from twinklr.core.curves.functions.musical import (
    generate_beat_pulse,
    generate_musical_accent,
    generate_musical_swell,
)


class TestGenerateMusicalAccent:
    """Tests for generate_musical_accent function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of samples."""
        result = generate_musical_accent(10)
        assert len(result) == 10

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_musical_accent(50)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_times_in_valid_range(self) -> None:
        """All times are in [0, 1)."""
        result = generate_musical_accent(10)
        for p in result:
            assert 0.0 <= p.t < 1.0

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

    def test_custom_cycles(self) -> None:
        """Custom cycles parameter works."""
        result = generate_musical_accent(20, cycles=2.0)
        assert len(result) == 20

    def test_custom_attack_frac(self) -> None:
        """Custom attack_frac parameter works."""
        result = generate_musical_accent(20, attack_frac=0.2)
        assert len(result) == 20

    def test_custom_decay_rate(self) -> None:
        """Custom decay_rate parameter works."""
        result = generate_musical_accent(20, decay_rate=5.0)
        assert len(result) == 20

    def test_attack_frac_clamped_high(self) -> None:
        """attack_frac > 1.0 is clamped to 1.0."""
        result = generate_musical_accent(10, attack_frac=2.0)
        assert len(result) == 10

    def test_attack_frac_clamped_low(self) -> None:
        """attack_frac < 0.0 is clamped to 0.0."""
        result = generate_musical_accent(10, attack_frac=-0.5)
        assert len(result) == 10

    def test_decay_rate_clamped_low(self) -> None:
        """Negative decay_rate is clamped to 0.0."""
        result = generate_musical_accent(10, decay_rate=-5.0)
        assert len(result) == 10


class TestGenerateMusicalSwell:
    """Tests for generate_musical_swell function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of samples."""
        result = generate_musical_swell(10)
        assert len(result) == 10

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_musical_swell(50)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_times_in_valid_range(self) -> None:
        """All times are in [0, 1)."""
        result = generate_musical_swell(10)
        for p in result:
            assert 0.0 <= p.t < 1.0

    def test_n_less_than_two_raises(self) -> None:
        """n < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_musical_swell(1)

    def test_cycles_zero_raises(self) -> None:
        """cycles <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="cycles must be > 0"):
            generate_musical_swell(10, cycles=0)

    def test_cycles_negative_raises(self) -> None:
        """Negative cycles raises ValueError."""
        with pytest.raises(ValueError, match="cycles must be > 0"):
            generate_musical_swell(10, cycles=-1)

    def test_custom_cycles(self) -> None:
        """Custom cycles parameter works."""
        result = generate_musical_swell(20, cycles=2.0)
        assert len(result) == 20

    def test_custom_rise_frac(self) -> None:
        """Custom rise_frac parameter works."""
        result = generate_musical_swell(20, rise_frac=0.8)
        assert len(result) == 20

    def test_custom_rise_rate(self) -> None:
        """Custom rise_rate parameter works."""
        result = generate_musical_swell(20, rise_rate=5.0)
        assert len(result) == 20

    def test_rise_frac_clamped_high(self) -> None:
        """rise_frac > 1.0 is clamped to 1.0."""
        result = generate_musical_swell(10, rise_frac=2.0)
        assert len(result) == 10

    def test_rise_frac_clamped_low(self) -> None:
        """rise_frac < 0.0 is clamped to 0.0."""
        result = generate_musical_swell(10, rise_frac=-0.5)
        assert len(result) == 10

    def test_rise_rate_clamped_low(self) -> None:
        """Negative rise_rate is clamped to 0.0."""
        result = generate_musical_swell(10, rise_rate=-5.0)
        assert len(result) == 10


class TestGenerateBeatPulse:
    """Tests for generate_beat_pulse function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of samples."""
        result = generate_beat_pulse(10)
        assert len(result) == 10

    def test_values_in_valid_range(self) -> None:
        """All values are in [0, 1]."""
        result = generate_beat_pulse(50)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_times_in_valid_range(self) -> None:
        """All times are in [0, 1)."""
        result = generate_beat_pulse(10)
        for p in result:
            assert 0.0 <= p.t < 1.0

    def test_n_less_than_two_raises(self) -> None:
        """n < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_beat_pulse(1)

    def test_cycles_zero_raises(self) -> None:
        """cycles <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="cycles must be > 0"):
            generate_beat_pulse(10, cycles=0)

    def test_cycles_negative_raises(self) -> None:
        """Negative cycles raises ValueError."""
        with pytest.raises(ValueError, match="cycles must be > 0"):
            generate_beat_pulse(10, cycles=-1)

    def test_beat_subdivision_zero_raises(self) -> None:
        """beat_subdivision <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="beat_subdivision must be > 0"):
            generate_beat_pulse(10, beat_subdivision=0)

    def test_beat_subdivision_negative_raises(self) -> None:
        """Negative beat_subdivision raises ValueError."""
        with pytest.raises(ValueError, match="beat_subdivision must be > 0"):
            generate_beat_pulse(10, beat_subdivision=-1)

    def test_custom_cycles(self) -> None:
        """Custom cycles parameter works."""
        result = generate_beat_pulse(20, cycles=2.0)
        assert len(result) == 20

    def test_custom_beat_subdivision(self) -> None:
        """Custom beat_subdivision parameter works."""
        result = generate_beat_pulse(20, beat_subdivision=8)
        assert len(result) == 20

    def test_custom_phase(self) -> None:
        """Custom phase parameter works."""
        result = generate_beat_pulse(20, phase=0.25)
        assert len(result) == 20

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
