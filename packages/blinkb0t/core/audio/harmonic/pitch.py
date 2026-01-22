"""Pitch tracking and analysis."""

from __future__ import annotations

import logging
from typing import Any

import librosa
import numpy as np

logger = logging.getLogger(__name__)


def extract_pitch_tracking(y: np.ndarray, sr: int, *, hop_length: int) -> dict[str, Any]:
    """Extract pitch contour using pYIN algorithm.

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length

    Returns:
        Dict with pitch tracking data including mean, range, and confidence
    """
    try:
        # Use pYIN for pitch tracking (probabilistic YIN)
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y,
            fmin=float(librosa.note_to_hz("C2")),  # ~65 Hz
            fmax=float(librosa.note_to_hz("C7")),  # ~2093 Hz
            sr=sr,
            hop_length=hop_length,
        )

        # Filter to voiced frames with confidence
        valid_mask = (~np.isnan(f0)) & (voiced_flag) & (voiced_probs > 0.5)
        valid_pitches = f0[valid_mask]

        if len(valid_pitches) == 0:
            return {
                "mean_hz": 0.0,
                "std_hz": 0.0,
                "range_hz": 0.0,
                "min_hz": 0.0,
                "max_hz": 0.0,
                "confidence": 0.0,
                "voiced_ratio": 0.0,
            }

        # Compute statistics
        mean_conf = float(np.mean(voiced_probs[valid_mask]))
        voiced_ratio = float(np.sum(valid_mask) / len(f0))

        return {
            "mean_hz": float(np.mean(valid_pitches)),
            "std_hz": float(np.std(valid_pitches)),
            "range_hz": float(np.max(valid_pitches) - np.min(valid_pitches)),
            "min_hz": float(np.min(valid_pitches)),
            "max_hz": float(np.max(valid_pitches)),
            "confidence": mean_conf,
            "voiced_ratio": voiced_ratio,
        }

    except Exception as e:
        logger.warning(f"Pitch tracking failed: {e}")
        return {
            "mean_hz": 0.0,
            "std_hz": 0.0,
            "range_hz": 0.0,
            "min_hz": 0.0,
            "max_hz": 0.0,
            "confidence": 0.0,
            "voiced_ratio": 0.0,
        }


__all__ = ["extract_pitch_tracking"]
