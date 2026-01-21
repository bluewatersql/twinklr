"""BeatGrid - Musical timing grid for bar and beat alignment.

Provides pre-calculated bar and beat boundaries for efficient timeline planning.
Wraps TimeResolver to provide a simpler interface focused on boundary access.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .resolver import TimeResolver


class BeatGrid(BaseModel):
    """Musical timing grid with pre-calculated bar and beat boundaries.

    Wraps TimeResolver to provide efficient access to timing boundaries
    for timeline planning and quantization.

    The BeatGrid is the interface between audio analysis (TimeResolver) and
    the rendering pipeline (TemplateTimelinePlanner, SegmentRenderer).

    Attributes:
        bar_boundaries: List of bar start times in milliseconds
        beat_boundaries: List of beat start times in milliseconds
        eighth_boundaries: List of eighth note times in milliseconds
        sixteenth_boundaries: List of sixteenth note times in milliseconds
        tempo_bpm: Average tempo in beats per minute
        beats_per_bar: Number of beats per bar (time signature)
        duration_ms: Total song duration in milliseconds

    Example:
        >>> resolver = TimeResolver(song_features)
        >>> beat_grid = BeatGrid.from_resolver(resolver, duration_ms=180000.0)
        >>> print(f"Song has {len(beat_grid.bar_boundaries)} bars")
        >>> first_chorus_start = beat_grid.bar_boundaries[8]  # Bar 8
    """

    model_config = ConfigDict(frozen=True)

    bar_boundaries: list[float] = Field(description="Bar start times in milliseconds")
    beat_boundaries: list[float] = Field(description="Beat start times in milliseconds")
    eighth_boundaries: list[float] = Field(description="Eighth note times in milliseconds")
    sixteenth_boundaries: list[float] = Field(description="Sixteenth note times in milliseconds")
    tempo_bpm: float = Field(description="Average tempo in beats per minute", gt=0.0)
    beats_per_bar: int = Field(
        description="Number of beats per bar (time signature numerator)", gt=0
    )
    duration_ms: float = Field(description="Total song duration in milliseconds", ge=0.0)

    @classmethod
    def from_resolver(cls, resolver: TimeResolver, duration_ms: float) -> BeatGrid:
        """Create BeatGrid from TimeResolver.

        Args:
            resolver: TimeResolver with audio analysis results
            duration_ms: Total song duration in milliseconds

        Returns:
            BeatGrid with pre-calculated boundaries

        Example:
            >>> resolver = TimeResolver(song_features)
            >>> beat_grid = BeatGrid.from_resolver(resolver, duration_ms=180000.0)
        """
        beat_boundaries_int = resolver.get_beat_positions_ms()
        bar_boundaries_int = resolver.get_bar_boundaries_ms()

        # Convert to float for BeatGrid (which uses float for timing precision)
        beat_boundaries = [float(b) for b in beat_boundaries_int]
        bar_boundaries = [float(b) for b in bar_boundaries_int]

        return cls(
            bar_boundaries=bar_boundaries,
            beat_boundaries=beat_boundaries,
            eighth_boundaries=cls._calculate_eighth_boundaries(beat_boundaries),
            sixteenth_boundaries=cls._calculate_sixteenth_boundaries(beat_boundaries),
            tempo_bpm=resolver.tempo_bpm,
            beats_per_bar=resolver.beats_per_bar,
            duration_ms=duration_ms,
        )

    @classmethod
    def from_song_features(
        cls, song_features: dict[str, Any], duration_ms: float | None = None
    ) -> BeatGrid:
        """Create BeatGrid directly from song features.

        Convenience method that creates TimeResolver internally.

        Args:
            song_features: Audio analysis results from AudioAnalyzer
            duration_ms: Optional total duration (will use song_features["duration_s"] if not provided)

        Returns:
            BeatGrid with pre-calculated boundaries

        Example:
            >>> song_features = {"tempo_bpm": 120, "beats_s": [...], "bars_s": [...]}
            >>> beat_grid = BeatGrid.from_song_features(song_features)
        """
        resolver = TimeResolver(song_features)

        # Get duration from parameter or song features
        if duration_ms is None:
            duration_s = song_features.get("duration_s", 0.0)
            duration_ms = duration_s * 1000.0

        return cls.from_resolver(resolver, duration_ms=duration_ms or 0.0)

    @property
    def total_bars(self) -> int:
        """Get total number of bars in the song.

        Returns:
            Number of complete bars

        Example:
            >>> print(f"Song has {beat_grid.total_bars} bars")
        """
        return len(self.bar_boundaries)

    @property
    def total_beats(self) -> int:
        """Get total number of beats in the song.

        Returns:
            Number of beats

        Example:
            >>> print(f"Song has {beat_grid.total_beats} beats")
        """
        return len(self.beat_boundaries)

    @property
    def total_eighths(self) -> int:
        """Get total number of eighth note boundaries.

        Returns:
            Number of eighth note boundaries

        Example:
            >>> print(f"Song has {beat_grid.total_eighths} eighth notes")
        """
        return len(self.eighth_boundaries)

    @property
    def total_sixteenths(self) -> int:
        """Get total number of sixteenth note boundaries.

        Returns:
            Number of sixteenth note boundaries

        Example:
            >>> print(f"Song has {beat_grid.total_sixteenths} sixteenth notes")
        """
        return len(self.sixteenth_boundaries)

    @property
    def ms_per_bar(self) -> float:
        """Get average bar duration in milliseconds.

        Returns:
            Average milliseconds per bar

        Example:
            >>> bar_duration = beat_grid.ms_per_bar
            >>> print(f"Each bar is ~{bar_duration:.0f}ms")
        """
        if len(self.bar_boundaries) < 2:
            # Fallback to mathematical calculation
            return (60000.0 / self.tempo_bpm) * self.beats_per_bar

        # Calculate average from actual boundaries
        total_duration = self.bar_boundaries[-1] - self.bar_boundaries[0]
        return total_duration / (len(self.bar_boundaries) - 1)

    @property
    def ms_per_beat(self) -> float:
        """Get average beat duration in milliseconds.

        Returns:
            Average milliseconds per beat

        Example:
            >>> beat_duration = beat_grid.ms_per_beat
            >>> print(f"Each beat is ~{beat_duration:.0f}ms")
        """
        if len(self.beat_boundaries) < 2:
            # Fallback to mathematical calculation
            return 60000.0 / self.tempo_bpm

        # Calculate average from actual boundaries
        total_duration = self.beat_boundaries[-1] - self.beat_boundaries[0]
        return total_duration / (len(self.beat_boundaries) - 1)

    def get_bar_start_ms(self, bar_index: int) -> float:
        """Get the start time of a specific bar.

        Args:
            bar_index: Bar index (0-based)

        Returns:
            Start time in milliseconds

        Raises:
            IndexError: If bar_index is out of range

        Example:
            >>> chorus_start = beat_grid.get_bar_start_ms(8)  # Bar 8
        """
        return self.bar_boundaries[bar_index]

    def get_beat_time_ms(self, beat_index: int) -> float:
        """Get the time of a specific beat.

        Args:
            beat_index: Beat index (0-based)

        Returns:
            Time in milliseconds

        Raises:
            IndexError: If beat_index is out of range

        Example:
            >>> beat_time = beat_grid.get_beat_time_ms(32)  # Beat 32
        """
        return self.beat_boundaries[beat_index]

    def snap_to_nearest_bar(self, time_ms: float) -> float:
        """Snap arbitrary time to nearest bar boundary.

        Critical for precise beat synchronization - ensures effect timing
        aligns exactly with bar boundaries even if LLM-generated times
        are slightly off.

        Args:
            time_ms: Arbitrary time in milliseconds

        Returns:
            Time of nearest bar boundary in milliseconds

        Example:
            >>> # Snap slightly off-time to exact bar boundary
            >>> precise_time = beat_grid.snap_to_nearest_bar(2050.0)  # → 2000.0
        """
        if not self.bar_boundaries:
            return time_ms

        # Find nearest bar boundary
        min_distance = float("inf")
        nearest_bar_time = self.bar_boundaries[0]

        for bar_time in self.bar_boundaries:
            distance = abs(time_ms - bar_time)
            if distance < min_distance:
                min_distance = distance
                nearest_bar_time = bar_time

        return nearest_bar_time

    def snap_to_nearest_beat(self, time_ms: float) -> float:
        """Snap arbitrary time to nearest beat boundary.

        Critical for precise beat synchronization - ensures effect timing
        aligns exactly with beat boundaries for tight musical sync.

        Args:
            time_ms: Arbitrary time in milliseconds

        Returns:
            Time of nearest beat boundary in milliseconds

        Example:
            >>> # Snap to exact beat for precise sync
            >>> precise_time = beat_grid.snap_to_nearest_beat(530.0)  # → 500.0
        """
        if not self.beat_boundaries:
            return time_ms

        # Find nearest beat boundary using binary search for efficiency
        # beat_boundaries is sorted
        import bisect

        # Find insertion point
        idx = bisect.bisect_left(self.beat_boundaries, time_ms)

        # Handle edge cases
        if idx == 0:
            return self.beat_boundaries[0]
        if idx >= len(self.beat_boundaries):
            return self.beat_boundaries[-1]

        # Compare distances to neighbors
        before = self.beat_boundaries[idx - 1]
        after = self.beat_boundaries[idx]

        if abs(time_ms - before) <= abs(time_ms - after):
            return before
        else:
            return after

    def snap_to_beat_or_bar(self, time_ms: float, prefer_bar: bool = False) -> tuple[float, str]:
        """Snap to nearest beat or bar boundary with type indication.

        Useful when you want to know what type of boundary was snapped to
        (e.g., for transition logic that differs at bar vs beat boundaries).

        Args:
            time_ms: Arbitrary time in milliseconds
            prefer_bar: If True and time is equidistant from beat/bar, choose bar

        Returns:
            Tuple of (snapped_time_ms, boundary_type) where boundary_type is "bar" or "beat"

        Example:
            >>> time, boundary = beat_grid.snap_to_beat_or_bar(2010.0)
            >>> if boundary == "bar":
            ...     # Use stronger transition at bar boundaries
        """
        nearest_beat = self.snap_to_nearest_beat(time_ms)
        nearest_bar = self.snap_to_nearest_bar(time_ms)

        beat_distance = abs(time_ms - nearest_beat)
        bar_distance = abs(time_ms - nearest_bar)

        # Check if this beat is also a bar (downbeat)
        is_bar_boundary = nearest_beat in self.bar_boundaries

        if is_bar_boundary:
            return (nearest_beat, "bar")
        elif prefer_bar and bar_distance <= beat_distance:
            return (nearest_bar, "bar")
        else:
            return (nearest_beat, "beat")

    def snap_to_grid(
        self, time_ms: float, quantize_to: str = "beat", direction: str = "nearest"
    ) -> float:
        """Snap arbitrary time to musical grid boundary.

        This is the comprehensive quantization method supporting all grid levels
        and snapping directions. Critical for precise beat synchronization.

        Args:
            time_ms: Arbitrary time in milliseconds
            quantize_to: Grid level - "bar", "beat", "eighth", or "sixteenth"
            direction: Snapping direction - "nearest", "floor" (down), or "ceil" (up)

        Returns:
            Quantized time in milliseconds (snapped to boundary)

        Raises:
            ValueError: If quantize_to or direction is invalid

        Example:
            >>> # Snap to nearest beat
            >>> precise_time = grid.snap_to_grid(2350.0, quantize_to="beat", direction="nearest")
            >>> # Returns: 2000.0

            >>> # Snap down to previous eighth note
            >>> time = grid.snap_to_grid(1240.0, quantize_to="eighth", direction="floor")
            >>> # Returns: 1000.0

            >>> # Snap up to next sixteenth
            >>> time = grid.snap_to_grid(120.0, quantize_to="sixteenth", direction="ceil")
            >>> # Returns: 125.0
        """
        # Validate inputs
        valid_levels = {"bar", "beat", "eighth", "sixteenth"}
        if quantize_to not in valid_levels:
            raise ValueError(f"Invalid quantize_to: '{quantize_to}'. Must be one of {valid_levels}")

        valid_directions = {"nearest", "floor", "ceil"}
        if direction not in valid_directions:
            raise ValueError(f"Invalid direction: '{direction}'. Must be one of {valid_directions}")

        # Get appropriate boundary list
        if quantize_to == "bar":
            boundaries = self.bar_boundaries
        elif quantize_to == "beat":
            boundaries = self.beat_boundaries
        elif quantize_to == "eighth":
            boundaries = self.eighth_boundaries
        else:  # sixteenth
            boundaries = self.sixteenth_boundaries

        if not boundaries:
            return time_ms

        # Apply snapping logic based on direction
        if direction == "nearest":
            return self._snap_nearest(time_ms, boundaries)
        elif direction == "floor":
            return self._snap_floor(time_ms, boundaries)
        else:  # ceil
            return self._snap_ceil(time_ms, boundaries)

    def _snap_nearest(self, time_ms: float, boundaries: list[float]) -> float:
        """Snap to nearest boundary using binary search for efficiency."""
        import bisect

        if not boundaries:
            return time_ms

        # Find insertion point
        idx = bisect.bisect_left(boundaries, time_ms)

        # Handle edge cases
        if idx == 0:
            return boundaries[0]
        if idx >= len(boundaries):
            return boundaries[-1]

        # Compare distances to neighbors
        before = boundaries[idx - 1]
        after = boundaries[idx]

        # 0.01ms tolerance for floating-point comparison (microsecond precision)
        if abs(time_ms - before) <= 0.01:
            return before
        if abs(time_ms - after) <= 0.01:
            return after

        # Return nearest (prefer higher value on ties)
        if abs(time_ms - before) < abs(time_ms - after):
            return before
        else:
            return after

    def _snap_floor(self, time_ms: float, boundaries: list[float]) -> float:
        """Snap down to previous boundary (or stay if on boundary)."""
        import bisect

        if not boundaries:
            return time_ms

        # Check if we're within 0.01ms of any boundary (on boundary for floating-point)
        for boundary in boundaries:
            if abs(time_ms - boundary) <= 0.01:
                return boundary

        # Find insertion point (where time_ms would be inserted)
        idx = bisect.bisect_right(boundaries, time_ms)

        # If we're past all boundaries, return last
        if idx >= len(boundaries):
            return boundaries[-1]

        # If we're before first boundary, return first
        if idx == 0:
            return boundaries[0]

        # Return previous boundary (floor)
        return boundaries[idx - 1]

    def _snap_ceil(self, time_ms: float, boundaries: list[float]) -> float:
        """Snap up to next boundary (or stay if on boundary)."""
        import bisect

        if not boundaries:
            return time_ms

        # Find insertion point
        idx = bisect.bisect_left(boundaries, time_ms)

        # If we're past all boundaries, return last
        if idx >= len(boundaries):
            return boundaries[-1]

        # Check if we're within 0.01ms of the boundary (tolerance for floating-point)
        if abs(time_ms - boundaries[idx]) <= 0.01:
            return boundaries[idx]

        # Otherwise, return next boundary
        if idx < len(boundaries):
            return boundaries[idx]

        return boundaries[-1]

    # ======================================================================
    # Private helper methods for subdivision calculation
    # ======================================================================

    @staticmethod
    def _calculate_eighth_boundaries(beat_boundaries: list[float]) -> list[float]:
        """Calculate eighth note boundaries from beat boundaries.

        Each beat is divided into 2 eighth notes. This inserts a subdivision
        point at the midpoint between each pair of beats.

        Args:
            beat_boundaries: List of beat times in milliseconds

        Returns:
            List of eighth note times (includes original beats + midpoints)

        Example:
            Beats at [0, 500, 1000] → Eighths at [0, 250, 500, 750, 1000]
        """
        if len(beat_boundaries) == 0:
            return []

        if len(beat_boundaries) == 1:
            # Only one beat - no subdivisions possible
            return beat_boundaries.copy()

        eighths = []

        # For each pair of consecutive beats, add beat and midpoint
        for i in range(len(beat_boundaries) - 1):
            beat_start = beat_boundaries[i]
            beat_end = beat_boundaries[i + 1]
            midpoint = (beat_start + beat_end) / 2.0

            eighths.append(beat_start)
            eighths.append(midpoint)

        # Add the final beat
        eighths.append(beat_boundaries[-1])

        return eighths

    @staticmethod
    def _calculate_sixteenth_boundaries(beat_boundaries: list[float]) -> list[float]:
        """Calculate sixteenth note boundaries from beat boundaries.

        Each beat is divided into 4 sixteenth notes. This inserts 3 subdivision
        points at 0.25, 0.5, and 0.75 of the distance between each pair of beats.

        Args:
            beat_boundaries: List of beat times in milliseconds

        Returns:
            List of sixteenth note times (includes original beats + subdivisions)

        Example:
            Beats at [0, 400] → Sixteenths at [0, 100, 200, 300, 400]
        """
        if len(beat_boundaries) == 0:
            return []

        if len(beat_boundaries) == 1:
            # Only one beat - no subdivisions possible
            return beat_boundaries.copy()

        sixteenths = []

        # For each pair of consecutive beats, add beat and 3 subdivision points
        for i in range(len(beat_boundaries) - 1):
            beat_start = beat_boundaries[i]
            beat_end = beat_boundaries[i + 1]
            duration = beat_end - beat_start

            # Add the beat and 3 sixteenth note subdivisions
            sixteenths.append(beat_start)
            sixteenths.append(beat_start + duration * 0.25)
            sixteenths.append(beat_start + duration * 0.50)
            sixteenths.append(beat_start + duration * 0.75)

        # Add the final beat
        sixteenths.append(beat_boundaries[-1])

        return sixteenths
