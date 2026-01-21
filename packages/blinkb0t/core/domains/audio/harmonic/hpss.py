"""Harmonic-percussive source separation."""

from __future__ import annotations

import librosa
import numpy as np


def compute_hpss(y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Harmonic-percussive source separation.

    Args:
        y: Audio time series

    Returns:
        Tuple of (y_harmonic, y_percussive)
    """
    try:
        y_harm, y_perc = librosa.effects.hpss(y)
        return np.asarray(y_harm, dtype=np.float32), np.asarray(y_perc, dtype=np.float32)
    except Exception:
        # fallback: treat all as both
        y_copy = y.copy().astype(np.float32)
        return y_copy, y_copy


def compute_onset_env(y_perc: np.ndarray, sr: int, hop_length: int) -> np.ndarray:
    """Compute onset strength envelope from percussive component.

    Args:
        y_perc: Percussive component from HPSS
        sr: Sample rate
        hop_length: Hop length

    Returns:
        Onset strength envelope
    """
    onset_env = librosa.onset.onset_strength(y=y_perc, sr=sr, hop_length=hop_length)
    return np.asarray(onset_env, dtype=np.float32)
