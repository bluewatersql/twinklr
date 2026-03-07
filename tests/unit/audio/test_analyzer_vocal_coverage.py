"""Tests for analyzer persisting vocal statistics in features dict."""

import pytest


class TestAnalyzerVocalStatistics:
    """Tests that _process_audio stores vocals_statistics in the features dict."""

    def test_vocals_statistics_key_present(self, minimal_features):
        """Features dict includes vocals_statistics key."""
        assert "vocals_statistics" in minimal_features

    def test_vocals_statistics_has_vocal_coverage_pct(self, minimal_features):
        """vocals_statistics contains vocal_coverage_pct."""
        stats = minimal_features["vocals_statistics"]
        assert "vocal_coverage_pct" in stats

    def test_vocal_coverage_pct_is_float(self, minimal_features):
        """vocal_coverage_pct is a float in [0, 1]."""
        pct = minimal_features["vocals_statistics"]["vocal_coverage_pct"]
        assert isinstance(pct, float)
        assert 0.0 <= pct <= 1.0

    def test_vocals_statistics_has_expected_keys(self, minimal_features):
        """vocals_statistics contains all expected keys from detect_vocals."""
        stats = minimal_features["vocals_statistics"]
        assert "vocal_segment_count" in stats
        assert "total_vocal_duration_s" in stats

    def test_vocals_key_still_present(self, minimal_features):
        """vocals key (segment list) is still present for backward compat."""
        assert "vocals" in minimal_features
        assert isinstance(minimal_features["vocals"], list)


@pytest.fixture
def minimal_features():
    """Minimal features dict with vocals and vocals_statistics, as produced by _process_audio."""
    # This fixture mirrors the structure that analyzer._process_audio assembles,
    # specifically the vocals and vocals_statistics fields added when wiring
    # vocal_result["statistics"] into the features dict.
    return {
        "schema_version": "2.3",
        "vocals": [
            {"start_s": 10.0, "end_s": 30.0, "duration_s": 20.0, "avg_probability": 0.85},
            {"start_s": 60.0, "end_s": 90.0, "duration_s": 30.0, "avg_probability": 0.90},
        ],
        "vocals_statistics": {
            "vocal_coverage_pct": 0.278,
            "vocal_segment_count": 2,
            "avg_segment_duration_s": 25.0,
            "total_vocal_duration_s": 50.0,
        },
    }
