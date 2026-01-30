"""Lighting hints generation from audio features."""

from __future__ import annotations

from typing import Any

import numpy as np


def build_lighting_hints(song_features: dict[str, Any]) -> dict[str, Any]:
    """Generate actionable lighting hints from audio features.

    Args:
        song_features: Full audio analysis from process_song

    Returns:
        Dict with lighting recommendations based on audio characteristics
    """
    tempo_bpm = song_features.get("tempo_bpm", 120)

    # Use tempo analysis if available
    tempo_analysis = song_features.get("tempo_analysis", {})
    is_tempo_stable = tempo_analysis.get("is_stable", True)
    avg_tempo = tempo_analysis.get("average_tempo_bpm", tempo_bpm)

    # Movement speed based on tempo
    if avg_tempo < 80:
        movement_speed = "slow"
    elif avg_tempo < 120:
        movement_speed = "medium"
    elif avg_tempo < 150:
        movement_speed = "fast"
    else:
        movement_speed = "very_fast"

    # Energy analysis
    energy = song_features.get("energy", {})
    energy_vals = energy.get("phrase_level", energy.get("rms_norm", []))
    avg_energy = np.mean(energy_vals) if energy_vals else 0.5
    energy_variance = np.std(energy_vals) if energy_vals else 0.1

    # Spectral analysis
    spectral = song_features.get("spectral", {})
    spectral_stats = spectral.get("statistics", {})
    brightness_variance = spectral_stats.get("brightness_variance", 0)

    # Use hpss_perc_ratio from timeline
    timeline = song_features.get("extensions", {}).get("timeline", {})
    perc_ratio_vals = timeline.get("hpss_perc_ratio", [])
    percussiveness = float(np.mean(perc_ratio_vals)) if perc_ratio_vals else 0.5

    # Dynamic range
    dynamics = song_features.get("dynamics", {})
    dynamics_stats = dynamics.get("statistics", {})
    dynamic_range = dynamics_stats.get("dynamic_range", 0.5)
    transient_density = dynamics_stats.get("transient_density", 1.0)

    # Structure
    structure = song_features.get("structure", {})
    sections = structure.get("sections", [])
    num_sections = len(sections)

    # Section type breakdown
    section_labels = [s.get("label", "unknown") for s in sections]
    has_chorus = "chorus" in section_labels
    has_verse = "verse" in section_labels
    has_bridge = "bridge" in section_labels

    # Musical key
    key_info = song_features.get("key", {})
    key = key_info.get("key", "C")
    mode = key_info.get("mode", "major")

    # Pitch & vocal info
    pitch_info = song_features.get("pitch", {})
    pitch_stats = pitch_info.get("statistics", {})
    pitch_range = pitch_stats.get("pitch_std", 0.0)
    voiced_proportion = pitch_stats.get("voiced_proportion", 0.0)

    vocal_info = song_features.get("vocals", {})
    vocal_coverage = vocal_info.get("statistics", {}).get("vocal_coverage_pct", 0.0)

    # Chord & tension info
    chord_info = song_features.get("chords", {})
    chord_stats = chord_info.get("statistics", {})
    major_pct = chord_stats.get("major_pct", 0.5)

    tension_info = song_features.get("tension", {})
    tension_stats = tension_info.get("statistics", {})
    avg_tension = tension_stats.get("avg_tension", 0.5)

    # Builds & drops
    builds_drops = song_features.get("builds_drops", {})
    build_count = builds_drops.get("statistics", {}).get("build_count", 0)
    drop_count = builds_drops.get("statistics", {}).get("drop_count", 0)

    return {
        "movement_speed": movement_speed,
        "tempo_category": f"{avg_tempo:.0f} BPM ({movement_speed})",
        "tempo_stability": "stable" if is_tempo_stable else "variable",
        "energy_profile": {
            "average": float(avg_energy),
            "variance": float(energy_variance),
            "recommendation": ("high_contrast" if energy_variance > 0.2 else "smooth_transitions"),
        },
        "complexity_hints": {
            "spectral_complexity": (
                "high"
                if brightness_variance > 1000
                else "medium"
                if brightness_variance > 500
                else "low"
            ),
            "percussive_content": (
                "high" if percussiveness > 0.1 else "medium" if percussiveness > 0.05 else "low"
            ),
            "suggested_pattern_complexity": (
                "complex" if brightness_variance > 800 else "moderate"
            ),
        },
        "dynamic_hints": {
            "dynamic_range": "wide" if dynamic_range > 0.3 else "narrow",
            "transient_density": float(transient_density),
            "use_bumps": transient_density > 1.5,
            "suggested_dimmer_behavior": ("pulse_beat" if percussiveness > 0.1 else "swell_bars"),
        },
        "structure_hints": {
            "num_sections": num_sections,
            "has_chorus": has_chorus,
            "has_verse": has_verse,
            "has_bridge": has_bridge,
            "recommend_section_changes": num_sections >= 5,
            "variation_level": (
                "high" if num_sections >= 7 else "medium" if num_sections >= 5 else "low"
            ),
        },
        "musical_context": {
            "key": key,
            "mode": mode,
            "tonal_character": f"{key} {mode}",
            "suggested_color_palette": "warm" if mode == "major" else "cool",
        },
        "vocal_hints": {
            "has_vocals": vocal_coverage > 20.0,
            "vocal_coverage_pct": vocal_coverage,
            "pitch_range_hz": pitch_range,
            "voiced_proportion": voiced_proportion,
            "recommendation": (
                "spotlight_on_vocals" if vocal_coverage > 50.0 else "mixed_treatment"
            ),
        },
        "harmonic_hints": {
            "chord_changes": chord_stats.get("chord_change_count", 0),
            "tonality": "bright" if major_pct > 0.6 else "dark" if major_pct < 0.4 else "mixed",
            "major_pct": major_pct,
            "recommendation": (
                "match_chord_changes"
                if chord_stats.get("chord_change_count", 0) > 20
                else "stable_colors"
            ),
        },
        "build_drop_hints": {
            "has_builds": build_count > 0,
            "has_drops": drop_count > 0,
            "build_count": build_count,
            "drop_count": drop_count,
            "recommendation": (
                "anticipatory_builds_explosive_drops"
                if build_count > 0 and drop_count > 0
                else "standard_dynamics"
            ),
        },
        "tension_hints": {
            "avg_tension": avg_tension,
            "tension_variance": tension_stats.get("tension_variance", 0.0),
            "peak_count": tension_stats.get("peak_count", 0),
            "recommendation": (
                "follow_tension_curve"
                if tension_stats.get("tension_variance", 0.0) > 0.1
                else "steady_intensity"
            ),
        },
    }


__all__ = ["build_lighting_hints"]
