"""Song energy profiling for context-aware feature detection.

Classifies songs by energy characteristics to enable adaptive detection
of builds, drops, and other dynamic features.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def classify_song_energy_profile(
    energy_curve: np.ndarray,
    tempo_bpm: float,
    onset_env: np.ndarray,
    duration_s: float,
) -> dict[str, Any]:
    """Classify song's overall energy characteristics for adaptive detection.

    This enables context-aware detection of builds/drops that works across
    genres from holiday ballads to high-energy EDM.

    Args:
        energy_curve: Normalized RMS energy curve (0-1)
        tempo_bpm: Song tempo in BPM
        onset_env: Onset strength envelope
        duration_s: Song duration in seconds

    Returns:
        Dictionary with profile classification and adaptive parameters
    """
    # Energy statistics
    energy_mean = float(np.mean(energy_curve))
    energy_std = float(np.std(energy_curve))
    energy_range = float(np.ptp(energy_curve))  # peak-to-peak
    energy_cv = energy_std / (energy_mean + 1e-9)  # coefficient of variation
    energy_median = float(np.median(energy_curve))

    # Dynamic variation (how much energy changes)
    gradient = np.gradient(energy_curve)
    gradient_std = float(np.std(gradient))
    gradient_mean_abs = float(np.mean(np.abs(gradient)))

    # Onset density (transient activity)
    onset_density = float(np.sum(onset_env > np.percentile(onset_env, 80)) / len(onset_env))

    # Classify energy profile based on characteristics
    profile_name = _classify_profile(
        energy_mean=energy_mean,
        energy_cv=energy_cv,
        gradient_std=gradient_std,
        tempo_bpm=tempo_bpm,
        onset_density=onset_density,
    )

    # Get adaptive parameters for this profile
    params = _get_profile_parameters(profile_name, energy_cv, gradient_std)

    logger.debug(
        f"Song profile: {profile_name} "
        f"(energy_mean={energy_mean:.2f}, cv={energy_cv:.2f}, tempo={tempo_bpm:.0f})"
    )

    return {
        "profile": profile_name,
        "parameters": params,
        "statistics": {
            "energy_mean": round(energy_mean, 3),
            "energy_std": round(energy_std, 3),
            "energy_median": round(energy_median, 3),
            "energy_range": round(energy_range, 3),
            "energy_cv": round(energy_cv, 3),
            "gradient_std": round(gradient_std, 5),
            "gradient_mean_abs": round(gradient_mean_abs, 5),
            "onset_density": round(onset_density, 3),
            "tempo_bpm": round(tempo_bpm, 1),
        },
    }


def _classify_profile(
    energy_mean: float,
    energy_cv: float,
    gradient_std: float,
    tempo_bpm: float,
    onset_density: float,
) -> str:
    """Classify song into energy profile category.

    Args:
        energy_mean: Mean normalized energy (0-1)
        energy_cv: Coefficient of variation (std/mean)
        gradient_std: Standard deviation of energy gradient
        tempo_bpm: Tempo in BPM
        onset_density: Proportion of strong onsets

    Returns:
        Profile name string
    """
    # High energy, high dynamics (EDM, rock, dance)
    if energy_mean > 0.65 and gradient_std > 0.008:
        return "high_energy"

    # Low energy, stable (ballads, ambient, gentle holiday)
    if energy_mean < 0.4 and energy_cv < 0.35:
        return "low_energy_stable"

    # Slow tempo, gentle (holiday, lullabies, soft jazz)
    if tempo_bpm < 100 and energy_mean < 0.5:
        return "slow_gentle"

    # High dynamics, varying energy (classical, cinematic, prog rock)
    if energy_cv > 0.5 or gradient_std > 0.01:
        return "highly_dynamic"

    # Medium-low energy, moderate dynamics (folk, acoustic, some holiday)
    if energy_mean < 0.5 and energy_cv < 0.5:
        return "moderate_low"

    # Everything else (pop, country, most mainstream)
    return "moderate"


def _get_profile_parameters(profile: str, energy_cv: float, gradient_std: float) -> dict[str, Any]:
    """Get adaptive detection parameters for a given profile.

    Args:
        profile: Profile name
        energy_cv: Coefficient of variation (for fine-tuning)
        gradient_std: Gradient standard deviation (for fine-tuning)

    Returns:
        Dictionary of detection parameters
    """
    # Base parameters for each profile
    base_params = {
        "high_energy": {
            "min_build_bars": 4,
            "gradient_percentile": 60,
            "min_energy_gain": 0.15,
            "detect_drops_independent": True,
            "drop_gradient_percentile": 10,
        },
        "low_energy_stable": {
            "min_build_bars": 2,
            "gradient_percentile": 35,  # Very sensitive
            "min_energy_gain": 0.05,  # Small changes matter
            "detect_drops_independent": True,
            "drop_gradient_percentile": 20,
        },
        "slow_gentle": {
            "min_build_bars": 2,
            "gradient_percentile": 30,  # Very sensitive
            "min_energy_gain": 0.04,  # Tiny changes matter
            "detect_drops_independent": True,
            "drop_gradient_percentile": 25,
        },
        "highly_dynamic": {
            "min_build_bars": 3,
            "gradient_percentile": 50,
            "min_energy_gain": 0.12,
            "detect_drops_independent": True,
            "drop_gradient_percentile": 15,
        },
        "moderate_low": {
            "min_build_bars": 2,
            "gradient_percentile": 40,
            "min_energy_gain": 0.07,
            "detect_drops_independent": True,
            "drop_gradient_percentile": 20,
        },
        "moderate": {
            "min_build_bars": 3,
            "gradient_percentile": 50,
            "min_energy_gain": 0.10,
            "detect_drops_independent": True,
            "drop_gradient_percentile": 15,
        },
    }

    params = base_params.get(profile, base_params["moderate"]).copy()

    # Fine-tune based on actual characteristics
    # If song is particularly stable, be more sensitive
    if energy_cv < 0.25:
        params["gradient_percentile"] = max(25, params["gradient_percentile"] - 10)
        params["min_energy_gain"] *= 0.7

    # If song has very little gradient variation, be more lenient
    if gradient_std < 0.003:
        params["min_energy_gain"] *= 0.6

    return params
