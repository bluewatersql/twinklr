"""Tests for timing models."""

from pydantic import ValidationError
import pytest

from twinklr.core.sequencer.timing.models import MusicalTiming, QuantizeMode


class TestTimingMode:
    """Test TimingMode enum."""

    def test_quantize_modes(self):
        """Test all quantize modes."""
        assert QuantizeMode.NONE == "none"
        assert QuantizeMode.ANY_BEAT == "any_beat"
        assert QuantizeMode.DOWNBEAT == "downbeat"
        assert QuantizeMode.HALF_BAR == "half_bar"
        assert QuantizeMode.QUARTER_BAR == "quarter_bar"


class TestMusicalTiming:
    """Test MusicalTiming model."""

    def test_custom_musical_timing(self):
        """Test custom musical timing values."""
        timing = MusicalTiming(
            start_offset_bars=2.5, duration_bars=4.0, quantize_start=QuantizeMode.DOWNBEAT
        )

        assert timing.start_offset_bars == 2.5
        assert timing.duration_bars == 4.0
        assert timing.quantize_start == QuantizeMode.DOWNBEAT

    def test_immutability(self):
        """Test that MusicalTiming is immutable."""
        timing = MusicalTiming(start_offset_bars=2.0)

        with pytest.raises((ValidationError, AttributeError)):
            timing.start_offset_bars = 3.0
