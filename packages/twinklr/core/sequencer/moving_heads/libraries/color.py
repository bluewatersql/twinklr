"""Colour-wheel preset identifiers the moving-head plan schema names, and their colours."""

from __future__ import annotations

from enum import StrEnum
import re


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


COLOR_PRESET_HEX: dict[ColorPreset, str] = {
    ColorPreset.RED: "#FF0000",
    ColorPreset.BLUE: "#0000FF",
    ColorPreset.GREEN: "#00FF00",
    ColorPreset.YELLOW: "#FFFF00",
    ColorPreset.MAGENTA: "#FF00FF",
    ColorPreset.CYAN: "#00FFFF",
    ColorPreset.ORANGE: "#FF8000",
    ColorPreset.PURPLE: "#800080",
    ColorPreset.AMBER: "#FFBF00",
    ColorPreset.LIME: "#BFFF00",
    ColorPreset.WHITE: "#FFFFFF",
    ColorPreset.WARM_WHITE: "#F5F1E8",
    ColorPreset.COOL_WHITE: "#DCF0FF",
    ColorPreset.UV: "#6E00FF",
}
"""Each preset's canonical colour: the RGB representatives the deleted renderer's palette
projection used (`sequencer/show_coordination.py` `_PRESET_RGB` at tag
`mh-last-with-legacy-renderer`). Chosen, not measured; what a fixture's wheel really
shows is its profile's `hex` tags."""

_HEX = re.compile(r"#[0-9A-Fa-f]{6}")


def canonical_hex(color: str) -> str:
    """`color` as an uppercase `#RRGGBB`: a hex colour as given, or a `ColorPreset` name
    as its canonical colour.

    Raises:
        ValueError: Naming both forms it accepts.
    """
    if _HEX.fullmatch(color):
        return color.upper()
    if color in COLOR_PRESET_HEX:
        return COLOR_PRESET_HEX[ColorPreset(color)]
    raise ValueError(
        f"{color!r} is not a colour: write '#RRGGBB' (six hex digits) or one of "
        f"{', '.join(ColorPreset)}"
    )
