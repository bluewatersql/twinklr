"""Multi-scale energy analysis."""

from __future__ import annotations

import logging
from typing import Any

import librosa
import numpy as np

from blinkb0t.core.audio.utils import as_float_list, frames_to_time, normalize_to_0_1

logger = logging.getLogger(__name__)

# Check for scipy
try:
    from scipy.ndimage import gaussian_filter1d

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logger.warning("scipy not available, energy smoothing will use basic smoothing")


def extract_smoothed_energy(
    y: np.ndarray, sr: int, *, hop_length: int, frame_length: int
) -> dict[str, Any]:
    """Extract RMS energy at multiple temporal scales.

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length
        frame_length: Frame length

    Returns:
        Dict with raw, beat_level, phrase_level, section_level energy curves
    """
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0].astype(
        np.float32
    )
    times_s = frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
    rms_norm = normalize_to_0_1(rms)

    if HAS_SCIPY:
        rms_beat = gaussian_filter1d(rms_norm, sigma=2).astype(np.float32)
        rms_phrase = gaussian_filter1d(rms_norm, sigma=10).astype(np.float32)
        rms_section = gaussian_filter1d(rms_norm, sigma=50).astype(np.float32)
    else:

        def smooth(arr: np.ndarray, window: int) -> np.ndarray:
            if arr.size < window:
                return arr.copy()
            return np.convolve(arr, np.ones(window) / window, mode="same").astype(np.float32)

        rms_beat = smooth(rms_norm, 5)
        rms_phrase = smooth(rms_norm, 20)
        rms_section = smooth(rms_norm, 100)

    raw_var = float(np.var(rms_norm)) if rms_norm.size > 0 else 0.0
    phrase_var = float(np.var(rms_phrase)) if rms_phrase.size > 0 else 0.0

    return {
        "times_s": as_float_list(times_s, 3),
        "raw": as_float_list(rms_norm, 5),
        "beat_level": as_float_list(rms_beat, 5),
        "phrase_level": as_float_list(rms_phrase, 5),
        "section_level": as_float_list(rms_section, 5),
        "statistics": {
            "raw_variance": raw_var,
            "phrase_variance": phrase_var,
            "smoothness_score": float(phrase_var / (raw_var + 1e-9)),
        },
        "_np": {"rms_norm": rms_norm, "rms_raw": rms, "times_s": times_s},
    }
