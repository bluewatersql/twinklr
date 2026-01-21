"""Tests for timing models."""

from pydantic import ValidationError
import pytest

from blinkb0t.core.domains.sequencing.models.timing import MusicalTiming, QuantizeMode, TimingMode


class TestTimingMode:
    """Test TimingMode enum."""

    def test_musical_mode(self):
        """Test musical timing mode."""
        assert TimingMode.MUSICAL == "musical"

    def test_absolute_mode(self):
        """Test absolute timing mode."""
        assert TimingMode.ABSOLUTE_MS == "absolute_ms"


class TestQuantizeMode:
    """Test QuantizeMode enum."""

    def test_quantize_modes(self):
        """Test all quantize modes."""
        assert QuantizeMode.NONE == "none"
        assert QuantizeMode.ANY_BEAT == "any_beat"
        assert QuantizeMode.DOWNBEAT == "downbeat"
        assert QuantizeMode.HALF_BAR == "half_bar"
        assert QuantizeMode.QUARTER_BAR == "quarter_bar"


class TestMusicalTiming:
    """Test MusicalTiming model."""

    def test_default_musical_timing(self):
        """Test default musical timing (musical mode)."""
        timing = MusicalTiming()

        assert timing.mode == TimingMode.MUSICAL
        assert timing.start_offset_bars == 0.0
        assert timing.duration_bars == 1.0
        assert timing.quantize_start == QuantizeMode.ANY_BEAT
        assert timing.quantize_end == QuantizeMode.ANY_BEAT

    def test_custom_musical_timing(self):
        """Test custom musical timing values."""
        timing = MusicalTiming(
            start_offset_bars=2.5, duration_bars=4.0, quantize_start=QuantizeMode.DOWNBEAT
        )

        assert timing.start_offset_bars == 2.5
        assert timing.duration_bars == 4.0
        assert timing.quantize_start == QuantizeMode.DOWNBEAT

    def test_absolute_timing(self):
        """Test absolute timing mode."""
        timing = MusicalTiming(mode=TimingMode.ABSOLUTE_MS, start_offset_ms=5000, duration_ms=2000)

        assert timing.mode == TimingMode.ABSOLUTE_MS
        assert timing.start_offset_ms == 5000
        assert timing.duration_ms == 2000

    def test_musical_mode_negative_offset_fails(self):
        """Test that negative offset fails in musical mode."""
        with pytest.raises(ValidationError) as exc_info:
            MusicalTiming(start_offset_bars=-1.0)

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_musical_mode_zero_duration_fails(self):
        """Test that zero duration fails in musical mode."""
        with pytest.raises(ValidationError) as exc_info:
            MusicalTiming(duration_bars=0.0)

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_musical_mode_negative_duration_fails(self):
        """Test that negative duration fails in musical mode."""
        with pytest.raises(ValidationError) as exc_info:
            MusicalTiming(duration_bars=-2.0)

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_absolute_mode_requires_start_offset_ms(self):
        """Test that absolute mode requires start_offset_ms."""
        with pytest.raises(ValidationError) as exc_info:
            MusicalTiming(mode=TimingMode.ABSOLUTE_MS, duration_ms=1000)

        errors = exc_info.value.errors()
        assert any("start_offset_ms" in str(e) for e in errors)

    def test_absolute_mode_requires_duration_ms(self):
        """Test that absolute mode requires duration_ms."""
        with pytest.raises(ValidationError) as exc_info:
            MusicalTiming(mode=TimingMode.ABSOLUTE_MS, start_offset_ms=1000)

        errors = exc_info.value.errors()
        assert any("duration_ms" in str(e) for e in errors)

    def test_absolute_mode_negative_start_fails(self):
        """Test that negative start_offset_ms fails."""
        with pytest.raises(ValidationError) as exc_info:
            MusicalTiming(mode=TimingMode.ABSOLUTE_MS, start_offset_ms=-1000, duration_ms=1000)

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_absolute_mode_zero_duration_fails(self):
        """Test that zero duration_ms fails."""
        with pytest.raises(ValidationError) as exc_info:
            MusicalTiming(mode=TimingMode.ABSOLUTE_MS, start_offset_ms=1000, duration_ms=0)

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_immutability(self):
        """Test that MusicalTiming is immutable."""
        timing = MusicalTiming(start_offset_bars=2.0)

        with pytest.raises((ValidationError, AttributeError)):
            timing.start_offset_bars = 3.0
