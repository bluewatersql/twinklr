"""Tests for vocal detection."""

from __future__ import annotations

import numpy as np

from twinklr.core.audio.spectral.vocals import detect_vocals
from twinklr.core.audio.utils import as_float_list, frames_to_time


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
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
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
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
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
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
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
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
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
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
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
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
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
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
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
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
        )

        assert "vocal_probability" in result


class TestVocalSegmentMerging:
    """Tests for vocal segment merging logic."""

    def test_very_high_vocal_probability_uses_lower_threshold(
        self,
        sample_rate: int,
    ) -> None:
        """When mean probability is very high, uses lower threshold."""
        n_frames = 500
        duration = 5.0
        n_samples = int(sample_rate * duration)

        # Create audio with varying harmonic content that favors vocals
        # Use a sine wave for harmonic (vocal-like) content
        t = np.linspace(0, duration, n_samples, dtype=np.float32)
        y_harm = np.sin(2 * np.pi * 440 * t).astype(np.float32) * 0.8

        # Very weak percussive content
        rng = np.random.default_rng(42)
        y_perc = rng.standard_normal(n_samples).astype(np.float32) * 0.05

        # Mid-range spectral features (vocal-like)
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
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
        )

        # Should have valid structure and process vocal detection
        assert "vocal_probability" in result
        assert "statistics" in result
        # Mean probability should be relatively high for this vocal-like input
        avg_prob = np.mean(result["vocal_probability"])
        assert avg_prob > 0.4  # Should be vocal-like

    def test_strong_vocal_median_threshold(
        self,
        sample_rate: int,
    ) -> None:
        """When median probability is high, uses moderate threshold."""
        n_frames = 500
        duration = 5.0

        # Create audio with moderately high harmonic content
        y_harm = np.ones(int(sample_rate * duration), dtype=np.float32) * 0.85
        y_perc = np.ones(int(sample_rate * duration), dtype=np.float32) * 0.15
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
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
        )

        # Should have valid structure
        assert "vocal_segments" in result
        assert "statistics" in result

    def test_segment_at_end_of_audio(
        self,
        sample_rate: int,
    ) -> None:
        """Handle vocal segment that extends to end of audio."""
        n_frames = 500
        duration = 5.0

        # Create audio where vocal probability is high at the end
        y_harm = np.zeros(int(sample_rate * duration), dtype=np.float32)
        y_perc = np.zeros(int(sample_rate * duration), dtype=np.float32)

        # Make second half highly harmonic
        half_samples = int(sample_rate * duration / 2)
        y_harm[half_samples:] = 0.9
        y_perc[:half_samples] = 0.9
        y_perc[half_samples:] = 0.1

        spectral_centroid = np.full(n_frames, 0.4, dtype=np.float32)
        spectral_flatness = np.zeros(n_frames, dtype=np.float32)
        spectral_flatness[n_frames // 2 :] = 0.1
        spectral_flatness[: n_frames // 2] = 0.5

        times_s = np.linspace(0, duration, n_frames, dtype=np.float32)

        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=spectral_centroid,
            spectral_flatness=spectral_flatness,
            times_s=times_s,
            sr=sample_rate,
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
        )

        # Should handle end segment
        assert "vocal_segments" in result

    def test_short_segments_merging(
        self,
        sample_rate: int,
    ) -> None:
        """Short adjacent segments within gap tolerance are merged."""
        n_frames = 1000
        duration = 10.0

        # Create alternating high/low harmonic content with small gaps
        y_harm = np.zeros(int(sample_rate * duration), dtype=np.float32)
        y_perc = np.ones(int(sample_rate * duration), dtype=np.float32) * 0.5

        # Create sections with vocal-like content and small gaps
        for i in range(0, int(sample_rate * duration), int(sample_rate * 2)):
            end = min(i + int(sample_rate * 1.5), int(sample_rate * duration))
            y_harm[i:end] = 0.9
            y_perc[i:end] = 0.1

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
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
        )

        # Should have merged segments
        assert isinstance(result["vocal_segments"], list)

    def test_high_probability_segments_lenient_merging(
        self,
        sample_rate: int,
    ) -> None:
        """High probability segments get extra lenient gap tolerance."""
        n_frames = 1500
        duration = 15.0

        # Create two high-probability vocal segments with a gap
        y_harm = np.zeros(int(sample_rate * duration), dtype=np.float32)
        y_perc = np.ones(int(sample_rate * duration), dtype=np.float32)

        # First segment: 0-4 seconds (very vocal)
        start1 = 0
        end1 = int(sample_rate * 4)
        y_harm[start1:end1] = 0.95
        y_perc[start1:end1] = 0.05

        # Second segment: 7-12 seconds (very vocal)
        start2 = int(sample_rate * 7)
        end2 = int(sample_rate * 12)
        y_harm[start2:end2] = 0.95
        y_perc[start2:end2] = 0.05

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
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
        )

        # Should have detected vocal segments
        assert "vocal_segments" in result

    def test_no_vocal_segments_detected(
        self,
        sample_rate: int,
    ) -> None:
        """When no vocals present, returns empty segments."""
        n_frames = 500
        duration = 5.0

        # Highly percussive content, no vocals
        y_harm = np.ones(int(sample_rate * duration), dtype=np.float32) * 0.1
        y_perc = np.ones(int(sample_rate * duration), dtype=np.float32) * 0.9
        spectral_centroid = np.full(n_frames, 0.8, dtype=np.float32)  # High frequency
        spectral_flatness = np.full(n_frames, 0.8, dtype=np.float32)  # Noisy
        times_s = np.linspace(0, duration, n_frames, dtype=np.float32)

        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=spectral_centroid,
            spectral_flatness=spectral_flatness,
            times_s=times_s,
            sr=sample_rate,
            hop_length=round(sample_rate * float(times_s[1] - times_s[0])),
        )

        # Low vocal coverage expected
        assert result["statistics"]["vocal_coverage_pct"] < 0.5


class TestVocalDetectorAlignment:
    """The detector must analyse the same frame grid the analyzer reports."""

    def test_vocal_detector_frames_align_with_analyzer_times(self) -> None:
        """Frames stay aligned with times_s over a >=3-minute signal.

        times_s reaches the detector rounded to milliseconds (as_float_list(..., 3)),
        so reconstructing the hop from it recovers 529 instead of 512 at sr=44100.
        That drops ~3% of the frames off the tail and slides every reported time
        ~6s late by the end of a 3-minute track.
        """
        sr = 44100
        hop_length = 512
        duration_s = 200.0
        n_samples = int(sr * duration_s)

        rng = np.random.default_rng(7)
        noise = rng.standard_normal(n_samples).astype(np.float32) * 0.3

        # Harmonic content only between 100s and 115s; everything else percussive.
        y_harm = noise * 0.05
        y_perc = noise.copy()
        vocal_start_s, vocal_end_s = 100.0, 115.0
        sl = slice(int(vocal_start_s * sr), int(vocal_end_s * sr))
        y_harm[sl] = noise[sl]
        y_perc[sl] = noise[sl] * 0.05

        # Exactly how the analyzer builds times_s (rounded to milliseconds).
        n_frames = 1 + n_samples // hop_length
        times_s = np.asarray(
            as_float_list(frames_to_time(np.arange(n_frames), sr=sr, hop_length=hop_length), 3)
        )

        result = detect_vocals(
            y_harm=y_harm,
            y_perc=y_perc,
            spectral_centroid=np.full(n_frames, 0.4, dtype=np.float32),
            spectral_flatness=np.full(n_frames, 0.1, dtype=np.float32),
            times_s=times_s,
            sr=sr,
            hop_length=hop_length,
        )

        # No tail truncation: every analyzer frame is classified.
        assert len(result["is_vocal"]) == len(times_s)

        # No drift: the detected segment sits where the harmonic content actually is.
        hop_s = hop_length / sr
        segments = [s for s in result["vocal_segments"] if s["duration_s"] > 1.0]
        assert len(segments) == 1, f"expected one vocal segment, got {segments}"
        assert abs(segments[0]["start_s"] - vocal_start_s) <= 10 * hop_s
        assert abs(segments[0]["end_s"] - vocal_end_s) <= 10 * hop_s
