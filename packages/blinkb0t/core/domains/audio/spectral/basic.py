"""Basic spectral features."""

from __future__ import annotations

from typing import Any

import librosa
import numpy as np

from blinkb0t.core.domains.audio.utils import as_float_list, frames_to_time, normalize_to_0_1


def extract_spectral_features(
    y: np.ndarray, sr: int, *, hop_length: int, frame_length: int
) -> dict[str, Any]:
    """Extract spectral characteristics: brightness, fullness, high-freq energy, flatness.

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length
        frame_length: Frame length

    Returns:
        Dict with brightness, fullness, high_freq_energy, spectral_flatness
    """
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0].astype(
        np.float32
    )
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, hop_length=hop_length)[0].astype(
        np.float32
    )
    rolloff = librosa.feature.spectral_rolloff(
        y=y, sr=sr, hop_length=hop_length, roll_percent=0.85
    )[0].astype(np.float32)
    flatness = librosa.feature.spectral_flatness(y=np.asarray(y, dtype=np.float32))[0].astype(
        np.float32
    )

    times_s = frames_to_time(np.arange(len(centroid)), sr=sr, hop_length=hop_length)

    return {
        "times_s": as_float_list(times_s, 3),
        "brightness": as_float_list(normalize_to_0_1(centroid), 5),
        "fullness": as_float_list(normalize_to_0_1(bandwidth), 5),
        "high_freq_energy": as_float_list(normalize_to_0_1(rolloff), 5),
        "spectral_flatness": as_float_list(normalize_to_0_1(flatness), 5),
        "statistics": {
            "avg_brightness": float(np.mean(centroid)) if centroid.size > 0 else 0.0,
            "brightness_variance": float(np.std(centroid)) if centroid.size > 0 else 0.0,
            "avg_fullness": float(np.mean(bandwidth)) if bandwidth.size > 0 else 0.0,
            "flatness_avg": float(np.mean(flatness)) if flatness.size > 0 else 0.0,
        },
        "_np": {
            "centroid_norm": normalize_to_0_1(centroid),
            "flatness_norm": normalize_to_0_1(flatness),
        },
    }
