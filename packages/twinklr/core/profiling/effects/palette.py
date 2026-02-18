"""Color palette parsing/classification for XSequence models."""

from __future__ import annotations

import re
from collections import defaultdict

from twinklr.core.formats.xlights.sequence.models.xsq import XSequence
from twinklr.core.profiling.models.palette import (
    ColorPaletteProfile,
    PaletteClassifications,
    PaletteEntry,
)

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_COLOR_CURVE_RE = re.compile(r"c=(#[0-9A-Fa-f]{6})")


def _parse_color_curve(value: str) -> list[str]:
    colors = _COLOR_CURVE_RE.findall(value)
    seen: set[str] = set()
    unique: list[str] = []
    for color in colors:
        upper = color.upper()
        if upper not in seen:
            seen.add(upper)
            unique.append(upper)
    return unique


def _parse_palette_entry(palette_str: str) -> tuple[list[str], list[int]]:
    parts = palette_str.split(",")
    color_buttons: dict[int, list[str]] = {}
    checkboxes: dict[int, bool] = {}

    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()

        if key.startswith("C_BUTTON_Palette"):
            match = re.match(r"C_BUTTON_Palette(\d+)", key)
            if not match:
                continue
            slot = int(match.group(1))
            if _HEX_COLOR_RE.match(value):
                color_buttons[slot] = [value.upper()]
            elif value.startswith("Active="):
                parsed = _parse_color_curve(value)
                if parsed:
                    color_buttons[slot] = parsed

        elif key.startswith("C_CHECKBOX_Palette"):
            match = re.match(r"C_CHECKBOX_Palette(\d+)", key)
            if not match:
                continue
            slot = int(match.group(1))
            checkboxes[slot] = value == "1"

    enabled_colors: list[str] = []
    enabled_slots: list[int] = []
    for slot in sorted(color_buttons):
        if not checkboxes.get(slot, False):
            continue
        slot_index = slot - 1
        for color in color_buttons[slot]:
            enabled_colors.append(color)
            enabled_slots.append(slot_index)

    seen_colors: set[str] = set()
    unique_colors: list[str] = []
    unique_slots: list[int] = []
    for color, slot in zip(enabled_colors, enabled_slots, strict=False):
        if color in seen_colors:
            continue
        seen_colors.add(color)
        unique_colors.append(color)
        unique_slots.append(slot)

    return unique_colors, unique_slots


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int] | None:
    stripped = hex_color.lstrip("#")
    if len(stripped) != 6:
        return None
    if not all(c in "0123456789ABCDEFabcdef" for c in stripped):
        return None
    return (
        int(stripped[0:2], 16),
        int(stripped[2:4], 16),
        int(stripped[4:6], 16),
    )


def _is_grayscale(hex_color: str) -> bool:
    rgb = _hex_to_rgb(hex_color)
    if rgb is None:
        return False
    r, g, b = rgb
    return r == g == b


def _is_warm(hex_color: str) -> bool:
    rgb = _hex_to_rgb(hex_color)
    if rgb is None:
        return False
    r, g, b = rgb
    return r > b and r > g * 0.8


def _is_cool(hex_color: str) -> bool:
    rgb = _hex_to_rgb(hex_color)
    if rgb is None:
        return False
    r, g, b = rgb
    return (b > r and b > g * 0.8) or (g > r and g > b * 0.8)


def _color_family(hex_color: str) -> str:
    rgb = _hex_to_rgb(hex_color)
    if rgb is None:
        return "unknown"

    r, g, b = rgb
    if r == g == b:
        if r == 0:
            return "black"
        if r == 255:
            return "white"
        return "gray"

    max_val = max(r, g, b)
    if r == max_val and g < 100 and b < 100:
        return "red"
    if g == max_val and r < 100 and b < 100:
        return "green"
    if b == max_val and r < 100 and g < 100:
        return "blue"
    if r == max_val and g == max_val and b < 100:
        return "yellow"
    if r == max_val and b == max_val and g < 100:
        return "magenta"
    if g == max_val and b == max_val and r < 100:
        return "cyan"
    if r > 200 and 100 < g < 200 and b < 100:
        return "orange"
    if r > 100 and g < 100 and b > 100:
        return "purple"
    return "mixed"


def classify_palettes(
    single_colors: list[PaletteEntry],
    multi_colors: list[PaletteEntry],
) -> PaletteClassifications:
    """Classify palette entries by high-level color properties."""
    all_entries = [*single_colors, *multi_colors]

    monochrome: list[PaletteEntry] = []
    warm: list[PaletteEntry] = []
    cool: list[PaletteEntry] = []
    primary_only: list[PaletteEntry] = []
    by_color_family: dict[str, list[PaletteEntry]] = defaultdict(list)

    primary_set = {"#FF0000", "#0000FF", "#FFFF00", "#000000", "#FFFFFF"}

    for entry in all_entries:
        colors = entry.colors
        if all(_is_grayscale(c) for c in colors):
            monochrome.append(entry)
        if any(_is_warm(c) for c in colors):
            warm.append(entry)
        if any(_is_cool(c) for c in colors):
            cool.append(entry)
        if all(c.upper() in primary_set for c in colors):
            primary_only.append(entry)
        for color in colors:
            by_color_family[_color_family(color)].append(entry)

    return PaletteClassifications(
        monochrome=tuple(monochrome),
        warm=tuple(warm),
        cool=tuple(cool),
        primary_only=tuple(primary_only),
        by_color_family={k: tuple(v) for k, v in by_color_family.items()},
    )


def parse_color_palettes(sequence: XSequence) -> ColorPaletteProfile:
    """Parse and classify color palette entries from an XSequence."""
    if not sequence.color_palettes:
        return ColorPaletteProfile(
            unique_colors=(),
            single_colors=(),
            color_palettes=(),
            classifications=PaletteClassifications(
                monochrome=(),
                warm=(),
                cool=(),
                primary_only=(),
                by_color_family={},
            ),
        )

    unique_colors: set[str] = set()
    single_color_map: dict[str, list[int]] = {}
    multi_color_map: dict[tuple[str, ...], list[int]] = {}

    for entry_index, color_palette in enumerate(sequence.color_palettes):
        colors, _slots = _parse_palette_entry(color_palette.settings)
        if not colors:
            continue

        for color in colors:
            unique_colors.add(color)

        if len(colors) == 1:
            color = colors[0]
            single_color_map.setdefault(color, []).append(entry_index)
        else:
            combo = tuple(sorted(colors))
            multi_color_map.setdefault(combo, []).append(entry_index)

    single_entries = [
        PaletteEntry(colors=(color,), palette_entry_indices=tuple(indices))
        for color, indices in sorted(single_color_map.items())
    ]
    multi_entries = [
        PaletteEntry(colors=combo, palette_entry_indices=tuple(indices))
        for combo, indices in sorted(multi_color_map.items())
    ]

    return ColorPaletteProfile(
        unique_colors=tuple(sorted(unique_colors)),
        single_colors=tuple(single_entries),
        color_palettes=tuple(multi_entries),
        classifications=classify_palettes(single_entries, multi_entries),
    )
