"""Dimmer identifiers `TemplateStep.dimmer` validates."""

from __future__ import annotations

from enum import StrEnum


class DimmerType(StrEnum):
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    BLACKOUT = "blackout"
    HOLD = "hold"
    PULSE = "pulse"
    NONE = "none"
