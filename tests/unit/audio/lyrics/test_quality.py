"""Tests for lyrics quality metrics (Phase 4).

Testing quality metrics computation from word-level timing.
"""

import pytest

from twinklr.core.audio.lyrics.quality import compute_quality_metrics
from twinklr.core.audio.models.lyrics import LyricWord


class TestComputeQualityMetrics:
    """Test quality metrics computation."""

    def test_empty_words(self):
        """Empty words list returns default metrics."""
        quality = compute_quality_metrics(words=[], duration_ms=180000)

        assert quality.coverage_pct == 0.0
        assert quality.monotonicity_violations == 0
        assert quality.overlap_violations == 0
        assert quality.out_of_bounds_violations == 0
        assert quality.large_gaps_count == 0
        assert quality.avg_word_duration_ms is None
        assert quality.min_word_duration_ms is None

    def test_perfect_coverage(self):
        """Words covering entire duration."""
        words = [
            LyricWord(text="word1", start_ms=0, end_ms=60000),
            LyricWord(text="word2", start_ms=60000, end_ms=120000),
            LyricWord(text="word3", start_ms=120000, end_ms=180000),
        ]

        quality = compute_quality_metrics(words=words, duration_ms=180000)

        assert quality.coverage_pct == 1.0
        assert quality.monotonicity_violations == 0
        assert quality.overlap_violations == 0
        assert quality.out_of_bounds_violations == 0
        assert quality.avg_word_duration_ms == 60000.0

    def test_partial_coverage(self):
        """Words covering part of duration."""
        words = [
            LyricWord(text="word1", start_ms=10000, end_ms=20000),  # 10s
            LyricWord(text="word2", start_ms=30000, end_ms=40000),  # 10s
        ]

        quality = compute_quality_metrics(words=words, duration_ms=100000)

        assert quality.coverage_pct == 0.2  # 20s / 100s

    def test_monotonicity_violation(self):
        """Detect timestamps going backward."""
        words = [
            LyricWord(text="word1", start_ms=10000, end_ms=20000),
            LyricWord(text="word2", start_ms=5000, end_ms=15000),  # Goes backward
        ]

        quality = compute_quality_metrics(words=words, duration_ms=100000)

        assert quality.monotonicity_violations == 1

    def test_overlap_violation(self):
        """Detect overlapping words."""
        words = [
            LyricWord(text="word1", start_ms=10000, end_ms=25000),
            LyricWord(text="word2", start_ms=20000, end_ms=30000),  # Overlaps
        ]

        quality = compute_quality_metrics(words=words, duration_ms=100000)

        assert quality.overlap_violations == 1

    def test_out_of_bounds_violation(self):
        """Detect words outside song duration."""
        words = [
            LyricWord(text="word1", start_ms=5000, end_ms=0),  # end < start
            LyricWord(text="word2", start_ms=95000, end_ms=110000),  # Beyond duration
        ]

        quality = compute_quality_metrics(words=words, duration_ms=100000)

        assert quality.out_of_bounds_violations == 2

    def test_large_gaps(self):
        """Detect large gaps between words."""
        words = [
            LyricWord(text="word1", start_ms=0, end_ms=5000),
            LyricWord(text="word2", start_ms=20000, end_ms=25000),  # 15s gap
            LyricWord(text="word3", start_ms=30000, end_ms=35000),  # 5s gap (ok)
        ]

        # Default max gap is 10 seconds
        quality = compute_quality_metrics(words=words, duration_ms=100000)

        assert quality.large_gaps_count == 1  # Only first gap is >10s

    def test_word_durations(self):
        """Compute average and minimum word durations."""
        words = [
            LyricWord(text="word1", start_ms=0, end_ms=500),  # 500ms
            LyricWord(text="word2", start_ms=500, end_ms=1500),  # 1000ms
            LyricWord(text="word3", start_ms=1500, end_ms=2000),  # 500ms
        ]

        quality = compute_quality_metrics(words=words, duration_ms=100000)

        assert quality.avg_word_duration_ms == pytest.approx(666.67, rel=0.01)
        assert quality.min_word_duration_ms == 500.0

    def test_custom_max_gap(self):
        """Custom max gap threshold."""
        words = [
            LyricWord(text="word1", start_ms=0, end_ms=5000),
            LyricWord(text="word2", start_ms=10000, end_ms=15000),  # 5s gap
        ]

        # With max_gap=3s, this 5s gap should count
        quality = compute_quality_metrics(words=words, duration_ms=100000, max_large_gap_s=3.0)

        assert quality.large_gaps_count == 1

    def test_zero_duration_word(self):
        """Handle word with zero duration (start == end)."""
        words = [
            LyricWord(text="word1", start_ms=1000, end_ms=1000),  # Zero duration
            LyricWord(text="word2", start_ms=2000, end_ms=3000),
        ]

        quality = compute_quality_metrics(words=words, duration_ms=10000)

        # Should not crash, zero-duration word contributes 0 to coverage
        assert quality.coverage_pct == pytest.approx(0.1)  # 1s / 10s
        assert quality.min_word_duration_ms == 0.0
