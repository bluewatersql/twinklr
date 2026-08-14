"""Harmonic-percussive source separation."""

from __future__ import annotations

from dataclasses import dataclass
import logging

import librosa
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HpssResult:
    """Harmonic/percussive components plus whether separation actually happened.

    When separation fails the fallback returns the same signal as both components,
    which drives every downstream harmonic ratio to a constant ~0.5. Callers need
    `separated` to tell that constant apart from genuinely balanced content.
    """

    harmonic: np.ndarray
    percussive: np.ndarray
    separated: bool = True
    error: str | None = None


def compute_hpss(y: np.ndarray) -> HpssResult:
    """Harmonic-percussive source separation.

    Args:
        y: Audio time series

    Returns:
        HpssResult with the two components and a separation status flag
    """
    try:
        y_harm, y_perc = librosa.effects.hpss(y)
        return HpssResult(
            harmonic=np.asarray(y_harm, dtype=np.float32),
            percussive=np.asarray(y_perc, dtype=np.float32),
        )
    except Exception as e:
        logger.warning(
            "HPSS separation failed (%s); falling back to the unseparated signal for both "
            "components — harmonic ratios will be a constant ~0.5",
            e,
        )
        y_copy = y.copy().astype(np.float32)
        return HpssResult(harmonic=y_copy, percussive=y_copy, separated=False, error=str(e))


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
