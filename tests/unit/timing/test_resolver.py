"""Tests for TimeResolver."""

import pytest

from twinklr.core.sequencer.timing.models import MusicalTiming, QuantizeMode, TimingMode
from twinklr.core.sequencer.timing.resolver import TimeResolver


class TestTimeResolver:
    """Test TimeResolver functionality."""

    @pytest.fixture
    def song_features(self):
        """Mock song features with known beat/bar positions."""
        return {
            "tempo_bpm": 120.0,
            "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],  # 120 BPM
            "bars_s": [0.0, 2.0, 4.0],  # 4/4 time, 2 second bars
            "duration_s": 6.0,
            "assumptions": {"beats_per_bar": 4},
        }

    @pytest.fixture
    def resolver(self, song_features):
        return TimeResolver(song_features)

    def test_bars_to_ms_exact(self, resolver):
        """Test exact bar boundary conversion."""
        assert resolver.bars_to_ms(0.0) == 0
        assert resolver.bars_to_ms(1.0) == 2000
        assert resolver.bars_to_ms(2.0) == 4000

    def test_bars_to_ms_interpolation(self, resolver):
        """Test fractional bar conversion."""
        # Bar 0.5 (halfway through first bar)
        assert resolver.bars_to_ms(0.5) == 1000

        # Bar 1.5 (halfway through second bar)
        assert resolver.bars_to_ms(1.5) == 3000

    def test_quantize_downbeat(self, resolver):
        """Test downbeat quantization."""
        # 2.3 should snap to 2.0
        result = resolver.bars_to_ms(2.3, quantize=QuantizeMode.DOWNBEAT)
        assert result == 4000  # Bar 2.0

    def test_quantize_any_beat(self, resolver):
        """Test beat quantization."""
        # 2.3 bars = 9.2 beats, should snap to 9 beats = 2.25 bars
        result = resolver.bars_to_ms(2.3, quantize=QuantizeMode.ANY_BEAT)
        expected_ms = resolver.bars_to_ms(2.25)  # 9 beats / 4 beats_per_bar
        assert abs(result - expected_ms) < 10  # Within 10ms

    def test_resolve_musical_timing(self, resolver):
        """Test MusicalTiming resolution."""
        timing = MusicalTiming(
            start_offset_bars=1.0, duration_bars=2.0, quantize_start=QuantizeMode.DOWNBEAT
        )

        start_ms, end_ms = resolver.resolve_timing(timing)

        assert start_ms == 2000  # Bar 1
        # Bar 3 may not exist, so this will extrapolate
        assert end_ms > start_ms

    def test_ms_to_bars_inverse(self, resolver):
        """Test inverse conversion."""
        # Convert bars to ms and back
        original_bars = 1.5
        ms = resolver.bars_to_ms(original_bars)
        recovered_bars = resolver.ms_to_bars(ms)

        assert abs(recovered_bars - original_bars) < 0.01  # Within 0.01 bars

    def test_get_bar_boundaries(self, resolver):
        """Test bar boundary retrieval."""
        boundaries = resolver.get_bar_boundaries_ms()
        assert boundaries == [0, 2000, 4000]

    def test_get_beat_positions(self, resolver):
        """Test beat position retrieval."""
        beats = resolver.get_beat_positions_ms()
        assert beats == [0, 500, 1000, 1500, 2000, 2500, 3000, 3500]

    def test_fallback_mode(self):
        """Test mathematical fallback when audio data missing."""
        empty_features = {
            "tempo_bpm": 120.0,
            "beats_s": [],
            "bars_s": [],
            "duration_s": 10.0,
            "assumptions": {"beats_per_bar": 4},
        }

        resolver = TimeResolver(empty_features)

        # Should use mathematical fallback
        # 120 BPM, 4 beats/bar = 2 second bars
        assert resolver.bars_to_ms(1.0) == 2000
        assert resolver.bars_to_ms(2.0) == 4000

    def test_resolve_absolute_timing(self, resolver):
        """Test that absolute timing mode passes through."""
        timing = MusicalTiming(mode=TimingMode.ABSOLUTE_MS, start_offset_ms=5000, duration_ms=2000)

        start_ms, end_ms = resolver.resolve_timing(timing)

        assert start_ms == 5000
        assert end_ms == 7000
