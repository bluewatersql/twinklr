"""Color Family Discovery — extract, cluster, and name color palettes from effect params.

This module provides corpus-level color family discovery by:
1. Extracting hex colors from enriched effect event params
2. Clustering colors by hue into 12 chromatic + 1 achromatic bins
3. Building palettes from co-occurring colors within (package_id, sequence_file_id, section_label)
4. Naming palettes via heuristics based on color composition
"""

from __future__ import annotations

import colorsys
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

# Hex color pattern: # followed by exactly 6 hex digits.
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Param names that carry color values (normalized to lowercase for matching).
_COLOR_PARAM_PATTERNS: tuple[str, ...] = (
    "palette",
    "color1",
    "color2",
    "color3",
    "singlestrand_colors",
)

# Prefixes / suffixes for color param detection.
_COLOR_PARAM_PREFIX = "c_slider_color"
_COLOR_PARAM_SUFFIX = "_color"

# 12 chromatic hue bin boundaries (degrees) and names, plus achromatic.
# Each bin spans 30 degrees of hue.
_HUE_BINS: tuple[tuple[str, float, float], ...] = (
    ("red", 0.0, 15.0),
    ("orange", 15.0, 45.0),
    ("yellow", 45.0, 75.0),
    ("yellow_green", 75.0, 105.0),
    ("green", 105.0, 135.0),
    ("green_cyan", 135.0, 165.0),
    ("cyan", 165.0, 195.0),
    ("blue_cyan", 195.0, 225.0),
    ("blue", 225.0, 255.0),
    ("blue_violet", 255.0, 285.0),
    ("violet", 285.0, 315.0),
    ("magenta", 315.0, 345.0),
    ("red_wrap", 345.0, 360.0),
)

# Saturation threshold below which a color is considered achromatic.
_ACHROMATIC_SATURATION_THRESHOLD = 0.10

# Number of distinct hue bins required for "rainbow" naming.
_RAINBOW_BIN_THRESHOLD = 5

# Warm hue bin names.
_WARM_BINS = frozenset({"red", "red_wrap", "orange", "yellow", "magenta"})
# Cool hue bin names.
_COOL_BINS = frozenset(
    {"green", "green_cyan", "cyan", "blue_cyan", "blue", "blue_violet", "violet"}
)


@dataclass(frozen=True)
class HueBin:
    """A cluster of hex colors sharing the same hue bin."""

    bin_name: str
    colors: tuple[str, ...]


@dataclass(frozen=True)
class DiscoveredPalette:
    """A palette discovered from co-occurring colors in a section scope."""

    scope_key: tuple[str, str, str]
    colors: tuple[str, ...]
    name: str
    hue_bins: tuple[HueBin, ...]


class ColorFamilyDiscoverer:
    """Discover color families from enriched effect event data.

    Extracts hex colors from effect params, clusters them by hue,
    builds palettes from co-occurring colors, and names them heuristically.
    """

    HUE_BIN_NAMES: tuple[str, ...] = (
        "red",
        "orange",
        "yellow",
        "yellow_green",
        "green",
        "green_cyan",
        "cyan",
        "blue_cyan",
        "blue",
        "blue_violet",
        "violet",
        "magenta",
        "achromatic",
    )

    def discover(
        self,
        enriched_events: Sequence[dict[str, Any]],
    ) -> list[DiscoveredPalette]:
        """Run full discovery pipeline on enriched events.

        Args:
            enriched_events: List of enriched effect event dicts.

        Returns:
            List of discovered palettes with names and hue bin assignments.
        """
        palettes = self._build_palettes(list(enriched_events))
        return palettes

    def _extract_colors(
        self,
        enriched_events: Sequence[dict[str, Any]],
    ) -> list[str]:
        """Extract validated hex colors from enriched event params.

        Args:
            enriched_events: List of enriched effect event dicts.

        Returns:
            List of validated hex color strings (uppercase, e.g. '#FF0000').
        """
        colors: list[str] = []
        for event in enriched_events:
            colors.extend(self._extract_colors_from_event(event))
        return colors

    def _extract_colors_from_event(
        self,
        event: dict[str, Any],
    ) -> list[str]:
        """Extract hex colors from a single enriched event dict.

        Args:
            event: A single enriched effect event dict.

        Returns:
            List of validated hex color strings from this event.
        """
        found: list[str] = []

        # 1. Top-level palette field.
        palette_val = event.get("palette")
        if isinstance(palette_val, str):
            found.extend(_extract_hex_from_string(palette_val))

        # 2. effectdb_params entries.
        params = event.get("effectdb_params")
        if isinstance(params, list):
            for param in params:
                if not isinstance(param, dict):
                    continue
                name = str(param.get("param_name_normalized", "")).lower()
                value = param.get("value_string")
                if not isinstance(value, str) or not value:
                    continue
                if _is_color_param_name(name):
                    found.extend(_extract_hex_from_string(value))

        return found

    @staticmethod
    def _cluster_by_hue(colors: Sequence[str]) -> list[HueBin]:
        """Cluster hex colors into hue bins using HSV decomposition.

        Args:
            colors: Sequence of hex color strings.

        Returns:
            List of HueBin instances, one per non-empty bin.
        """
        if not colors:
            return []

        bins: dict[str, list[str]] = defaultdict(list)
        for hex_color in colors:
            bin_name = _hue_bin_for_hex(hex_color)
            bins[bin_name].append(hex_color)

        result: list[HueBin] = []
        for bin_name, bin_colors in sorted(bins.items()):
            result.append(HueBin(bin_name=bin_name, colors=tuple(bin_colors)))
        return result

    def _build_palettes(
        self,
        enriched_events: list[dict[str, Any]],
    ) -> list[DiscoveredPalette]:
        """Build palettes from co-occurring colors within section scopes.

        Groups events by (package_id, sequence_file_id, section_label),
        extracts unique colors per group, and builds named palettes.

        Args:
            enriched_events: List of enriched effect event dicts.

        Returns:
            List of DiscoveredPalette instances.
        """
        if not enriched_events:
            return []

        # Group events by scope key.
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for event in enriched_events:
            key = (
                str(event.get("package_id", "")),
                str(event.get("sequence_file_id", "")),
                str(event.get("section_label", "")),
            )
            grouped[key].append(event)

        palettes: list[DiscoveredPalette] = []
        for scope_key in sorted(grouped.keys()):
            scope_events = grouped[scope_key]
            scope_colors: list[str] = []
            for evt in scope_events:
                scope_colors.extend(self._extract_colors_from_event(evt))

            # Deduplicate while preserving order.
            unique_colors = _deduplicate_preserve_order(scope_colors)
            if not unique_colors:
                continue

            hue_bins = self._cluster_by_hue(unique_colors)
            name = self._name_palette(tuple(unique_colors))
            palettes.append(
                DiscoveredPalette(
                    scope_key=scope_key,
                    colors=tuple(unique_colors),
                    name=name,
                    hue_bins=tuple(hue_bins),
                )
            )

        return palettes

    def _name_palette(self, colors: tuple[str, ...] | Sequence[str]) -> str:
        """Generate a heuristic name for a palette based on color composition.

        Args:
            colors: Tuple of hex color strings.

        Returns:
            Human-readable palette name string.
        """
        if not colors:
            return "Empty Palette"

        bins = self._cluster_by_hue(list(colors))
        bin_names = {b.bin_name for b in bins}
        chromatic_bins = bin_names - {"achromatic"}

        # All achromatic.
        if not chromatic_bins:
            return "Neutral Achromatic"

        # Rainbow / spectrum.
        if len(chromatic_bins) >= _RAINBOW_BIN_THRESHOLD:
            return "Rainbow Spectrum"

        # Determine temperature balance.
        warm_count = len(chromatic_bins & _WARM_BINS)
        cool_count = len(chromatic_bins & _COOL_BINS)

        if warm_count > 0 and cool_count == 0:
            if len(chromatic_bins) == 1:
                dominant_bin = next(iter(chromatic_bins))
                return f"Warm {_humanize_bin_name(dominant_bin)}"
            return "Warm Blend"

        if cool_count > 0 and warm_count == 0:
            if len(chromatic_bins) == 1:
                dominant_bin = next(iter(chromatic_bins))
                return f"Cool {_humanize_bin_name(dominant_bin)}"
            return "Cool Blend"

        # Mixed warm and cool.
        return "Warm Cool Mix"


# ---------------------------------------------------------------------------
# Module-level helpers (private)
# ---------------------------------------------------------------------------


def _is_valid_hex(value: str) -> bool:
    """Check if a string is a valid 6-digit hex color."""
    return bool(_HEX_COLOR_RE.match(value))


def _normalize_hex(value: str) -> str:
    """Normalize a hex color to uppercase with # prefix."""
    return f"#{value.lstrip('#').upper()}"


def _extract_hex_from_string(value: str) -> list[str]:
    """Extract all valid hex colors from a string (comma-separated or single).

    Args:
        value: A string that may contain one or more hex colors.

    Returns:
        List of validated, normalized hex color strings.
    """
    results: list[str] = []
    candidates = value.split(",")
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        normalized = _normalize_hex(candidate)
        if _is_valid_hex(normalized):
            results.append(normalized)
    return results


def _is_color_param_name(name: str) -> bool:
    """Check if a param name indicates a color value.

    Args:
        name: Normalized (lowercase) parameter name.

    Returns:
        True if the param name is a known color param.
    """
    if name in _COLOR_PARAM_PATTERNS:
        return True
    if name.startswith(_COLOR_PARAM_PREFIX):
        return True
    if name.endswith(_COLOR_PARAM_SUFFIX):
        return True
    return False


def _hex_to_hsv(hex_color: str) -> tuple[float, float, float]:
    """Convert a hex color to HSV (hue in degrees 0-360, sat 0-1, val 0-1).

    Args:
        hex_color: Normalized hex color string (e.g. '#FF0000').

    Returns:
        (hue_degrees, saturation, value) tuple.
    """
    hex_str = hex_color.lstrip("#")
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360.0, s, v


def _hue_bin_for_hex(hex_color: str) -> str:
    """Determine the hue bin name for a hex color.

    Args:
        hex_color: Normalized hex color string.

    Returns:
        Hue bin name string.
    """
    hue_deg, saturation, _ = _hex_to_hsv(hex_color)

    if saturation < _ACHROMATIC_SATURATION_THRESHOLD:
        return "achromatic"

    for bin_name, low, high in _HUE_BINS:
        if low <= hue_deg < high:
            # Map red_wrap back to red.
            if bin_name == "red_wrap":
                return "red"
            return bin_name

    # Fallback (should not happen with correct bin boundaries).
    return "red"


def _deduplicate_preserve_order(items: list[str]) -> list[str]:
    """Deduplicate a list while preserving insertion order.

    Args:
        items: List of strings.

    Returns:
        Deduplicated list preserving first occurrence order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _humanize_bin_name(bin_name: str) -> str:
    """Convert a hue bin name to a human-readable label.

    Args:
        bin_name: Internal bin name (e.g. 'yellow_green').

    Returns:
        Title-cased human-readable string.
    """
    return bin_name.replace("_", " ").title()
