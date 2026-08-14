"""Feature validation and quality checks."""

from __future__ import annotations

from typing import Any

import numpy as np


def _key_info(result: dict[str, Any]) -> dict[str, Any] | None:
    """Locate the key-detection result in either schema the analyzer emits.

    The full analysis path writes it to ``features["harmonic"]["key"]``; the
    short-audio path writes a top-level ``features["key"]``.
    """
    harmonic = result.get("harmonic")
    if isinstance(harmonic, dict):
        harmonic_key = harmonic.get("key")
        if isinstance(harmonic_key, dict):
            return harmonic_key
    top_level = result.get("key")
    if isinstance(top_level, dict):
        return top_level
    return None


def validate_features(result: dict[str, Any]) -> list[str]:
    """Check for common issues in extracted features.

    Returns list of warning strings (empty if all OK).

    Args:
        result: Feature extraction result dictionary

    Returns:
        List of warning messages
    """
    warnings = []

    tempo = result.get("tempo_bpm", 0)
    if tempo < 40 or tempo > 240:
        warnings.append(f"Unusual tempo: {tempo:.1f} BPM (expected 40-240)")

    beats = result.get("beats_s", [])
    if len(beats) < 10:
        warnings.append(f"Very few beats detected ({len(beats)}) - possible detection failure")

    key_info = _key_info(result)
    if key_info is None:
        warnings.append("Key detection result missing")
    else:
        key_conf = float(key_info.get("confidence", 0.0))
        if key_conf < 0.3:
            warnings.append(f"Low key detection confidence: {key_conf:.2f}")

    # Check beat intervals for outliers
    if len(beats) > 2:
        intervals = np.diff(beats)
        cv = np.std(intervals) / (np.mean(intervals) + 1e-9)
        if cv > 0.5:
            warnings.append(f"Highly irregular beat spacing (CV={cv:.2f})")

    # Check section detection
    sections = result.get("structure", {}).get("sections", [])
    if not sections:
        warnings.append("No sections detected")

    # Check downbeat confidence
    db_conf = result.get("rhythm", {}).get("downbeat_meta", {}).get("phase_confidence", 1.0)
    if db_conf < 0.4:
        warnings.append(f"Low downbeat phase confidence: {db_conf:.2f}")

    return warnings
