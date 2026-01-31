"""Segmentation algorithms for section boundary detection.

Implements Foote novelty-based segmentation with adaptive peak picking.
"""

from __future__ import annotations

import librosa
import numpy as np

from twinklr.core.audio.structure.models import SectioningPreset


def compute_self_similarity_matrix(features: np.ndarray) -> np.ndarray:
    """Compute self-similarity matrix via dot product of normalized features.

    Args:
        features: Normalized feature matrix (features × frames)

    Returns:
        Self-similarity matrix (frames × frames) with values in [-1, 1]
    """
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        ssm = (features.T @ features).astype(np.float32)
    ssm = np.nan_to_num(ssm, nan=0.0, posinf=1.0, neginf=-1.0)
    ssm = np.clip(ssm, -1.0, 1.0).astype(np.float32)
    return ssm  # type: ignore[no-any-return]


def compute_foote_novelty(ssm: np.ndarray, kernel_size: int) -> np.ndarray:
    """Compute Foote novelty curve from self-similarity matrix.

    Uses checkerboard kernel to detect transitions between similar regions.

    Args:
        ssm: Self-similarity matrix (frames × frames)
        kernel_size: Half-size of checkerboard kernel (in frames)

    Returns:
        Novelty curve (one value per frame), normalized to [0, 1]
    """
    n = int(ssm.shape[0])
    L = int(max(2, kernel_size))

    if n < (2 * L + 1):
        return np.zeros(n, dtype=np.float32)

    # Checkerboard kernel
    kernel = np.zeros((2 * L, 2 * L), dtype=np.float32)
    kernel[:L, :L] = 1.0
    kernel[L:, L:] = 1.0
    kernel[:L, L:] = -1.0
    kernel[L:, :L] = -1.0

    # Convolve kernel with SSM
    novelty = np.zeros(n, dtype=np.float32)
    for t in range(L, n - L):
        patch = ssm[t - L : t + L, t - L : t + L]
        novelty[t] = float(np.sum(patch * kernel))

    # Normalize to [0, 1]
    if float(np.max(novelty)) > float(np.min(novelty)):
        novelty = (novelty - float(np.min(novelty))) / (
            float(np.max(novelty)) - float(np.min(novelty)) + 1e-8
        )

    return novelty.astype(np.float32)


def compute_boundary_prominence(novelty: np.ndarray, window_size: int) -> np.ndarray:
    """Compute prominence of each boundary (novelty - local median).

    Prominence helps identify which boundaries are most salient relative
    to their local context.

    Args:
        novelty: Novelty curve
        window_size: Window size for local median computation

    Returns:
        Prominence values normalized to [0, 1] via robust sigmoid
    """
    from twinklr.core.audio.structure.descriptors import robust_sigmoid_norm

    n = int(novelty.size)
    if n == 0:
        return np.array([], dtype=np.float32)

    w = int(max(2, window_size))
    prom = np.zeros(n, dtype=np.float32)

    for t in range(n):
        a = max(0, t - w)
        b = min(n, t + w + 1)
        local = novelty[a:b]
        prom[t] = float(novelty[t] - float(np.median(local)))

    # Keep only positive evidence
    prom = np.maximum(prom, 0.0)

    # Robust normalization
    norm_result = robust_sigmoid_norm(prom)
    return norm_result.values_0_1.astype(np.float32)


def adaptive_peak_pick(
    novelty: np.ndarray,
    preset: SectioningPreset,
    min_len_beats: int,
) -> tuple[list[int], float]:
    """Adaptive delta search to find optimal peak set within section count bounds.

    Iteratively adjusts peak picking threshold to achieve target number of sections.

    Args:
        novelty: Novelty curve
        preset: Sectioning preset with min/max section bounds
        min_len_beats: Minimum section length in beats

    Returns:
        Tuple of (peak indices, final delta threshold)
    """
    n = int(novelty.size)
    if n <= 2:
        return ([], float(preset.peak_delta))

    delta = float(preset.peak_delta)
    delta_min, delta_max = 0.005, 0.25

    def _pick(d: float) -> list[int]:
        """Pick peaks with given delta threshold."""
        b = librosa.util.peak_pick(
            novelty,
            pre_max=int(preset.pre_avg),
            post_max=int(preset.post_avg),
            pre_avg=int(preset.pre_avg),
            post_avg=int(preset.post_avg),
            delta=float(d),
            wait=int(min_len_beats),
        )
        beats = [int(x) for x in b.tolist()]
        # Remove edge peaks (handled separately)
        beats = [x for x in beats if 0 < x < (n - 1)]
        return sorted(set(beats))

    best = _pick(delta)
    best_delta = delta

    # Iteratively adjust delta to meet section count constraints
    for _ in range(18):
        section_count = len(best) + 1
        if int(preset.min_sections) <= section_count <= int(preset.max_sections):
            break

        if section_count < int(preset.min_sections):
            delta = max(delta_min, delta * 0.85)  # Lower threshold for more peaks
        else:
            delta = min(delta_max, delta * 1.15)  # Raise threshold for fewer peaks

        cand = _pick(delta)
        if cand != best:
            best = cand
            best_delta = delta

    return (best, best_delta)


def align_boundaries_to_bars(
    boundary_times: list[float], bars_s: list[float], tolerance_s: float = 2.0
) -> list[float]:
    """Snap section boundaries to nearest bar start within tolerance.

    Args:
        boundary_times: Candidate boundary times in seconds
        bars_s: Bar start times in seconds
        tolerance_s: Maximum distance to snap (seconds)

    Returns:
        Aligned boundary times (de-duplicated)
    """
    if not bars_s:
        return boundary_times

    bars = np.array(bars_s, dtype=np.float32)
    aligned: list[float] = []

    for boundary in boundary_times:
        distances = np.abs(bars - boundary)
        nearest_idx = int(np.argmin(distances))
        if float(distances[nearest_idx]) < float(tolerance_s):
            aligned.append(float(bars[nearest_idx]))
        else:
            aligned.append(float(boundary))

    # De-duplicate while preserving order
    seen: set[float] = set()
    result: list[float] = []
    for v in aligned:
        if v not in seen:
            seen.add(v)
            result.append(v)

    return result


def merge_short_sections(times: list[float], min_s: float, duration: float) -> list[float]:
    """Merge sections shorter than min_s while avoiding overly long merges.

    Args:
        times: Boundary times in seconds
        min_s: Minimum section duration
        duration: Total audio duration

    Returns:
        Merged boundary times (always includes 0 and duration)
    """
    if len(times) < 3:
        return [float(times[0]), float(times[-1])] if times else [0.0, float(duration)]

    times_sorted = sorted({float(t) for t in times})
    if times_sorted[0] != 0.0:
        times_sorted = [0.0] + times_sorted
    if times_sorted[-1] != float(duration):
        times_sorted.append(float(duration))

    result = [times_sorted[0]]
    for i in range(1, len(times_sorted) - 1):
        cur = float(times_sorted[i])
        nxt = float(times_sorted[i + 1])

        # Keep if section meets minimum OR would create overly long section
        if cur - result[-1] >= min_s:
            result.append(cur)
        elif nxt - result[-1] > min_s * 3:
            result.append(cur)

    # Always end at duration
    if result[-1] != float(duration):
        if float(duration) - result[-1] < min_s and len(result) > 1:
            result[-1] = float(duration)
        else:
            result.append(float(duration))

    out = sorted(set(result))
    if out[0] != 0.0:
        out = [0.0] + out
    if out[-1] != float(duration):
        out.append(float(duration))

    return out


def suppress_micro_edge_boundaries(
    boundaries: list[float], *, pickup_s: float = 0.35, tailtick_s: float = 0.35
) -> list[float]:
    """Remove tiny first/last segments caused by near-zero offsets or tail ticks.

    Args:
        boundaries: Boundary times
        pickup_s: Minimum first segment duration
        tailtick_s: Minimum last segment duration

    Returns:
        Cleaned boundary list
    """
    if len(boundaries) < 3:
        return boundaries

    b = [float(x) for x in boundaries]
    b = sorted(set(b))

    # Remove boundary creating tiny first segment [0, b1]
    if len(b) >= 3 and (b[1] - b[0]) < pickup_s:
        b = [b[0]] + b[2:]

    # Remove boundary creating tiny last segment [b[-2], b[-1]]
    if len(b) >= 3 and (b[-1] - b[-2]) < tailtick_s:
        b = b[:-2] + [b[-1]]

    return sorted(set(b))


def detect_fade_out_start(
    rms: np.ndarray, sr: int, hop_length: int, duration_s: float
) -> float | None:
    """Detect fade-out start time from RMS energy.

    Args:
        rms: RMS energy curve
        sr: Sample rate
        hop_length: Hop length
        duration_s: Audio duration

    Returns:
        Fade-out start time in seconds, or None if no fade detected
    """
    rms = np.asarray(rms, dtype=np.float32)
    if rms.size < 16:
        return None

    # Smooth RMS
    w = max(3, int(0.35 * sr / max(hop_length, 1)))
    kern = np.ones(w, dtype=np.float32) / float(w)
    rms_s = np.convolve(rms, kern, mode="same")

    # Look at last ~20 seconds
    tail_s = 20.0
    start_s = max(0.0, float(duration_s) - tail_s)
    start_f = int(librosa.time_to_frames(start_s, sr=sr, hop_length=hop_length))
    start_f = int(np.clip(start_f, 0, max(0, rms_s.size - 1)))
    tail = rms_s[start_f:]

    if tail.size < 12:
        return None

    # Check for energy drop
    begin = float(np.mean(tail[: max(3, tail.size // 8)]))
    end = float(np.mean(tail[-max(3, tail.size // 8) :]))
    if begin <= 1e-8:
        return None

    drop_ratio = (begin - end) / begin
    if drop_ratio < 0.35:
        return None

    # Find where energy drops below threshold
    p10 = float(np.percentile(tail, 10))
    p70 = float(np.percentile(tail, 70))
    thresh = p10 + 0.15 * (p70 - p10)

    below = np.where(tail <= thresh)[0]
    if below.size == 0:
        return None

    fade_f = start_f + int(below[0])
    fade_s = float(librosa.frames_to_time(fade_f, sr=sr, hop_length=hop_length))
    fade_s = float(np.clip(fade_s, 0.0, float(duration_s)))

    # Don't create tiny outro fragments
    if (duration_s - fade_s) < 3.0:
        return None

    return fade_s
