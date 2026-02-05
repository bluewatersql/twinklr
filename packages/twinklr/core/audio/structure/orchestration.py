"""Orchestration utilities for section detection pipeline."""

from __future__ import annotations

import logging
from typing import Any

import librosa
import numpy as np

from twinklr.core.audio.structure import descriptors

logger = logging.getLogger(__name__)


def build_beat_grid(
    y_work: np.ndarray,
    sr: int,
    hop_length: int,
    duration_work: float,
    beats_s: list[float] | None,
    bars_s: list[float] | None,
    start_offset_s: float,
) -> tuple[list[float] | None, list[float] | None, np.ndarray, float]:
    """Build beat grid (prefer provided beats, estimate otherwise).

    Args:
        y_work: Audio signal (work timeline)
        sr: Sample rate
        hop_length: Hop length
        duration_work: Duration in work timeline
        beats_s: Provided beat times (original timeline)
        bars_s: Provided bar times (original timeline)
        start_offset_s: Trim offset

    Returns:
        Tuple of (beats_work, bars_work, beat_times, tempo_bpm)
    """
    # Map beats/bars to work timeline
    beats_work: list[float] | None = None
    if beats_s:
        beats_work = [float(t) - start_offset_s for t in beats_s]
        beats_work = [t for t in beats_work if 0.0 <= t <= duration_work]

    bars_work: list[float] | None = None
    if bars_s:
        bars_work = [float(t) - start_offset_s for t in bars_s]
        bars_work = [t for t in bars_work if 0.0 <= t <= duration_work]

    # Construct beat times
    if beats_work and len(beats_work) >= 2:
        beat_times = np.array(beats_work, dtype=np.float32)
        beat_times = beat_times[(beat_times >= 0.0) & (beat_times <= duration_work)]
        beat_times = np.unique(beat_times)
        if beat_times.size < 2:
            beat_times = np.linspace(
                0.0, duration_work, num=max(8, int(duration_work * 2.0))
            ).astype(np.float32)
    else:
        _, beat_frames = librosa.beat.beat_track(y=y_work, sr=sr, units="frames")
        beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length).astype(
            np.float32
        )
        beat_times = beat_times[(beat_times >= 0.0) & (beat_times <= duration_work)]
        beat_times = np.unique(beat_times)

    if beat_times.size < 8:
        beat_times = np.linspace(0.0, duration_work, num=max(8, int(duration_work * 2.0))).astype(
            np.float32
        )

    # Estimate tempo
    if beat_times.size >= 2:
        diffs = np.diff(beat_times)
        diffs = diffs[diffs > 1e-4]
        if diffs.size > 0:
            med = float(np.median(diffs))
            tempo_bpm = float(np.clip(60.0 / med, 40.0, 220.0))
        else:
            tempo_bpm = 120.0
    else:
        tempo_bpm = 120.0

    return beats_work, bars_work, beat_times, tempo_bpm


def compute_section_descriptors(
    X_normalized: np.ndarray,
    beat_times: np.ndarray,
    boundaries_work: list[float],
    boundaries_orig: list[float],
    prominence: np.ndarray,
    rms_for_energy: np.ndarray | None,
    y_work: np.ndarray,
    sr: int,
    hop_length: int,
    vocal_segments: list[dict[str, Any]],
    chords: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compute section descriptors (energy, repetition, confidence).

    Args:
        X_normalized: Normalized feature matrix
        beat_times: Beat times in work timeline
        boundaries_work: Boundaries in work timeline
        boundaries_orig: Boundaries in original timeline
        prominence: Boundary prominence values
        rms_for_energy: Pre-computed RMS or None
        y_work: Audio signal (work timeline)
        sr: Sample rate
        hop_length: Hop length
        vocal_segments: Vocal segments
        chords: Chord detections

    Returns:
        List of section dictionaries
    """
    # Beat-sync RMS
    beat_frames = [int(librosa.time_to_frames(t, sr=sr, hop_length=hop_length)) for t in beat_times]
    if rms_for_energy is None:
        rms_work = librosa.feature.rms(y=y_work, hop_length=hop_length)[0].astype(np.float32)
    else:
        rms_work = np.asarray(rms_for_energy, dtype=np.float32)

    rms_sync = librosa.util.sync(rms_work.reshape(1, -1), beat_frames, aggregate=np.mean)[
        0, : len(beat_times)
    ].astype(np.float32)

    # Section centroids and similarity
    centroids = descriptors.compute_section_centroids(X_normalized, beat_times, boundaries_work)
    sim_mat = descriptors.compute_similarity_matrix(centroids)
    max_sim = sim_mat.max(axis=1) if len(centroids) > 0 else np.array([], dtype=np.float32)

    # Repetition and energy
    rep_strength_raw = descriptors.compute_repetition_strength(sim_mat)
    rep_norm = descriptors.robust_sigmoid_norm(rep_strength_raw)

    section_energies = []
    for i in range(len(boundaries_work) - 1):
        sb = int(np.argmin(np.abs(beat_times - boundaries_work[i])))
        eb = int(np.argmin(np.abs(beat_times - boundaries_work[i + 1])))
        if eb <= sb:
            eb = min(sb + 1, len(beat_times))
        seg_rms = rms_sync[sb:eb] if eb > sb else rms_sync[sb : sb + 1]
        section_energies.append(float(np.mean(seg_rms)))

    energy_arr = np.array(section_energies, dtype=np.float32)
    energy_norm = descriptors.robust_sigmoid_norm(energy_arr)

    # Repeat counts
    threshold = descriptors.derive_repeat_threshold(sim_mat)
    repeat_counts = descriptors.compute_repeat_counts(sim_mat, threshold)

    # Discrimination power
    discrimination = float(
        np.clip(0.5 * energy_norm.discrim_power + 0.5 * rep_norm.discrim_power, 0.0, 1.0)
    )

    # Build section dicts
    sections: list[dict[str, Any]] = []
    total_sections = max(1, len(boundaries_orig) - 1)

    for i in range(len(boundaries_orig) - 1):
        start_s = float(boundaries_orig[i])
        end_s = float(boundaries_orig[i + 1])

        # Boundary strength - use work boundaries if available, else map from original
        # boundaries_work may be shorter than boundaries_orig due to trimming
        if i < len(boundaries_work):
            start_work = boundaries_work[i]
        else:
            # Fallback: map original to work timeline (assuming parallel timing)
            start_work = float(boundaries_orig[i])

        if i + 1 < len(boundaries_work):
            end_work = boundaries_work[i + 1]
        else:
            # Fallback: map original to work timeline
            end_work = float(boundaries_orig[i + 1])

        sb = int(np.argmin(np.abs(beat_times - start_work)))
        eb = int(np.argmin(np.abs(beat_times - end_work)))
        sb = int(np.clip(sb, 0, max(0, len(beat_times) - 1)))
        eb = int(np.clip(eb, 0, max(0, len(beat_times) - 1)))

        b_in = float(prominence[sb]) if prominence.size else 0.0
        b_out = float(prominence[eb]) if prominence.size else 0.0

        boundary_vals: list[float] = []
        if i > 0:
            boundary_vals.append(b_in)
        if i < (total_sections - 1):
            boundary_vals.append(b_out)
        boundary_evidence = float(np.mean(boundary_vals)) if boundary_vals else 0.0

        # Section metrics
        sim = float(max_sim[i]) if i < len(max_sim) else 0.0
        reps = int(repeat_counts[i]) if i < len(repeat_counts) else 0
        energy_rank = float(energy_norm.values_0_1[i]) if i < len(energy_norm.values_0_1) else 0.5
        rep_val = float(rep_norm.values_0_1[i]) if i < len(rep_norm.values_0_1) else 0.5

        conf = descriptors.compute_section_confidence(
            boundary_evidence=boundary_evidence,
            repetition_val=rep_val,
            energy_rank=energy_rank,
            discrimination=discrimination,
        )

        # Vocal density
        vocal_density = 0.0
        if vocal_segments:
            sec_dur = max(end_s - start_s, 1e-9)
            vocal_time = sum(
                max(0.0, min(float(v["end_s"]), end_s) - max(float(v["start_s"]), start_s))
                for v in vocal_segments
                if float(v["start_s"]) < end_s and float(v["end_s"]) > start_s
            )
            vocal_density = float(vocal_time / sec_dur)

        # Harmonic complexity
        harmonic_complexity = None
        if chords:
            sec_chords = [
                c
                for c in chords
                if start_s <= float(c["time_s"]) < end_s and str(c.get("chord", "N")) != "N"
            ]
            if sec_chords:
                changes = len(sec_chords)
                per_s = changes / max(end_s - start_s, 1e-9)
                harmonic_complexity = float(np.clip(per_s / 2.0, 0.0, 1.0))

        sections.append(
            {
                "section_id": int(i),
                "start_s": start_s,
                "end_s": end_s,
                "duration_s": float(end_s - start_s),
                "similarity": sim,
                "repeat_count": reps,
                "energy_rank": float(np.round(energy_rank, 3)),
                "energy": float(np.round(energy_rank, 3)),
                "repetition": float(np.round(rep_val, 3)),
                "confidence": float(np.round(conf, 3)),
                "label": "",
                "label_confidence": 0.0,
                "boundary_strength_in": float(np.round(b_in, 3)),
                "boundary_strength_out": float(np.round(b_out, 3)),
                "vocal_density": float(np.round(vocal_density, 3)),
                "harmonic_complexity": harmonic_complexity,
            }
        )

    return sections


def build_diagnostics(
    tempo_bpm: float,
    beat_times: np.ndarray,
    start_offset_s: float,
    bars_s: list[float] | None,
    duration_orig: float,
    duration_work: float,
    novelty: np.ndarray,
    prominence: np.ndarray,
    ssm: np.ndarray,
    X_normalized: np.ndarray,
) -> dict[str, Any]:
    """Build diagnostic information.

    Args:
        tempo_bpm: Detected tempo
        beat_times: Beat times (work timeline)
        start_offset_s: Trim offset
        bars_s: Bar times (original timeline)
        duration_orig: Original duration
        duration_work: Work timeline duration
        novelty: Novelty curve
        prominence: Prominence curve
        ssm: Self-similarity matrix
        X_normalized: Normalized features

    Returns:
        Diagnostics dictionary
    """
    num_beats = len(beat_times)

    # Compute per-beat repetition
    if num_beats > 1:
        ssm_no_diag = ssm.copy()
        np.fill_diagonal(ssm_no_diag, 0.0)
        rep_per_beat = np.mean(ssm_no_diag, axis=1).astype(np.float32)
        rep_per_beat = descriptors.robust_sigmoid_norm(rep_per_beat).values_0_1
    else:
        rep_per_beat = np.zeros(num_beats, dtype=np.float32)

    return {
        "tempo_bpm": float(tempo_bpm),
        "beat_times_s_work": [float(x) for x in beat_times.tolist()],
        "beat_times_s_orig": [float(x + start_offset_s) for x in beat_times.tolist()],
        "bar_times_s_orig": [float(x) for x in (bars_s or [])] if bars_s else None,
        "duration_s": float(duration_orig),
        "duration_work_s": float(duration_work),
        "novelty": [float(x) for x in novelty.tolist()],
        "prominence": [float(x) for x in prominence.tolist()],
        "repetition": [float(x) for x in rep_per_beat.tolist()],
    }
