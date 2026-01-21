"""Beat Mapper Protocol for the moving head sequencer.

This module defines the BeatMapper protocol for converting between
musical time (bars/beats) and absolute time (milliseconds).
"""

from typing import Protocol


class BeatMapper(Protocol):
    """Protocol for converting between bars/beats and milliseconds.

    All timing in the sequencer uses this protocol to convert between
    musical time (bars, beats) and absolute time (milliseconds).
    """

    def bars_to_ms(self, bars: float) -> float:
        """Convert bars to milliseconds.

        Args:
            bars: Number of bars (can be fractional).

        Returns:
            Equivalent time in milliseconds.
        """
        ...

    def ms_to_bars(self, ms: float) -> float:
        """Convert milliseconds to bars.

        Args:
            ms: Time in milliseconds.

        Returns:
            Equivalent time in bars (can be fractional).
        """
        ...

    def get_beat_at(self, ms: float) -> int:
        """Get the beat number at a given time.

        Args:
            ms: Time in milliseconds.

        Returns:
            Beat number (1-indexed, continuous across bars).
        """
        ...


class MockBeatMapper:
    """Mock implementation of BeatMapper for testing.

    Provides a simple, predictable beat mapper with configurable BPM
    and beats per bar for use in unit tests.

    Attributes:
        bpm: Beats per minute.
        beats_per_bar: Number of beats in each bar.
        ms_per_beat: Milliseconds per beat (computed).
        ms_per_bar: Milliseconds per bar (computed).

    Example:
        >>> mapper = MockBeatMapper(bpm=120.0, beats_per_bar=4)
        >>> mapper.bars_to_ms(1.0)
        2000.0
        >>> mapper.ms_to_bars(2000.0)
        1.0
        >>> mapper.get_beat_at(500.0)
        2
    """

    def __init__(self, bpm: float = 120.0, beats_per_bar: int = 4) -> None:
        """Initialize MockBeatMapper.

        Args:
            bpm: Beats per minute. Defaults to 120.0.
            beats_per_bar: Number of beats per bar. Defaults to 4.
        """
        self.bpm = bpm
        self.beats_per_bar = beats_per_bar
        self.ms_per_beat = 60_000.0 / bpm
        self.ms_per_bar = self.ms_per_beat * beats_per_bar

    def bars_to_ms(self, bars: float) -> float:
        """Convert bars to milliseconds.

        Args:
            bars: Number of bars (can be fractional).

        Returns:
            Equivalent time in milliseconds.
        """
        return bars * self.ms_per_bar

    def ms_to_bars(self, ms: float) -> float:
        """Convert milliseconds to bars.

        Args:
            ms: Time in milliseconds.

        Returns:
            Equivalent time in bars (can be fractional).
        """
        return ms / self.ms_per_bar

    def get_beat_at(self, ms: float) -> int:
        """Get the beat number at a given time.

        Args:
            ms: Time in milliseconds.

        Returns:
            Beat number (1-indexed, continuous across bars).
        """
        return int(ms / self.ms_per_beat) + 1
