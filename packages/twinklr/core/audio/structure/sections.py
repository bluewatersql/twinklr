"""Song section detection and analysis using hybrid segmentation.

METHODOLOGY:
Hybrid approach combining baseline segmentation with novelty detection.
More robust and predictable than pure clustering while still being data-driven.

IMPROVEMENTS:
1. Multi-Feature Fusion: MFCC, chroma, spectral contrast, tonnetz, onset, centroid
2. Hybrid Segmentation: Baseline time-grid boundaries + novelty peak boundaries (union)
3. Beat/Bar Alignment: Snaps to beats (always) and bars (when provided)
4. Context-Aware Labeling: Uses builds, drops, vocals, chords
5. Confidence: Boundary prominence + repetition + energy; edge-safe; variance-aware
6. Edge fixes:
   - Leading/trailing trim for analysis (output re-mapped to original timeline)
   - Pickup/tail-tick boundary suppression (<350ms)
   - Fade-out detection to force a final "outro-ish" boundary

NOTES:
- Keeps output schema compatible with existing callers.
- Adds (non-breaking) fields: energy, repetition, confidence, label_confidence,
  boundary_strength_in/out, vocal_density, harmonic_complexity.
"""

from __future__ import annotations

import logging
from typing import Any, cast

import librosa
import numpy as np

from twinklr.core.audio.structure import (
    descriptors,
    features,
    labeling,
    orchestration,
    segmentation,
)
from twinklr.core.audio.structure.presets import get_preset_or_default

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
    genre: str | None = None,
) -> dict[str, Any]:
    """Detect song sections using hybrid Foote novelty + baseline grid approach.

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length for STFT
        min_section_s: Minimum section duration
        rms_for_energy: Pre-computed RMS energy (optional)
        chroma_cqt: Pre-computed chroma (optional)
        beats_s: Beat times in seconds (optional)
        bars_s: Bar times in seconds (optional)
        builds: Build detections (optional)
        drops: Drop detections (optional)
        vocal_segments: Vocal segments (optional)
        chords: Chord detections (optional)
        genre: Genre hint for preset selection (optional)

    Returns:
        Dictionary with sections, boundary_times_s, and meta information
    """
    detector = SongSectionDetector()
    return detector.detect(
        y,
        sr,
        hop_length=hop_length,
        min_section_s=min_section_s,
        rms_for_energy=rms_for_energy,
        chroma_cqt=chroma_cqt,
        beats_s=beats_s,
        bars_s=bars_s,
        builds=builds,
        drops=drops,
        vocal_segments=vocal_segments,
        chords=chords,
        genre=genre,
    )


def merge_short_sections(times: list[float], min_s: float, duration: float) -> list[float]:
    """Merge sections shorter than min_s while avoiding overly long merges.

    Args:
        times: Boundary times
        min_s: Minimum section duration
        duration: Total audio duration

    Returns:
        Merged boundary times
    """
    return segmentation.merge_short_sections(times, min_s, duration)


# Legacy compatibility for old function name
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
    """Legacy wrapper for label_section_contextual (for backward compatibility).

    Args:
        idx: Section index
        total_sections: Total number of sections
        repeat_count: Repeat count
        max_similarity: Max similarity
        energy_rank: Energy rank
        start_s: Start time
        end_s: End time
        duration: Total duration

    Returns:
        Section label
    """
    # Create minimal sections list with proper structure
    sections = []
    for i in range(total_sections):
        # Create stub sections
        if i == idx:
            sections.append(
                {
                    "start_s": start_s,
                    "end_s": end_s,
                    "repetition": float(repeat_count) / max(total_sections, 1),
                    "repeat_count": repeat_count,
                    "confidence": 0.2
                    if idx == total_sections - 1
                    else 0.5,  # Low confidence for outro
                    "vocal_density": 0.2
                    if idx == total_sections - 1
                    else 0.5,  # Low vocals for outro
                    "energy_rank": energy_rank,
                }
            )
        else:
            # Stub sections
            sections.append(
                {
                    "start_s": float(i) * duration / total_sections,
                    "end_s": float(i + 1) * duration / total_sections,
                    "repetition": 0.3,
                    "repeat_count": 1,
                    "confidence": 0.5,
                    "vocal_density": 0.5,
                    "energy_rank": 0.5,
                }
            )

    relative_pos = start_s / duration if duration > 0 else 0.0

    return labeling.label_section_contextual(
        idx=idx,
        sections=sections,
        chords=[],
        builds=[],
        drops=[],
        vocal_segments=[],
        energy_rank=energy_rank,
        repeat_count=repeat_count,
        max_similarity=max_similarity,
        relative_pos=relative_pos,
        duration=duration,
    )


class SongSectionDetector:
    """Song section detector using hybrid Foote novelty + baseline grid.

    Orchestrates multi-stage detection:
    1. Audio trimming (analysis only)
    2. Beat grid construction
    3. Feature extraction
    4. SSM + novelty computation
    5. Hybrid boundary detection
    6. Section descriptor computation
    7. Context-aware labeling
    """

    def __init__(self, preset=None, *, include_diagnostics: bool = False):
        """Initialize detector.

        Args:
            preset: Optional SectioningPreset override
            include_diagnostics: Include diagnostic data in output
        """
        self.preset = preset
        self.include_diagnostics = include_diagnostics

    def detect(
        self,
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
        genre: str | None = None,
    ) -> dict[str, Any]:
        """Run section detection pipeline.

        Args:
            y: Audio time series
            sr: Sample rate
            hop_length: Hop length
            min_section_s: Minimum section duration
            rms_for_energy: Pre-computed RMS (optional)
            chroma_cqt: Pre-computed chroma (optional)
            beats_s: Beat times (optional)
            bars_s: Bar times (optional)
            builds: Build detections (optional)
            drops: Drop detections (optional)
            vocal_segments: Vocal segments (optional)
            chords: Chord detections (optional)
            genre: Genre hint (optional)

        Returns:
            Detection result dictionary
        """
        duration_orig = float(librosa.get_duration(y=y, sr=sr))

        # Handle very short audio
        if duration_orig < 15.0:
            return self._handle_short_audio(duration_orig, hop_length, min_section_s)

        # Load preset
        preset = self.preset or get_preset_or_default(genre)
        preset_source = "explicit" if self.preset is not None else "genre_lookup"
        builds = builds or []
        drops = drops or []
        vocal_segments = vocal_segments or []
        chords = chords or []

        try:
            # Stage 1: Trim for analysis (map back to original timeline later)
            y_work, start_offset_s, duration_work = self._trim_audio(y, sr, duration_orig)

            # Stage 2: Build beat grid
            beats_work, bars_work, beat_times, tempo_bpm = orchestration.build_beat_grid(
                y_work, sr, hop_length, duration_work, beats_s, bars_s, start_offset_s
            )

            # Stage 3: Extract features
            X_normalized = features.extract_beat_sync_features(
                y=y_work,
                sr=sr,
                hop_length=hop_length,
                beat_frames=[
                    int(librosa.time_to_frames(t, sr=sr, hop_length=hop_length)) for t in beat_times
                ],
                num_beats=len(beat_times),
                chroma_cqt=chroma_cqt if start_offset_s == 0.0 else None,
            )

            # Stage 4: Compute SSM + novelty
            ssm = segmentation.compute_self_similarity_matrix(X_normalized)
            novelty = segmentation.compute_foote_novelty(
                ssm, kernel_size=int(preset.novelty_L_beats)
            )
            prominence = segmentation.compute_boundary_prominence(
                novelty, window_size=int(max(preset.pre_avg, preset.post_avg))
            )

            # Stage 5: Hybrid boundary detection
            boundaries_work = self._detect_boundaries(
                beat_times=beat_times,
                tempo_bpm=tempo_bpm,
                duration_work=duration_work,
                novelty=novelty,
                preset=preset,
                min_section_s=min_section_s,
                bars_work=bars_work,
                rms_for_energy=rms_for_energy,
                y_work=y_work,
                sr=sr,
                hop_length=hop_length,
            )

            # Stage 6: Map back to original timeline and compute descriptors
            boundaries_orig = self._map_to_original_timeline(
                boundaries_work, start_offset_s, duration_orig
            )

            sections = orchestration.compute_section_descriptors(
                X_normalized=X_normalized,
                beat_times=beat_times,
                boundaries_work=boundaries_work,
                boundaries_orig=boundaries_orig,
                prominence=prominence,
                rms_for_energy=rms_for_energy,
                y_work=y_work,
                sr=sr,
                hop_length=hop_length,
                vocal_segments=vocal_segments,
                chords=chords,
            )

            # Stage 7: Label sections
            self._label_sections(
                sections=sections,
                chords=chords,
                builds=builds,
                drops=drops,
                vocal_segments=vocal_segments,
                duration_orig=duration_orig,
            )

            # Build result
            result = self._build_result(
                sections=sections,
                boundaries_orig=boundaries_orig,
                preset=preset,
                preset_source=preset_source,
                tempo_bpm=tempo_bpm,
                num_beats=len(beat_times),
                hop_length=hop_length,
                min_section_s=min_section_s,
                start_offset_s=start_offset_s,
                duration_work=duration_work,
                duration_orig=duration_orig,
            )

            # Optional diagnostics
            if self.include_diagnostics:
                result["diagnostics"] = orchestration.build_diagnostics(
                    tempo_bpm=tempo_bpm,
                    beat_times=beat_times,
                    start_offset_s=start_offset_s,
                    bars_s=bars_s,
                    duration_orig=duration_orig,
                    duration_work=duration_work,
                    novelty=novelty,
                    prominence=prominence,
                    ssm=ssm,
                    X_normalized=X_normalized,
                )

            return result

        except Exception as e:
            logger.warning("Section detection failed: %s", e, exc_info=True)
            return {
                "sections": [],
                "boundary_times_s": [0.0, duration_orig],
                "meta": {"method": "hybrid_foote_v3", "error": str(e), "hop_length": hop_length},
            }

    def _handle_short_audio(
        self, duration_orig: float, hop_length: int, min_section_s: float
    ) -> dict[str, Any]:
        """Handle very short audio (<15s)."""
        return {
            "sections": [
                {
                    "section_id": 0,
                    "start_s": 0.0,
                    "end_s": duration_orig,
                    "duration_s": duration_orig,
                    "label": "full",
                    "similarity": 0.0,
                    "repeat_count": 0,
                    "energy_rank": 0.5,
                    "energy": 0.5,
                    "repetition": 0.5,
                    "confidence": 0.0,
                    "label_confidence": 0.0,
                    "boundary_strength_in": 0.0,
                    "boundary_strength_out": 0.0,
                }
            ],
            "boundary_times_s": [0.0, duration_orig],
            "meta": {
                "method": "hybrid_foote_v3",
                "hop_length": hop_length,
                "min_section_s": min_section_s,
            },
        }

    def _trim_audio(
        self, y: np.ndarray, sr: int, duration_orig: float
    ) -> tuple[np.ndarray, float, float]:
        """Trim audio for analysis (re-map back later)."""
        y_trim, idx = librosa.effects.trim(y, top_db=35)
        trim_start_s = float(idx[0] / sr)
        trim_end_s = float(idx[1] / sr)

        # If trimming is excessive (bad trim), fall back to original
        if (trim_end_s - trim_start_s) > 0.6 * duration_orig:
            y_work = y_trim
            start_offset_s = trim_start_s
            duration_work = float(librosa.get_duration(y=y_work, sr=sr))
        else:
            y_work = y
            start_offset_s = 0.0
            duration_work = duration_orig

        return y_work, start_offset_s, duration_work

    def _build_beat_grid(
        self,
        y_work: np.ndarray,
        sr: int,
        hop_length: int,
        duration_work: float,
        beats_s: list[float] | None,
        bars_s: list[float] | None,
        start_offset_s: float,
    ) -> tuple[list[float] | None, list[float] | None, np.ndarray, float]:
        """Build beat grid (prefer provided beats, estimate otherwise)."""
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
            beat_times = np.linspace(
                0.0, duration_work, num=max(8, int(duration_work * 2.0))
            ).astype(np.float32)

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

    def _detect_boundaries(
        self,
        beat_times: np.ndarray,
        tempo_bpm: float,
        duration_work: float,
        novelty: np.ndarray,
        preset,
        min_section_s: float,
        bars_work: list[float] | None,
        rms_for_energy: np.ndarray | None,
        y_work: np.ndarray,
        sr: int,
        hop_length: int,
    ) -> list[float]:
        """Detect section boundaries via hybrid approach."""
        beat_len_s = float(60.0 / max(tempo_bpm, 1e-9))
        beat_based_min_s = float(preset.min_len_beats) * beat_len_s
        effective_min_section_s = float(max(min_section_s, 1.5 * beat_based_min_s))

        # Novelty peaks
        boundary_beats, _ = segmentation.adaptive_peak_pick(
            novelty=novelty,
            preset=preset,
            min_len_beats=int(preset.min_len_beats),
        )
        novelty_times = [float(beat_times[b]) for b in boundary_beats]

        # Baseline grid
        target_sections = int(
            np.clip(round(duration_work / 12.0), int(preset.min_sections), int(preset.max_sections))
        )
        baseline_times = (
            np.linspace(0.0, duration_work, num=target_sections + 1).astype(np.float32).tolist()
        )

        # Snap to beats
        beat_times_f = beat_times.astype(np.float32)

        def _snap_to_nearest_beat(t: float) -> float:
            if beat_times_f.size == 0:
                return float(t)
            j = int(np.argmin(np.abs(beat_times_f - float(t))))
            return float(beat_times_f[j])

        baseline_times = [float(_snap_to_nearest_beat(t)) for t in baseline_times]

        # Union
        times_work = sorted(set([0.0, float(duration_work)] + novelty_times + baseline_times))

        # Fade detection
        if rms_for_energy is None:
            rms_work = librosa.feature.rms(y=y_work, hop_length=hop_length)[0].astype(np.float32)
        else:
            rms_work = np.asarray(rms_for_energy, dtype=np.float32)

        fade_start_work = segmentation.detect_fade_out_start(
            rms_work, sr=sr, hop_length=hop_length, duration_s=duration_work
        )
        if fade_start_work is not None:
            times_work = sorted(set(times_work + [float(fade_start_work)]))

        # Merge short sections
        cleaned_work = segmentation.merge_short_sections(
            times_work, effective_min_section_s, duration_work
        )

        # Bar alignment
        if bars_work:
            cleaned_work = segmentation.align_boundaries_to_bars(
                cleaned_work, bars_work, tolerance_s=2.0
            )
            cleaned_work = segmentation.merge_short_sections(
                cleaned_work, effective_min_section_s, duration_work
            )

        return cleaned_work

    def _map_to_original_timeline(
        self, boundaries_work: list[float], start_offset_s: float, duration_orig: float
    ) -> list[float]:
        """Map boundaries from work timeline back to original timeline."""
        cleaned = [float(t + start_offset_s) for t in boundaries_work]
        cleaned = [float(np.clip(t, 0.0, duration_orig)) for t in cleaned]
        cleaned = sorted(set([0.0, duration_orig] + cleaned))

        # Suppress micro edge boundaries
        cleaned = segmentation.suppress_micro_edge_boundaries(
            cleaned, pickup_s=0.35, tailtick_s=0.35
        )

        return cleaned

    def _compute_section_descriptors(
        self,
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
        """Compute section descriptors (energy, repetition, confidence)."""
        # Beat-sync RMS
        beat_frames = [
            int(librosa.time_to_frames(t, sr=sr, hop_length=hop_length)) for t in beat_times
        ]
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

            # Boundary strength
            sb = int(np.argmin(np.abs(beat_times - boundaries_work[i])))
            eb = int(np.argmin(np.abs(beat_times - boundaries_work[i + 1])))
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
            energy_rank = (
                float(energy_norm.values_0_1[i]) if i < len(energy_norm.values_0_1) else 0.5
            )
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

    def _label_sections(
        self,
        sections: list[dict[str, Any]],
        chords: list[dict[str, Any]],
        builds: list[dict[str, Any]],
        drops: list[dict[str, Any]],
        vocal_segments: list[dict[str, Any]],
        duration_orig: float,
    ) -> None:
        """Label sections in-place using context-aware heuristics."""
        for i, section in enumerate(sections):
            label = labeling.label_section_contextual(
                idx=i,
                sections=sections,
                chords=chords,
                builds=builds,
                drops=drops,
                vocal_segments=vocal_segments,
                energy_rank=cast(float, section["energy_rank"]),
                repeat_count=cast(int, section["repeat_count"]),
                max_similarity=cast(float, section["similarity"]),
                relative_pos=cast(float, section["start_s"]) / duration_orig
                if duration_orig > 0
                else 0.0,
                duration=duration_orig,
            )
            section["label"] = label

            # Label confidence
            base = labeling.get_label_base_confidence(label)
            seg_conf = float(section.get("confidence", 0.0))
            section["label_confidence"] = float(np.round(base * (0.5 + 0.5 * seg_conf), 3))

    def _build_result(
        self,
        sections: list[dict[str, Any]],
        boundaries_orig: list[float],
        preset,
        preset_source: str,
        tempo_bpm: float,
        num_beats: int,
        hop_length: int,
        min_section_s: float,
        start_offset_s: float,
        duration_work: float,
        duration_orig: float,
    ) -> dict[str, Any]:
        """Build final result dictionary."""
        # Compute derived metrics (placeholder for future enhancement)
        # threshold = descriptors.derive_repeat_threshold(...)
        # rep_strength = np.array([s["repetition"] for s in sections])
        # energy_vals = np.array([s["energy"] for s in sections])
        discrimination = 0.5  # Placeholder

        return {
            "sections": sections,
            "boundary_times_s": [float(x) for x in boundaries_orig],
            "meta": {
                "method": "hybrid_foote_v3",
                "genre": preset.genre,
                "preset_source": preset_source,
                "tempo_bpm": float(tempo_bpm),
                "num_beats": int(num_beats),
                "hop_length": int(hop_length),
                "min_section_s_input": float(min_section_s),
                "min_section_s_effective": float(min_section_s),
                "trim": {
                    "used": bool(start_offset_s > 0.0),
                    "start_offset_s": float(np.round(start_offset_s, 6)),
                    "duration_work_s": float(np.round(duration_work, 6)),
                    "duration_orig_s": float(np.round(duration_orig, 6)),
                },
                "preset": {
                    "min_sections": int(preset.min_sections),
                    "max_sections": int(preset.max_sections),
                    "min_len_beats": int(preset.min_len_beats),
                    "novelty_L_beats": int(preset.novelty_L_beats),
                    "peak_delta": float(preset.peak_delta),
                    "pre_avg": int(preset.pre_avg),
                    "post_avg": int(preset.post_avg),
                },
                "repeat_threshold_derived": 0.9,  # Placeholder
                "discrimination": float(np.round(discrimination, 3)),
            },
        }

    def _build_diagnostics(
        self,
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
        """Build diagnostic information."""
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
