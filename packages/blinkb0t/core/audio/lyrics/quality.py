"""Lyrics quality metrics (Phase 4).

Compute quality metrics from word-level timing to assess lyrics quality.
"""

from blinkb0t.core.audio.models.lyrics import LyricsQuality, LyricWord


def compute_quality_metrics(
    *,
    words: list[LyricWord],
    duration_ms: int,
    max_large_gap_s: float = 10.0,
) -> LyricsQuality:
    """Compute quality metrics from word-level timing.

    Args:
        words: List of words with timing
        duration_ms: Song duration in milliseconds
        max_large_gap_s: Threshold for large gap detection (seconds)

    Returns:
        LyricsQuality with computed metrics
    """
    if not words:
        return LyricsQuality()

    # Compute coverage
    total_coverage_ms = 0.0
    for word in words:
        # Clip word span to [0, duration_ms]
        start = max(0, word.start_ms)
        end = min(duration_ms, word.end_ms)
        word_duration = max(0, end - start)
        total_coverage_ms += word_duration

    coverage_pct = total_coverage_ms / duration_ms if duration_ms > 0 else 0.0

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
        coverage_pct=coverage_pct,
        monotonicity_violations=monotonicity_violations,
        overlap_violations=overlap_violations,
        out_of_bounds_violations=out_of_bounds_violations,
        large_gaps_count=large_gaps_count,
        avg_word_duration_ms=avg_word_duration_ms,
        min_word_duration_ms=min_word_duration_ms,
    )
