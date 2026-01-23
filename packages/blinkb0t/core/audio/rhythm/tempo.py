"""Tempo change detection."""

from __future__ import annotations

from typing import Any

import librosa
import numpy as np


def detect_tempo_changes(
    y: np.ndarray, sr: int, *, hop_length: int, window_size_s: float = 10.0
) -> dict[str, Any]:
    """Detect global tempo changes using sliding window analysis.

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length
        window_size_s: Window size in seconds

    Returns:
        Dict with tempo_curve, tempo_changes, average_tempo_bpm, tempo_std, is_stable
    """
    window_samples = int(window_size_s * sr)
    hop_samples = int(window_samples / 2)

    # Early exit for short audio
    if len(y) < window_samples:
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length)
            # Convert numpy array/scalar to Python float using .item()
            tempo_float = float(tempo.item()) if hasattr(tempo, "item") else float(tempo)
            return {
                "tempo_curve": [{"time_s": 0.0, "tempo_bpm": tempo_float}],
                "tempo_changes": [],
                "average_tempo_bpm": tempo_float,
                "tempo_std": 0.0,
                "is_stable": True,
            }
        except Exception:
            return {
                "tempo_curve": [],
                "tempo_changes": [],
                "average_tempo_bpm": 0.0,
                "tempo_std": 0.0,
                "is_stable": True,
            }

    tempos: list[dict[str, Any]] = []
    for i in range(0, max(0, len(y) - window_samples), hop_samples):
        segment = y[i : i + window_samples]
        time_s = i / sr
        try:
            # Use simpler tempo detection for windowed analysis
            onset_env = librosa.onset.onset_strength(y=segment, sr=sr, hop_length=hop_length)
            tempo, _ = librosa.beat.beat_track(
                onset_envelope=onset_env, sr=sr, hop_length=hop_length
            )
            # Convert numpy array/scalar to Python float using .item()
            tempo_float = float(tempo.item()) if hasattr(tempo, "item") else float(tempo)
            tempos.append({"time_s": float(time_s), "tempo_bpm": tempo_float})
        except Exception:
            continue

    tempo_changes: list[dict[str, Any]] = []
    if len(tempos) > 1:
        for i in range(1, len(tempos)):
            prev = tempos[i - 1]["tempo_bpm"]
            curr = tempos[i]["tempo_bpm"]
            if prev > 0:
                change_pct = abs(curr - prev) / prev
                if change_pct > 0.1:
                    tempo_changes.append(
                        {
                            "time_s": tempos[i]["time_s"],
                            "from_bpm": prev,
                            "to_bpm": curr,
                            "change_pct": float(change_pct),
                        }
                    )

    if tempos:
        vals = np.array([t["tempo_bpm"] for t in tempos], dtype=np.float32)
        avg = float(np.mean(vals))
        std = float(np.std(vals))
        is_stable = std < avg * 0.05 if avg > 0 else True
    else:
        avg, std, is_stable = 0.0, 0.0, True

    return {
        "tempo_curve": tempos,
        "tempo_changes": tempo_changes,
        "average_tempo_bpm": avg,
        "tempo_std": std,
        "is_stable": is_stable,
    }
