"""RecipeSynthesizer — converts MinedTemplate to EffectRecipe.

Maps FE-mined template signatures (effect_family, motion_class, color_class,
energy_class, taxonomy_labels) to renderable EffectRecipe specifications using
deterministic mapping rules.

Lane assignment uses three tiers:
1. Explicit ``role`` field (orchestration templates)
2. Taxonomy labels (``texture_bed`` → BASE, ``accent_hit`` → ACCENT, etc.)
3. Energy/continuity heuristic (low+sustained → BASE, burst → ACCENT)
"""

from __future__ import annotations

from twinklr.core.feature_engineering.models.templates import MinedTemplate
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    PaletteSpec,
    ParamValue,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    VisualDepth,
)

# ── Mapping tables ──────────────────────────────────────────────────────────

# effect_family → xLights effect type name.
# Keys use the snake_case family IDs from the phrase encoder; values are the
# PascalCase names expected by the renderer and XSQ export layer.
_EFFECT_TYPE_MAP: dict[str, str] = {
    # Original entries (keep for backward compat)
    "bars": "Bars",
    "butterfly": "Butterfly",
    "color_wash": "ColorWash",
    "curtain": "Curtain",
    "fire": "Fire",
    "garlands": "Garlands",
    "marquee": "Marquee",
    "morph": "Morph",
    "off": "Off",
    "on": "On",
    "pictures": "Pictures",
    "ripple": "Ripple",
    "shimmer": "Shimmer",
    "single_strand": "SingleStrand",
    "snowflakes": "Snowflakes",
    "sparkle": "Sparkle",
    "strobe": "Strobe",
    "twinkle": "Twinkle",
    "wave": "Wave",
    # Families present in real corpus but previously unmapped
    "candle": "Candle",
    "circles": "Circles",
    "dmx": "DMX",
    "faces": "Faces",
    "fan": "Fan",
    "fill": "Fill",
    "fireworks": "Fireworks",
    "galaxy": "Galaxy",
    "kaleidoscope": "Kaleidoscope",
    "lightning": "Lightning",
    "lines": "Lines",
    "liquid": "Liquid",
    "meteors": "Meteors",
    "moving_head": "MovingHead",
    "pinwheel": "Pinwheel",
    "plasma": "Plasma",
    "shader": "Shader",
    "shape": "Shape",
    "shockwave": "Shockwave",
    "sketch": "Sketch",
    "snow_storm": "Snowstorm",
    "spirals": "Spirals",
    "spirograph": "Spirograph",
    "state": "State",
    "tendrils": "Tendrils",
    "text": "Text",
    "tree": "Tree",
    "video": "Video",
    "vu_meter": "VUMeter",
    "warp": "Warp",
    # Deprecated singular forms (redirect to canonical plural)
    "spiral": "Spirals",
    "meteor": "Meteors",
    "fade": "Fade",
    # Rare / device-specific
    "glediator": "Glediator",
    "guitar": "Guitar",
    "life": "Life",
    "music": "Music",
    "piano": "Piano",
    "servo": "Servo",
    "duplicate": "Duplicate",
}

# motion_class → MotionVerb(s)
_MOTION_MAP: dict[str, list[MotionVerb]] = {
    "sweep": [MotionVerb.SWEEP],
    "pulse": [MotionVerb.PULSE],
    "chase": [MotionVerb.CHASE],
    "sparkle": [MotionVerb.SPARKLE],
    "fade": [MotionVerb.FADE],
    "strobe": [MotionVerb.STROBE],
    "wave": [MotionVerb.WAVE],
    "breathe": [MotionVerb.PULSE],
    "cascade": [MotionVerb.CHASE],
    "static": [MotionVerb.NONE],
    "none": [MotionVerb.NONE],
    "dmx_program": [MotionVerb.NONE],
}

# Explicit role → GroupTemplateType (for orchestration templates that have a role)
_ROLE_MAP: dict[str, GroupTemplateType] = {
    "base_fill": GroupTemplateType.BASE,
    "base_ambient": GroupTemplateType.BASE,
    "rhythm_driver": GroupTemplateType.RHYTHM,
    "rhythm_accent": GroupTemplateType.RHYTHM,
    "accent_hit": GroupTemplateType.ACCENT,
    "accent_burst": GroupTemplateType.ACCENT,
    "accent_sparkle": GroupTemplateType.ACCENT,
}

# Taxonomy label → GroupTemplateType (for content templates where role is None)
_TAXONOMY_LANE_MAP: dict[str, GroupTemplateType] = {
    "texture_bed": GroupTemplateType.BASE,
    "sustainer": GroupTemplateType.BASE,
    "rhythm_driver": GroupTemplateType.RHYTHM,
    "motion_driver": GroupTemplateType.RHYTHM,
    "accent_hit": GroupTemplateType.ACCENT,
    "transition": GroupTemplateType.RHYTHM,
}

# color_class → ColorMode
_COLOR_MODE_MAP: dict[str, ColorMode] = {
    "mono": ColorMode.MONOCHROME,
    "palette": ColorMode.DICHROME,
    "multi": ColorMode.TRIAD,
    "rainbow": ColorMode.FULL_SPECTRUM,
    "white": ColorMode.MONOCHROME,
    "unknown": ColorMode.DICHROME,
}

# energy_class → layer density
_ENERGY_DENSITY_MAP: dict[str, float] = {
    "low": 0.3,
    "mid": 0.5,
    "high": 0.8,
    "burst": 0.95,
    "peak": 0.95,
}

# Effect families that are inherently sparkle/overlay types (skip sparkle overlay)
_SPARKLE_FAMILIES: frozenset[str] = frozenset(
    {
        "sparkle",
        "twinkle",
        "shimmer",
        "snowflakes",
        "candle",
        "fireworks",
    }
)

# Ambient/wash-like families where a ColorWash underlay would be redundant
_WASH_LIKE_FAMILIES: frozenset[str] = frozenset(
    {
        "color_wash",
        "fill",
        "on",
        "morph",
    }
)

# Non-visual families that should never receive layering (underlay or overlay).
# These are utility/device effects without meaningful visual rendering.
_NON_VISUAL_FAMILIES: frozenset[str] = frozenset(
    {
        "off",
    }
)

# energy_class → EnergyTarget for StyleMarkers
_ENERGY_TARGET_MAP: dict[str, EnergyTarget] = {
    "low": EnergyTarget.LOW,
    "mid": EnergyTarget.MED,
    "high": EnergyTarget.HIGH,
    "burst": EnergyTarget.HIGH,
    "peak": EnergyTarget.HIGH,
}


def _infer_lane(mined: MinedTemplate) -> GroupTemplateType:
    """Infer GroupTemplateType from role, taxonomy labels, or energy heuristic.

    Priority:
    1. Explicit role field (orchestration templates)
    2. Taxonomy labels (texture_bed → BASE, accent_hit → ACCENT, etc.)
    3. Energy + continuity heuristic (low+sustained → BASE, burst → ACCENT)
    """
    if mined.role:
        result = _ROLE_MAP.get(mined.role)
        if result is not None:
            return result

    for label in mined.taxonomy_labels:
        result = _TAXONOMY_LANE_MAP.get(label)
        if result is not None:
            return result

    if mined.energy_class == "low" and mined.continuity_class == "sustained":
        return GroupTemplateType.BASE
    if mined.energy_class == "burst":
        return GroupTemplateType.ACCENT

    return GroupTemplateType.RHYTHM


# layer_role → VisualDepth mapping
_ROLE_DEPTH_MAP: dict[str, VisualDepth] = {
    "BASE": VisualDepth.BACKGROUND,
    "RHYTHM": VisualDepth.MIDGROUND,
    "ACCENT": VisualDepth.FOREGROUND,
    "HIGHLIGHT": VisualDepth.ACCENT,
    "FILL": VisualDepth.BACKGROUND,
    "TEXTURE": VisualDepth.TEXTURE,
    "CUSTOM": VisualDepth.MIDGROUND,
}


class RecipeSynthesizer:
    """Converts MinedTemplate instances to EffectRecipe specifications.

    Two synthesis modes:
    - ``synthesize()`` (legacy): heuristic layering from single-effect templates.
    - ``synthesize_from_stack()`` (V2): data-driven layering from stack metadata.

    Optional ``param_profiles`` provide effect-family-level modal parameter
    values (from Cycle 0 effect metadata analysis).  When provided, layer
    params are populated from the profile.  When absent, existing
    deterministic mapping rules are used unchanged.
    """

    def __init__(
        self,
        *,
        param_profiles: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self._param_profiles = param_profiles or {}

    def synthesize_from_stack(
        self,
        mined: MinedTemplate,
        *,
        recipe_id: str,
        recipe_version: str = "1.0.0",
    ) -> EffectRecipe:
        """Synthesize an EffectRecipe using stack composition data.

        When the MinedTemplate has stack_composition populated (from stack
        mining), layers are built directly from the discovered data rather
        than heuristic rules.

        Falls back to ``synthesize()`` if stack_composition is empty.

        Args:
            mined: The mined template (with stack metadata).
            recipe_id: Human-readable recipe ID for the output.
            recipe_version: Semantic version for the recipe.

        Returns:
            A renderable EffectRecipe with layers matching the stack.
        """
        if not mined.stack_composition:
            return self.synthesize(mined, recipe_id=recipe_id, recipe_version=recipe_version)

        template_type = _infer_lane(mined)
        color_mode = _COLOR_MODE_MAP.get(mined.color_class, ColorMode.DICHROME)
        energy_target = _ENERGY_TARGET_MAP.get(mined.energy_class, EnergyTarget.MED)

        if color_mode == ColorMode.MONOCHROME:
            palette_roles = ["primary"]
        elif color_mode == ColorMode.TRIAD:
            palette_roles = ["primary", "accent", "tertiary"]
        else:
            palette_roles = ["primary", "accent"]

        layers = self._build_stack_layers(mined)

        if template_type == GroupTemplateType.BASE:
            timing = TimingHints(bars_min=4, bars_max=64)
        elif template_type == GroupTemplateType.ACCENT:
            timing = TimingHints(bars_min=1, bars_max=4)
        else:
            timing = TimingHints(bars_min=2, bars_max=16)

        tags = list(mined.stack_composition) + [
            mined.motion_class,
            mined.color_class,
            mined.energy_class,
        ]
        if mined.role:
            tags.append(mined.role)
        tags.extend(mined.taxonomy_labels)

        name_parts = [_EFFECT_TYPE_MAP.get(f, f.title()) for f in mined.stack_composition]
        name = " + ".join(name_parts)

        complexity = min(1.0, mined.layer_count / 4.0)

        return EffectRecipe(
            recipe_id=recipe_id,
            name=name,
            description=(
                f"Stack recipe from {mined.layer_count}-layer template {mined.template_id}"
            ),
            recipe_version=recipe_version,
            template_type=template_type,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=tags,
            timing=timing,
            palette_spec=PaletteSpec(mode=color_mode, palette_roles=palette_roles),
            layers=tuple(layers),
            provenance=RecipeProvenance(source="mined"),
            style_markers=StyleMarkers(
                complexity=complexity,
                energy_affinity=energy_target,
            ),
        )

    def _build_stack_layers(self, mined: MinedTemplate) -> list[RecipeLayer]:
        """Build recipe layers directly from stack composition data."""
        layers: list[RecipeLayer] = []
        blend_modes = mined.layer_blend_modes or ()
        mixes = mined.layer_mixes or ()

        # Positional depth mapping
        depth_sequence = [VisualDepth.BACKGROUND, VisualDepth.MIDGROUND, VisualDepth.FOREGROUND]

        for idx, family in enumerate(mined.stack_composition):
            effect_type = _EFFECT_TYPE_MAP.get(family, family.title())
            motion = _MOTION_MAP.get(mined.motion_class, [MotionVerb.NONE])
            density = _ENERGY_DENSITY_MAP.get(mined.energy_class, 0.5)

            raw_blend = blend_modes[idx] if idx < len(blend_modes) else "NORMAL"
            try:
                blend = BlendMode(raw_blend)
            except ValueError:
                blend = BlendMode.NORMAL
            mix = mixes[idx] if idx < len(mixes) else 1.0

            depth = depth_sequence[min(idx, len(depth_sequence) - 1)]

            color_src = ColorSource.PALETTE_PRIMARY
            if family in _SPARKLE_FAMILIES:
                color_src = ColorSource.WHITE_ONLY
                motion = [MotionVerb.SPARKLE]
                density = 0.2

            params = self._resolve_profile_params(family)

            layers.append(
                RecipeLayer(
                    layer_index=idx,
                    layer_name=effect_type,
                    layer_depth=depth,
                    effect_type=effect_type,
                    blend_mode=blend,
                    mix=mix,
                    params=params,
                    motion=motion,
                    density=density,
                    color_source=color_src,
                )
            )

        return layers

    def _resolve_profile_params(self, effect_family: str) -> dict[str, ParamValue]:
        """Resolve params from profile for a given effect family.

        Returns a dict of ParamValue instances built from the profile's
        modal values for the family.  Returns an empty dict if no profile
        entry exists.
        """
        profile = self._param_profiles.get(effect_family)
        if not profile:
            return {}
        return {name: ParamValue(value=val) for name, val in profile.items()}

    def synthesize(
        self,
        mined: MinedTemplate,
        *,
        recipe_id: str,
        recipe_version: str = "1.0.0",
    ) -> EffectRecipe:
        """Synthesize an EffectRecipe from a MinedTemplate.

        Args:
            mined: The mined template to convert.
            recipe_id: Human-readable recipe ID for the output.
            recipe_version: Semantic version for the recipe.

        Returns:
            A renderable EffectRecipe with 1-3 layers.
        """
        effect_type = _EFFECT_TYPE_MAP.get(mined.effect_family, mined.effect_family.title())
        motion = _MOTION_MAP.get(mined.motion_class, [MotionVerb.NONE])
        template_type = _infer_lane(mined)
        color_mode = _COLOR_MODE_MAP.get(mined.color_class, ColorMode.DICHROME)
        density = _ENERGY_DENSITY_MAP.get(mined.energy_class, 0.5)

        if color_mode == ColorMode.MONOCHROME:
            palette_roles = ["primary"]
        elif color_mode == ColorMode.TRIAD:
            palette_roles = ["primary", "accent", "tertiary"]
        else:
            palette_roles = ["primary", "accent"]

        visual_intent = GroupVisualIntent.ABSTRACT

        layers = self._build_layers(
            effect_type=effect_type,
            motion=motion,
            density=density,
            template_type=template_type,
            energy_class=mined.energy_class,
            effect_family=mined.effect_family,
        )

        if template_type == GroupTemplateType.BASE:
            timing = TimingHints(bars_min=4, bars_max=64)
        elif template_type == GroupTemplateType.ACCENT:
            timing = TimingHints(bars_min=1, bars_max=4)
        else:
            timing = TimingHints(bars_min=2, bars_max=16)

        tags = [
            mined.effect_family,
            mined.motion_class,
            mined.color_class,
            mined.energy_class,
        ]
        if mined.role:
            tags.append(mined.role)
        tags.extend(mined.taxonomy_labels)

        complexity = len(layers) / 3.0
        energy_target = _ENERGY_TARGET_MAP.get(mined.energy_class, EnergyTarget.MED)

        return EffectRecipe(
            recipe_id=recipe_id,
            name=f"{effect_type} {mined.motion_class.title()}",
            description=(
                f"Synthesized from mined template {mined.template_id} ({mined.template_signature})"
            ),
            recipe_version=recipe_version,
            template_type=template_type,
            visual_intent=visual_intent,
            tags=tags,
            timing=timing,
            palette_spec=PaletteSpec(mode=color_mode, palette_roles=palette_roles),
            layers=tuple(layers),
            provenance=RecipeProvenance(source="mined"),
            style_markers=StyleMarkers(
                complexity=complexity,
                energy_affinity=energy_target,
            ),
        )

    def _build_layers(
        self,
        *,
        effect_type: str,
        motion: list[MotionVerb],
        density: float,
        template_type: GroupTemplateType,
        energy_class: str,
        effect_family: str,
    ) -> list[RecipeLayer]:
        """Build 1-3 layers depending on lane and energy.

        - BASE recipes: single primary layer (ambient/fill effects).
        - RHYTHM recipes: color wash underlay + primary effect.
        - ACCENT recipes: color wash underlay + primary effect.
        - High-energy non-sparkle recipes: add sparkle overlay.
        - Non-visual families (off) always get a single layer with no extras.
        - Wash-like families (color_wash, fill, on, morph) skip the underlay.
        """
        layers: list[RecipeLayer] = []
        idx = 0

        skip_extras = effect_family in _NON_VISUAL_FAMILIES
        want_underlay = (
            template_type in (GroupTemplateType.RHYTHM, GroupTemplateType.ACCENT)
            and not skip_extras
            and effect_family not in _WASH_LIKE_FAMILIES
        )
        want_overlay = (
            energy_class in ("high", "burst")
            and effect_family not in _SPARKLE_FAMILIES
            and not skip_extras
        )

        if want_underlay:
            layers.append(
                RecipeLayer(
                    layer_index=idx,
                    layer_name="Wash",
                    layer_depth=VisualDepth.BACKGROUND,
                    effect_type="ColorWash",
                    blend_mode=BlendMode.NORMAL,
                    mix=1.0,
                    params={"Speed": ParamValue(value=0)},
                    motion=[MotionVerb.FADE],
                    density=0.9,
                    color_source=ColorSource.PALETTE_PRIMARY,
                )
            )
            idx += 1

        # Primary effect layer — use profile params if available
        primary_params = self._resolve_profile_params(effect_family)

        layers.append(
            RecipeLayer(
                layer_index=idx,
                layer_name=effect_type,
                layer_depth=(VisualDepth.MIDGROUND if want_underlay else VisualDepth.BACKGROUND),
                effect_type=effect_type,
                blend_mode=BlendMode.ADD if want_underlay else BlendMode.NORMAL,
                mix=0.8 if want_underlay else 1.0,
                params=primary_params,
                motion=motion,
                density=density,
                color_source=ColorSource.PALETTE_PRIMARY,
            )
        )
        idx += 1

        if want_overlay:
            layers.append(
                RecipeLayer(
                    layer_index=idx,
                    layer_name="Sparkle",
                    layer_depth=VisualDepth.FOREGROUND,
                    effect_type="Twinkle",
                    blend_mode=BlendMode.SCREEN,
                    mix=0.3,
                    params={
                        "Count": ParamValue(expr="energy * 40", min_val=5, max_val=50),
                    },
                    motion=[MotionVerb.SPARKLE],
                    density=0.2,
                    color_source=ColorSource.WHITE_ONLY,
                )
            )

        return layers
