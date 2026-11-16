"""Local tempo along the resolved beat grid."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

# Fewest beats in a window that yield a tempo (three intervals); two far-apart beats
# would otherwise read as an absurd tempo.
_MIN_WINDOW_BEATS = 4


def _window_tempo(beats: np.ndarray) -> float | None:
    """Tempo from the median inter-beat interval, or None below ``_MIN_WINDOW_BEATS``."""
    if beats.size < _MIN_WINDOW_BEATS:
        return None
    intervals = np.diff(beats)
    intervals = intervals[intervals > 1e-6]
    return 60.0 / float(np.median(intervals)) if intervals.size else None


def local_tempo_curve(
    beats_s: Sequence[float], *, duration_s: float, window_size_s: float = 10.0
) -> dict[str, Any]:
    """Local tempo of the resolved beat grid over sliding windows.

    The curve is read from the same beats that the BeatGrid uses, so it always agrees
    with the analysis tempo (including a halved tempo octave). Windows start every half
    window and the last one ends at the song end; each reports 60 / median inter-beat
    interval of its beats when it holds at least ``_MIN_WINDOW_BEATS`` beats. Audio no
    longer than one window gives a single point.

    Args:
        beats_s: Beat times in seconds (the resolved grid)
        duration_s: Audio duration in seconds
        window_size_s: Window size in seconds

    Returns:
        Dict with tempo_curve ([{time_s, tempo_bpm}]), average_tempo_bpm, tempo_std
    """
    # Sorted; a NaN sorts last and never falls inside a window.
    beats = np.sort(np.asarray(beats_s, dtype=np.float64))
    if duration_s <= window_size_s:
        starts = [0.0]
        window_size_s = max(duration_s, 0.0) + 1e-9
    else:
        last = duration_s - window_size_s
        starts = [float(t) for t in np.arange(0.0, last, window_size_s / 2.0)] + [last]

    tempos: list[dict[str, Any]] = []
    for start_s in starts:
        inside = beats[(beats >= start_s) & (beats < start_s + window_size_s)]
        tempo = _window_tempo(inside)
        if tempo is not None:
            tempos.append({"time_s": start_s, "tempo_bpm": tempo})

    curve = np.array([point["tempo_bpm"] for point in tempos], dtype=np.float64)
    return {
        "tempo_curve": tempos,
        "average_tempo_bpm": float(np.mean(curve)) if curve.size else 0.0,
        "tempo_std": float(np.std(curve)) if curve.size else 0.0,
    }
