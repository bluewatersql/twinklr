"""Song section detection and analysis."""

from __future__ import annotations

import logging
from typing import Any

import librosa
import numpy as np

from blinkb0t.core.audio.utils import cosine_similarity, frames_to_time, normalize_to_0_1

logger = logging.getLogger(__name__)


def detect_song_sections(
    y: np.ndarray,
    sr: int,
    *,
    hop_length: int,
    min_section_s: float = 6.0,
    rms_for_energy: np.ndarray | None = None,
) -> dict[str, Any]:
    """Detect song structure using MFCC-based segmentation.

    IMPROVED: Better section labeling with intro/outro detection and energy ranking.
    FIXED: Section merge algorithm preserves important boundaries.

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length
        min_section_s: Minimum section duration
        rms_for_energy: Pre-computed RMS for energy ranking

    Returns:
        Dict with sections, boundary_times_s, meta
    """
    duration = float(librosa.get_duration(y=y, sr=sr))

    # Early exit for very short audio
    if duration < 15.0:
        return {
            "sections": [
                {
                    "section_id": 0,
                    "start_s": 0.0,
                    "end_s": duration,
                    "duration_s": duration,
                    "label": "full",
                    "similarity": 0.0,
                    "repeat_count": 0,
                }
            ],
            "boundary_times_s": [0.0, duration],
            "meta": {"k": 1, "hop_struct": hop_length, "min_section_s": min_section_s},
        }

    hop_struct = hop_length * 4

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=hop_struct).astype(np.float32)
    k = int(np.clip(round(duration / 15.0), 4, 14))

    try:
        boundary_frames = librosa.segment.agglomerative(mfcc, k=k)
        boundary_times = frames_to_time(boundary_frames, sr=sr, hop_length=hop_struct)

        # Ensure start/end
        times: list[float] = [0.0]
        for t in boundary_times.tolist():
            tf = float(t)
            if tf > times[-1] + 1e-3 and tf < duration - 1e-3:
                times.append(tf)
        times.append(duration)

        # FIXED: Improved section merge that doesn't lose important boundaries
        cleaned = merge_short_sections(times, min_section_s, duration)

        # Compute section features
        frame_times = frames_to_time(np.arange(mfcc.shape[1]), sr=sr, hop_length=hop_struct)
        centroids: list[np.ndarray] = []
        section_energies: list[float] = []

        # Compute RMS for energy ranking if not provided
        rms_energy: np.ndarray
        if rms_for_energy is None:
            rms_energy = librosa.feature.rms(y=y, hop_length=hop_struct)[0].astype(np.float32)
        else:
            rms_energy = rms_for_energy
        rms_times = frames_to_time(np.arange(len(rms_energy)), sr=sr, hop_length=hop_struct)

        for i in range(len(cleaned) - 1):
            s, e = cleaned[i], cleaned[i + 1]

            # MFCC centroid
            s_idx = int(np.searchsorted(frame_times, s))
            e_idx = int(np.searchsorted(frame_times, e))
            e_idx = max(e_idx, s_idx + 1)
            sec = mfcc[:, s_idx:e_idx]
            centroids.append(np.mean(sec, axis=1))

            # Section energy
            rs_idx = int(np.searchsorted(rms_times, s))
            re_idx = int(np.searchsorted(rms_times, e))
            re_idx = max(re_idx, rs_idx + 1)
            section_energies.append(float(np.mean(rms_energy[rs_idx:re_idx])))

        # Build pairwise similarity matrix
        n = len(centroids)
        sim_mat = np.zeros((n, n), dtype=np.float32)
        for i in range(n):
            for j in range(n):
                if i != j:
                    sim_mat[i, j] = cosine_similarity(centroids[i], centroids[j])

        # Repetition analysis
        repeat_thresh = 0.88  # Slightly lowered for better detection
        repeat_counts = (sim_mat >= repeat_thresh).sum(axis=1).astype(int)
        max_sim = sim_mat.max(axis=1) if n > 0 else np.array([])

        # Energy ranking (0-1 scale within song)
        if section_energies:
            energy_arr = np.array(section_energies, dtype=np.float32)
            energy_ranks = normalize_to_0_1(energy_arr)
        else:
            energy_ranks = np.array([])

        # IMPROVED: Labeling with intro/outro and energy consideration
        sections = []
        for i in range(len(cleaned) - 1):
            start_s = float(cleaned[i])
            end_s = float(cleaned[i + 1])
            sim = float(max_sim[i]) if i < len(max_sim) else 0.0
            reps = int(repeat_counts[i]) if i < len(repeat_counts) else 0
            energy_rank = float(energy_ranks[i]) if i < len(energy_ranks) else 0.5

            label = label_section(
                idx=i,
                total_sections=n,
                repeat_count=reps,
                max_similarity=sim,
                energy_rank=energy_rank,
                start_s=start_s,
                end_s=end_s,
                duration=duration,
            )

            sections.append(
                {
                    "section_id": int(i),
                    "start_s": start_s,
                    "end_s": end_s,
                    "duration_s": float(end_s - start_s),
                    "label": label,
                    "similarity": sim,
                    "repeat_count": reps,
                    "energy_rank": round(energy_rank, 3),
                }
            )

        return {
            "sections": sections,
            "boundary_times_s": [float(x) for x in cleaned],
            "meta": {
                "k": k,
                "hop_struct": hop_struct,
                "min_section_s": float(min_section_s),
                "repeat_thresh": repeat_thresh,
            },
        }

    except Exception as e:
        logger.warning(f"Section detection failed: {e}")
        return {
            "sections": [],
            "boundary_times_s": [0.0, duration],
            "meta": {"k": k, "hop_struct": hop_struct, "error": str(e)},
        }


def merge_short_sections(times: list[float], min_s: float, duration: float) -> list[float]:
    """Merge sections shorter than min_s while preserving important boundaries.

    FIXED: Original could lose final section entirely.

    Args:
        times: Boundary times
        min_s: Minimum section duration
        duration: Total duration

    Returns:
        Cleaned boundary times
    """
    if len(times) < 3:
        return times

    result = [times[0]]
    for i in range(1, len(times) - 1):
        # Keep boundary if resulting section is long enough
        if times[i] - result[-1] >= min_s:
            result.append(times[i])
        # Otherwise, check if merging would create too-long section
        elif i < len(times) - 1 and times[i + 1] - result[-1] > min_s * 3:
            # Keep this boundary to avoid overly long sections
            result.append(times[i])

    # Always include end
    if result[-1] != duration:
        if duration - result[-1] < min_s and len(result) > 1:
            # Merge final tiny section with previous
            result[-1] = duration
        else:
            result.append(duration)

    return result


def label_section(
    *,
    idx: int,
    total_sections: int,
    repeat_count: int,
    max_similarity: float,
    energy_rank: float,
    start_s: float,
    end_s: float,
    duration: float,
) -> str:
    """Heuristic section labeling with more nuance.

    IMPROVED: Considers position, repetition, and energy.

    Args:
        idx: Section index
        total_sections: Total number of sections
        repeat_count: Number of similar sections
        max_similarity: Maximum similarity to any other section
        energy_rank: Energy rank (0-1)
        start_s: Section start time
        end_s: Section end time
        duration: Total song duration

    Returns:
        Section label (intro, verse, chorus, bridge, outro)
    """
    section_duration = end_s - start_s
    relative_pos = start_s / duration if duration > 0 else 0

    # Intro: first section, typically lower energy, short
    if idx == 0 and total_sections > 3:
        if section_duration < 20 and energy_rank < 0.6:
            return "intro"

    # Outro: last section, often fading
    if idx == total_sections - 1 and total_sections > 3:
        if section_duration < 30 and energy_rank < 0.5:
            return "outro"

    # Chorus: repeats frequently (3+) AND high energy
    if repeat_count >= 3 and energy_rank > 0.5:
        return "chorus"

    # Chorus: Moderate repetition but VERY high energy
    if repeat_count >= 2 and energy_rank > 0.85:
        return "chorus"

    # Chorus: Very high similarity with high energy (even if lower repeat count)
    if repeat_count >= 2 and max_similarity > 0.90 and energy_rank > 0.75:
        return "chorus"

    # Bridge: late in song, low repetition, often different
    # Check bridge BEFORE verse since bridge is more specific
    if relative_pos > 0.55 and repeat_count <= 1 and max_similarity < 0.75:
        return "bridge"

    # Bridge: unique section (no repetition) in middle-to-late portion
    if repeat_count == 0 and relative_pos > 0.45:
        return "bridge"

    # Verse: Moderate repetition with lower-to-mid energy
    # Verses often repeat (verse 1, verse 2) but are less energetic than chorus
    if repeat_count >= 2 and energy_rank <= 0.65:
        return "verse"

    # Verse: Low repetition, mid energy, not at extremes of song
    if repeat_count <= 1 and 0.3 <= energy_rank <= 0.7 and 0.15 < relative_pos < 0.85:
        return "verse"

    # Pre-chorus: just before high-energy repeated section
    # (would need lookahead - simplified here)

    # Default to verse
    return "verse"
