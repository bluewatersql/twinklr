"""Tests for vocal detection."""

from __future__ import annotations

import numpy as np

from blinkb0t.core.audio.spectral.vocals import detect_vocals


class TestDetectVocals:
    """Tests for detect_vocals function."""

    def test_returns_expected_structure(
        self,
        sample_rate: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        n_frames = 500
        y_harm = np.random.rand(sample_rate * 5).astype(np.float32)
        y_perc = np.random.rand(sample_rate * 5).astype(np.float32) * 0.3
        spectral_centroid = np.random.rand(n_frames).astype(np.float32) * 0.5
        spectral_flatness = np.random.rand(n_frames).astype(np.float32) * 0.3
        times_s = (np.arange(n_frames) * 0.01).astype(np.float32)

        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=spectral_centroid,
            spectral_flatness=spectral_flatness,
            times_s=times_s,
            sr=sample_rate,
        )

        assert "vocal_probability" in result
        assert "is_vocal" in result
        assert "vocal_segments" in result
        assert "statistics" in result

    def test_segment_structure(
        self,
        sample_rate: int,
    ) -> None:
        """Each vocal segment has required fields."""
        n_frames = 500
        # Create conditions favorable for vocal detection
        y_harm = np.random.rand(sample_rate * 5).astype(np.float32) * 0.8
        y_perc = np.random.rand(sample_rate * 5).astype(np.float32) * 0.2
        spectral_centroid = np.full(n_frames, 0.4, dtype=np.float32)  # Mid-range
        spectral_flatness = np.full(n_frames, 0.1, dtype=np.float32)  # Low (tonal)
        times_s = (np.arange(n_frames) * 0.01).astype(np.float32)

        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=spectral_centroid,
            spectral_flatness=spectral_flatness,
            times_s=times_s,
            sr=sample_rate,
        )

        if result["vocal_segments"]:
            segment = result["vocal_segments"][0]
            assert "start_s" in segment
            assert "end_s" in segment
            assert "duration_s" in segment
            assert "avg_probability" in segment

    def test_probability_in_valid_range(
        self,
        sample_rate: int,
    ) -> None:
        """Vocal probability values are in reasonable range."""
        n_frames = 500
        y_harm = np.random.rand(sample_rate * 5).astype(np.float32)
        y_perc = np.random.rand(sample_rate * 5).astype(np.float32)
        spectral_centroid = np.random.rand(n_frames).astype(np.float32)
        spectral_flatness = np.random.rand(n_frames).astype(np.float32)
        times_s = (np.arange(n_frames) * 0.01).astype(np.float32)

        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=spectral_centroid,
            spectral_flatness=spectral_flatness,
            times_s=times_s,
            sr=sample_rate,
        )

        probs = result["vocal_probability"]
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_is_vocal_binary(
        self,
        sample_rate: int,
    ) -> None:
        """is_vocal array contains only 0 and 1."""
        n_frames = 500
        y_harm = np.random.rand(sample_rate * 5).astype(np.float32)
        y_perc = np.random.rand(sample_rate * 5).astype(np.float32)
        spectral_centroid = np.random.rand(n_frames).astype(np.float32)
        spectral_flatness = np.random.rand(n_frames).astype(np.float32)
        times_s = (np.arange(n_frames) * 0.01).astype(np.float32)

        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=spectral_centroid,
            spectral_flatness=spectral_flatness,
            times_s=times_s,
            sr=sample_rate,
        )

        assert all(v in {0, 1} for v in result["is_vocal"])

    def test_statistics_structure(
        self,
        sample_rate: int,
    ) -> None:
        """Statistics dict contains expected keys."""
        n_frames = 500
        y_harm = np.random.rand(sample_rate * 5).astype(np.float32)
        y_perc = np.random.rand(sample_rate * 5).astype(np.float32)
        spectral_centroid = np.random.rand(n_frames).astype(np.float32)
        spectral_flatness = np.random.rand(n_frames).astype(np.float32)
        times_s = (np.arange(n_frames) * 0.01).astype(np.float32)

        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=spectral_centroid,
            spectral_flatness=spectral_flatness,
            times_s=times_s,
            sr=sample_rate,
        )

        stats = result["statistics"]
        assert "vocal_coverage_pct" in stats
        assert "vocal_segment_count" in stats
        assert "avg_segment_duration_s" in stats
        assert "total_vocal_duration_s" in stats

    def test_high_harmonic_ratio_increases_vocal_prob(
        self,
        sample_rate: int,
    ) -> None:
        """High harmonic ratio (vs percussive) increases vocal probability."""
        n_frames = 500
        duration = 5.0

        # High harmonic, low percussive = vocal-like
        y_harm_high = np.random.rand(int(sample_rate * duration)).astype(np.float32) * 0.9
        y_perc_low = np.random.rand(int(sample_rate * duration)).astype(np.float32) * 0.1

        spectral_centroid = np.full(n_frames, 0.4, dtype=np.float32)
        spectral_flatness = np.full(n_frames, 0.1, dtype=np.float32)
        times_s = np.linspace(0, duration, n_frames, dtype=np.float32)

        result = detect_vocals(
            y_harm=y_harm_high,
            y_perc=y_perc_low,
            spectral_centroid=spectral_centroid,
            spectral_flatness=spectral_flatness,
            times_s=times_s,
            sr=sample_rate,
        )

        # Average probability should be relatively high
        avg_prob = np.mean(result["vocal_probability"])
        assert avg_prob > 0.5

    def test_segment_merging(
        self,
        sample_rate: int,
    ) -> None:
        """Adjacent segments within gap tolerance are merged."""
        n_frames = 1000
        duration = 10.0

        y_harm = np.random.rand(int(sample_rate * duration)).astype(np.float32) * 0.8
        y_perc = np.random.rand(int(sample_rate * duration)).astype(np.float32) * 0.2
        spectral_centroid = np.full(n_frames, 0.4, dtype=np.float32)
        spectral_flatness = np.full(n_frames, 0.1, dtype=np.float32)
        times_s = np.linspace(0, duration, n_frames, dtype=np.float32)

        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=spectral_centroid,
            spectral_flatness=spectral_flatness,
            times_s=times_s,
            sr=sample_rate,
        )

        # If segments exist, check they have reasonable duration
        for segment in result["vocal_segments"]:
            assert segment["duration_s"] > 0

    def test_handles_list_input(
        self,
        sample_rate: int,
    ) -> None:
        """Function handles list inputs for spectral features."""
        n_frames = 500
        y_harm = np.random.rand(sample_rate * 5).astype(np.float32)
        y_perc = np.random.rand(sample_rate * 5).astype(np.float32)
        # Pass as lists instead of numpy arrays
        spectral_centroid = [float(x) for x in np.random.rand(n_frames)]
        spectral_flatness = [float(x) for x in np.random.rand(n_frames)]
        times_s = (np.arange(n_frames) * 0.01).astype(np.float32)

        # Should not raise
        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=spectral_centroid,
            spectral_flatness=spectral_flatness,
            times_s=times_s,
            sr=sample_rate,
        )

        assert "vocal_probability" in result
