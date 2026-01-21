"""Unified song map builder combining audio and sequence features."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def _extract_peaks(
    times: list[float] | np.ndarray,
    values: list[float] | np.ndarray,
    n_peaks: int = 8,
    min_sep_s: float = 5.0,
) -> list[dict[str, float]]:
    """Extract peaks from a time series.

    Args:
        times: Time array in seconds
        values: Value array
        n_peaks: Maximum number of peaks to extract
        min_sep_s: Minimum separation between peaks in seconds

    Returns:
        List of peak dicts with 't_s' and 'v' keys
    """
    if len(times) == 0 or len(values) == 0:
        return []

    times_arr = np.array(times)
    values_arr = np.array(values)

    # Find local maxima using scipy.signal.find_peaks approach
    # Simple implementation: find points where value is greater than neighbors
    peaks = []
    for i in range(1, len(values_arr) - 1):
        if values_arr[i] > values_arr[i - 1] and values_arr[i] > values_arr[i + 1]:
            peaks.append({"t_s": float(times_arr[i]), "v": float(values_arr[i])})

    # Sort by value (descending) and filter by minimum separation
    peaks.sort(key=lambda p: p["v"], reverse=True)

    filtered_peaks: list[dict[str, float]] = []
    for peak in peaks:
        # Check minimum separation from already selected peaks
        if all(abs(peak["t_s"] - p["t_s"]) >= min_sep_s for p in filtered_peaks):
            filtered_peaks.append(peak)
            if len(filtered_peaks) >= n_peaks:
                break

    # Sort by time
    filtered_peaks.sort(key=lambda p: p["t_s"])

    return filtered_peaks


def _find_section_for_time(sections: list[dict[str, Any]], time_s: float) -> dict[str, Any] | None:
    """Find which section contains a given time point.

    Args:
        sections: List of section dicts with start_s/end_s
        time_s: Time point in seconds

    Returns:
        Section dict or None if not found
    """
    for section in sections:
        if section["start_s"] <= time_s < section["end_s"]:
            return section
    return None


def _sample_timeline_at_time(timeline: dict[str, Any], time_s: float) -> dict[str, float]:
    """Sample all timeline features at a specific time point using linear interpolation.

    Args:
        timeline: Timeline dict with t_sec and feature arrays
        time_s: Time point in seconds

    Returns:
        Dict of feature values at time_s
    """
    t_sec = timeline.get("t_sec", [])
    if not t_sec:
        return {}

    # Find surrounding indices
    t_arr = np.array(t_sec)
    idx = np.searchsorted(t_arr, time_s)

    # Handle edge cases
    idx_int = int(idx)
    if idx_int == 0:
        idx = np.int64(0)
        alpha = 0.0
    elif idx_int >= len(t_arr):
        idx = np.int64(len(t_arr) - 1)
        alpha = 0.0
    else:
        # Linear interpolation
        t0, t1 = t_arr[idx - 1], t_arr[idx]
        alpha = (time_s - t0) / (t1 - t0) if t1 > t0 else 0.0

    # Sample all numeric features
    state = {}
    for key in [
        "energy",
        "loudness",
        "onset",
        "brightness",
        "flatness",
        "motion",
        "tonal_novelty",
        "hpss_perc_ratio",
    ]:
        values = timeline.get(key, [])
        if values and idx < len(values):
            if alpha > 0 and idx > 0:
                v0, v1 = values[idx - 1], values[idx]
                state[key] = float(v0 + alpha * (v1 - v0))
            else:
                state[key] = float(values[idx])

    return state


def _filter_meaningful_timing_events(
    timing_track_events: dict[str, list[dict[str, Any]]], max_events_per_track: int = 20
) -> list[dict[str, Any]]:
    """Filter timing track events to most meaningful ones.

    Args:
        timing_track_events: Dict mapping track names to event lists
        max_events_per_track: Maximum events to keep per track

    Returns:
        Flattened list of meaningful timing events
    """
    meaningful_events = []

    for track_name, events in timing_track_events.items():
        # Filter to tracks with meaningful names
        if any(
            keyword in track_name.lower()
            for keyword in ["beat", "phrase", "section", "bar", "measure", "drop", "build"]
        ):
            # Limit events
            for event in events[:max_events_per_track]:
                event["track_name"] = track_name
                meaningful_events.append(event)

    return meaningful_events


def build_unified_song_map(
    song_features: dict[str, Any],
    seq_fingerprint: dict[str, Any] | None = None,
    *,
    resolution: str = "downbeat",
    max_events: int = 100,
) -> dict[str, Any]:
    """Build unified song map combining audio features and sequence timing.

    Hybrid approach:
    - Section summaries for strategic planning
    - Event snapshots at musically significant moments
    - Arc analysis for key moments
    - Integration with sequence timing events

    Args:
        song_features: Full audio analysis from process_song
        seq_fingerprint: Optional sequence fingerprint with timing tracks
        resolution: "beat", "downbeat", or "bar" - temporal resolution for events
        max_events: Maximum events to include (smart sampling applied)

    Returns:
        Unified song map with sections, events, arc, and sequence timing
    """
    duration_s = float(song_features.get("duration_s", 0))
    tempo_bpm = float(song_features.get("tempo_bpm", 0))

    # Get core musical structure
    sections = song_features.get("structure", {}).get("sections", [])
    beats_s = song_features.get("beats_s", [])
    bars_s = song_features.get("bars_s", [])
    # Downbeat times are now in bars_s directly (schema v2.3+)
    downbeats_s = bars_s

    # Get timeline for feature sampling
    timeline = song_features.get("extensions", {}).get("timeline", {})
    composites = song_features.get("extensions", {}).get("composites", {})
    show_intensity = composites.get("show_intensity", [])
    t_sec = timeline.get("t_sec", [])

    # Build section summaries
    section_summaries = []
    for section in sections:
        start_s = float(section.get("start_s", 0))
        end_s = float(section.get("end_s", 0))

        # Find bars in this section
        section_bars = [i + 1 for i, b in enumerate(bars_s) if start_s <= b < end_s]

        # Sample audio features for this section
        section_indices = [i for i, t in enumerate(t_sec) if start_s <= t < end_s] if t_sec else []

        audio_summary = {}
        if section_indices:
            for key in ["energy", "brightness", "hpss_perc_ratio", "motion", "tonal_novelty"]:
                values = timeline.get(key, [])
                if values:
                    section_vals = [values[i] for i in section_indices if i < len(values)]
                    if section_vals:
                        arr = np.array(section_vals)
                        audio_summary[key] = {
                            "mean": float(np.mean(arr)),
                            "min": float(np.min(arr)),
                            "max": float(np.max(arr)),
                        }

            # Show intensity for section
            if show_intensity:
                section_intensity = [
                    show_intensity[i] for i in section_indices if i < len(show_intensity)
                ]
                if section_intensity:
                    intensity_arr = np.array(section_intensity)
                    audio_summary["show_intensity"] = {
                        "mean": float(np.mean(intensity_arr)),
                        "peak": float(np.max(intensity_arr)),
                    }

        section_summaries.append(
            {
                "id": section.get("section_id", 0),
                "label": section.get("label", "unknown"),
                "time_range": [start_s, end_s],
                "duration_s": float(end_s - start_s),
                "bars": section_bars,
                "bar_range": [section_bars[0], section_bars[-1]] if section_bars else [0, 0],
                "energy_rank": section.get("energy_rank", 0.5),
                "audio_summary": audio_summary,
            }
        )

    # Build events at musically significant moments
    events = []

    # Choose time points based on resolution
    if resolution == "beat":
        time_points = beats_s
    elif resolution == "bar":
        time_points = bars_s
    else:  # downbeat
        time_points = downbeats_s if downbeats_s else bars_s

    # Sample time points intelligently if needed
    if len(time_points) > max_events:
        # Smart sampling: always include first, last, section boundaries, and evenly spaced
        sampled = {time_points[0], time_points[-1]}

        # Add section boundaries
        for section in sections:
            start = section.get("start_s", 0)
            # Find closest time point to section start
            closest = min(time_points, key=lambda t: abs(t - start))
            sampled.add(closest)

        # Add evenly spaced points
        step = len(time_points) / (max_events - len(sampled))
        for i in range(max_events - len(sampled)):
            idx = int(i * step)
            if idx < len(time_points):
                sampled.add(time_points[idx])

        time_points = sorted(sampled)
        logger.debug(f"Sampled {len(time_points)} events from {len(downbeats_s or bars_s)}")

    # Build event snapshots
    for time_s in time_points:
        # Find beat/bar number
        beat_num = next((i + 1 for i, b in enumerate(beats_s) if abs(b - time_s) < 0.05), None)
        bar_num = next((i + 1 for i, b in enumerate(bars_s) if abs(b - time_s) < 0.05), None)

        # Find section
        section = _find_section_for_time(sections, time_s)

        # Sample timeline features at this time
        audio_state = _sample_timeline_at_time(timeline, time_s)

        # Add show_intensity
        if show_intensity and t_sec:
            idx = np.searchsorted(t_sec, time_s)
            if 0 <= idx < len(show_intensity):
                audio_state["show_intensity"] = float(show_intensity[idx])

        event = {
            "t_s": float(time_s),
            "beat": beat_num,
            "bar": bar_num,
            "section": {
                "id": section.get("section_id", 0) if section else 0,
                "label": section.get("label", "unknown") if section else "unknown",
                "energy_rank": section.get("energy_rank", 0.5) if section else 0.5,
            }
            if section
            else None,
            "state": audio_state,
        }

        events.append(event)

    # Build arc analysis - identify key moments
    arc: dict[str, Any] = {
        "energy_peaks": [],
        "tonal_shifts": [],
        "section_transitions": [],
    }

    # Energy peaks
    if show_intensity and t_sec:
        intensity_peaks = _extract_peaks(t_sec, show_intensity, n_peaks=8, min_sep_s=5.0)
        for peak in intensity_peaks:
            section = _find_section_for_time(sections, peak["t_s"])
            arc["energy_peaks"].append(
                {
                    "t_s": peak["t_s"],
                    "intensity": peak["v"],
                    "section_id": section.get("section_id", 0) if section else 0,
                }
            )

    # Tonal shifts
    tonal_novelty = timeline.get("tonal_novelty", [])
    if tonal_novelty and t_sec:
        tonal_peaks = _extract_peaks(t_sec, tonal_novelty, n_peaks=8, min_sep_s=4.0)
        arc["tonal_shifts"] = [{"t_s": p["t_s"], "novelty": p["v"]} for p in tonal_peaks]

    # Section transitions
    for i in range(len(sections) - 1):
        curr = sections[i]
        next_sec = sections[i + 1]
        transition_time = float(next_sec.get("start_s", 0))

        # Sample audio state at transition
        transition_state = _sample_timeline_at_time(timeline, transition_time)

        arc["section_transitions"].append(
            {
                "t_s": transition_time,
                "from_section": curr.get("label", "unknown"),
                "to_section": next_sec.get("label", "unknown"),
                "energy_delta": float(
                    next_sec.get("energy_rank", 0.5) - curr.get("energy_rank", 0.5)
                ),
                "tonal_novelty": transition_state.get("tonal_novelty", 0.0),
            }
        )

    # Integrate sequence timing events if provided
    sequence_events = []
    if seq_fingerprint:
        timing_track_events = seq_fingerprint.get("timing_track_events", {})
        if timing_track_events:
            filtered_timing = _filter_meaningful_timing_events(
                timing_track_events, max_events_per_track=20
            )

            # Convert to seconds and add to sequence events
            for event in filtered_timing:
                # Timing track events use 'time_ms' not 'start_ms'
                time_ms = event.get("time_ms", 0)
                if not isinstance(time_ms, (int, float)):
                    time_ms = 0
                time_s = float(time_ms) / 1000.0
                section = _find_section_for_time(sections, time_s)

                sequence_events.append(
                    {
                        "t_s": time_s,
                        "t_ms": int(time_ms),
                        "label": event.get("label", ""),
                        "track": event.get("track_name", ""),
                        "section_id": section.get("section_id", 0) if section else 0,
                    }
                )

            logger.info(f"Integrated {len(sequence_events)} meaningful sequence timing events")

    # Build final map
    return {
        "metadata": {
            "duration_s": duration_s,
            "tempo_bpm": tempo_bpm,
            "total_bars": len(bars_s),
            "total_beats": len(beats_s),
            "total_sections": len(sections),
            "event_resolution": resolution,
            "total_events": len(events),
            "sequence_events": len(sequence_events),
        },
        "sections": section_summaries,
        "events": events,
        "arc": arc,
        "sequence_timing": sequence_events if sequence_events else None,
    }


__all__ = [
    "build_unified_song_map",
    "_find_section_for_time",
    "_sample_timeline_at_time",
    "_filter_meaningful_timing_events",
]
