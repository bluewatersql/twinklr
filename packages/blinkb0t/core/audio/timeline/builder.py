"""Unified timeline builder for frame-aligned features."""

from __future__ import annotations

from typing import Any

import librosa
import numpy as np

from blinkb0t.core.audio.harmonic.hpss import compute_hpss
from blinkb0t.core.audio.utils import (
    align_to_length,
    as_float_list,
    frames_to_time,
    normalize_to_0_1,
    safe_divide,
    time_to_frames,
)


def build_timeline_export(
    *,
    y: np.ndarray,
    sr: int,
    hop_length: int,
    frame_length: int,
    onset_env: np.ndarray,
    rms_norm: np.ndarray,
    brightness_norm: np.ndarray,
    flatness_norm: np.ndarray,
    motion_norm: np.ndarray,
    chroma_cqt: np.ndarray,
    beats_s: list[float],
    downbeats_s: list[float],
    section_bounds_s: list[float],
    y_harm: np.ndarray | None = None,
    y_perc: np.ndarray | None = None,
) -> dict[str, Any]:
    """Build unified frame-based timeline with all features aligned.

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length
        frame_length: Frame length
        onset_env: Onset strength envelope
        rms_norm: Normalized RMS energy
        brightness_norm: Normalized spectral centroid
        flatness_norm: Normalized spectral flatness
        motion_norm: Normalized spectral flux
        chroma_cqt: Chroma features (12 x n_frames)
        beats_s: Beat times in seconds
        downbeats_s: Downbeat times in seconds
        section_bounds_s: Section boundary times
        y_harm: Pre-computed harmonic component (optional)
        y_perc: Pre-computed percussive component (optional)

    Returns:
        Dict with timeline and composites
    """
    # Ensure inputs are numpy arrays (may be passed as lists from feature extraction)
    onset_env = np.asarray(onset_env, dtype=np.float32)
    rms_norm = np.asarray(rms_norm, dtype=np.float32)
    brightness_norm = np.asarray(brightness_norm, dtype=np.float32)
    flatness_norm = np.asarray(flatness_norm, dtype=np.float32)
    motion_norm = np.asarray(motion_norm, dtype=np.float32)

    n_frames = int(len(rms_norm))
    if n_frames == 0:
        return {"timeline": {}, "composites": {"show_intensity": []}}

    t_sec = frames_to_time(np.arange(n_frames), sr=sr, hop_length=hop_length)

    # Align onset_env length
    onset_env = align_to_length(onset_env, n_frames)
    onset_env_norm = normalize_to_0_1(onset_env)

    # Loudness proxy: mean log-mel dB per frame
    mel = librosa.feature.melspectrogram(
        y=y, sr=sr, hop_length=hop_length, n_fft=frame_length, power=2.0
    ).astype(np.float32)
    mel_db = librosa.power_to_db(mel, ref=np.max).astype(np.float32)
    loudness = mel_db.mean(axis=0).astype(np.float32)
    loudness = align_to_length(loudness, n_frames)
    loudness_norm = normalize_to_0_1(loudness)

    # OPTIMIZATION: Use pre-computed HPSS if available
    if y_harm is None or y_perc is None:
        y_harm, y_perc = compute_hpss(y)

    try:
        rms_h = librosa.feature.rms(y=y_harm, frame_length=frame_length, hop_length=hop_length)[
            0
        ].astype(np.float32)
        rms_p = librosa.feature.rms(y=y_perc, frame_length=frame_length, hop_length=hop_length)[
            0
        ].astype(np.float32)
        m = min(n_frames, len(rms_h), len(rms_p))
        ratio = safe_divide(rms_p[:m], rms_h[:m] + rms_p[:m])
        hpss_perc_ratio = align_to_length(ratio, n_frames)
    except Exception:
        hpss_perc_ratio = np.zeros(n_frames, dtype=np.float32)

    # Tonal novelty from chroma deltas
    C = np.asarray(chroma_cqt, dtype=np.float32)
    if C.ndim == 1:
        C = C.reshape(1, -1)
    if C.shape[1] != n_frames:
        if C.shape[1] > n_frames:
            C = C[:, :n_frames]
        else:
            C = np.pad(C, ((0, 0), (0, n_frames - C.shape[1])), mode="edge")

    dC = np.zeros(n_frames, dtype=np.float32)
    if n_frames >= 2:
        d = C[:, 1:] - C[:, :-1]
        dC[1:] = np.linalg.norm(d, axis=0).astype(np.float32)
    tonal_novelty_norm = normalize_to_0_1(dC)

    # Markers on the same frame grid
    is_beat = np.zeros(n_frames, dtype=np.uint8)
    is_downbeat = np.zeros(n_frames, dtype=np.uint8)

    if beats_s:
        bf = time_to_frames(
            np.asarray(beats_s, dtype=np.float32), sr=sr, hop_length=hop_length, n_frames=n_frames
        )
        is_beat[bf] = 1

    if downbeats_s:
        dbf = time_to_frames(
            np.asarray(downbeats_s, dtype=np.float32),
            sr=sr,
            hop_length=hop_length,
            n_frames=n_frames,
        )
        is_downbeat[dbf] = 1

    # Section ID as step function
    last_time = float(t_sec[-1]) if len(t_sec) > 0 else 0.0
    bounds = [b for b in (section_bounds_s or []) if 0.0 <= float(b) <= last_time]
    bounds = sorted(set([0.0] + [float(b) for b in bounds] + [last_time + 1e-3]))
    section_id = np.zeros(n_frames, dtype=np.int32)
    for i in range(len(bounds) - 1):
        sf = int(librosa.time_to_frames(bounds[i], sr=sr, hop_length=hop_length))
        ef = int(librosa.time_to_frames(bounds[i + 1], sr=sr, hop_length=hop_length))
        sf = max(0, min(sf, n_frames))
        ef = max(0, min(ef, n_frames))
        section_id[sf:ef] = i

    # Align all feature arrays
    brightness_norm = align_to_length(brightness_norm, n_frames)
    flatness_norm = align_to_length(flatness_norm, n_frames)
    motion_norm = align_to_length(motion_norm, n_frames)

    # Composite "show intensity" curve
    show_intensity = (
        0.25 * rms_norm
        + 0.20 * loudness_norm
        + 0.20 * onset_env_norm
        + 0.15 * brightness_norm
        + 0.10 * tonal_novelty_norm
        + 0.10 * motion_norm
    ).astype(np.float32)
    show_intensity = normalize_to_0_1(show_intensity)

    timeline = {
        "times_s": as_float_list(t_sec, 3),  # Changed from t_sec for schema compatibility
        "rms_norm": as_float_list(rms_norm, 5),  # Changed from energy
        "loudness": as_float_list(loudness_norm, 5),
        "onset_norm": as_float_list(onset_env_norm, 5),  # Changed from onset
        "brightness_norm": as_float_list(brightness_norm, 5),  # Changed from brightness
        "flatness": as_float_list(flatness_norm, 5),
        "motion": as_float_list(motion_norm, 5),
        "tonal_novelty": as_float_list(tonal_novelty_norm, 5),
        "hpss_perc_ratio": as_float_list(hpss_perc_ratio, 5),
        "is_beat": [int(x) for x in is_beat.tolist()],
        "is_downbeat": [int(x) for x in is_downbeat.tolist()],
        "section_id": [int(x) for x in section_id.tolist()],
    }

    return {
        "timeline": timeline,
        "composites": {
            "show_intensity": as_float_list(show_intensity, 5),
        },
    }
