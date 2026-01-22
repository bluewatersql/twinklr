"""Musical key detection."""

from __future__ import annotations

import logging
from typing import Any

import librosa
import numpy as np

logger = logging.getLogger(__name__)


def detect_musical_key(y: np.ndarray, sr: int, *, hop_length: int) -> dict[str, Any]:
    """Krumhansl-Schmuckler key estimation.

    FIXED: Was rotating chroma instead of profile. Now correctly rotates profile.

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length

    Returns:
        Dict with key, mode, confidence, alternative
    """
    try:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length).astype(np.float32)
        chroma_avg = np.mean(chroma, axis=1)

        # Krumhansl-Kessler profiles (C major/minor as reference)
        major_profile = np.array(
            [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88],
            dtype=np.float32,
        )
        minor_profile = np.array(
            [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17],
            dtype=np.float32,
        )

        def corr(a: np.ndarray, b: np.ndarray) -> float:
            a_norm = (a - a.mean()) / (a.std() + 1e-9)
            b_norm = (b - b.mean()) / (b.std() + 1e-9)
            return float(np.mean(a_norm * b_norm))

        major_corr, minor_corr = [], []
        keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

        for i in range(12):
            # FIXED: Rotate the PROFILE to test each key, not the chroma
            # Rolling profile by -i is equivalent to testing key i
            major_rotated = np.roll(major_profile, -i)
            minor_rotated = np.roll(minor_profile, -i)
            major_corr.append(corr(chroma_avg, major_rotated))
            minor_corr.append(corr(chroma_avg, minor_rotated))

        bestM = int(np.argmax(major_corr))
        bestm = int(np.argmax(minor_corr))

        # Report both best major and minor with confidence
        major_conf = float(major_corr[bestM])
        minor_conf = float(minor_corr[bestm])

        if major_conf >= minor_conf:
            return {
                "key": keys[bestM],
                "mode": "major",
                "confidence": major_conf,
                "alternative": {"key": keys[bestm], "mode": "minor", "confidence": minor_conf},
            }
        return {
            "key": keys[bestm],
            "mode": "minor",
            "confidence": minor_conf,
            "alternative": {"key": keys[bestM], "mode": "major", "confidence": major_conf},
        }

    except Exception as e:
        logger.warning(f"Key detection failed: {e}")
        return {"key": "C", "mode": "major", "confidence": 0.0}


def extract_chroma(y: np.ndarray, sr: int, *, hop_length: int) -> np.ndarray:
    """Extract chroma CQT features.

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length

    Returns:
        Chroma features (12 x n_frames)
    """
    chroma_cqt = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length).astype(np.float32)
    return chroma_cqt
