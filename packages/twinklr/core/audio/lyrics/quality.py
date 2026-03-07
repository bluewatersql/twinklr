"""Lyrics quality metrics (Phase 4).

Compute quality metrics from word-level timing to assess lyrics quality.
"""

from twinklr.core.audio.models.lyrics import LyricsQuality, LyricWord


def compute_quality_metrics(
    *,
    words: list[LyricWord],
    duration_ms: int,
    max_large_gap_s: float = 10.0,
    gap_merge_ms: float = 250.0,
    vocal_segments: list[dict[str, float]] | None = None,
) -> LyricsQuality:
    """Compute quality metrics from word-level timing.

    Args:
        words: List of words with timing
        duration_ms: Song duration in milliseconds
        max_large_gap_s: Threshold for large gap detection (seconds)
        gap_merge_ms: Merge gaps smaller than this (for coverage calculation)
        vocal_segments: Optional vocal detector segments for coverage validation
                       Format: [{"start_s": float, "end_s": float, ...}, ...]

    Returns:
        LyricsQuality with computed metrics
    """
    vocal_presence_pct: float | None = None
    if vocal_segments:
        vocal_presence_pct = _compute_vocal_presence_pct(vocal_segments, duration_ms)

    if not words:
        return LyricsQuality(vocal_presence_pct=vocal_presence_pct)

    # Compute coverage with gap merging (vocal time, not individual word time)
    # Merge word intervals with small gaps to represent continuous vocal phrases
    intervals: list[tuple[int, int]] = []
    for word in words:
        start = max(0, word.start_ms)
        end = min(duration_ms, word.end_ms)
        if start < end:
            intervals.append((start, end))

    # Sort by start time
    intervals.sort()

    # Merge overlapping/close intervals (gap_merge_ms tolerance)
    merged: list[tuple[int, int]] = []
    for start, end in intervals:
        if merged and start - merged[-1][1] <= gap_merge_ms:
            # Merge with previous interval
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            # New interval
            merged.append((start, end))

    # Calculate coverage from merged intervals
    total_coverage_ms = sum(end - start for start, end in merged)
    coverage_pct = total_coverage_ms / duration_ms if duration_ms > 0 else 0.0

    # vocal_presence_pct is already computed above from vocal_segments (if provided)

    # Detect violations
    monotonicity_violations = 0
    overlap_violations = 0
    out_of_bounds_violations = 0
    large_gaps_count = 0

    prev_word: LyricWord | None = None
    for word in words:
        # Check monotonicity (start_ms should not decrease)
        if prev_word and word.start_ms < prev_word.start_ms:
            monotonicity_violations += 1

        # Check overlaps (start should be >= prev end)
        if prev_word and word.start_ms < prev_word.end_ms:
            overlap_violations += 1

        # Check out of bounds
        if word.start_ms < 0 or word.end_ms > duration_ms or word.end_ms < word.start_ms:
            out_of_bounds_violations += 1

        # Check for large gaps
        if prev_word:
            gap_ms = word.start_ms - prev_word.end_ms
            max_gap_ms = max_large_gap_s * 1000
            if gap_ms > max_gap_ms:
                large_gaps_count += 1

        prev_word = word

    # Compute word durations
    durations = [word.end_ms - word.start_ms for word in words]
    avg_word_duration_ms = sum(durations) / len(durations) if durations else None
    min_word_duration_ms = min(durations) if durations else None

    return LyricsQuality(
        timed_word_coverage_pct=coverage_pct,
        vocal_presence_pct=vocal_presence_pct,
        monotonicity_violations=monotonicity_violations,
        overlap_violations=overlap_violations,
        out_of_bounds_violations=out_of_bounds_violations,
        large_gaps_count=large_gaps_count,
        avg_word_duration_ms=avg_word_duration_ms,
        min_word_duration_ms=min_word_duration_ms,
    )


def _compute_vocal_presence_pct(
    vocal_segments: list[dict[str, float]],
    duration_ms: int,
) -> float | None:
    """Compute vocal presence percentage from vocal detector segments.

    Merges overlapping segments then divides by song duration.

    Args:
        vocal_segments: List of dicts with 'start_s' and 'end_s' keys
        duration_ms: Song duration in milliseconds

    Returns:
        Vocal presence fraction [0, 1], or None if duration_ms is 0
    """
    if duration_ms <= 0:
        return None

    # Convert to ms intervals and sort
    intervals: list[tuple[int, int]] = sorted(
        (int(seg["start_s"] * 1000), int(seg["end_s"] * 1000)) for seg in vocal_segments
    )

    # Merge overlapping intervals
    merged: list[tuple[int, int]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    total_vocal_ms = sum(end - start for start, end in merged)
    return min(1.0, total_vocal_ms / duration_ms)
