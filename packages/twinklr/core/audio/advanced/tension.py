"""Musical tension curve computation."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from twinklr.core.audio.utils import as_float_list, normalize_to_0_1

try:
    from scipy.ndimage import gaussian_filter1d

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

logger = logging.getLogger(__name__)


def compute_tension_curve(
    chroma_cqt: np.ndarray,
    energy_curve: np.ndarray,
    spectral_flatness: np.ndarray,
    onset_env: np.ndarray,
    times_s: np.ndarray,
    key_info: dict[str, Any],
    sr: int,
    hop_length: int,
) -> dict[str, Any]:
    """Compute musical tension curve.

    Tension components:
    1. Harmonic dissonance (chroma deviation from key)
    2. Dynamic intensity (energy + onsets)
    3. Spectral density (flatness)

    Args:
        chroma_cqt: Chroma CQT features (12 x n_frames)
        energy_curve: Normalized energy curve
        spectral_flatness: Spectral flatness values
        onset_env: Onset envelope
        times_s: Time points in seconds
        key_info: Musical key information
        sr: Sample rate
        hop_length: Hop length in samples

    Returns:
        Dictionary with tension curve, peaks, releases, and statistics
    """
    # Ensure inputs are numpy arrays (may be passed as lists from feature extraction)
    energy_curve = np.asarray(energy_curve, dtype=np.float32)
    spectral_flatness = np.asarray(spectral_flatness, dtype=np.float32)
    onset_env = np.asarray(onset_env, dtype=np.float32)
    times_s = np.asarray(times_s, dtype=np.float32)

    n_frames = min(chroma_cqt.shape[1], len(energy_curve), len(spectral_flatness), len(onset_env))

    # Component 1: Harmonic dissonance
    # Compare chroma to key profile
    key_name = key_info.get("key", "C")
    NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    try:
        key_idx = NOTE_NAMES.index(key_name)
    except ValueError:
        logger.warning(f"Unknown key {key_name}, using C")
        key_idx = 0

    # Key profile (stronger weight on tonic, dominant, subdominant)
    if key_info.get("mode") == "major":
        # Major: I, iii, IV, V (1, 3, 4, 5 scale degrees)
        key_profile = np.array(
            [1.0, 0.2, 0.4, 0.3, 0.8, 0.7, 0.2, 0.9, 0.2, 0.4, 0.2, 0.3], dtype=np.float32
        )
    else:
        # Minor: i, III, iv, V (1, 3, 4, 5 scale degrees)
        key_profile = np.array(
            [1.0, 0.2, 0.3, 0.8, 0.2, 0.7, 0.3, 0.9, 0.4, 0.2, 0.4, 0.2], dtype=np.float32
        )

    # Rotate to key
    key_profile = np.roll(key_profile, key_idx)
    key_profile_norm = key_profile / (np.linalg.norm(key_profile) + 1e-9)

    # Compute dissonance per frame (1 - similarity to key)
    dissonance = np.zeros(n_frames, dtype=np.float32)
    for i in range(n_frames):
        chroma_frame = chroma_cqt[:, i]
        chroma_norm = chroma_frame / (np.linalg.norm(chroma_frame) + 1e-9)
        consonance = np.dot(chroma_norm, key_profile_norm)
        dissonance[i] = 1.0 - consonance

    dissonance_norm = normalize_to_0_1(dissonance)

    # Component 2: Dynamic intensity
    energy_norm = energy_curve[:n_frames]
    onset_norm = normalize_to_0_1(onset_env[:n_frames])
    dynamic_intensity = 0.6 * energy_norm + 0.4 * onset_norm

    # Component 3: Spectral density (flatness inverted)
    flatness_norm = spectral_flatness[:n_frames]
    spectral_density = 1.0 - flatness_norm

    # Combine components
    tension = 0.4 * dissonance_norm + 0.4 * dynamic_intensity + 0.2 * spectral_density

    # Smooth tension curve
    if HAS_SCIPY:
        tension_smooth = gaussian_filter1d(tension, sigma=5).astype(np.float32)
    else:
        window = 11
        tension_smooth = np.convolve(tension, np.ones(window) / window, mode="same").astype(
            np.float32
        )

    # Detect tension peaks and releases
    tension_grad = np.gradient(tension_smooth)

    # Peaks: local maxima above threshold
    threshold = np.percentile(tension_smooth, 75)
    peaks = []
    for i in range(1, len(tension_smooth) - 1):
        if (
            tension_smooth[i] > tension_smooth[i - 1]
            and tension_smooth[i] > tension_smooth[i + 1]
            and tension_smooth[i] > threshold
        ):
            peaks.append(
                {
                    "time_s": float(times_s[i]),
                    "tension": round(float(tension_smooth[i]), 3),
                }
            )

    # Releases: steep negative gradients
    release_threshold = (
        np.percentile(tension_grad[tension_grad < 0], 20) if np.any(tension_grad < 0) else -0.01
    )
    releases = []
    for i in range(1, len(tension_grad)):
        if tension_grad[i] < release_threshold:
            releases.append(
                {
                    "time_s": float(times_s[i]),
                    "tension_drop": round(float(-tension_grad[i]), 5),
                }
            )

    return {
        "tension_curve": as_float_list(tension_smooth, 3),
        "times_s": as_float_list(times_s[:n_frames], 3),
        "components": {
            "dissonance": as_float_list(dissonance_norm, 3),
            "dynamic_intensity": as_float_list(dynamic_intensity, 3),
            "spectral_density": as_float_list(spectral_density, 3),
        },
        "tension_peaks": peaks,
        "tension_releases": releases,
        "statistics": {
            "avg_tension": round(float(np.mean(tension_smooth)), 3),
            "tension_variance": round(float(np.var(tension_smooth)), 3),
            "peak_count": len(peaks),
            "release_count": len(releases),
            "max_tension": round(float(np.max(tension_smooth)), 3),
            "min_tension": round(float(np.min(tension_smooth)), 3),
        },
    }
