"""RecipeSynthesizer — converts MinedTemplate to EffectRecipe.

Maps FE-mined template signatures (effect_family, motion_class, color_class,
energy_class, role) to renderable EffectRecipe specifications using
deterministic mapping rules.
"""

from __future__ import annotations

from twinklr.core.feature_engineering.models.templates import MinedTemplate
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
)
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    VisualDepth,
)

# ── Mapping tables ──────────────────────────────────────────────────────────

# effect_family → xLights effect type name
_EFFECT_TYPE_MAP: dict[str, str] = {
    "single_strand": "SingleStrand",
    "shimmer": "Shimmer",
    "twinkle": "Twinkle",
    "color_wash": "ColorWash",
    "sparkle": "Sparkle",
    "bars": "Bars",
    "curtain": "Curtain",
    "spiral": "Spirals",
    "fire": "Fire",
    "meteor": "Meteor",
    "snowflakes": "Snowflakes",
    "on": "On",
    "off": "Off",
    "fade": "Fade",
    "strobe": "Strobe",
    "wave": "Wave",
    "butterfly": "Butterfly",
    "marquee": "Marquee",
    "garlands": "Garlands",
    "pictures": "Pictures",
    "morph": "Morph",
    "ripple": "Ripple",
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
}

# role → GroupTemplateType
_ROLE_MAP: dict[str, GroupTemplateType] = {
    "base_fill": GroupTemplateType.BASE,
    "base_ambient": GroupTemplateType.BASE,
    "rhythm_driver": GroupTemplateType.RHYTHM,
    "rhythm_accent": GroupTemplateType.RHYTHM,
    "accent_hit": GroupTemplateType.ACCENT,
    "accent_burst": GroupTemplateType.ACCENT,
    "accent_sparkle": GroupTemplateType.ACCENT,
}

# color_class → ColorMode
_COLOR_MODE_MAP: dict[str, ColorMode] = {
    "mono": ColorMode.MONOCHROME,
    "palette": ColorMode.DICHROME,
    "multi": ColorMode.TRIAD,
    "rainbow": ColorMode.FULL_SPECTRUM,
    "white": ColorMode.MONOCHROME,
}

# energy_class → layer density
_ENERGY_DENSITY_MAP: dict[str, float] = {
    "low": 0.3,
    "mid": 0.5,
    "high": 0.8,
    "peak": 0.95,
}


class RecipeSynthesizer:
    """Converts MinedTemplate instances to EffectRecipe specifications."""

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
            A renderable EffectRecipe.
        """
        # Map fields
        effect_type = _EFFECT_TYPE_MAP.get(mined.effect_family, mined.effect_family.title())
        motion = _MOTION_MAP.get(mined.motion_class, [MotionVerb.NONE])
        template_type = _ROLE_MAP.get(mined.role or "", GroupTemplateType.RHYTHM)
        color_mode = _COLOR_MODE_MAP.get(mined.color_class, ColorMode.DICHROME)
        density = _ENERGY_DENSITY_MAP.get(mined.energy_class, 0.5)

        # Derive palette roles from color mode
        if color_mode == ColorMode.MONOCHROME:
            palette_roles = ["primary"]
        elif color_mode == ColorMode.TRIAD:
            palette_roles = ["primary", "accent", "tertiary"]
        else:
            palette_roles = ["primary", "accent"]

        # Determine visual intent from effect family heuristics
        visual_intent = GroupVisualIntent.ABSTRACT

        # Build the single primary layer
        layer = RecipeLayer(
            layer_index=0,
            layer_name=effect_type,
            layer_depth=VisualDepth.BACKGROUND,
            effect_type=effect_type,
            blend_mode=BlendMode.NORMAL,
            mix=1.0,
            params={},
            motion=motion,
            density=density,
            color_source=ColorSource.PALETTE_PRIMARY,
        )

        # Build timing hints from energy/role heuristics
        if template_type == GroupTemplateType.BASE:
            timing = TimingHints(bars_min=4, bars_max=64)
        elif template_type == GroupTemplateType.ACCENT:
            timing = TimingHints(bars_min=1, bars_max=4)
        else:
            timing = TimingHints(bars_min=2, bars_max=16)

        # Build tags from signature components
        tags = [
            mined.effect_family,
            mined.motion_class,
            mined.color_class,
            mined.energy_class,
        ]
        if mined.role:
            tags.append(mined.role)

        return EffectRecipe(
            recipe_id=recipe_id,
            name=f"{effect_type} {mined.motion_class.title()}",
            description=(
                f"Synthesized from mined template {mined.template_id} "
                f"({mined.template_signature})"
            ),
            recipe_version=recipe_version,
            template_type=template_type,
            visual_intent=visual_intent,
            tags=tags,
            timing=timing,
            palette_spec=PaletteSpec(mode=color_mode, palette_roles=palette_roles),
            layers=(layer,),
            provenance=RecipeProvenance(
                source="mined",
                mined_template_ids=[mined.template_id],
            ),
        )
