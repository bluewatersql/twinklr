"""Gobo pattern identifiers the moving-head plan schema names."""

from __future__ import annotations

from enum import StrEnum


class GoboPattern(StrEnum):
    """Predefined gobo pattern identifiers."""

    OPEN = "open"
    CIRCLES = "circles"
    TRIANGLES = "triangles"
    STARS = "stars"
    DIAMONDS = "diamonds"
    CLOUDS = "clouds"
    PRISM = "prism"
    SHATTER = "shatter"
    DOTS = "dots"
    FLAME = "flame"
    WATER = "water"
    FOLIAGE = "foliage"
    ABSTRACT = "abstract"
