"""Context-aware build and drop detection.

Uses song energy profiling to adapt detection parameters based on
genre and energy characteristics. Works across holiday ballads to EDM.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

try:
    from scipy.ndimage import gaussian_filter1d

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from twinklr.core.audio.energy.profiling import classify_song_energy_profile

logger = logging.getLogger(__name__)


def detect_builds_and_drops(
    energy_curve: np.ndarray,
    times_s: np.ndarray,
    onset_env: np.ndarray,
    beats_s: list[float],
    tempo_bpm: float,
) -> dict[str, Any]:
    """Detect energy ramps (builds) and sudden changes (drops) with context awareness.

    Uses song profiling to adapt parameters based on genre and energy characteristics.
    Works across genres from holiday ballads to high-energy EDM.

    Args:
        energy_curve: Normalized energy curve
        times_s: Time points in seconds
        onset_env: Onset envelope
        beats_s: Beat positions in seconds
        tempo_bpm: Estimated tempo

    Returns:
        Dictionary with builds, drops, pre-drops, statistics, and profile info
    """
    if len(energy_curve) < 50:
        return {
            "builds": [],
            "drops": [],
            "pre_drops": [],
            "statistics": {},
            "profile": {"profile": "unknown", "parameters": {}, "statistics": {}},
        }

    # Classify song energy profile for adaptive detection
    duration_s = float(times_s[-1] - times_s[0]) if len(times_s) > 0 else 0.0
    profile_info = classify_song_energy_profile(
        energy_curve=energy_curve,
        tempo_bpm=tempo_bpm,
        onset_env=onset_env,
        duration_s=duration_s,
    )
    params = profile_info["parameters"]

    logger.debug(
        f"Using profile '{profile_info['profile']}': "
        f"min_build_bars={params['min_build_bars']}, "
        f"gradient_percentile={params['gradient_percentile']}, "
        f"min_energy_gain={params['min_energy_gain']}"
    )

    # Smooth energy for trend detection
    window = int(len(energy_curve) / 100)
    window = max(5, min(window, 50))

    if HAS_SCIPY:
        energy_smooth = gaussian_filter1d(energy_curve, sigma=window / 3)
    else:
        energy_smooth = np.convolve(energy_curve, np.ones(window) / window, mode="same")

    # Compute gradient (change per frame)
    gradient = np.gradient(energy_smooth)

    # Build detection: Use window-based approach for gentle music
    # Traditional continuous gradient fails on subtle energy changes
    bar_duration_s = 60.0 / tempo_bpm * 4  # 4 beats per bar
    min_build_bars = params["min_build_bars"]  # Adaptive based on profile

    builds = _detect_builds_windowed(
        energy_smooth=energy_smooth,
        times_s=times_s,
        bar_duration_s=bar_duration_s,
        min_build_bars=min_build_bars,
        min_energy_gain=params["min_energy_gain"],
        gradient=gradient,
    )

    # Drop detection: both build-associated and independent
    drops = []
    pre_drops = []  # "Pre-drop" moments (silence before drop)

    # Adaptive drop threshold
    drop_gradient_percentile = params["drop_gradient_percentile"]
    drop_threshold = (
        np.percentile(gradient[gradient < 0], drop_gradient_percentile)
        if np.any(gradient < 0)
        else -0.001
    )

    logger.debug(f"Drop detection: threshold={drop_threshold:.5f}")

    # 1. Detect drops after builds (traditional EDM-style)
    for build in builds:
        # Look for drop within 2 bars after build ends
        search_window_s = bar_duration_s * 2
        end_idx = int(np.searchsorted(times_s, build["end_s"]))
        search_end_idx = int(np.searchsorted(times_s, build["end_s"] + search_window_s))
        search_end_idx = min(search_end_idx, len(gradient) - 1)

        # Find steepest negative gradient
        if end_idx < search_end_idx:
            window_grad = gradient[end_idx:search_end_idx]
            if len(window_grad) > 0:
                min_grad_rel_idx = np.argmin(window_grad)
                min_grad = window_grad[min_grad_rel_idx]

                if min_grad < drop_threshold:
                    drop_idx = int(end_idx + min_grad_rel_idx)
                    drop_time = float(times_s[drop_idx])

                    # Check for pre-drop (low energy just before drop)
                    pre_drop_window = 10  # frames
                    pre_drop_start = int(max(0, drop_idx - pre_drop_window))
                    pre_drop_energy = float(np.mean(energy_smooth[pre_drop_start:drop_idx]))

                    if pre_drop_energy < energy_smooth[drop_idx] - 0.2:
                        # Silence before drop
                        pre_drops.append(
                            {
                                "time_s": float(times_s[pre_drop_start]),
                                "duration_s": float(times_s[drop_idx] - times_s[pre_drop_start]),
                                "energy_dip": round(
                                    float(energy_smooth[drop_idx] - pre_drop_energy), 3
                                ),
                            }
                        )

                    drops.append(
                        {
                            "time_s": drop_time,
                            "energy_before": round(float(energy_smooth[drop_idx - 1]), 3),
                            "energy_after": round(
                                float(energy_smooth[min(drop_idx + 5, len(energy_smooth) - 1)]),
                                3,
                            ),
                            "gradient": round(float(min_grad), 5),
                            "associated_build": build,
                            "has_pre_drop": (
                                len(pre_drops) > 0
                                and abs(pre_drops[-1]["time_s"] - drop_time) < 2.0
                            ),
                            "type": "build_associated",
                        }
                    )

    # 2. Detect independent drops (not associated with builds)
    # This catches sudden energy changes in songs without traditional builds
    if params["detect_drops_independent"]:
        independent_drops = _detect_independent_drops(
            energy_smooth=energy_smooth,
            gradient=gradient,
            times_s=times_s,
            drop_threshold=drop_threshold,
            existing_drops=drops,
            bar_duration_s=bar_duration_s,
        )
        drops.extend(independent_drops)

        logger.debug(
            f"Found {len(builds)} builds, {len(drops)} drops ({len(independent_drops)} independent)"
        )

    return {
        "builds": builds,
        "drops": drops,
        "pre_drops": pre_drops,
        "profile": profile_info,
        "statistics": {
            "build_count": len(builds),
            "drop_count": len(drops),
            "pre_drop_count": len(pre_drops),
            "independent_drop_count": sum(1 for d in drops if d.get("type") == "independent"),
            "avg_build_duration_s": (
                float(np.mean([b["duration_s"] for b in builds])) if builds else 0.0
            ),
            "avg_energy_gain": (
                float(np.mean([b["energy_gain"] for b in builds])) if builds else 0.0
            ),
        },
    }


def _detect_builds_windowed(
    energy_smooth: np.ndarray,
    times_s: np.ndarray,
    bar_duration_s: float,
    min_build_bars: int,
    min_energy_gain: float,
    gradient: np.ndarray,
) -> list[dict]:
    """Detect builds using sliding window approach.

    Instead of requiring continuous positive gradient, looks at net
    energy gain over windows. Works better for gentle/subtle builds.

    Args:
        energy_smooth: Smoothed energy curve
        times_s: Time array
        bar_duration_s: Duration of one bar
        min_build_bars: Minimum bars for build
        min_energy_gain: Minimum energy increase required
        gradient: Energy gradient (for metadata)

    Returns:
        List of build dictionaries
    """
    builds: list[dict[str, Any]] = []
    duration_s = float(times_s[-1] - times_s[0])
    n_frames = len(energy_smooth)

    # Window size for build detection
    window_duration_s = bar_duration_s * min_build_bars
    window_frames = int(window_duration_s * n_frames / duration_s)

    # Slide window with 50% overlap
    step_frames = max(1, window_frames // 2)

    for start_idx in range(0, n_frames - window_frames, step_frames):
        end_idx = start_idx + window_frames

        # Check energy gain over this window
        energy_start = float(energy_smooth[start_idx])
        energy_end = float(energy_smooth[end_idx])
        energy_gain = energy_end - energy_start

        # Calculate trend: use linear regression slope
        window_energy = energy_smooth[start_idx:end_idx]
        x = np.arange(len(window_energy))
        slope = np.polyfit(x, window_energy, 1)[0] if len(window_energy) > 1 else 0

        # Build criteria:
        # 1. Net energy gain meets threshold
        # 2. Positive overall slope (trend is upward)
        # 3. Energy at end > energy at start (monotonic overall)
        if energy_gain >= min_energy_gain and slope > 0:
            start_time = float(times_s[start_idx])
            end_time = float(times_s[end_idx])

            # Check if this overlaps with existing builds (avoid duplicates)
            overlaps = any(
                (b["start_s"] <= start_time <= b["end_s"])
                or (b["start_s"] <= end_time <= b["end_s"])
                or (start_time <= b["start_s"] and end_time >= b["end_s"])
                for b in builds
            )

            if not overlaps:
                builds.append(
                    {
                        "start_s": start_time,
                        "end_s": end_time,
                        "duration_s": end_time - start_time,
                        "energy_start": round(energy_start, 3),
                        "energy_end": round(energy_end, 3),
                        "energy_gain": round(energy_gain, 3),
                        "slope": round(float(slope), 6),
                        "avg_gradient": round(float(np.mean(gradient[start_idx:end_idx])), 5),
                    }
                )

    # Sort by energy gain and keep most significant
    builds.sort(key=lambda b: b["energy_gain"], reverse=True)

    # Merge overlapping/adjacent builds
    merged_builds: list[dict[str, Any]] = []
    for build in builds:
        if not merged_builds:
            merged_builds.append(build)
            continue

        # Check if this build is adjacent to or overlaps with last merged build
        last = merged_builds[-1]
        gap = build["start_s"] - last["end_s"]

        if gap < bar_duration_s:  # Within 1 bar
            # Extend the existing build
            last["end_s"] = max(last["end_s"], build["end_s"])
            last["duration_s"] = last["end_s"] - last["start_s"]
            last["energy_end"] = max(last["energy_end"], build["energy_end"])
            last["energy_gain"] = last["energy_end"] - last["energy_start"]
        else:
            merged_builds.append(build)

    logger.debug(f"Window-based detection found {len(merged_builds)} builds")
    return merged_builds


def _detect_independent_drops(
    energy_smooth: np.ndarray,
    gradient: np.ndarray,
    times_s: np.ndarray,
    drop_threshold: float,
    existing_drops: list[dict],
    bar_duration_s: float,
) -> list[dict]:
    """Detect drops that aren't associated with builds.

    These are sudden energy decreases that occur independently,
    common in holiday music, ballads, and dynamic arrangements.

    Args:
        energy_smooth: Smoothed energy curve
        gradient: Energy gradient
        times_s: Time array
        drop_threshold: Gradient threshold for drops
        existing_drops: Already detected drops (to avoid duplicates)
        bar_duration_s: Duration of one bar in seconds

    Returns:
        List of independent drop dictionaries
    """
    independent_drops: list[dict[str, Any]] = []
    existing_drop_times = {d["time_s"] for d in existing_drops}

    # Find all steep negative gradients
    drop_candidates = np.where(gradient < drop_threshold)[0]

    if len(drop_candidates) == 0:
        return independent_drops

    # Group nearby candidates (within 1 bar)
    min_separation_frames = int(bar_duration_s * len(times_s) / times_s[-1])

    i = 0
    while i < len(drop_candidates):
        drop_idx = drop_candidates[i]
        drop_time = float(times_s[drop_idx])

        # Skip if too close to an existing drop
        if any(abs(drop_time - t) < bar_duration_s for t in existing_drop_times):
            i += 1
            continue

        # Check if this is a significant energy decrease
        energy_before = float(energy_smooth[max(0, drop_idx - 5)])
        energy_after = float(energy_smooth[min(drop_idx + 5, len(energy_smooth) - 1)])
        energy_decrease = energy_before - energy_after

        # Require meaningful energy decrease (relative to song dynamics)
        if energy_decrease > 0.08:  # At least 8% energy drop
            independent_drops.append(
                {
                    "time_s": drop_time,
                    "energy_before": round(energy_before, 3),
                    "energy_after": round(energy_after, 3),
                    "energy_decrease": round(energy_decrease, 3),
                    "gradient": round(float(gradient[drop_idx]), 5),
                    "type": "independent",
                    "associated_build": None,
                    "has_pre_drop": False,
                }
            )
            existing_drop_times.add(drop_time)

            # Skip nearby frames
            i += min_separation_frames
        else:
            i += 1

    return independent_drops
