"""Shutter pattern identifiers the moving-head plan schema names."""

from __future__ import annotations

from enum import StrEnum


class ShutterPattern(StrEnum):
    """Predefined shutter pattern identifiers.

    Provides type-safe pattern IDs with IDE autocomplete.
    """

    OPEN = "open"
    CLOSED = "closed"
    STROBE_FAST = "strobe_fast"
    STROBE_MEDIUM = "strobe_medium"
    STROBE_SLOW = "strobe_slow"
    PULSE = "pulse"
