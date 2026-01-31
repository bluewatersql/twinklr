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
    if not words:
        return LyricsQuality()

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

    # Optional: Validate against vocal segments if provided
    # This can help detect if word timing is significantly off from actual vocals
    if vocal_segments:
        # Convert vocal segments to ms intervals
        vocal_intervals = [
            (int(seg["start_s"] * 1000), int(seg["end_s"] * 1000)) for seg in vocal_segments
        ]

        # Compute overlap between word intervals and vocal segments
        total_overlap_ms = 0
        for word_start, word_end in merged:
            for vocal_start, vocal_end in vocal_intervals:
                # Compute intersection
                overlap_start = max(word_start, vocal_start)
                overlap_end = min(word_end, vocal_end)
                if overlap_start < overlap_end:
                    total_overlap_ms += overlap_end - overlap_start

        # If word coverage significantly exceeds vocal segments, may indicate timing issues
        # (But this is normal if vocal detector misses some vocals, so just informational)
        # vocal_total_ms = sum(end - start for start, end in vocal_intervals)  # Reserved for future use

        # Store as metadata for debugging (could add to model if needed)
        # For now, just use word-based coverage as the primary metric

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
