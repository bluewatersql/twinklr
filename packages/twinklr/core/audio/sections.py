"""Canonical section ID generation for audio structure.

Provides a deterministic algorithm for generating section IDs from raw audio
structure data. Used by both the audio profile and lyrics context shapers
to ensure consistent section references across all pipeline stages.

The algorithm uses per-type counters:
- Singleton types get no suffix: "intro", "outro", "bridge"
- Multi-occurrence types get 1-based suffixes: "chorus_1", "chorus_2", "verse_1"
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def generate_section_ids(sections: list[dict[str, Any]]) -> list[str]:
    """Generate canonical section IDs using per-type counters.

    Produces stable, deterministic IDs that match the convention used by
    the audio profile LLM (per-type counters, 1-based). Singleton section
    types omit the counter suffix for readability.

    Args:
        sections: List of raw section dicts, each containing a "label" or
            "type" key identifying the section type (e.g., "intro", "chorus").

    Returns:
        List of section IDs in the same order as input sections.

    Examples:
        >>> sections = [
        ...     {"label": "intro"},
        ...     {"label": "chorus"},
        ...     {"label": "verse"},
        ...     {"label": "chorus"},
        ...     {"label": "outro"},
        ... ]
        >>> generate_section_ids(sections)
        ['intro', 'chorus_1', 'verse', 'chorus_2', 'outro']
    """
    # Count total occurrences of each type
    labels = [_extract_label(s) for s in sections]
    totals = Counter(labels)

    # Generate IDs with per-type counters
    type_counter: dict[str, int] = {}
    ids: list[str] = []
    for label in labels:
        type_counter[label] = type_counter.get(label, 0) + 1
        if totals[label] == 1:
            # Singleton — no suffix
            ids.append(label)
        else:
            # Multi-occurrence — 1-based counter suffix
            ids.append(f"{label}_{type_counter[label]}")

    return ids


def _extract_label(section: dict[str, Any]) -> str:
    """Extract section type label from raw section dict.

    Handles both 'label' (structure.sections) and 'type' (flat sections) keys.

    Args:
        section: Raw section dict.

    Returns:
        Section type label string.
    """
    return str(section.get("label", section.get("type", "unknown")))


__all__ = [
    "generate_section_ids",
]
