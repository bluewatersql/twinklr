"""Context-aware section labeling.

Uses multiple musical features to assign semantic labels to sections:
- Position in song (intro, outro)
- Energy and repetition patterns (chorus, verse)
- Contextual features (builds, drops, vocals, chords)
"""

from __future__ import annotations

from typing import Any

import numpy as np


def get_label_base_confidence(label: str) -> float:
    """Get base confidence for a given label type.

    Args:
        label: Section label

    Returns:
        Base confidence value (0-1)
    """
    return {
        "intro": 0.85,
        "outro": 0.85,
        "chorus": 0.75,
        "pre_chorus": 0.65,
        "post_chorus": 0.65,
        "bridge": 0.60,
        "break": 0.60,
        "instrumental": 0.55,
        "verse": 0.45,
        "full": 0.40,
    }.get(label, 0.40)


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
    """Assign semantic label to section using contextual features.

    Multi-pass labeling strategy:
    1. Position-based overrides (intro/outro)
    2. Context features (builds, drops, vocals, chords)
    3. Energy + repetition heuristics

    Args:
        idx: Section index
        sections: All sections (for context)
        chords: Chord detections
        builds: Build detections
        drops: Drop detections
        vocal_segments: Vocal segments
        energy_rank: Energy rank (0-1)
        repeat_count: Number of similar sections
        max_similarity: Max similarity to other sections
        relative_pos: Position in song (0-1)
        duration: Total song duration

    Returns:
        Section label string
    """
    section = sections[idx]
    start_s, end_s = float(section["start_s"]), float(section["end_s"])
    section_duration = end_s - start_s
    total_sections = len(sections)

    # Compute repetition rank (prefer continuous signal if available)
    rep_vals = [float(s.get("repetition", np.nan)) for s in sections]
    has_rep = all(np.isfinite(v) for v in rep_vals) and len(rep_vals) > 0

    if has_rep:
        cur_rep = float(section.get("repetition", 0.0))
        repeat_rank = sum(1 for r in rep_vals if r < cur_rep) / max(len(rep_vals), 1)
    else:
        all_repeat_counts = [int(s.get("repeat_count", 0)) for s in sections]
        repeat_rank = sum(1 for r in all_repeat_counts if r < repeat_count) / max(
            len(all_repeat_counts), 1
        )

    # PASS 1: Position-based overrides
    if idx == 0 and total_sections > 3:
        # First section
        if energy_rank < 0.15:
            return "intro"
        if repeat_count <= 1 and energy_rank < 0.30:
            return "intro"

    if idx == total_sections - 1 and total_sections > 3:
        # Last section
        conf = float(section.get("confidence", 0.0))
        vocal = float(section.get("vocal_density", 1.0))
        if vocal < 0.25 and energy_rank < 0.65:
            return "outro"
        if conf < 0.22 and energy_rank < 0.60:
            return "outro"

    # PASS 2: Context features
    has_drop = any(start_s <= float(d["time_s"]) <= end_s for d in drops)

    # Check if preceded by build
    preceded_by_build = False
    if idx > 0:
        prev_section = sections[idx - 1]
        prev_start = float(prev_section["start_s"])
        prev_end = float(prev_section["end_s"])
        preceded_by_build = any(
            float(b["end_s"]) >= prev_start and float(b["end_s"]) <= prev_end for b in builds
        )

    # Compute vocal coverage
    vocal_coverage = float(section.get("vocal_density", 0.0))
    if vocal_segments and (vocal_coverage <= 0.0 or not np.isfinite(vocal_coverage)):
        vocal_time = sum(
            max(0.0, min(float(v["end_s"]), end_s) - max(float(v["start_s"]), start_s))
            for v in vocal_segments
            if float(v["start_s"]) < end_s and float(v["end_s"]) > start_s
        )
        vocal_coverage = vocal_time / max(section_duration, 1e-9)

    # Chord analysis
    section_chords = [c for c in chords if start_s <= float(c["time_s"]) < end_s]
    unique_chords = len({str(c["chord"]) for c in section_chords if str(c["chord"]) != "N"})
    chord_changes = len([c for c in section_chords if str(c["chord"]) != "N"])

    # Pre-chorus detection (build before high-energy section)
    if (
        preceded_by_build
        and energy_rank > 0.6
        and idx < total_sections - 1
        and section_duration >= 5.0
    ):
        next_section = sections[idx + 1]
        next_rep = float(next_section.get("repetition", 0.0))
        next_energy = float(next_section.get("energy_rank", 0.0))
        if next_rep >= float(section.get("repetition", 0.0)) and next_energy > energy_rank:
            return "pre_chorus"

    # Break detection (drop with low vocals + low energy)
    if has_drop and vocal_coverage < 0.3 and energy_rank < 0.4:
        return "break"

    # Chorus detection (high repetition + high energy, multiple criteria)
    if repeat_rank > 0.70 and energy_rank > 0.65:
        return "chorus"
    if repeat_rank > 0.65 and energy_rank > 0.75:
        return "chorus"
    if repeat_rank > 0.35 and energy_rank > 0.88:
        return "chorus"
    if repeat_rank > 0.70 and has_drop:
        return "chorus"
    if repeat_rank > 0.65 and max_similarity > 0.95 and energy_rank > 0.50:
        return "chorus"
    if repeat_rank > 0.60 and vocal_coverage > 0.7 and energy_rank > 0.65:
        return "chorus"

    # Bridge detection (late in song, low repetition, unique harmony)
    if relative_pos > 0.55 and repeat_rank < 0.30 and max_similarity < 0.75:
        return "bridge"
    if (
        repeat_rank < 0.20
        and relative_pos > 0.45
        and chord_changes > 0
        and unique_chords > chord_changes * 0.6
    ):
        return "bridge"

    # Instrumental detection (low vocals, moderate energy)
    if vocal_coverage < 0.2 and 0.4 < energy_rank < 0.8 and relative_pos > 0.2:
        return "instrumental"

    # Default: verse
    return "verse"
