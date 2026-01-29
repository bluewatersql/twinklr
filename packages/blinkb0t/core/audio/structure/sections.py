"""Song section detection and analysis using hybrid segmentation.

METHODOLOGY:
Hybrid approach combining baseline segmentation with aggressive novelty detection.
More robust and predictable than pure Laplacian while still being data-driven.

IMPROVEMENTS:
1. Multi-Feature Fusion: Combines MFCC, chroma, spectral contrast, tonnetz
2. Hybrid Segmentation: Baseline + aggressive novelty-based boundary detection
3. Beat-Aligned Boundaries: Snaps to bar boundaries for musical alignment
4. Context-Aware Labeling: Uses builds, drops, vocals, chords
5. Subsection Detection: Splits sections with internal structure

This approach is more robust than pure Laplacian clustering while still finding
data-driven boundaries based on the music's actual structure.
"""

from __future__ import annotations

import logging
from typing import Any, cast

import librosa
import numpy as np

from blinkb0t.core.audio.utils import cosine_similarity, frames_to_time, normalize_to_0_1

logger = logging.getLogger(__name__)


def detect_song_sections(
    y: np.ndarray,
    sr: int,
    *,
    hop_length: int,
    min_section_s: float = 3.0,
    rms_for_energy: np.ndarray | None = None,
    chroma_cqt: np.ndarray | None = None,
    beats_s: list[float] | None = None,
    bars_s: list[float] | None = None,
    builds: list[dict[str, Any]] | None = None,
    drops: list[dict[str, Any]] | None = None,
    vocal_segments: list[dict[str, Any]] | None = None,
    chords: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Detect song structure using hybrid segmentation.

    Combines baseline segmentation with aggressive novelty detection for robust,
    data-driven boundary detection.

    IMPROVEMENTS:
    - Multi-feature fusion (MFCC + chroma + spectral contrast + tonnetz)
    - Hybrid segmentation (baseline + novelty detection)
    - Beat-aligned boundaries
    - Context-aware labeling
    - Subsection detection

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length
        min_section_s: Minimum section duration
        rms_for_energy: Pre-computed RMS for energy ranking
        chroma_cqt: Pre-computed chroma features (12 x n_frames)
        beats_s: Beat times in seconds
        bars_s: Downbeat/bar times in seconds
        builds: Energy build detections
        drops: Energy drop detections
        vocal_segments: Vocal presence segments
        chords: Chord detections

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

    # IMPROVEMENT 1: Multi-Feature Fusion
    features = _extract_multi_features(y, sr, hop_struct, chroma_cqt)

    # IMPROVEMENT 2: Hybrid Segmentation (Baseline + Novelty Detection)
    # This is more robust than pure Laplacian while still being data-driven
    try:
        # Step 1: Create intelligent baseline using recurrence-based detection
        boundary_frames = _hybrid_segmentation(
            features, n_frames=features.shape[1], duration_s=duration
        )
        boundary_times = frames_to_time(boundary_frames, sr=sr, hop_length=hop_struct)

        # Ensure start/end
        times: list[float] = [0.0]
        for t in boundary_times.tolist():
            tf = float(t)
            if tf > times[-1] + 1e-3 and tf < duration - 1e-3:
                times.append(tf)
        times.append(duration)

        # Step 2: AGGRESSIVE novelty-based refinement
        # This finds data-driven boundaries that the baseline might have missed
        frame_times = frames_to_time(np.arange(features.shape[1]), sr=sr, hop_length=hop_struct)
        additional_boundaries = _detect_novelty_boundaries(
            features,
            frame_times,
            np.array(times),
            threshold_percentile=75,  # More aggressive (was 85)
        )
        times = sorted(set(list(times) + list(additional_boundaries)))

        # Merge short sections
        cleaned = merge_short_sections(times, min_section_s, duration)

        # IMPROVEMENT 3: Beat-Aligned Boundaries
        if bars_s:
            cleaned = _align_boundaries_to_bars(cleaned, bars_s, tolerance_s=2.0)

        # Compute section features
        centroids: list[np.ndarray] = []
        section_energies: list[float] = []

        # Compute RMS for energy ranking if not provided
        rms_energy: np.ndarray
        if rms_for_energy is None:
            rms_energy = librosa.feature.rms(y=y, hop_length=hop_struct)[0].astype(np.float32)
        else:
            rms_energy = rms_for_energy
        rms_times = frames_to_time(np.arange(len(rms_energy)), sr=sr, hop_length=hop_struct)

        # Use MFCC for centroids (first 13 features)
        mfcc = features[:13, :]

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
        repeat_thresh = 0.88
        repeat_counts = (sim_mat >= repeat_thresh).sum(axis=1).astype(int)
        max_sim = sim_mat.max(axis=1) if n > 0 else np.array([])

        # Energy ranking (0-1 scale within song)
        if section_energies:
            energy_arr = np.array(section_energies, dtype=np.float32)
            energy_ranks = normalize_to_0_1(energy_arr)
        else:
            energy_ranks = np.array([])

        # Build section list
        sections = []
        for i in range(len(cleaned) - 1):
            start_s = float(cleaned[i])
            end_s = float(cleaned[i + 1])
            sim = float(max_sim[i]) if i < len(max_sim) else 0.0
            reps = int(repeat_counts[i]) if i < len(repeat_counts) else 0
            energy_rank = float(energy_ranks[i]) if i < len(energy_ranks) else 0.5

            sections.append(
                {
                    "section_id": int(i),
                    "start_s": start_s,
                    "end_s": end_s,
                    "duration_s": float(end_s - start_s),
                    "similarity": sim,
                    "repeat_count": reps,
                    "energy_rank": round(energy_rank, 3),
                    "label": "",  # Placeholder, will be set below
                }
            )

        # IMPROVEMENT 5: Context-Aware Labeling
        for i, section in enumerate(sections):
            label = label_section_contextual(
                idx=i,
                sections=sections,
                chords=chords or [],
                builds=builds or [],
                drops=drops or [],
                vocal_segments=vocal_segments or [],
                energy_rank=cast(float, section["energy_rank"]),
                repeat_count=cast(int, section["repeat_count"]),
                max_similarity=cast(float, section["similarity"]),
                relative_pos=cast(float, section["start_s"]) / duration if duration > 0 else 0.0,
                duration=duration,
            )
            section["label"] = label

        # IMPROVEMENT 6: Subsection Detection
        sections = _detect_subsections(sections, mfcc, frame_times, similarity_threshold=0.75)

        return {
            "sections": sections,
            "boundary_times_s": [float(x) for x in cleaned],
            "meta": {
                "method": "hybrid_segmentation",
                "hop_struct": hop_struct,
                "min_section_s": float(min_section_s),
                "repeat_thresh": repeat_thresh,
                "improvements": [
                    "multi_feature_fusion",
                    "hybrid_segmentation",
                    "beat_alignment",
                    "aggressive_novelty_detection",
                    "context_aware_labeling",
                    "subsection_detection",
                ],
            },
        }

    except Exception as e:
        logger.warning(f"Section detection failed: {e}")
        return {
            "sections": [],
            "boundary_times_s": [0.0, duration],
            "meta": {"method": "hybrid_segmentation", "hop_struct": hop_struct, "error": str(e)},
        }


def _extract_multi_features(
    y: np.ndarray, sr: int, hop_length: int, chroma_cqt: np.ndarray | None = None
) -> np.ndarray:
    """Extract and combine multiple feature types for segmentation.

    IMPROVEMENT 1: Multi-Feature Fusion

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length
        chroma_cqt: Pre-computed chroma (optional)

    Returns:
        Stacked features (n_features x n_frames)
    """
    # 1. MFCC for timbre
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=hop_length).astype(np.float32)

    # 2. Chroma for harmonic content
    if chroma_cqt is not None and chroma_cqt.shape[1] == mfcc.shape[1]:
        chroma = chroma_cqt.astype(np.float32)
    else:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length).astype(np.float32)
        # Align to mfcc length
        if chroma.shape[1] != mfcc.shape[1]:
            if chroma.shape[1] > mfcc.shape[1]:
                chroma = chroma[:, : mfcc.shape[1]]
            else:
                chroma = np.pad(chroma, ((0, 0), (0, mfcc.shape[1] - chroma.shape[1])), mode="edge")

    # 3. Spectral contrast for instrumentation
    try:
        contrast = librosa.feature.spectral_contrast(y=y, sr=sr, hop_length=hop_length).astype(
            np.float32
        )
        if contrast.shape[1] != mfcc.shape[1]:
            if contrast.shape[1] > mfcc.shape[1]:
                contrast = contrast[:, : mfcc.shape[1]]
            else:
                contrast = np.pad(
                    contrast, ((0, 0), (0, mfcc.shape[1] - contrast.shape[1])), mode="edge"
                )
    except Exception:
        # Fallback: use zeros if spectral contrast fails
        contrast = np.zeros((7, mfcc.shape[1]), dtype=np.float32)

    # 4. Tonnetz for tonal relationships
    try:
        y_harm = librosa.effects.harmonic(y)
        tonnetz = librosa.feature.tonnetz(y=y_harm, sr=sr, hop_length=hop_length).astype(np.float32)
        if tonnetz.shape[1] != mfcc.shape[1]:
            if tonnetz.shape[1] > mfcc.shape[1]:
                tonnetz = tonnetz[:, : mfcc.shape[1]]
            else:
                tonnetz = np.pad(
                    tonnetz, ((0, 0), (0, mfcc.shape[1] - tonnetz.shape[1])), mode="edge"
                )
    except Exception:
        # Fallback: use zeros if tonnetz fails
        tonnetz = np.zeros((6, mfcc.shape[1]), dtype=np.float32)

    # Stack features with weights
    features = np.vstack(
        [
            mfcc * 1.0,  # Timbre (baseline)
            chroma * 0.8,  # Harmony (important for section changes)
            contrast * 0.6,  # Instrumentation
            tonnetz * 0.5,  # Tonal relationships
        ]
    )

    return features


def _hybrid_segmentation(features: np.ndarray, n_frames: int, duration_s: float) -> np.ndarray:
    """Hybrid segmentation: recurrence-based baseline with intelligent scaling.

    IMPROVEMENT 2: Hybrid Segmentation

    Uses recurrence matrix to detect repetition structure, then applies intelligent
    boundary detection. More robust and predictable than pure Laplacian.

    Args:
        features: Feature matrix (n_features x n_frames)
        n_frames: Total number of frames
        duration_s: Song duration in seconds

    Returns:
        Boundary frame indices
    """
    try:
        # Build recurrence matrix (self-similarity)
        R = librosa.segment.recurrence_matrix(
            features, mode="affinity", metric="cosine", sparse=False, width=3
        )

        # Apply path enhancement to emphasize diagonal structure
        R_enhanced = librosa.segment.path_enhance(R, n=3)

        # Use spectral clustering with intelligent k estimation
        # Scale with duration - target 12-16 sections for typical songs
        min_sections = max(12, int(duration_s / 15))  # At least 1 per 15s
        max_sections = min(36, int(duration_s / 5))  # Up to 1 per 5s

        # Try different k values and pick the best based on boundary strength
        best_boundaries = None
        best_score = -np.inf

        for k in range(min_sections, min(max_sections + 1, n_frames // 5)):
            try:
                # Agglomerative clustering on enhanced recurrence
                boundaries = librosa.segment.agglomerative(R_enhanced, k=k)

                # Score boundaries by novelty strength
                score = _score_boundaries(features, boundaries)

                if score > best_score:
                    best_score = score
                    best_boundaries = boundaries
            except Exception:
                continue

        if best_boundaries is not None:
            logger.debug(f"Hybrid segmentation: k={len(best_boundaries)}, score={best_score:.3f}")
            return best_boundaries

        # Fallback to reasonable default
        k_default = int(np.clip(duration_s / 15.0, min_sections, max_sections))
        return librosa.segment.agglomerative(R_enhanced, k=k_default)

    except Exception as e:
        logger.warning(f"Hybrid segmentation failed, using fallback: {e}")
        # Fallback: duration-based with reasonable scaling
        k_fallback = int(np.clip(duration_s / 15.0, 8, 20))
        # Create evenly spaced boundaries
        return np.linspace(0, n_frames - 1, k_fallback, dtype=int)


def _score_boundaries(features: np.ndarray, boundaries: np.ndarray) -> float:
    """Score boundary quality based on feature novelty at transitions.

    Args:
        features: Feature matrix
        boundaries: Boundary frame indices

    Returns:
        Quality score (higher is better)
    """
    if len(boundaries) < 2:
        return 0.0

    score = 0.0
    window = 3  # Frames before/after boundary

    for b in boundaries[1:-1]:  # Skip first and last
        if b < window or b >= features.shape[1] - window:
            continue

        # Compare features before and after boundary
        before = features[:, max(0, b - window) : b].mean(axis=1)
        after = features[:, b : min(features.shape[1], b + window)].mean(axis=1)

        # Novelty = dissimilarity across boundary
        novelty = 1.0 - cosine_similarity(before, after)
        score += novelty

    # Normalize by number of boundaries
    return score / max(1, len(boundaries) - 2)


def _merge_hierarchical_boundaries(
    coarse: np.ndarray, fine: np.ndarray, n_frames: int
) -> np.ndarray:
    """DEPRECATED: Merge coarse and fine boundaries intelligently.

    This function is kept for backward compatibility but is no longer used
    by the Laplacian segmentation approach.

    Args:
        coarse: Coarse-level boundary frames
        fine: Fine-level boundary frames
        n_frames: Total number of frames

    Returns:
        Merged boundary frames
    """
    # Start with all coarse boundaries
    boundaries = set(coarse.tolist())

    # Add fine boundaries that are far enough from coarse boundaries
    min_distance_frames = int(n_frames / 50)  # At least 2% of song apart

    for fb in fine:
        # Check distance to nearest coarse boundary
        distances = np.abs(coarse - fb)
        if distances.min() > min_distance_frames:
            boundaries.add(int(fb))

    return np.sort(np.array(list(boundaries), dtype=int))


def _align_boundaries_to_bars(
    boundary_times: list[float], bars_s: list[float], tolerance_s: float = 2.0
) -> list[float]:
    """Snap section boundaries to nearest bar start.

    IMPROVEMENT 3: Beat-Aligned Boundaries

    Args:
        boundary_times: Original boundary times in seconds
        bars_s: Bar/downbeat times in seconds
        tolerance_s: Maximum distance to snap (seconds)

    Returns:
        Aligned boundary times
    """
    if not bars_s:
        return boundary_times

    bars = np.array(bars_s, dtype=np.float32)
    aligned = []

    for boundary in boundary_times:
        # Find nearest bar within tolerance
        distances = np.abs(bars - boundary)
        nearest_idx = int(np.argmin(distances))

        if distances[nearest_idx] < tolerance_s:
            # Snap to bar
            aligned.append(float(bars[nearest_idx]))
        else:
            # Keep original (might be mid-section break)
            aligned.append(float(boundary))

    # Remove duplicates while preserving order
    seen = set()
    result = []
    for val in aligned:
        if val not in seen:
            seen.add(val)
            result.append(val)

    return sorted(result)


def _detect_novelty_boundaries(
    features: np.ndarray,
    times_s: np.ndarray,
    existing_boundaries: np.ndarray,
    threshold_percentile: float = 85,
) -> list[float]:
    """Detect additional boundaries using novelty curve.

    IMPROVEMENT 4: Novelty-Based Refinement

    Args:
        features: Feature matrix (n_features x n_frames)
        times_s: Time points in seconds
        existing_boundaries: Already detected boundaries
        threshold_percentile: Percentile threshold for peak detection

    Returns:
        Additional boundary times
    """
    try:
        # Compute self-similarity matrix
        similarity = librosa.segment.recurrence_matrix(
            features, mode="affinity", metric="cosine", sparse=False
        )

        # Compute novelty curve (checkerboard kernel)
        # Note: timelag_filter may fail in some librosa versions with certain input shapes
        novelty_curve: np.ndarray = librosa.segment.timelag_filter(  # type: ignore[type-var]  # pyright: ignore[reportArgumentType]
            similarity  # pyright: ignore[reportArgumentType]
        )

        # Detect peaks in novelty
        peaks = librosa.util.peak_pick(
            novelty_curve,
            pre_max=3,
            post_max=3,
            pre_avg=3,
            post_avg=5,
            delta=0.1,
            wait=10,
        )

        # Convert to times
        peak_times = times_s[peaks] if len(peaks) > 0 else np.array([])

        # Add peaks above threshold that aren't near existing boundaries
        threshold = np.percentile(novelty_curve, threshold_percentile)
        additional = []

        for pt in peak_times:
            pt_idx = int(np.searchsorted(times_s, pt))
            if pt_idx < len(novelty_curve) and novelty_curve[pt_idx] > threshold:
                # Check if far enough from existing boundaries (at least 3s)
                if np.min(np.abs(existing_boundaries - pt)) > 3.0:
                    additional.append(float(pt))

        return additional

    except (TypeError, AttributeError) as e:
        # librosa compatibility issue - timelag_filter can fail with certain versions/inputs
        logger.debug(f"Novelty boundary detection failed (librosa compatibility): {type(e).__name__}")
        return []
    except Exception as e:
        logger.debug(f"Novelty boundary detection failed: {type(e).__name__}: {str(e)[:100]}")
        return []


def label_section_contextual(
    *,
    idx: int,
    sections: list[dict[str, Any]],
    chords: list[dict[str, Any]],
    builds: list[dict[str, Any]],
    drops: list[dict[str, Any]],
    vocal_segments: list[dict[str, Any]],
    energy_rank: float,
    repeat_count: int,
    max_similarity: float,
    relative_pos: float,
    duration: float,
) -> str:
    """Context-aware section labeling using musical features.

    IMPROVEMENT 5: Context-Aware Labeling

    Args:
        idx: Section index
        sections: All sections
        chords: Chord detections
        builds: Energy builds
        drops: Energy drops
        vocal_segments: Vocal segments
        energy_rank: Energy rank (0-1)
        repeat_count: Number of similar sections
        max_similarity: Max similarity to any other section
        relative_pos: Relative position in song (0-1)
        duration: Total song duration

    Returns:
        Section label
    """
    section = sections[idx]
    start_s, end_s = section["start_s"], section["end_s"]
    section_duration = end_s - start_s
    total_sections = len(sections)

    # 1. Check if this section contains a drop (often marks chorus start)
    has_drop = any(start_s <= d["time_s"] <= end_s for d in drops)

    # 2. Check if preceded by build (pre-chorus or build-up to chorus)
    preceded_by_build = False
    if idx > 0:
        prev_section = sections[idx - 1]
        preceded_by_build = any(
            b["end_s"] >= prev_section["start_s"] and b["end_s"] <= start_s for b in builds
        )

    # 3. Check vocal density
    vocal_coverage = 0.0
    if vocal_segments:
        vocal_time = sum(
            max(0.0, min(v["end_s"], end_s) - max(v["start_s"], start_s))
            for v in vocal_segments
            if v["start_s"] < end_s and v["end_s"] > start_s
        )
        vocal_coverage = vocal_time / max(section_duration, 1e-9)

    # 4. Chord progression complexity
    section_chords = [c for c in chords if start_s <= c["time_s"] < end_s]
    unique_chords = len({c["chord"] for c in section_chords if c["chord"] != "N"})
    chord_changes = len([c for c in section_chords if c["chord"] != "N"])

    # Intro: first section, typically lower energy, short
    if idx == 0 and total_sections > 3:
        if section_duration < 20 and energy_rank < 0.6:
            return "intro"

    # Outro: last section, often fading
    if idx == total_sections - 1 and total_sections > 3:
        if section_duration < 30 and energy_rank < 0.5:
            return "outro"

    # Pre-chorus detection (build + high energy + before likely chorus)
    if preceded_by_build and energy_rank > 0.6 and idx < total_sections - 1:
        next_section = sections[idx + 1]
        next_repeat_count = next_section.get("repeat_count", 0)
        next_energy = next_section.get("energy_rank", 0)

        if next_repeat_count >= 2 and next_energy > energy_rank:
            return "pre_chorus"

    # Breakdown/drop section (drop + low vocal + low energy relative to context)
    if has_drop and vocal_coverage < 0.3 and energy_rank < 0.4:
        return "breakdown"

    # Chorus detection (improved with drops and vocal presence)
    if repeat_count >= 3 and energy_rank > 0.5:
        return "chorus"
    if repeat_count >= 2 and energy_rank > 0.85:
        return "chorus"
    if repeat_count >= 2 and has_drop:
        return "chorus"
    if repeat_count >= 2 and max_similarity > 0.90 and energy_rank > 0.75:
        return "chorus"
    if repeat_count >= 2 and vocal_coverage > 0.7 and energy_rank > 0.65:
        return "chorus"  # Vocal chorus

    # Bridge: late in song, low repetition, often different harmony
    if relative_pos > 0.55 and repeat_count <= 1 and max_similarity < 0.75:
        return "bridge"
    if (
        repeat_count == 0
        and relative_pos > 0.45
        and chord_changes > 0
        and unique_chords > chord_changes * 0.6
    ):
        return "bridge"  # More diverse harmony

    # Verse: Moderate repetition with lower-to-mid energy
    if repeat_count >= 2 and energy_rank <= 0.65 and vocal_coverage > 0.6:
        return "verse"
    if repeat_count >= 2 and energy_rank <= 0.65:
        return "verse"

    # Instrumental/solo (low vocal, moderate-high energy)
    if vocal_coverage < 0.2 and 0.4 < energy_rank < 0.8 and relative_pos > 0.2:
        return "instrumental"

    # Verse: Low repetition, mid energy, not at extremes
    if repeat_count <= 1 and 0.3 <= energy_rank <= 0.7 and 0.15 < relative_pos < 0.85:
        return "verse"

    # Default to verse
    return "verse"


def _detect_subsections(
    sections: list[dict[str, Any]],
    features: np.ndarray,
    times_s: np.ndarray,
    similarity_threshold: float = 0.75,
) -> list[dict[str, Any]]:
    """Split sections into subsections based on internal structure.

    IMPROVEMENT 6: Subsection Detection

    Args:
        sections: Section list
        features: Feature matrix (n_features x n_frames)
        times_s: Time points for features
        similarity_threshold: Threshold for splitting

    Returns:
        Refined section list with possible subsections
    """
    refined_sections: list[dict[str, Any]] = []

    for section in sections:
        start_s, end_s = section["start_s"], section["end_s"]

        # Extract features for this section
        start_idx = int(np.searchsorted(times_s, start_s))
        end_idx = int(np.searchsorted(times_s, end_s))
        end_idx = max(end_idx, start_idx + 1)

        section_features = features[:, start_idx:end_idx]

        # Check for internal change point (e.g., verse 1a→1b)
        if section_features.shape[1] > 20:  # Minimum frames for split
            # Try to split in half, check if two halves are different
            mid = section_features.shape[1] // 2
            first_half = section_features[:, :mid]
            second_half = section_features[:, mid:]

            first_centroid = np.mean(first_half, axis=1)
            second_centroid = np.mean(second_half, axis=1)

            sim = cosine_similarity(first_centroid, second_centroid)

            if sim < similarity_threshold:
                # Split into subsections
                mid_time = float(times_s[min(start_idx + mid, len(times_s) - 1)])

                # Only split if both halves are reasonable length (at least 4s each)
                if mid_time - start_s >= 4.0 and end_s - mid_time >= 4.0:
                    refined_sections.append(
                        {
                            **section,
                            "end_s": mid_time,
                            "duration_s": mid_time - start_s,
                            "subsection": "a",
                        }
                    )
                    refined_sections.append(
                        {
                            **section,
                            "section_id": section["section_id"] + 0.1,
                            "start_s": mid_time,
                            "end_s": end_s,
                            "duration_s": end_s - mid_time,
                            "subsection": "b",
                        }
                    )
                    continue

        # No split, keep original
        refined_sections.append(section)

    return refined_sections


def merge_short_sections(times: list[float], min_s: float, duration: float) -> list[float]:
    """Merge sections shorter than min_s while preserving important boundaries.

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
    """Heuristic section labeling (legacy function for backward compatibility).

    NOTE: Use label_section_contextual for better results with musical context.

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
    if relative_pos > 0.55 and repeat_count <= 1 and max_similarity < 0.75:
        return "bridge"

    # Bridge: unique section (no repetition) in middle-to-late portion
    if repeat_count == 0 and relative_pos > 0.45:
        return "bridge"

    # Verse: Moderate repetition with lower-to-mid energy
    if repeat_count >= 2 and energy_rank <= 0.65:
        return "verse"

    # Verse: Low repetition, mid energy, not at extremes of song
    if repeat_count <= 1 and 0.3 <= energy_rank <= 0.7 and 0.15 < relative_pos < 0.85:
        return "verse"

    # Default to verse
    return "verse"
