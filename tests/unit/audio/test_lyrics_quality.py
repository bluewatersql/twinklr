"""Tests for LyricsQuality model split and compute_quality_metrics with vocal_segments."""

from pydantic import ValidationError
import pytest

from twinklr.core.audio.lyrics.quality import compute_quality_metrics
from twinklr.core.audio.models.lyrics import LyricsQuality, LyricWord

# ---------------------------------------------------------------------------
# LyricsQuality model tests
# ---------------------------------------------------------------------------


class TestLyricsQualityModel:
    """Tests for the LyricsQuality Pydantic model."""

    def test_default_construction(self):
        """Model can be constructed with all defaults."""
        q = LyricsQuality()
        assert q.timed_word_coverage_pct == 0.0
        assert q.vocal_presence_pct is None
        assert q.monotonicity_violations == 0
        assert q.overlap_violations == 0
        assert q.out_of_bounds_violations == 0
        assert q.large_gaps_count == 0
        assert q.avg_word_duration_ms is None
        assert q.min_word_duration_ms is None

    def test_coverage_pct_backward_compat_property(self):
        """coverage_pct property returns timed_word_coverage_pct (deprecated alias)."""
        q = LyricsQuality(timed_word_coverage_pct=0.75)
        assert q.coverage_pct == 0.75

    def test_coverage_pct_zero(self):
        """coverage_pct returns 0.0 when timed_word_coverage_pct is 0."""
        q = LyricsQuality(timed_word_coverage_pct=0.0)
        assert q.coverage_pct == 0.0

    def test_vocal_presence_pct_can_be_set(self):
        """vocal_presence_pct can be set to a valid float."""
        q = LyricsQuality(timed_word_coverage_pct=0.5, vocal_presence_pct=0.8)
        assert q.vocal_presence_pct == 0.8

    def test_vocal_presence_pct_none_by_default(self):
        """vocal_presence_pct defaults to None."""
        q = LyricsQuality(timed_word_coverage_pct=0.5)
        assert q.vocal_presence_pct is None

    def test_timed_word_coverage_pct_bounds(self):
        """timed_word_coverage_pct is bounded [0, 1]."""
        q = LyricsQuality(timed_word_coverage_pct=1.0)
        assert q.timed_word_coverage_pct == 1.0

        with pytest.raises(ValidationError):
            LyricsQuality(timed_word_coverage_pct=1.1)

        with pytest.raises(ValidationError):
            LyricsQuality(timed_word_coverage_pct=-0.1)

    def test_vocal_presence_pct_bounds(self):
        """vocal_presence_pct is bounded [0, 1] when not None."""
        q = LyricsQuality(vocal_presence_pct=1.0)
        assert q.vocal_presence_pct == 1.0

        with pytest.raises(ValidationError):
            LyricsQuality(vocal_presence_pct=1.1)

        with pytest.raises(ValidationError):
            LyricsQuality(vocal_presence_pct=-0.1)

    def test_extra_fields_forbidden(self):
        """Extra fields are rejected (extra='forbid')."""
        with pytest.raises(ValidationError):
            LyricsQuality(coverage_pct=0.5)  # old field name, now a property

    def test_full_construction(self):
        """Full construction with all fields."""
        q = LyricsQuality(
            timed_word_coverage_pct=0.6,
            vocal_presence_pct=0.7,
            monotonicity_violations=1,
            overlap_violations=2,
            out_of_bounds_violations=0,
            large_gaps_count=3,
            avg_word_duration_ms=250.0,
            min_word_duration_ms=50.0,
        )
        assert q.timed_word_coverage_pct == 0.6
        assert q.vocal_presence_pct == 0.7
        assert q.coverage_pct == 0.6  # backward compat


# ---------------------------------------------------------------------------
# compute_quality_metrics tests
# ---------------------------------------------------------------------------


def _make_word(text: str, start_ms: int, end_ms: int) -> LyricWord:
    return LyricWord(text=text, start_ms=start_ms, end_ms=end_ms)


class TestComputeQualityMetrics:
    """Tests for compute_quality_metrics function."""

    def test_empty_words_returns_default(self):
        """Empty word list returns default LyricsQuality."""
        result = compute_quality_metrics(words=[], duration_ms=60000)
        assert result.timed_word_coverage_pct == 0.0
        assert result.vocal_presence_pct is None

    def test_empty_words_with_vocal_segments_returns_vocal_presence(self):
        """Empty words but vocal_segments provided → vocal_presence_pct populated."""
        vocal_segments = [
            {"start_s": 0.0, "end_s": 10.0},
            {"start_s": 20.0, "end_s": 30.0},
        ]
        result = compute_quality_metrics(words=[], duration_ms=60000, vocal_segments=vocal_segments)
        assert result.timed_word_coverage_pct == 0.0
        # 20s vocal / 60s duration = 0.333...
        assert result.vocal_presence_pct is not None
        assert abs(result.vocal_presence_pct - 20000 / 60000) < 0.001

    def test_basic_coverage_no_vocal_segments(self):
        """Without vocal_segments, vocal_presence_pct is None."""
        words = [
            _make_word("hello", 0, 500),
            _make_word("world", 600, 1000),
        ]
        result = compute_quality_metrics(words=words, duration_ms=10000)
        assert result.timed_word_coverage_pct > 0.0
        assert result.vocal_presence_pct is None

    def test_timed_word_coverage_pct_correct(self):
        """timed_word_coverage_pct equals merged word interval coverage."""
        words = [
            _make_word("a", 0, 1000),
            _make_word("b", 2000, 3000),
        ]
        result = compute_quality_metrics(words=words, duration_ms=10000)
        # 2000ms covered / 10000ms = 0.2
        assert abs(result.timed_word_coverage_pct - 0.2) < 0.001

    def test_coverage_pct_property_matches_timed_word_coverage_pct(self):
        """coverage_pct backward-compat property matches timed_word_coverage_pct."""
        words = [_make_word("a", 0, 5000)]
        result = compute_quality_metrics(words=words, duration_ms=10000)
        assert result.coverage_pct == result.timed_word_coverage_pct

    def test_with_vocal_segments_populates_vocal_presence_pct(self):
        """When vocal_segments provided, vocal_presence_pct is computed."""
        words = [
            _make_word("a", 0, 1000),
            _make_word("b", 2000, 3000),
        ]
        vocal_segments = [
            {"start_s": 0.0, "end_s": 5.0},
            {"start_s": 10.0, "end_s": 20.0},
        ]
        result = compute_quality_metrics(
            words=words, duration_ms=30000, vocal_segments=vocal_segments
        )
        # 15s vocal / 30s duration = 0.5
        assert result.vocal_presence_pct is not None
        assert abs(result.vocal_presence_pct - 15000 / 30000) < 0.001

    def test_without_vocal_segments_vocal_presence_none(self):
        """Without vocal_segments, vocal_presence_pct remains None."""
        words = [_make_word("a", 0, 1000)]
        result = compute_quality_metrics(words=words, duration_ms=10000)
        assert result.vocal_presence_pct is None

    def test_vocal_segments_full_coverage(self):
        """Vocal segments covering full duration gives 1.0 vocal_presence_pct."""
        words = [_make_word("a", 0, 1000)]
        vocal_segments = [{"start_s": 0.0, "end_s": 10.0}]
        result = compute_quality_metrics(
            words=words, duration_ms=10000, vocal_segments=vocal_segments
        )
        assert result.vocal_presence_pct == pytest.approx(1.0, abs=0.001)

    def test_vocal_presence_pct_clamped_to_one(self):
        """vocal_presence_pct does not exceed 1.0 even with overlapping segments."""
        words = [_make_word("a", 0, 1000)]
        # Two overlapping segments covering more than full duration
        vocal_segments = [
            {"start_s": 0.0, "end_s": 10.0},
            {"start_s": 5.0, "end_s": 15.0},
        ]
        result = compute_quality_metrics(
            words=words, duration_ms=10000, vocal_segments=vocal_segments
        )
        assert result.vocal_presence_pct is not None
        assert result.vocal_presence_pct <= 1.0

    def test_minimal_quality_empty_words_no_vocal(self):
        """Empty words, no vocal_segments → all defaults."""
        result = compute_quality_metrics(words=[], duration_ms=60000)
        assert result.timed_word_coverage_pct == 0.0
        assert result.vocal_presence_pct is None
        assert result.monotonicity_violations == 0
        assert result.overlap_violations == 0
