"""Template-to-effect mapping for the display renderer.

Maps group template IDs (gtpl_*) to xLights effect types with
energy-appropriate parameter presets.

Group templates define visual intent (motifs, motion, depth) but do NOT
specify xLights effect types. This module bridges that gap using:
1. Explicit mappings for known template IDs (with preset parameters).
2. Keyword-based heuristics for unknown templates (with energy detection).
3. Fallback to "On" for completely unrecognized templates.

Parameter presets are organized by **energy level**:
- ambient: Gentle, slow, low density (base layers)
- drive:   Moderate speed, rhythmic movement (rhythm layers)
- hit_small: Quick, compact punch (small accents)
- hit_big:   Dramatic, high-count, aggressive (big accents)
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class EffectMapping(BaseModel):
    """Mapping from a template to an xLights effect type with defaults.

    Attributes:
        effect_type: xLights effect type name (e.g., 'Color Wash').
        defaults: Default parameter overrides for this mapping.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_type: str = Field(description="xLights effect type name")
    defaults: dict[str, Any] = Field(
        default_factory=dict,
        description="Default parameter overrides",
    )


# ===================================================================
# Preset profiles — per effect type × energy level
# ===================================================================
# Keys match the parameter names handlers read via params.get().

_COLOR_WASH_PRESETS: dict[str, dict[str, Any]] = {
    "ambient": {
        "speed": 20,
        "cycles": 1.0,
        "horizontal_fade": True,
        "vertical_fade": False,
        "shimmer": False,
    },
    "drive": {
        "speed": 50,
        "cycles": 2.0,
        "horizontal_fade": True,
        "vertical_fade": False,
        "shimmer": True,
    },
    "hit_small": {
        "speed": 80,
        "cycles": 1.0,
        "horizontal_fade": False,
        "vertical_fade": False,
        "shimmer": True,
    },
    "hit_big": {
        "speed": 100,
        "cycles": 1.5,
        "horizontal_fade": False,
        "vertical_fade": False,
        "shimmer": True,
    },
}

_SPIRALS_PRESETS: dict[str, dict[str, Any]] = {
    "ambient": {
        "palette_count": 2,
        "movement": 0.5,
        "rotation": 10,
        "thickness": 60,
        "blend": True,
        "3d": False,
    },
    "drive": {
        "palette_count": 4,
        "movement": 2.0,
        "rotation": 50,
        "thickness": 40,
        "blend": False,
        "3d": False,
    },
    "hit_small": {
        "palette_count": 3,
        "movement": 3.0,
        "rotation": 80,
        "thickness": 30,
        "blend": False,
        "3d": False,
    },
    "hit_big": {
        "palette_count": 5,
        "movement": 4.0,
        "rotation": 100,
        "thickness": 25,
        "blend": False,
        "3d": True,
    },
}

_TWINKLE_PRESETS: dict[str, dict[str, Any]] = {
    "ambient": {
        "count": 3,
        "steps": 40,
        "strobe": False,
        "re_random": False,
    },
    "drive": {
        "count": 8,
        "steps": 20,
        "strobe": False,
        "re_random": True,
    },
    "hit_small": {
        "count": 15,
        "steps": 10,
        "strobe": True,
        "re_random": True,
    },
    "hit_big": {
        "count": 25,
        "steps": 5,
        "strobe": True,
        "re_random": True,
    },
}

_METEORS_PRESETS: dict[str, dict[str, Any]] = {
    "ambient": {
        "count": 5,
        "length": 40,
        "speed": 5,
        "swirl_intensity": 0,
        "direction": "Down",
        "color_type": "Palette",
    },
    "drive": {
        "count": 15,
        "length": 30,
        "speed": 15,
        "swirl_intensity": 10,
        "direction": "Down",
        "color_type": "Palette",
    },
    "hit_small": {
        "count": 20,
        "length": 20,
        "speed": 25,
        "swirl_intensity": 20,
        "direction": "Down",
        "color_type": "Palette",
    },
    "hit_big": {
        "count": 30,
        "length": 15,
        "speed": 35,
        "swirl_intensity": 30,
        "direction": "Explode",
        "color_type": "Palette",
    },
}

_FAN_PRESETS: dict[str, dict[str, Any]] = {
    "ambient": {
        "num_blades": 8,
        "blade_width": 60,
        "revolutions": 100,
        "start_radius": 1,
        "end_radius": 250,
        "num_elements": 1,
        "blend_edges": True,
        "reverse": False,
    },
    "drive": {
        "num_blades": 16,
        "blade_width": 42,
        "revolutions": 276,
        "start_radius": 1,
        "end_radius": 250,
        "num_elements": 1,
        "blend_edges": True,
        "reverse": False,
    },
    "hit_small": {
        "num_blades": 12,
        "blade_width": 50,
        "revolutions": 400,
        "start_radius": 1,
        "end_radius": 200,
        "num_elements": 1,
        "blend_edges": True,
        "reverse": False,
    },
    "hit_big": {
        "num_blades": 20,
        "blade_width": 35,
        "revolutions": 500,
        "start_radius": 1,
        "end_radius": 250,
        "num_elements": 2,
        "blend_edges": True,
        "reverse": False,
    },
}

_SHOCKWAVE_PRESETS: dict[str, dict[str, Any]] = {
    "hit_small": {
        "start_radius": 1,
        "end_radius": 200,
        "start_width": 60,
        "end_width": 5,
        "accel": 3,
        "blend_edges": True,
    },
    "hit_big": {
        "start_radius": 1,
        "end_radius": 250,
        "start_width": 99,
        "end_width": 10,
        "accel": 5,
        "blend_edges": True,
    },
}

_STROBE_PRESETS: dict[str, dict[str, Any]] = {
    "hit_small": {
        "num_strobes": 200,
        "strobe_duration": 2,
        "strobe_type": 3,
        "music_reactive": False,
    },
    "hit_big": {
        "num_strobes": 400,
        "strobe_duration": 1,
        "strobe_type": 3,
        "music_reactive": False,
    },
}

_ON_PRESETS: dict[str, dict[str, Any]] = {
    "hit_small": {"_preset": "hit_small"},
    "hit_big": {"_preset": "hit_big"},
}

_SNOWFLAKES_PRESETS: dict[str, dict[str, Any]] = {
    "ambient": {
        "count": 50,
        "speed": 30,
        "snowflake_type": 1,
    },
    "hit_small": {
        "count": 100,
        "speed": 60,
        "snowflake_type": 2,
    },
    "hit_big": {
        "count": 200,
        "speed": 80,
        "snowflake_type": 3,
    },
}

_MARQUEE_PRESETS: dict[str, dict[str, Any]] = {
    "drive": {
        "band_size": 39,
        "skip_size": 44,
        "speed": 50,
        "stagger": 16,
        "thickness": 100,
    },
}

_SINGLE_STRAND_PRESETS: dict[str, dict[str, Any]] = {
    "drive": {
        "chase_type": "Left-Right",
        "speed": 50,
        "color_chase": True,
        "group_count": 3,
    },
}


# ===================================================================
# Preset lookup by effect type
# ===================================================================

_EFFECT_PRESETS: dict[str, dict[str, dict[str, Any]]] = {
    "Color Wash": _COLOR_WASH_PRESETS,
    "Spirals": _SPIRALS_PRESETS,
    "Twinkle": _TWINKLE_PRESETS,
    "Meteors": _METEORS_PRESETS,
    "Fan": _FAN_PRESETS,
    "Shockwave": _SHOCKWAVE_PRESETS,
    "Strobe": _STROBE_PRESETS,
    "On": _ON_PRESETS,
    "Snowflakes": _SNOWFLAKES_PRESETS,
    "Marquee": _MARQUEE_PRESETS,
    "SingleStrand": _SINGLE_STRAND_PRESETS,
}


def _get_preset(effect_type: str, energy: str) -> dict[str, Any]:
    """Look up a preset for an effect type and energy level.

    Falls back through: exact energy → "drive" → "ambient" → first
    available → empty dict.

    Args:
        effect_type: xLights effect type name.
        energy: Energy level (ambient, drive, hit_small, hit_big).

    Returns:
        Parameter dict (may be empty if no presets exist).
    """
    presets = _EFFECT_PRESETS.get(effect_type)
    if not presets:
        return {}

    if energy in presets:
        return dict(presets[energy])

    # Fallback chain
    for fallback in ("drive", "ambient"):
        if fallback in presets:
            return dict(presets[fallback])

    # Use first available preset
    first = next(iter(presets.values()), {})
    return dict(first)


# ===================================================================
# Valid parameter keys per effect type (handler allowlist)
# ===================================================================
# Only these keys are safe to merge from param_overrides. Planning-level
# params (motif_bias, beacon_color, decay, feel, etc.) are LLM hints
# that use different vocabularies and value ranges and must NOT leak
# into xLights settings strings.

_VALID_PARAMS: dict[str, frozenset[str]] = {
    "Color Wash": frozenset({
        "horizontal_fade", "vertical_fade", "shimmer", "cycles", "speed",
    }),
    "Spirals": frozenset({
        "palette_count", "movement", "rotation", "thickness",
        "blend", "3d", "grow", "shrink",
    }),
    "Twinkle": frozenset({
        "count", "steps", "strobe", "re_random", "style",
    }),
    "Meteors": frozenset({
        "count", "length", "speed", "swirl_intensity",
        "direction", "color_type", "music_reactive",
    }),
    "Fan": frozenset({
        "num_blades", "blade_width", "revolutions", "start_angle",
        "start_radius", "end_radius", "center_x", "center_y",
        "duration", "num_elements", "blend_edges", "reverse",
    }),
    "Shockwave": frozenset({
        "start_radius", "end_radius", "start_width", "end_width",
        "center_x", "center_y", "accel", "blend_edges", "scale",
    }),
    "Strobe": frozenset({
        "num_strobes", "strobe_duration", "strobe_type", "music_reactive",
    }),
    "On": frozenset(),  # On uses intensity, not params
    "Snowflakes": frozenset({
        "count", "speed", "snowflake_type",
    }),
    "Marquee": frozenset({
        "band_size", "skip_size", "speed", "stagger", "start",
        "thickness", "reverse", "wrap_x", "wrap_y",
    }),
    "SingleStrand": frozenset({
        "chase_type", "speed", "color_chase", "group_count",
        "chase_rotations",
    }),
    "Pictures": frozenset({
        "filename", "movement", "direction", "speed",
    }),
}


def filter_valid_overrides(
    effect_type: str,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Filter param_overrides to only handler-recognized keys with valid values.

    Two-stage filtering:
    1. **Key filter**: Only handler-recognized parameter names pass.
    2. **Value filter**: Values must match the expected type for that
       parameter. Planning params often reuse key names like ``speed``
       or ``direction`` but with incompatible values (0.55 vs int 1-50,
       ``"forward"`` vs ``"Down"``).

    Args:
        effect_type: xLights effect type name.
        overrides: Raw param_overrides from the plan.

    Returns:
        Filtered dict with only valid handler keys and values.
    """
    valid_keys = _VALID_PARAMS.get(effect_type)
    if not valid_keys or not overrides:
        return {}

    filtered: dict[str, Any] = {}
    for k, v in overrides.items():
        if k not in valid_keys:
            continue
        # Validate value type/range against handler expectations
        if not _is_valid_param_value(effect_type, k, v):
            logger.debug(
                "Rejected param_override %s=%r for %s (invalid value)",
                k,
                v,
                effect_type,
            )
            continue
        filtered[k] = v

    dropped = len(overrides) - len(filtered)
    if dropped:
        logger.debug(
            "Filtered %d param_overrides for %s (kept %d valid)",
            dropped,
            effect_type,
            len(filtered),
        )
    return filtered


def _is_valid_param_value(effect_type: str, key: str, value: Any) -> bool:
    """Check whether a param_override value is valid for an xLights handler.

    Rejects:
    - Strings for numeric parameters (e.g., speed="fast")
    - Normalized floats (0-1) for integer slider ranges (e.g., speed=0.55)
    - Invalid option strings for choice parameters

    Args:
        effect_type: xLights effect type name.
        key: Parameter key name.
        value: Proposed value.

    Returns:
        True if the value is acceptable for the handler.
    """
    # Check against known choice constraints
    constraints = _CHOICE_CONSTRAINTS.get(effect_type, {}).get(key)
    if constraints is not None:
        return value in constraints

    # For boolean params, accept bool only
    if key in _BOOLEAN_PARAMS:
        return isinstance(value, bool)

    # For numeric params: reject strings, reject normalized 0-1 floats
    # (planning uses 0.0-1.0 scale; xLights uses integer ranges like 1-50)
    if isinstance(value, str):
        return False
    if isinstance(value, float) and 0.0 < value < 1.0:
        # Likely a planning-level normalized value, not an xLights integer
        return False

    return True


# Choice parameter constraints — valid option values
_CHOICE_CONSTRAINTS: dict[str, dict[str, frozenset[str]]] = {
    "Meteors": {
        "direction": frozenset({
            "Down", "Up", "Left", "Right",
            "Explode", "Implode", "Icicles", "Icicles + bkg",
        }),
        "color_type": frozenset({"Palette", "Rainbow"}),
    },
    "SingleStrand": {
        "chase_type": frozenset({
            "Left-Right", "Right-Left",
            "Bounce from Left", "Bounce from Right", "Dual Bounce",
        }),
    },
    "Twinkle": {
        "style": frozenset({"New Render Method", "Old Render Method"}),
    },
}

# Boolean parameter names (across all handlers)
_BOOLEAN_PARAMS: frozenset[str] = frozenset({
    "horizontal_fade", "vertical_fade", "shimmer",
    "blend", "3d", "grow", "shrink",
    "strobe", "re_random",
    "music_reactive",
    "blend_edges", "reverse", "scale",
    "color_chase",
    "wrap_x", "wrap_y",
})


# ===================================================================
# Energy detection from template ID
# ===================================================================


def _detect_energy(template_id: str) -> str:
    """Detect energy level from a template ID.

    Examines the template ID for lane and size hints:
    - hit_big, burst_big → hit_big
    - hit_small, burst_small, bell → hit_small
    - drive, beat, offbeat → drive
    - ambient, haze, soft, low → ambient

    Falls back to lane prefix: accent → hit_small, rhythm → drive,
    base → ambient.

    Args:
        template_id: Template ID string.

    Returns:
        Energy level string.
    """
    tid = template_id.lower()

    # Size-specific hits
    if "hit_big" in tid or "burst_big" in tid or "shower" in tid:
        return "hit_big"
    if "hit_small" in tid or "burst_small" in tid:
        return "hit_small"
    if "bell" in tid or "cut_to" in tid:
        return "hit_small"

    # Energy keywords
    if "drive" in tid or "beat" in tid or "offbeat" in tid or "scroll" in tid:
        return "drive"
    if "ambient" in tid or "haze" in tid or "soft" in tid or "low" in tid:
        return "ambient"

    # Lane-based fallback
    if "accent" in tid:
        return "hit_small"
    if "rhythm" in tid:
        return "drive"
    return "ambient"


# ===================================================================
# Keyword → effect type heuristics
# ===================================================================
# Order matters: first match wins. More specific keywords first.

_KEYWORD_RULES: list[tuple[list[str], str]] = [
    # Asset display
    (["picture", "image", "cutout", "texture", "asset"], "Pictures"),
    # Specific effect families
    (["chase", "alternate", "marquee_scroll"], "SingleStrand"),
    (["spiral", "candy_stripe", "candy_stripes"], "Spirals"),
    (["wash", "gradient", "abstract", "bokeh"], "Color Wash"),
    (["snow", "snowflake", "ornament", "ornaments"], "Snowflakes"),
    (["sparkle", "twinkle", "shimmer"], "Twinkle"),
    (["pulse", "throb"], "Color Wash"),
    (["strobe", "flash"], "Strobe"),
    (["fan", "radial_ray", "radial_rays"], "Fan"),
    (["pinwheel"], "Pinwheel"),
    (["shockwave", "burst"], "Shockwave"),
    (["marquee"], "Marquee"),
    (["meteor", "spark_shower", "light_trail", "light_trails"], "Meteors"),
    (["sweep", "wave_band", "wave_bands", "wave_lr", "wave"], "Color Wash"),
    (["ripple"], "Ripple"),
    (["fire", "flicker"], "Fire"),
    (["glow", "vignette"], "Color Wash"),
    (["starfield"], "Twinkle"),
    (["ambient"], "Color Wash"),
    # Accent hits → On (quick flash)
    (["hit", "bell", "cut_to"], "On"),
]


def resolve_effect_type(template_id: str) -> EffectMapping:
    """Resolve a template_id to an xLights effect type with parameters.

    Strategy:
    1. Check explicit mapping table.
    2. Parse template_id keywords against heuristic rules, with
       energy-aware parameter presets.
    3. Fall back to On effect.

    Args:
        template_id: Group template ID (e.g., 'gtpl_base_wash_soft').

    Returns:
        EffectMapping with the resolved xLights effect type and defaults.
    """
    # 1. Check explicit overrides
    if template_id in _EXPLICIT_MAP:
        return _EXPLICIT_MAP[template_id]

    # 2. Keyword heuristic: parse template_id into tokens
    # Strip gtpl_ prefix and lane prefix for keyword matching
    tokens = template_id.lower().replace("gtpl_", "").split("_")
    # Remove common lane prefixes for cleaner matching
    lane_prefixes = {"base", "rhythm", "accent", "transition", "special"}
    content_tokens = [t for t in tokens if t not in lane_prefixes]
    # Also check against the full id minus gtpl_ prefix
    full_content = "_".join(content_tokens)

    for keywords, effect_type in _KEYWORD_RULES:
        for keyword in keywords:
            # Match against individual tokens or the joined content
            if keyword in content_tokens or keyword in full_content:
                energy = _detect_energy(template_id)
                defaults = _get_preset(effect_type, energy)
                logger.debug(
                    "Matched template '%s' to '%s' via keyword '%s' "
                    "(energy=%s, %d params)",
                    template_id,
                    effect_type,
                    keyword,
                    energy,
                    len(defaults),
                )
                return EffectMapping(effect_type=effect_type, defaults=defaults)

    # 3. Fallback
    energy = _detect_energy(template_id)
    defaults = _get_preset("On", energy)
    logger.warning(
        "No effect mapping for template '%s', falling back to 'On' (energy=%s)",
        template_id,
        energy,
    )
    return EffectMapping(effect_type="On", defaults=defaults)


# ===================================================================
# Explicit mapping overrides
# ===================================================================
# These take priority over keyword heuristics. Add entries here when
# the keyword approach gives wrong results or when specific parameter
# tuning is needed.

_EXPLICIT_MAP: dict[str, EffectMapping] = {
    # -----------------------------------------------------------------
    # BASE — gentle ambient fills
    # -----------------------------------------------------------------
    "gtpl_base_motif_abstract_ambient": EffectMapping(
        effect_type="Color Wash",
        defaults=_COLOR_WASH_PRESETS["ambient"],
    ),
    "gtpl_base_motif_bokeh_ambient": EffectMapping(
        effect_type="Color Wash",
        defaults={**_COLOR_WASH_PRESETS["ambient"], "vertical_fade": True},
    ),
    "gtpl_base_motif_candy_stripes_ambient": EffectMapping(
        effect_type="Spirals",
        defaults=_SPIRALS_PRESETS["ambient"],
    ),
    "gtpl_base_motif_sparkles_ambient": EffectMapping(
        effect_type="Twinkle",
        defaults=_TWINKLE_PRESETS["ambient"],
    ),
    "gtpl_base_motif_radial_rays_ambient": EffectMapping(
        effect_type="Fan",
        defaults=_FAN_PRESETS["ambient"],
    ),
    "gtpl_base_motif_wave_bands_ambient": EffectMapping(
        effect_type="Color Wash",
        defaults={**_COLOR_WASH_PRESETS["ambient"], "vertical_fade": True, "speed": 25},
    ),
    "gtpl_base_motif_light_trails_ambient": EffectMapping(
        effect_type="Meteors",
        defaults=_METEORS_PRESETS["ambient"],
    ),
    "gtpl_base_snow_haze_low": EffectMapping(
        effect_type="Snowflakes",
        defaults=_SNOWFLAKES_PRESETS["ambient"],
    ),
    # -----------------------------------------------------------------
    # RHYTHM — moderate energy, rhythmic motion
    # -----------------------------------------------------------------
    "gtpl_rhythm_motif_candy_stripes_drive": EffectMapping(
        effect_type="Spirals",
        defaults=_SPIRALS_PRESETS["drive"],
    ),
    "gtpl_rhythm_motif_radial_rays_drive": EffectMapping(
        effect_type="Fan",
        defaults=_FAN_PRESETS["drive"],
    ),
    "gtpl_rhythm_motif_sparkles_drive": EffectMapping(
        effect_type="Twinkle",
        defaults=_TWINKLE_PRESETS["drive"],
    ),
    "gtpl_rhythm_motif_abstract_drive": EffectMapping(
        effect_type="Color Wash",
        defaults=_COLOR_WASH_PRESETS["drive"],
    ),
    "gtpl_rhythm_motif_wave_bands_drive": EffectMapping(
        effect_type="Color Wash",
        defaults={**_COLOR_WASH_PRESETS["drive"], "vertical_fade": True},
    ),
    "gtpl_rhythm_motif_light_trails_drive": EffectMapping(
        effect_type="Meteors",
        defaults=_METEORS_PRESETS["drive"],
    ),
    "gtpl_rhythm_motif_bokeh_drive": EffectMapping(
        effect_type="Color Wash",
        defaults={**_COLOR_WASH_PRESETS["drive"], "vertical_fade": True},
    ),
    "gtpl_rhythm_candy_stripe_scroll": EffectMapping(
        effect_type="Marquee",
        defaults=_MARQUEE_PRESETS["drive"],
    ),
    "gtpl_rhythm_sparkle_beat": EffectMapping(
        effect_type="Twinkle",
        defaults={**_TWINKLE_PRESETS["drive"], "count": 10},
    ),
    "gtpl_rhythm_sparkle_offbeat": EffectMapping(
        effect_type="Twinkle",
        defaults=_TWINKLE_PRESETS["drive"],
    ),
    "gtpl_rhythm_alternate_ab": EffectMapping(
        effect_type="SingleStrand",
        defaults=_SINGLE_STRAND_PRESETS["drive"],
    ),
    "gtpl_rhythm_alternate_triplet": EffectMapping(
        effect_type="SingleStrand",
        defaults={
            **_SINGLE_STRAND_PRESETS["drive"],
            "chase_type": "Bounce from Left",
            "speed": 60,
            "group_count": 2,
        },
    ),
    # -----------------------------------------------------------------
    # ACCENT — punchy hits and bursts
    # -----------------------------------------------------------------
    "gtpl_accent_bell_single": EffectMapping(
        effect_type="On",
        defaults=_ON_PRESETS["hit_small"],
    ),
    "gtpl_accent_bell_double": EffectMapping(
        effect_type="On",
        defaults=_ON_PRESETS["hit_big"],
    ),
    "gtpl_accent_burst_small": EffectMapping(
        effect_type="Shockwave",
        defaults=_SHOCKWAVE_PRESETS["hit_small"],
    ),
    "gtpl_accent_burst_big": EffectMapping(
        effect_type="Shockwave",
        defaults=_SHOCKWAVE_PRESETS["hit_big"],
    ),
    "gtpl_accent_motif_sparkles_hit_small": EffectMapping(
        effect_type="Strobe",
        defaults=_STROBE_PRESETS["hit_small"],
    ),
    "gtpl_accent_motif_sparkles_hit_big": EffectMapping(
        effect_type="Strobe",
        defaults=_STROBE_PRESETS["hit_big"],
    ),
    "gtpl_accent_motif_radial_rays_hit_small": EffectMapping(
        effect_type="Fan",
        defaults=_FAN_PRESETS["hit_small"],
    ),
    "gtpl_accent_motif_radial_rays_hit_big": EffectMapping(
        effect_type="Fan",
        defaults=_FAN_PRESETS["hit_big"],
    ),
    "gtpl_accent_motif_candy_stripes_hit_small": EffectMapping(
        effect_type="Spirals",
        defaults=_SPIRALS_PRESETS["hit_small"],
    ),
    "gtpl_accent_motif_candy_stripes_hit_big": EffectMapping(
        effect_type="Spirals",
        defaults=_SPIRALS_PRESETS["hit_big"],
    ),
    "gtpl_accent_motif_light_trails_hit_small": EffectMapping(
        effect_type="Meteors",
        defaults=_METEORS_PRESETS["hit_small"],
    ),
    "gtpl_accent_motif_light_trails_hit_big": EffectMapping(
        effect_type="Meteors",
        defaults=_METEORS_PRESETS["hit_big"],
    ),
    "gtpl_accent_motif_snowflakes_hit_big": EffectMapping(
        effect_type="Snowflakes",
        defaults=_SNOWFLAKES_PRESETS["hit_big"],
    ),
    "gtpl_accent_motif_ornaments_hit_small": EffectMapping(
        effect_type="Snowflakes",
        defaults=_SNOWFLAKES_PRESETS["hit_small"],
    ),
    "gtpl_accent_spark_shower_up": EffectMapping(
        effect_type="Meteors",
        defaults={**_METEORS_PRESETS["hit_big"], "direction": "Up"},
    ),
    "gtpl_accent_cut_to_sparkle": EffectMapping(
        effect_type="Strobe",
        defaults=_STROBE_PRESETS["hit_small"],
    ),
}


__all__ = [
    "EffectMapping",
    "filter_valid_overrides",
    "resolve_effect_type",
]
