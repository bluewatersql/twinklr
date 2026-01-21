"""Tests for Beat Mapper Protocol.

Tests MockBeatMapper implementation.
All 6 test cases per implementation plan Task 0.10.
"""


from blinkb0t.core.sequencer.moving_heads.models.protocols import MockBeatMapper


class TestMockBeatMapper120BPM:
    """Tests for MockBeatMapper at 120 BPM (default)."""

    def test_at_120_bpm(self) -> None:
        """Test MockBeatMapper at 120 BPM."""
        mapper = MockBeatMapper(bpm=120.0, beats_per_bar=4)

        # At 120 BPM, one beat = 500ms, one bar = 2000ms
        assert mapper.ms_per_beat == 500.0
        assert mapper.ms_per_bar == 2000.0

        # 1 bar = 2000ms
        assert mapper.bars_to_ms(1.0) == 2000.0

        # 4 bars = 8000ms
        assert mapper.bars_to_ms(4.0) == 8000.0


class TestMockBeatMapper90BPM:
    """Tests for MockBeatMapper at 90 BPM."""

    def test_at_90_bpm(self) -> None:
        """Test MockBeatMapper at 90 BPM."""
        mapper = MockBeatMapper(bpm=90.0, beats_per_bar=4)

        # At 90 BPM, one beat = 666.67ms, one bar = 2666.67ms
        assert abs(mapper.ms_per_beat - 666.6666666666666) < 0.001
        assert abs(mapper.ms_per_bar - 2666.6666666666665) < 0.001

        # 1 bar
        assert abs(mapper.bars_to_ms(1.0) - 2666.6666666666665) < 0.001


class TestBarsToMsRoundtrip:
    """Tests for bars_to_ms roundtrip accuracy."""

    def test_bars_to_ms_roundtrip_accuracy(self) -> None:
        """Test bars_to_ms roundtrip accuracy."""
        mapper = MockBeatMapper(bpm=120.0)

        for bars in [0.0, 0.25, 0.5, 1.0, 2.5, 4.0, 8.0]:
            ms = mapper.bars_to_ms(bars)
            roundtrip = mapper.ms_to_bars(ms)
            assert abs(roundtrip - bars) < 1e-10, f"Roundtrip failed for {bars} bars"


class TestMsToBarsRoundtrip:
    """Tests for ms_to_bars roundtrip accuracy."""

    def test_ms_to_bars_roundtrip_accuracy(self) -> None:
        """Test ms_to_bars roundtrip accuracy."""
        mapper = MockBeatMapper(bpm=120.0)

        for ms in [0.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0]:
            bars = mapper.ms_to_bars(ms)
            roundtrip = mapper.bars_to_ms(bars)
            assert abs(roundtrip - ms) < 1e-10, f"Roundtrip failed for {ms} ms"


class TestGetBeatAt:
    """Tests for get_beat_at method."""

    def test_get_beat_at_beats_1_2_3_4(self) -> None:
        """Test get_beat_at for beat 1, 2, 3, 4."""
        mapper = MockBeatMapper(bpm=120.0)  # 500ms per beat

        # Beat 1: 0ms to 499ms
        assert mapper.get_beat_at(0.0) == 1
        assert mapper.get_beat_at(250.0) == 1
        assert mapper.get_beat_at(499.0) == 1

        # Beat 2: 500ms to 999ms
        assert mapper.get_beat_at(500.0) == 2
        assert mapper.get_beat_at(750.0) == 2

        # Beat 3: 1000ms to 1499ms
        assert mapper.get_beat_at(1000.0) == 3
        assert mapper.get_beat_at(1250.0) == 3

        # Beat 4: 1500ms to 1999ms
        assert mapper.get_beat_at(1500.0) == 4
        assert mapper.get_beat_at(1750.0) == 4

        # Beat 5 (next bar): 2000ms+
        assert mapper.get_beat_at(2000.0) == 5


class TestFractionalBars:
    """Tests for fractional bars conversion."""

    def test_fractional_bars_conversion(self) -> None:
        """Test fractional bars conversion."""
        mapper = MockBeatMapper(bpm=120.0)  # 2000ms per bar

        # Quarter bar
        assert mapper.bars_to_ms(0.25) == 500.0  # 1/4 of 2000ms

        # Half bar
        assert mapper.bars_to_ms(0.5) == 1000.0  # 1/2 of 2000ms

        # Three-quarter bar
        assert mapper.bars_to_ms(0.75) == 1500.0  # 3/4 of 2000ms

        # 1.5 bars
        assert mapper.bars_to_ms(1.5) == 3000.0

        # Reverse: ms to bars
        assert mapper.ms_to_bars(500.0) == 0.25
        assert mapper.ms_to_bars(1000.0) == 0.5
        assert mapper.ms_to_bars(1500.0) == 0.75
        assert mapper.ms_to_bars(3000.0) == 1.5


class TestProtocolCompliance:
    """Tests for protocol compliance."""

    def test_mock_beat_mapper_has_required_methods(self) -> None:
        """Test MockBeatMapper implements all protocol methods."""
        mapper = MockBeatMapper()

        # Verify methods exist and are callable
        assert callable(mapper.bars_to_ms)
        assert callable(mapper.ms_to_bars)
        assert callable(mapper.get_beat_at)

        # Verify return types
        assert isinstance(mapper.bars_to_ms(1.0), float)
        assert isinstance(mapper.ms_to_bars(1000.0), float)
        assert isinstance(mapper.get_beat_at(1000.0), int)
