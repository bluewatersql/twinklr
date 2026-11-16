"""Tempo change detection."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise
from typing import Any

import numpy as np


def _window_tempo(beats: np.ndarray) -> float | None:
    """Tempo from the median inter-beat interval, or None with fewer than two beats."""
    intervals = np.diff(beats)
    intervals = intervals[intervals > 1e-6]
    return 60.0 / float(np.median(intervals)) if intervals.size else None


def detect_tempo_changes(
    beats_s: Sequence[float], *, duration_s: float, window_size_s: float = 10.0
) -> dict[str, Any]:
    """Local tempo over sliding windows of the resolved beat grid.

    The curve is read from the same beats that the BeatGrid uses, so it always agrees
    with the analysis tempo (including a halved tempo octave). Windows start every half
    window; each reports 60 / median inter-beat interval of the beats inside it. A change
    of more than 10% between consecutive windows is reported as a tempo change.

    Args:
        beats_s: Beat times in seconds (the resolved grid)
        duration_s: Audio duration in seconds
        window_size_s: Window size in seconds

    Returns:
        Dict with tempo_curve, tempo_changes, average_tempo_bpm, tempo_std, is_stable
    """
    beats = np.asarray(sorted(beats_s), dtype=np.float64)
    tempos: list[dict[str, Any]] = []
    if duration_s <= window_size_s:
        tempo = _window_tempo(beats)
        if tempo is not None:
            tempos.append({"time_s": 0.0, "tempo_bpm": tempo})
    else:
        hop_s = window_size_s / 2.0
        for start_s in np.arange(0.0, duration_s - window_size_s, hop_s):
            inside = beats[(beats >= start_s) & (beats < start_s + window_size_s)]
            tempo = _window_tempo(inside)
            if tempo is not None:
                tempos.append({"time_s": float(start_s), "tempo_bpm": tempo})

    tempo_changes: list[dict[str, Any]] = []
    for previous, current in pairwise(tempos):
        change_pct = abs(current["tempo_bpm"] - previous["tempo_bpm"]) / previous["tempo_bpm"]
        if change_pct > 0.1:
            tempo_changes.append(
                {
                    "time_s": current["time_s"],
                    "from_bpm": previous["tempo_bpm"],
                    "to_bpm": current["tempo_bpm"],
                    "change_pct": float(change_pct),
                }
            )

    if tempos:
        values = np.array([point["tempo_bpm"] for point in tempos], dtype=np.float64)
        average, spread = float(np.mean(values)), float(np.std(values))
        is_stable = spread < average * 0.05
    else:
        average, spread, is_stable = 0.0, 0.0, True

    return {
        "tempo_curve": tempos,
        "tempo_changes": tempo_changes,
        "average_tempo_bpm": average,
        "tempo_std": spread,
        "is_stable": is_stable,
    }
