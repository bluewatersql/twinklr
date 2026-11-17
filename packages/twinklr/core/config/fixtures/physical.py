"""Retired and removed fixture-config fields.

A retired field (dropped before the physical renderer) still loads, with a warning. A
field removed with the old moving-head renderer is refused by name.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

REMOVED_FIXTURE_FIELDS = frozenset({"inversions", "pan_tilt_range", "orientation", "limits"})
REMOVED_DMX_MAPPING_FIELDS = frozenset(
    {
        "pan_fine_channel",
        "tilt_fine_channel",
        "use_16bit_pan_tilt",
        "shutter_default",
        "shutter_map",
        "color_map",
        "gobo_map",
    }
)
REMOVED_POSITION_FIELDS = frozenset({"pan_offset_deg", "tilt_offset_deg"})


def drop_retired_fields(value: object, retired: frozenset[str], kind: str) -> object:
    """Drop fixture-config fields that no longer affect output, with a warning.

    Fixture files written before 2026-08 carry these fields. Rejecting them made a
    rig description that had always loaded stop loading, so they are ignored instead.
    """
    if not isinstance(value, dict):
        return value
    found = sorted(retired & value.keys())
    if not found:
        return value
    logger.warning("Ignoring retired %s fields %s: they do not affect output", kind, found)
    return {key: item for key, item in value.items() if key not in retired}


_OLD_RENDERER_READ = (
    "were removed with the old moving-head renderer, their only reader; delete them. The "
    "renderer reads each fixture's physical_profile"
)


def reject_removed_fields(
    value: object, removed: frozenset[str], kind: str, reason: str = _OLD_RENDERER_READ
) -> object:
    """Refuse removed fixture-config fields, naming each and why."""
    if isinstance(value, dict):
        found = sorted(removed & value.keys())
        if found:
            raise ValueError(f"{kind} fields {found} {reason}")
    return value


def reject_removed_position_fields(value: object, kind: str = "position") -> object:
    """Refuse the mounting offsets, which nothing read, naming each."""
    return reject_removed_fields(
        value, REMOVED_POSITION_FIELDS, kind, "were removed: nothing read them; delete them"
    )
