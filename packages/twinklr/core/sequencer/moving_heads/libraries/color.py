"""Colour-wheel preset identifiers the moving-head plan schema names."""

from __future__ import annotations

from enum import StrEnum


class ColorPreset(StrEnum):
    """Predefined color preset identifiers."""

    RED = "red"
    BLUE = "blue"
    GREEN = "green"
    YELLOW = "yellow"
    MAGENTA = "magenta"
    CYAN = "cyan"
    ORANGE = "orange"
    PURPLE = "purple"
    AMBER = "amber"
    LIME = "lime"
    WHITE = "white"
    WARM_WHITE = "warm_white"
    COOL_WHITE = "cool_white"
    UV = "uv"
