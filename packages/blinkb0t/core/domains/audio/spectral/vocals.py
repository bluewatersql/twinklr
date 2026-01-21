"""Vocal detection using harmonic and spectral features."""

from __future__ import annotations

import logging
from typing import Any

import librosa
import numpy as np

from blinkb0t.core.domains.audio.utils import as_float_list, normalize_to_0_1

logger = logging.getLogger(__name__)


def detect_vocals(
    y_harm: np.ndarray,
    y_perc: np.ndarray,
    spectral_centroid: np.ndarray,
    spectral_flatness: np.ndarray,
    times_s: np.ndarray,
    sr: int,
) -> dict[str, Any]:
    """Detect vocal presence using harmonic ratio and spectral features.

    Vocals typically have:
    - High harmonic content (low percussive)
    - Mid-range spectral centroid (200-4000 Hz)
    - Low spectral flatness (tonal, not noisy)

    Args:
        y_harm: Harmonic component of audio
        y_perc: Percussive component of audio
        spectral_centroid: Spectral centroid values
        spectral_flatness: Spectral flatness values
        times_s: Time points in seconds
        sr: Sample rate

    Returns:
        Dictionary with vocal probability, segments, and statistics
    """
    # Compute harmonic/percussive ratio per frame
    hop_length = int(sr * (times_s[1] - times_s[0])) if len(times_s) > 1 else 512

    rms_h = librosa.feature.rms(y=y_harm, hop_length=hop_length)[0]
    rms_p = librosa.feature.rms(y=y_perc, hop_length=hop_length)[0]

    # Ensure inputs are numpy arrays (not lists)
    spectral_centroid = np.asarray(spectral_centroid)
    spectral_flatness = np.asarray(spectral_flatness)

    n_frames = min(len(rms_h), len(rms_p), len(spectral_centroid), len(spectral_flatness))
    rms_h = rms_h[:n_frames]
    rms_p = rms_p[:n_frames]
    centroid = spectral_centroid[:n_frames]
    flatness = spectral_flatness[:n_frames]

    # Harmonic ratio (0-1, higher = more harmonic)
    harmonic_ratio = rms_h / (rms_h + rms_p + 1e-9)

    # Vocal range detection (200-4000 Hz typical)
    # Spectral centroid normalized to 0-1, typical vocal range ~ 0.2-0.6
    centroid_norm = normalize_to_0_1(centroid)
    vocal_range_score = 1.0 - np.abs(centroid_norm - 0.4)  # Peak at 0.4

    # Low flatness = tonal (vocal characteristic)
    flatness_inv = 1.0 - flatness

    # Combine indicators (weighted)
    vocal_probability = 0.5 * harmonic_ratio + 0.3 * vocal_range_score + 0.2 * flatness_inv

    # Adaptive threshold based on distribution
    # Use lower threshold if vocals are prominent (high median)
    median_prob = np.median(vocal_probability)
    mean_prob = np.mean(vocal_probability)

    # Multi-strategy thresholding
    if mean_prob > 0.75:
        # Song has very strong vocal presence (like a cappella), use lower threshold
        vocal_threshold = max(0.65, np.percentile(vocal_probability, 40))
    elif median_prob > 0.7:
        # Song has strong vocal presence, use moderate threshold
        vocal_threshold = max(0.70, np.percentile(vocal_probability, 45))
    else:
        # Weaker vocals, use conservative threshold
        vocal_threshold = np.percentile(vocal_probability, 55)

    logger.debug(
        f"Vocal threshold: {vocal_threshold:.3f} (mean={mean_prob:.3f}, median={median_prob:.3f})"
    )
    is_vocal = (vocal_probability > vocal_threshold).astype(int)

    # Vocal segments (consecutive vocal frames)
    raw_segments = []
    in_vocal = False
    segment_start = 0

    min_segment_duration_s = 0.5  # Minimum vocal segment (was 2.0, too strict)
    min_segment_frames = int(min_segment_duration_s / (times_s[1] - times_s[0]))

    for i in range(len(is_vocal)):
        if is_vocal[i] and not in_vocal:
            in_vocal = True
            segment_start = i
        elif not is_vocal[i] and in_vocal:
            segment_duration = i - segment_start
            if segment_duration >= min_segment_frames:
                raw_segments.append(
                    {
                        "start_s": float(times_s[segment_start]),
                        "end_s": float(times_s[i]),
                        "duration_s": float(times_s[i] - times_s[segment_start]),
                        "avg_probability": round(
                            float(np.mean(vocal_probability[segment_start:i])), 3
                        ),
                    }
                )
            in_vocal = False

    # Handle segment at end
    if in_vocal and len(times_s) - segment_start >= min_segment_frames:
        raw_segments.append(
            {
                "start_s": float(times_s[segment_start]),
                "end_s": float(times_s[-1]),
                "duration_s": float(times_s[-1] - times_s[segment_start]),
                "avg_probability": round(float(np.mean(vocal_probability[segment_start:])), 3),
            }
        )

    # Merge segments separated by short gaps
    # Use adaptive gap tolerance based on segment characteristics
    vocal_segments = []

    if raw_segments:
        current = raw_segments[0].copy()

        for next_seg in raw_segments[1:]:
            gap = next_seg["start_s"] - current["end_s"]

            # Adaptive gap tolerance:
            # - Short segments (< 2s) likely individual phrases: allow 2s gaps
            # - Longer segments (>= 2s) likely verses/choruses: allow 3s gaps
            # - Very high probability segments: be more lenient
            if current["duration_s"] < 2.0 and next_seg["duration_s"] < 2.0:
                max_gap = 2.0  # Brief phrases separated by pauses
            else:
                max_gap = 3.0  # Longer vocal sections

            # Be more lenient if both segments have high vocal probability
            if current["avg_probability"] > 0.85 and next_seg["avg_probability"] > 0.85:
                max_gap += 1.0

            if gap <= max_gap:
                # Merge: extend current segment to include the gap and next segment
                total_duration = current["duration_s"] + next_seg["duration_s"]
                weighted_prob = (
                    current["avg_probability"] * current["duration_s"]
                    + next_seg["avg_probability"] * next_seg["duration_s"]
                ) / total_duration

                current["end_s"] = next_seg["end_s"]
                current["duration_s"] = current["end_s"] - current["start_s"]
                current["avg_probability"] = round(weighted_prob, 3)
            else:
                # Gap too large, save current and start new
                vocal_segments.append(current)
                current = next_seg.copy()

        # Don't forget the last segment
        vocal_segments.append(current)

    # Statistics
    total_vocal_duration = sum(seg["duration_s"] for seg in vocal_segments)
    total_duration = float(times_s[-1] - times_s[0])
    vocal_coverage_pct = total_vocal_duration / total_duration if total_duration > 0 else 0.0

    return {
        "vocal_probability": as_float_list(vocal_probability, 3),
        "is_vocal": [int(x) for x in is_vocal.tolist()],
        "vocal_segments": vocal_segments,
        "statistics": {
            "vocal_coverage_pct": round(vocal_coverage_pct, 3),
            "vocal_segment_count": len(vocal_segments),
            "avg_segment_duration_s": (
                round(total_vocal_duration / len(vocal_segments), 2) if vocal_segments else 0.0
            ),
            "total_vocal_duration_s": round(total_vocal_duration, 2),
        },
    }
