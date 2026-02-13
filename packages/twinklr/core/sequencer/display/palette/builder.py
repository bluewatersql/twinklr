"""Palette builder for converting ResolvedPalette to xLights format.

Generates the comma-separated ColorPalette settings strings that
xLights stores in the <ColorPalettes> section of .xsq files.

Format matches xLights convention:
1. All 8 C_BUTTON_PaletteN entries (colors for every slot).
2. Only C_CHECKBOX_PaletteN=1 for active slots (inactive omitted).
3. Optional modifiers (sparkle, brightness, music sparkles, etc.)
   only when non-default.

Example from a real xLights sequence::

    C_BUTTON_Palette1=#FFFFFF,C_BUTTON_Palette2=#FF0000,
    C_BUTTON_Palette3=#00FF00,...,C_BUTTON_Palette8=#FF00FF,
    C_CHECKBOX_Palette1=1,C_CHECKBOX_Palette3=1

Color slot ordering matters — effects consume palette colors by
position, so the same colors in different slots produce different
visual results depending on the effect type.
"""

from __future__ import annotations

from twinklr.core.sequencer.display.models.palette import ResolvedPalette

# Default inactive color (black)
_DEFAULT_COLOR = "#000000"

# Total palette slots in xLights
_MAX_SLOTS = 8


def build_palette_string(palette: ResolvedPalette) -> str:
    """Convert a ResolvedPalette to an xLights ColorPalette string.

    Produces the comma-separated key=value string stored in the
    ``<ColorPalettes>`` XML section, matching xLights native format:

    - All 8 button colors emitted first (grouped).
    - Only active checkbox entries emitted (``=1``), inactive omitted.
    - Sparkle/brightness/music modifiers only when non-default.

    Args:
        palette: Resolved palette with colors and modifiers.

    Returns:
        xLights-format palette settings string.

    Example:
        >>> p = ResolvedPalette(colors=["#FF0000", "#00FF00"], active_slots=[1, 2])
        >>> s = build_palette_string(p)
        >>> "C_BUTTON_Palette1=#FF0000" in s
        True
        >>> "C_CHECKBOX_Palette3" not in s  # inactive slot omitted
        True
    """
    parts: list[str] = []

    # 1. All 8 button colors (grouped)
    for slot in range(1, _MAX_SLOTS + 1):
        color_idx = slot - 1
        color = palette.colors[color_idx] if color_idx < len(palette.colors) else _DEFAULT_COLOR
        parts.append(f"C_BUTTON_Palette{slot}={color}")

    # 2. Only active checkboxes (omit inactive)
    for slot in range(1, _MAX_SLOTS + 1):
        if slot in palette.active_slots:
            parts.append(f"C_CHECKBOX_Palette{slot}=1")

    # 3. Modifiers — only when non-default

    # Music sparkles (before sparkle frequency, matching xLights order)
    if palette.music_sparkles:
        parts.append("C_CHECKBOX_MusicSparkles=1")

    # Sparkle frequency (only when > 0)
    if palette.sparkle_frequency is not None and palette.sparkle_frequency > 0:
        parts.append(f"C_SLIDER_SparkleFrequency={palette.sparkle_frequency}")

    # Brightness
    if palette.brightness is not None:
        parts.append(f"C_SLIDER_Brightness={palette.brightness}")

    # Brightness curve
    if palette.brightness_curve is not None:
        parts.append(f"C_VALUECURVE_Brightness={palette.brightness_curve}")

    # Sparkle color
    if palette.sparkle_color is not None:
        parts.append(f"C_COLOURPICKERCTRL_SparklesColour={palette.sparkle_color}")

    # Hue adjust
    if palette.hue_adjust is not None:
        parts.append(f"C_SLIDER_Color_HueAdjust={palette.hue_adjust}")

    return ",".join(parts)


__all__ = [
    "build_palette_string",
]
