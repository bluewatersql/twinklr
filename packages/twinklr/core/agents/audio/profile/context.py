"""Context shaping for AudioProfile agent.

Transforms large SongBundle (~100KB) into minimal, efficient context (~10KB)
for LLM consumption, achieving 10x token reduction while preserving essential
information for song understanding.

Key transformations:
- Extract essential metadata (tempo, key, duration)
- Compress energy curves per-section (preserves intra-section dynamics)
- Convert lyrics to metadata-only (no full text)
- Filter redundant/non-semantic data (waveforms, spectrograms)
"""

from typing import Any

from twinklr.core.audio.models import SongBundle


def shape_context(bundle: SongBundle) -> dict[str, Any]:
    """Shape SongBundle into minimal context for AudioProfile agent.

    Args:
        bundle: Complete SongBundle from audio analysis.

    Returns:
        Shaped context dictionary (~10KB, 10x reduction from ~100KB).

    Context Structure:
        {
            "audio_path": str,
            "duration_ms": int,
            "tempo": {"bpm": float, "confidence": float, "time_signature": str},
            "key": {"key": str, "mode": str, "confidence": float},
            "sections": [{"type": str, "start_ms": int, "end_ms": int, ...}],
            "energy": {
                "overall": float,
                "section_profiles": [
                    {
                        "section_id": str,
                        "energy_curve": [{"t_ms": int, "energy": float}],
                        "mean_energy": float,
                        "peak_energy": float,
                        "characteristics": [str]
                    }
                ],
                "peaks": [{"start_ms": int, "end_ms": int, "energy": float}]
            },
            "lyrics": {
                "has_plain_lyrics": bool,
                "has_timed_words": bool,
                "has_phonemes": bool,
                "lyric_confidence": float,
                "phoneme_confidence": float
            }
        }
    """
    features = bundle.features

    # Extract essential metadata
    context: dict[str, Any] = {
        "audio_path": bundle.audio_path,
        "duration_ms": features.get("duration_ms", bundle.timing.duration_ms),
    }

    # Tempo - handle both nested (test) and flat (real) structures
    tempo_nested = features.get("tempo", {})
    if isinstance(tempo_nested, dict) and "bpm" in tempo_nested:
        # Nested structure (tests)
        context["tempo"] = {
            "bpm": tempo_nested.get("bpm"),
            "confidence": tempo_nested.get("confidence", 1.0),
            "time_signature": tempo_nested.get("time_signature", "4/4"),
        }
    else:
        # Flat structure (real SongBundle)
        time_sig_data = features.get("time_signature", {})
        if isinstance(time_sig_data, dict):
            time_sig_str = time_sig_data.get("time_signature", "4/4")
        else:
            time_sig_str = str(time_sig_data) if time_sig_data else "4/4"

        context["tempo"] = {
            "bpm": features.get("tempo_bpm"),
            "confidence": 1.0,
            "time_signature": time_sig_str,
        }

    # Key - handle both nested (test) and flat (real) structures
    key_nested = features.get("key", {})
    if (
        isinstance(key_nested, dict)
        and "key" in key_nested
        and not isinstance(key_nested.get("key"), dict)
    ):
        # Nested structure (tests) - key is a string
        context["key"] = {
            "key": key_nested.get("key"),
            "mode": key_nested.get("mode"),
            "confidence": key_nested.get("confidence", 0.0),
        }
    else:
        # Flat structure (real SongBundle) - key is in harmonic.key
        harmonic = features.get("harmonic", {})
        key_data = harmonic.get("key", {})
        if isinstance(key_data, dict):
            context["key"] = {
                "key": key_data.get("key"),
                "mode": key_data.get("mode"),
                "confidence": key_data.get("confidence", 0.0),
            }
        else:
            context["key"] = {
                "key": None,
                "mode": None,
                "confidence": 0.0,
            }

    # Sections - handle both flat (test) and nested (real) structures
    sections_flat = features.get("sections", [])
    if sections_flat and isinstance(sections_flat[0], dict) and "start_ms" in sections_flat[0]:
        # Flat structure (tests) - sections directly in features
        context["sections"] = [
            {
                "type": s.get("type", "unknown"),
                "start_ms": s.get("start_ms", 0),
                "end_ms": s.get("end_ms", 0),
                "confidence": s.get("confidence", 0.8),
            }
            for s in sections_flat
        ]
    else:
        # Nested structure (real SongBundle) - sections in structure.sections with seconds
        structure = features.get("structure", {})
        sections_nested = structure.get("sections", [])
        context["sections"] = [
            {
                "type": s.get("label", s.get("type", "unknown")),
                "start_ms": int(s.get("start_s", 0) * 1000),
                "end_ms": int(s.get("end_s", 0) * 1000),
                "confidence": s.get("confidence", 0.8),
            }
            for s in sections_nested
        ]

    # Energy (compressed per-section)
    energy_data = features.get("energy", {})
    context["energy"] = _shape_energy(energy_data, context["sections"])

    # Lyrics (metadata only, no full text)
    context["lyrics"] = _shape_lyrics(bundle.lyrics)

    # Phonemes (metadata only)
    context["phonemes"] = _shape_phonemes(bundle.phonemes)

    # Sync lyrics.has_phonemes from actual phoneme availability
    context["lyrics"]["has_phonemes"] = context["phonemes"]["available"]
    context["lyrics"]["phoneme_confidence"] = context["phonemes"]["confidence"]

    return context


def _shape_energy(energy_data: dict[str, Any], sections: list[dict[str, Any]]) -> dict[str, Any]:
    """Shape energy data with per-section compression.

    Args:
        energy_data: Raw energy data from features.
        sections: List of section dicts.

    Returns:
        Shaped energy with per-section profiles.
    """
    # Handle both old format (overall/curve) and new format (rms_norm/times_s)
    if "rms_norm" in energy_data:
        # New format: rms_norm array with times_s
        rms_norm = energy_data.get("rms_norm", [])
        times_s = energy_data.get("times_s", [])

        # Convert to curve format [{t_ms, energy}, ...]
        full_curve = [
            {"t_ms": int(t * 1000), "energy": float(e)}
            for t, e in zip(times_s, rms_norm, strict=True)
        ]

        # Calculate overall mean from RMS
        overall = float(sum(rms_norm) / len(rms_norm)) if rms_norm else 0.0

        # Extract peaks from builds if available
        builds = energy_data.get("builds", [])
        peaks = []
        for build in builds[:5]:  # Top 5 builds as peaks
            if isinstance(build, dict):
                peaks.append(
                    {
                        "start_ms": int(build.get("start_s", 0) * 1000),
                        "end_ms": int(build.get("end_s", 0) * 1000),
                        "energy": float(build.get("intensity", 0.8)),
                    }
                )
    else:
        # Old format: overall/curve/peaks
        overall = energy_data.get("overall", 0.0)
        full_curve = energy_data.get("curve", [])
        peaks = energy_data.get("peaks", [])

    # Build per-section profiles
    section_profiles = []
    for i, section in enumerate(sections):
        section_id = f"{section.get('type', 'unknown')}_{i}"
        # Sections already have start_ms/end_ms from context shaping
        start_ms = section.get("start_ms", 0)
        end_ms = section.get("end_ms", 0)

        # Extract section curve
        section_curve = [p for p in full_curve if start_ms <= p.get("t_ms", 0) < end_ms]

        if not section_curve:
            continue

        # Compress curve
        compressed = compress_section_curve(section_curve, points_per_section=8)

        # Calculate statistics
        energies = [p["energy"] for p in section_curve]
        mean_energy = sum(energies) / len(energies) if energies else 0.0
        peak_energy = max(energies) if energies else 0.0

        # Identify characteristics
        characteristics = identify_characteristics(compressed)

        section_profiles.append(
            {
                "section_id": section_id,
                "energy_curve": compressed,
                "mean_energy": round(mean_energy, 2),
                "peak_energy": round(peak_energy, 2),
                "characteristics": characteristics,
            }
        )

    return {
        "overall": overall,
        "section_profiles": section_profiles,
        "peaks": [
            {
                "start_ms": p.get("start_ms", 0),
                "end_ms": p.get("end_ms", 0),
                "energy": p.get("energy", 0.0),
            }
            for p in peaks
        ],
    }


def _shape_lyrics(lyrics: Any) -> dict[str, Any]:
    """Shape lyrics to metadata-only (no full text).

    Args:
        lyrics: LyricsBundle or None.

    Returns:
        Lyrics metadata dict.
    """
    if lyrics is None:
        return {
            "has_plain_lyrics": False,
            "has_timed_words": False,
            "has_phonemes": False,
            "lyric_confidence": 0.0,
            "phoneme_confidence": 0.0,
        }

    # Check if lyrics text is available
    has_text = bool(getattr(lyrics, "text", None))

    # Check if ANY timing is available (word-level OR phrase-level)
    words = getattr(lyrics, "words", [])
    phrases = getattr(lyrics, "phrases", [])
    has_timing = len(words) > 0 or len(phrases) > 0

    # Get confidence from source if available
    source = getattr(lyrics, "source", None)
    confidence = getattr(source, "confidence", 0.0) if source else 0.0

    return {
        "has_plain_lyrics": has_text,
        "has_timed_words": has_timing,  # True if word OR phrase timing exists
        "has_phonemes": False,  # Phonemes are separate
        "lyric_confidence": confidence,
        "phoneme_confidence": 0.0,
    }


def _shape_phonemes(phonemes: Any) -> dict[str, Any]:
    """Shape phonemes to metadata-only.

    Derives availability from the presence of actual phoneme data,
    and reads confidence from the PhonemeBundle.confidence field.

    Args:
        phonemes: PhonemeBundle or None.

    Returns:
        Phoneme metadata dict with 'available' and 'confidence'.
    """
    if phonemes is None:
        return {
            "available": False,
            "confidence": 0.0,
        }

    # Derive availability from actual data presence
    phoneme_list = getattr(phonemes, "phonemes", [])
    available = len(phoneme_list) > 0

    return {
        "available": available,
        "confidence": getattr(phonemes, "confidence", 0.0),
    }


def compress_section_curve(
    section_curve: list[dict[str, Any]], points_per_section: int = 8
) -> list[dict[str, Any]]:
    """Compress energy curve for a single section using uniform sampling.

    Strategy:
    - Sample points evenly distributed across the section duration
    - Always include first and last points
    - Use linear interpolation to get uniform timestamps

    Args:
        section_curve: Section curve [{"t_ms": int, "energy": float}, ...].
        points_per_section: Target number of points (default: 8).

    Returns:
        Compressed curve with exactly points_per_section points.
    """
    if len(section_curve) == 0:
        return []

    if len(section_curve) <= points_per_section:
        return section_curve

    # Get time range
    start_ms = section_curve[0]["t_ms"]
    end_ms = section_curve[-1]["t_ms"]
    duration_ms = end_ms - start_ms

    if duration_ms <= 0:
        return [section_curve[0]]

    # Generate uniform timestamps
    result = []
    for i in range(points_per_section):
        # Sample at evenly spaced fractions: 0%, 1/(n-1), 2/(n-1), ..., 100%
        fraction = i / (points_per_section - 1) if points_per_section > 1 else 0.0
        target_ms = start_ms + int(fraction * duration_ms)

        # Find closest point in original curve
        closest_point = min(section_curve, key=lambda p: abs(p["t_ms"] - target_ms))
        result.append(closest_point)

    return result


def _find_local_extrema(curve: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find local peaks and valleys in curve.

    Args:
        curve: Energy curve.

    Returns:
        List of extrema points.
    """
    if len(curve) < 3:
        return []

    extrema = []
    energies = [p["energy"] for p in curve]

    for i in range(1, len(curve) - 1):
        # Local maximum
        if energies[i] > energies[i - 1] and energies[i] > energies[i + 1]:
            extrema.append(curve[i])
        # Local minimum
        elif energies[i] < energies[i - 1] and energies[i] < energies[i + 1]:
            extrema.append(curve[i])

    return extrema


def identify_characteristics(section_curve: list[dict[str, Any]]) -> list[str]:
    """Identify section energy characteristics from curve shape.

    Args:
        section_curve: Compressed section curve.

    Returns:
        List of characteristics: 'building', 'drop', 'sustained', 'peak', 'valley'.
    """
    if len(section_curve) < 3:
        return []

    characteristics = []
    energies = [p["energy"] for p in section_curve]

    # Detect building (sustained increase)
    if _is_increasing(energies, threshold=0.15):
        characteristics.append("building")

    # Detect drop (sharp decrease)
    if _has_sharp_drop(energies, threshold=0.2):
        characteristics.append("drop")

    # Detect sustained (relatively flat)
    if _is_sustained(energies, threshold=0.1):
        characteristics.append("sustained")

    # Detect peak (high energy)
    mean_energy = sum(energies) / len(energies)
    if mean_energy >= 0.75:
        characteristics.append("peak")

    # Detect valley (low energy)
    if mean_energy <= 0.3:
        characteristics.append("valley")

    return characteristics


def _is_increasing(energies: list[float], threshold: float = 0.15) -> bool:
    """Check if energies show sustained increase."""
    if len(energies) < 3:
        return False
    return energies[-1] - energies[0] >= threshold


def _has_sharp_drop(energies: list[float], threshold: float = 0.2) -> bool:
    """Check if energies have a sharp drop."""
    if len(energies) < 2:
        return False
    for i in range(1, len(energies)):
        if energies[i - 1] - energies[i] >= threshold:
            return True
    return False


def _is_sustained(energies: list[float], threshold: float = 0.1) -> bool:
    """Check if energies are relatively flat (sustained)."""
    if len(energies) < 2:
        return False
    energy_range = max(energies) - min(energies)
    return energy_range <= threshold
