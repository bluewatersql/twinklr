"""Frequency band energy extraction and transient detection."""

from __future__ import annotations

from typing import Any

import librosa
import numpy as np

from blinkb0t.core.domains.audio.utils import as_float_list, frames_to_time, normalize_to_0_1


def extract_dynamic_features(
    y: np.ndarray,
    sr: int,
    *,
    hop_length: int,
    frame_length: int,
    rms_precomputed: np.ndarray | None = None,
) -> dict[str, Any]:
    """Extract frequency band energies, motion/flux, and transient information.

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length
        frame_length: Frame length
        rms_precomputed: Optional pre-computed RMS for optimization

    Returns:
        Dict with bass_energy, mid_energy, high_energy, motion, transients
    """
    stft = librosa.stft(y, n_fft=frame_length, hop_length=hop_length)
    mag = np.abs(stft).astype(np.float32)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=frame_length)

    bass_idx = np.where((freqs >= 20) & (freqs < 250))[0]
    mid_idx = np.where((freqs >= 250) & (freqs < 4000))[0]
    high_idx = np.where(freqs >= 4000)[0]

    n_frames = mag.shape[1]
    bass = mag[bass_idx, :].mean(axis=0) if bass_idx.size else np.zeros(n_frames, dtype=np.float32)
    mid = mag[mid_idx, :].mean(axis=0) if mid_idx.size else np.zeros(n_frames, dtype=np.float32)
    high = mag[high_idx, :].mean(axis=0) if high_idx.size else np.zeros(n_frames, dtype=np.float32)

    times_s = frames_to_time(np.arange(n_frames), sr=sr, hop_length=hop_length)

    # Spectral flux (motion proxy)
    if n_frames >= 2:
        flux = np.maximum(0.0, mag[:, 1:] - mag[:, :-1]).mean(axis=0).astype(np.float32)
        flux = np.concatenate([[0.0], flux])
    else:
        flux = np.zeros(n_frames, dtype=np.float32)

    # Onset detection
    onset_frames = librosa.onset.onset_detect(
        y=y, sr=sr, hop_length=hop_length, backtrack=True, units="frames"
    ).astype(int)
    onset_times = frames_to_time(onset_frames, sr=sr, hop_length=hop_length)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length).astype(np.float32)
    onset_strengths = (
        onset_env[np.clip(onset_frames, 0, len(onset_env) - 1)]
        if onset_frames.size
        else np.array([], dtype=np.float32)
    )

    # OPTIMIZATION: Use precomputed RMS if available
    if rms_precomputed is not None:
        rms = rms_precomputed
    else:
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0].astype(
            np.float32
        )

    loudness_range = float(np.percentile(rms, 90) - np.percentile(rms, 10)) if rms.size > 1 else 0.0
    dynamic_contrast = float(np.max(rms) / (np.mean(rms) + 1e-9)) if rms.size > 0 else 0.0
    duration_s = float(len(y) / sr) if sr > 0 else 1.0

    return {
        "times_s": as_float_list(times_s, 3),
        "bass_energy": as_float_list(normalize_to_0_1(bass), 5),
        "mid_energy": as_float_list(normalize_to_0_1(mid), 5),
        "high_energy": as_float_list(normalize_to_0_1(high), 5),
        "motion": as_float_list(normalize_to_0_1(flux), 5),
        "transients": [
            {"time_s": float(t), "strength": float(s)}
            for t, s in zip(onset_times.tolist(), onset_strengths.tolist(), strict=False)
        ],
        "statistics": {
            "dynamic_range": loudness_range,
            "dynamic_contrast": dynamic_contrast,
            "transient_count": int(len(onset_times)),
            "transient_density": float(len(onset_times) / duration_s),
        },
        "_np": {"motion_norm": normalize_to_0_1(flux)},
    }
