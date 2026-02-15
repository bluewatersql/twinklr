"""Motif-primary effect resolver for the display rendering pipeline.

Resolves a ``LayerRecipe`` to an xLights effect configuration using a
three-tier strategy:

1. **Motifs** (primary) — selects WHICH xLights effect to use.
2. **MotionVerb** (secondary) — selects HOW the effect behaves (curves/presets).
3. **Density / contrast** (tertiary) — scales quantity and intensity parameters.

This replaces the old keyword-matching ``resolve_effect_type()`` in
``effect_map.py`` which only looked at the template ID string and
always returned a single effect type.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from twinklr.core.curves.library import CurveLibrary
from twinklr.core.sequencer.display.composition.value_curves import (
    build_value_curve_string,
)
from twinklr.core.sequencer.vocabulary.motion import MotionVerb
from twinklr.core.sequencer.vocabulary.visual import VisualDepth

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Output model
# ------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedEffect:
    """Result of resolving a LayerRecipe to an xLights effect configuration.

    Attributes:
        effect_type: xLights effect name (e.g., ``"Twinkle"``).
        parameters: Static params from motif + density/contrast scaling.
        value_curves: Animated params from motion verb modulation.
        buffer_style: xLights buffer style.
        buffer_transform: Optional buffer transform.
    """

    effect_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    value_curves: dict[str, str] = field(default_factory=dict)
    buffer_style: str = "Per Model Default"
    buffer_transform: str | None = None


# ------------------------------------------------------------------
# Tier 1: Motif → Effect Type mapping
# ------------------------------------------------------------------
#
# Each entry maps a motif string to its natural xLights effect type
# and a base preset of parameters.  Motifs are tried first-match from
# the LayerRecipe's motif list; more specific motifs should appear
# earlier in each recipe.
#
# This is the primary extensibility point: adding a new xLights effect
# requires adding new motif entries here (and an EffectHandler if one
# doesn't exist yet).  The full 50+ xLights effect set is reachable
# through appropriate motif strings — not bottlenecked by MotionVerbs.

_MOTIF_TO_EFFECT: dict[str, tuple[str, dict[str, Any]]] = {
    # ---- Radial / circular ----
    "radial_rays": ("Fan", {"num_blades": 16, "blade_width": 42, "revolutions": 276}),
    "fan": ("Fan", {"num_blades": 12, "blade_width": 50, "revolutions": 200}),
    "concentric_rings": ("Shockwave", {"start_radius": 1, "end_radius": 200}),
    "shockwave": ("Shockwave", {"start_radius": 1, "end_radius": 250}),
    "ripple": ("Ripple", {"object_to_draw": "Circle", "movement": "Explode"}),
    "ring": ("Ripple", {"object_to_draw": "Circle", "movement": "Explode"}),
    "pinwheel": ("Pinwheel", {"arms": 4, "twist": 30, "speed": 15}),
    "rotate": ("Pinwheel", {"arms": 3, "twist": 0, "speed": 10}),
    "rotation": ("Pinwheel", {"arms": 3, "twist": 0, "speed": 10}),
    # ---- Spiral / helical ----
    "spiral": ("Spirals", {"palette_count": 4, "rotation": 50, "thickness": 40}),
    "helix": ("Spirals", {"palette_count": 4, "rotation": 80, "thickness": 30}),
    "stripes": ("Spirals", {"palette_count": 3, "rotation": 30, "thickness": 50}),
    "candy_stripes": ("Spirals", {"palette_count": 3, "rotation": 30, "thickness": 50}),
    "ribbons": ("Spirals", {"palette_count": 2, "rotation": 20, "thickness": 60}),
    # ---- Weather / nature ----
    "snowflakes": ("Snowflakes", {"count": 100, "speed": 50}),
    "snow": ("Snowflakes", {"count": 80, "speed": 40}),
    "ornaments": ("Snowflakes", {"count": 60, "speed": 30, "snowflake_type": 2}),
    "fire": ("Fire", {"height": 60, "grow_with_music": True}),
    "candle": ("Fire", {"height": 30, "grow_with_music": False}),
    "rain": ("Meteors", {"count": 20, "direction": "Down", "speed": 15}),
    "water": ("Ripple", {"object_to_draw": "Circle", "movement": "Explode", "cycles": 2.0}),
    # ---- Particle / scatter ----
    "sparkles": ("Twinkle", {"count": 10, "steps": 20, "re_random": True}),
    "sparkle": ("Twinkle", {"count": 10, "steps": 20, "re_random": True}),
    "confetti": ("Twinkle", {"count": 15, "steps": 15, "re_random": True}),
    "stars": ("Twinkle", {"count": 8, "steps": 25}),
    "twinkle": ("Twinkle", {"count": 5, "steps": 30}),
    "dots": ("Twinkle", {"count": 12, "steps": 18, "re_random": True}),
    "particles": ("Twinkle", {"count": 12, "steps": 15, "re_random": True}),
    # ---- Meteor / trail ----
    "light_trails": ("Meteors", {"count": 15, "length": 30, "speed": 15}),
    "comet": ("Meteors", {"count": 5, "length": 50, "speed": 20}),
    "meteor": ("Meteors", {"count": 10, "length": 25, "speed": 25}),
    "fountain": ("Meteors", {"count": 20, "direction": "Up", "speed": 20}),
    # ---- Chase / sequential ----
    "chase": ("SingleStrand", {"chase_type": "Left-Right", "speed": 50}),
    "sequence": ("SingleStrand", {"chase_type": "Left-Right", "speed": 40}),
    "sequential": ("SingleStrand", {"chase_type": "Left-Right", "speed": 40}),
    "random_chase": ("SingleStrand", {"chase_type": "Left-Right", "speed": 60}),
    "alternate": ("SingleStrand", {"chase_type": "Bounce from Left", "speed": 50}),
    "pingpong": ("SingleStrand", {"chase_type": "Bounce from Left", "speed": 50}),
    "rollcall": ("SingleStrand", {"chase_type": "Left-Right", "speed": 30}),
    # ---- Marquee / band ----
    "chevrons": ("Marquee", {"band_size": 39, "skip_size": 44, "speed": 50}),
    "zigzag": ("Marquee", {"band_size": 30, "skip_size": 30, "speed": 40}),
    "stripe": ("Marquee", {"band_size": 50, "skip_size": 50, "speed": 30}),
    "segment_pulses": ("Marquee", {"band_size": 20, "skip_size": 30, "speed": 40}),
    # ---- Flash / strobe ----
    "flash": ("Strobe", {"num_strobes": 300, "strobe_duration": 2}),
    "strobe": ("Strobe", {"num_strobes": 400, "strobe_duration": 1}),
    "lightning": ("Strobe", {"num_strobes": 200, "strobe_duration": 3}),
    "flicker": ("Fire", {"height": 40, "grow_with_music": False}),
    # ---- Wash / ambient ----
    "wash": ("Color Wash", {"speed": 30, "horizontal_fade": True}),
    "gradient": ("Color Wash", {"speed": 20, "horizontal_fade": True}),
    "gradient_scroll": ("Color Wash", {"speed": 40, "shimmer": True}),
    "gradient_bands": ("Color Wash", {"speed": 25, "cycles": 2.0}),
    "abstract": ("Color Wash", {"speed": 25, "shimmer": False}),
    "bokeh": ("Color Wash", {"speed": 20, "vertical_fade": True}),
    "vignette": ("Color Wash", {"speed": 15, "vertical_fade": True}),
    "glow": ("Color Wash", {"speed": 10, "horizontal_fade": True}),
    "haze": ("Color Wash", {"speed": 15, "shimmer": False}),
    "ambient": ("Color Wash", {"speed": 20}),
    "bed": ("Color Wash", {"speed": 20, "horizontal_fade": True}),
    "blend": ("Color Wash", {"speed": 25, "horizontal_fade": True}),
    "color": ("Color Wash", {"speed": 25}),
    "warm": ("Color Wash", {"speed": 15}),
    "cool": ("Color Wash", {"speed": 15}),
    "atmospheric": ("Color Wash", {"speed": 15, "shimmer": False}),
    "smoke": ("Color Wash", {"speed": 10, "shimmer": False}),
    "clouds": ("Color Wash", {"speed": 10, "vertical_fade": True}),
    "ice": ("Color Wash", {"speed": 15}),
    # ---- Cosmic / special ----
    "cosmic": ("Fan", {"num_blades": 20, "blade_width": 35, "revolutions": 500}),
    "starburst": ("Shockwave", {"start_radius": 1, "end_radius": 250}),
    "explosion": ("Shockwave", {"start_radius": 1, "end_radius": 250, "accel": 5}),
    "burst": ("Shockwave", {"start_radius": 1, "end_radius": 200}),
    "flares": ("Fan", {"num_blades": 10, "blade_width": 60, "revolutions": 300}),
    "spotlight": ("Fan", {"num_blades": 1, "blade_width": 100, "revolutions": 50}),
    # ---- Directional ----
    "sweep": ("Color Wash", {"speed": 60, "shimmer": True}),
    "wave": ("Color Wash", {"speed": 40, "cycles": 2.0}),
    "wave_bands": ("Color Wash", {"speed": 35, "cycles": 2.0, "vertical_fade": True}),
    "scroll": ("Marquee", {"band_size": 40, "speed": 50}),
    "wipe": ("Color Wash", {"speed": 80, "horizontal_fade": False}),
    "color_wipe": ("Color Wash", {"speed": 80, "horizontal_fade": False}),
    # ---- On/impact ----
    "hit": ("On", {}),
    "impact": ("On", {}),
    "slam": ("On", {}),
    "pop": ("On", {}),
    "bell": ("On", {}),
    "ding": ("On", {}),
    "all-on": ("On", {}),
    # ---- Support / structural (low-visual-weight) ----
    "support": ("Color Wash", {"speed": 15, "shimmer": False}),
    "hold": ("On", {}),
    "static": ("On", {}),
    "freeze": ("On", {}),
    "blackout": ("On", {}),
    "dropout": ("On", {}),
    # ---- Pulse / beat ----
    "pulse": ("Strobe", {"num_strobes": 200, "strobe_duration": 4}),
    "rhythmic": ("Strobe", {"num_strobes": 250, "strobe_duration": 3}),
    # ---- Shimmer / atmospheric ----
    "shimmer": ("Color Wash", {"speed": 30, "shimmer": True}),
    "moody": ("Color Wash", {"speed": 10, "shimmer": False, "vertical_fade": True}),
    "sparse": ("Twinkle", {"count": 3, "steps": 40}),
    # ---- Nature extended ----
    "crystals": ("Snowflakes", {"count": 50, "speed": 25, "snowflake_type": 2}),
    # ---- Geometric extended ----
    "geometric": ("Spirals", {"palette_count": 3, "rotation": 40, "thickness": 40}),
    "grid": ("Marquee", {"band_size": 25, "skip_size": 25, "speed": 30}),
    "checker": ("Marquee", {"band_size": 50, "skip_size": 50, "speed": 20}),
    # ---- Strand / sequential extended ----
    "strand": ("SingleStrand", {"chase_type": "Left-Right", "speed": 45}),
    "call": ("SingleStrand", {"chase_type": "Bounce from Left", "speed": 40}),
    # ---- Spark / fountain ----
    "spark": ("Meteors", {"count": 10, "length": 15, "speed": 25}),
    # ---- Vertical / cascade ----
    "drip": ("Meteors", {"count": 15, "direction": "Down", "speed": 20}),
    "push": ("SingleStrand", {"chase_type": "Left-Right", "speed": 80}),
    # ---- Bounce ----
    "bounce": ("SingleStrand", {"chase_type": "Bounce from Left", "speed": 60}),
    # ---- Emphasis ----
    "underline": ("Strobe", {"num_strobes": 150, "strobe_duration": 3}),
    # ---- Transitions ----
    "fade": ("Color Wash", {"speed": 20, "horizontal_fade": True}),
    "crossfade": ("Color Wash", {"speed": 30, "horizontal_fade": True}),
    "ramp": ("Color Wash", {"speed": 40, "shimmer": False}),
    "swap": ("Color Wash", {"speed": 50, "shimmer": False}),
    "build": ("Color Wash", {"speed": 35, "shimmer": False}),
}

# Effects that render better with centered overlay buffers.
_CENTERED_EFFECTS: frozenset[str] = frozenset(
    {
        "Fan",
        "Shockwave",
        "Pinwheel",
        "Ripple",
        "Fire",
    }
)


# ------------------------------------------------------------------
# Tier 2: MotionVerb → behaviour modulation
# ------------------------------------------------------------------
#
# Each MotionVerb maps to a curve specification and optional param
# overrides that modulate the effect selected by Tier 1.  These
# produce ``value_curves`` entries on the ``RenderEvent``.


@dataclass(frozen=True)
class _MotionBehavior:
    """Internal descriptor for how a MotionVerb modulates an effect."""

    curve_id: CurveLibrary | None = None
    curve_param: str = "Speed"  # xLights param to animate
    curve_min: float = 0.0
    curve_max: float = 100.0
    amplitude: float = 1.0
    frequency: float = 1.0
    param_overrides: dict[str, Any] = field(default_factory=dict)


_MOTION_BEHAVIOR: dict[MotionVerb, _MotionBehavior] = {
    MotionVerb.NONE: _MotionBehavior(),  # no curves
    MotionVerb.PULSE: _MotionBehavior(
        curve_id=CurveLibrary.SINE,
        curve_param="Brightness",
        curve_min=0.0,
        curve_max=100.0,
        amplitude=0.8,
        frequency=1.0,
    ),
    MotionVerb.SHIMMER: _MotionBehavior(
        curve_id=CurveLibrary.SINE,
        curve_param="Speed",
        curve_min=0.0,
        curve_max=100.0,
        amplitude=0.4,
        frequency=2.0,
    ),
    MotionVerb.SPARKLE: _MotionBehavior(
        param_overrides={"re_random": True},
    ),
    MotionVerb.TWINKLE: _MotionBehavior(
        # Rely on Twinkle handler defaults
    ),
    MotionVerb.STROBE: _MotionBehavior(
        param_overrides={"strobe": True},
    ),
    MotionVerb.CHASE: _MotionBehavior(
        curve_id=CurveLibrary.LINEAR,
        curve_param="Speed",
        curve_min=0.0,
        curve_max=100.0,
        amplitude=1.0,
    ),
    MotionVerb.SWEEP: _MotionBehavior(
        curve_id=CurveLibrary.EASE_IN_OUT_SINE,
        curve_param="Speed",
        curve_min=0.0,
        curve_max=100.0,
        amplitude=1.0,
    ),
    MotionVerb.WAVE: _MotionBehavior(
        curve_id=CurveLibrary.SINE,
        curve_param="Speed",
        curve_min=0.0,
        curve_max=100.0,
        amplitude=0.7,
        frequency=1.5,
    ),
    MotionVerb.FADE: _MotionBehavior(
        curve_id=CurveLibrary.LINEAR,
        curve_param="Brightness",
        curve_min=0.0,
        curve_max=100.0,
        amplitude=1.0,
    ),
    MotionVerb.RIPPLE: _MotionBehavior(
        param_overrides={"cycles": 3.0},
    ),
    MotionVerb.BOUNCE: _MotionBehavior(
        curve_id=CurveLibrary.BOUNCE_OUT,
        curve_param="Speed",
        curve_min=0.0,
        curve_max=100.0,
        amplitude=1.0,
    ),
    MotionVerb.ROLL: _MotionBehavior(
        curve_id=CurveLibrary.LINEAR,
        curve_param="Speed",
        curve_min=10.0,
        curve_max=100.0,
        amplitude=1.0,
    ),
    MotionVerb.WIPE: _MotionBehavior(
        curve_id=CurveLibrary.EASE_IN_OUT_QUAD,
        curve_param="Speed",
        curve_min=0.0,
        curve_max=100.0,
        amplitude=1.0,
    ),
    MotionVerb.FLIP: _MotionBehavior(
        param_overrides={"reverse": True},
    ),
}


# ------------------------------------------------------------------
# Tier 3: density/contrast → parameter scaling
# ------------------------------------------------------------------
#
# Density scales "count/quantity" params; contrast scales "sharpness/
# brightness" params.  Ranges are per-effect.

_DENSITY_PARAMS: dict[str, tuple[str, int | float, int | float]] = {
    # effect_type: (param_name, min_val, max_val)
    "Twinkle": ("count", 3, 25),
    "Snowflakes": ("count", 30, 200),
    "Fan": ("num_blades", 4, 20),
    "Spirals": ("palette_count", 2, 6),
    "Meteors": ("count", 5, 30),
    "Strobe": ("num_strobes", 100, 500),
    "Shockwave": ("end_radius", 100, 250),
    "Ripple": ("cycles", 1.0, 5.0),
    "SingleStrand": ("group_count", 1, 10),
    "Marquee": ("band_size", 10, 60),
    "Fire": ("height", 20, 100),
    "Pinwheel": ("arms", 2, 10),
}

_CONTRAST_PARAMS: dict[str, tuple[str, int | float, int | float]] = {
    # effect_type: (param_name, min_val, max_val)
    "Twinkle": ("steps", 40, 5),  # inverted: high contrast = fewer steps = sharper
    "Color Wash": ("speed", 10, 100),
    "Spirals": ("rotation", 10, 100),
    "Meteors": ("speed", 5, 35),
    "Fan": ("revolutions", 50, 500),
    "Strobe": ("strobe_duration", 5, 1),  # inverted: high contrast = shorter duration
    "Shockwave": ("accel", 1, 5),
    "Ripple": ("velocity", 1.0, 10.0),
    "Fire": ("growth_cycles", 0.0, 3.0),
    "Pinwheel": ("speed", 3, 40),
}


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def resolve_effect(
    *,
    motifs: list[str],
    motion: list[MotionVerb],
    density: float,
    contrast: float,
    visual_depth: VisualDepth,
) -> ResolvedEffect:
    """Resolve a LayerRecipe's semantic description to a concrete xLights effect.

    Uses a three-tier strategy:

    1. First recognised motif → selects effect type + base params.
    2. First motion verb → selects value curves and param overrides.
    3. Density and contrast → scale quantity and intensity params.

    Args:
        motifs: Motif strings from ``LayerRecipe.motifs``.
        motion: Motion verbs from ``LayerRecipe.motion``.
        density: Density value (0.0-1.0) from the recipe.
        contrast: Contrast value (0.0-1.0) from the recipe.
        visual_depth: Visual depth of this layer (for buffer style).

    Returns:
        A ``ResolvedEffect`` with effect type, parameters, value curves,
        and buffer settings.

    Raises:
        ValueError: If no motif in the list is recognised.
    """
    # --- Tier 1: motif → effect type + base params ---
    effect_type: str | None = None
    base_params: dict[str, Any] = {}

    for motif in motifs:
        motif_lower = motif.lower().strip()
        if motif_lower in _MOTIF_TO_EFFECT:
            effect_type, base_params = _MOTIF_TO_EFFECT[motif_lower]
            base_params = dict(base_params)  # copy
            logger.debug(
                "Motif '%s' resolved to effect '%s'",
                motif_lower,
                effect_type,
            )
            break

    if effect_type is None:
        unrecognised = ", ".join(f"'{m}'" for m in motifs)
        raise ValueError(
            f"No recognised motif in [{unrecognised}]. "
            f"Add motif entries to _MOTIF_TO_EFFECT in effect_resolver.py."
        )

    # --- Tier 2: motion verb → curves + overrides ---
    value_curves: dict[str, str] = {}
    primary_verb = motion[0] if motion else MotionVerb.NONE
    behavior = _MOTION_BEHAVIOR.get(primary_verb, _MotionBehavior())

    if behavior.curve_id is not None:
        curve_str = build_value_curve_string(
            behavior.curve_id,
            behavior.curve_param,
            min_val=behavior.curve_min,
            max_val=behavior.curve_max,
            amplitude=behavior.amplitude,
            frequency=behavior.frequency,
        )
        value_curves[behavior.curve_param] = curve_str

    # Merge motion verb param overrides (e.g., reverse=True, strobe=True)
    for k, v in behavior.param_overrides.items():
        base_params.setdefault(k, v)

    # --- Tier 3: density/contrast scaling ---
    _apply_density(effect_type, density, base_params)
    _apply_contrast(effect_type, contrast, base_params)

    # --- Buffer style ---
    buffer_style = "Overlay - Centered" if effect_type in _CENTERED_EFFECTS else "Per Model Default"

    return ResolvedEffect(
        effect_type=effect_type,
        parameters=base_params,
        value_curves=value_curves,
        buffer_style=buffer_style,
        buffer_transform=None,
    )


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _apply_density(
    effect_type: str,
    density: float,
    params: dict[str, Any],
) -> None:
    """Scale a density-sensitive parameter for the given effect type.

    Modifies ``params`` in place.
    """
    spec = _DENSITY_PARAMS.get(effect_type)
    if spec is None:
        return
    param_name, lo, hi = spec
    scaled = lo + (hi - lo) * density
    params[param_name] = int(round(scaled)) if isinstance(lo, int) else round(scaled, 2)


def _apply_contrast(
    effect_type: str,
    contrast: float,
    params: dict[str, Any],
) -> None:
    """Scale a contrast-sensitive parameter for the given effect type.

    Modifies ``params`` in place.
    """
    spec = _CONTRAST_PARAMS.get(effect_type)
    if spec is None:
        return
    param_name, lo, hi = spec
    scaled = lo + (hi - lo) * contrast
    if isinstance(lo, int) and isinstance(hi, int):
        params[param_name] = int(round(scaled))
    else:
        params[param_name] = round(float(scaled), 2)


__all__ = [
    "ResolvedEffect",
    "resolve_effect",
]
