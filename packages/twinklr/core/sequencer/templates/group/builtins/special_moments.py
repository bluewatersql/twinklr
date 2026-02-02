"""SPECIAL lane group templates - Chorus, Drop, Bridge, Finale, Polar families.

Signature moment templates for high-impact sections.
"""

from twinklr.core.sequencer.templates.group.enums import (
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    LayerRole,
    MotionVerb,
    ProjectionIntent,
)
from twinklr.core.sequencer.templates.group.library import register_group_template
from twinklr.core.sequencer.templates.group.models import (
    GroupPlanTemplate,
    LayerRecipe,
    ProjectionSpec,
    TimingHints,
)


# Chorus Signature family
@register_group_template(aliases=["Chorus - Signature A"])
def make_gtpl_special_chorus_signature_a() -> GroupPlanTemplate:
    """Bright, energetic, all-on."""
    return GroupPlanTemplate(
        template_id="gtpl_special_chorus_signature_a",
        name="Chorus - Signature A",
        description="Bright energetic all-on chorus moment",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["chorus", "signature", "bright", "energetic"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["all-on", "bright", "energetic"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=1.0,
                contrast=0.9,
                color_mode=ColorMode.ANALOGOUS,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Chorus - Signature B"])
def make_gtpl_special_chorus_signature_b() -> GroupPlanTemplate:
    """Rhythmic pulse with accents."""
    return GroupPlanTemplate(
        template_id="gtpl_special_chorus_signature_b",
        name="Chorus - Signature B",
        description="Rhythmic pulse with accent hits for chorus",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["chorus", "signature", "rhythmic", "accents"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["rhythmic", "pulse", "accents"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE, MotionVerb.SPARKLE],
                density=0.9,
                contrast=1.0,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Drop Moment family
@register_group_template(aliases=["Drop - Freeze"])
def make_gtpl_special_drop_freeze() -> GroupPlanTemplate:
    """Freeze, then explode."""
    return GroupPlanTemplate(
        template_id="gtpl_special_drop_freeze",
        name="Drop - Freeze",
        description="Freeze moment then explosive drop",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["drop", "freeze", "explode", "impact"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["freeze", "drop", "explosion"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE, MotionVerb.RIPPLE],
                density=1.0,
                contrast=1.0,
                color_mode=ColorMode.FULL_SPECTRUM,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Drop - Explode"])
def make_gtpl_special_drop_explode() -> GroupPlanTemplate:
    """Immediate explosion drop."""
    return GroupPlanTemplate(
        template_id="gtpl_special_drop_explode",
        name="Drop - Explode",
        description="Immediate explosive drop moment",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["drop", "explode", "immediate", "impact"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=2),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["explosion", "drop", "impact"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.RIPPLE, MotionVerb.PULSE],
                density=1.0,
                contrast=1.0,
                color_mode=ColorMode.FULL_SPECTRUM,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Bridge Contrast family
@register_group_template(aliases=["Bridge - Sparse"])
def make_gtpl_special_bridge_sparse() -> GroupPlanTemplate:
    """Sparse, minimal motion."""
    return GroupPlanTemplate(
        template_id="gtpl_special_bridge_sparse",
        name="Bridge - Sparse",
        description="Sparse minimal motion for bridge contrast",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["bridge", "sparse", "minimal", "contrast"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BACKGROUND,
                motifs=["sparse", "minimal", "subtle"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE],
                density=0.3,
                contrast=0.4,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Bridge - Moody"])
def make_gtpl_special_bridge_moody() -> GroupPlanTemplate:
    """Moody, low-intensity."""
    return GroupPlanTemplate(
        template_id="gtpl_special_bridge_moody",
        name="Bridge - Moody",
        description="Moody low-intensity bridge contrast",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["bridge", "moody", "low-intensity", "atmospheric"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BACKGROUND,
                motifs=["moody", "atmospheric", "subtle"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SHIMMER, MotionVerb.FADE],
                density=0.5,
                contrast=0.5,
                color_mode=ColorMode.ANALOGOUS,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Finale Ramp family
@register_group_template(aliases=["Finale - Ramp"])
def make_gtpl_special_finale_ramp() -> GroupPlanTemplate:
    """Gradual to max intensity."""
    return GroupPlanTemplate(
        template_id="gtpl_special_finale_ramp",
        name="Finale - Ramp",
        description="Gradual ramp to maximum intensity finale",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["finale", "ramp", "build", "maximum"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["ramp", "crescendo", "maximum"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE, MotionVerb.RIPPLE],
                density=1.0,
                contrast=1.0,
                color_mode=ColorMode.FULL_SPECTRUM,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Finale - Strobe Safe"])
def make_gtpl_special_finale_strobe_safe() -> GroupPlanTemplate:
    """Safe strobe build."""
    return GroupPlanTemplate(
        template_id="gtpl_special_finale_strobe_safe",
        name="Finale - Strobe Safe",
        description="Safe strobe build to finale climax",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["finale", "strobe", "safe", "climax"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["strobe", "build", "climax"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.STROBE, MotionVerb.PULSE],
                density=0.9,
                contrast=1.0,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Mega-Tree Polar family
@register_group_template(aliases=["Polar - Spiral"])
def make_gtpl_special_polar_spiral() -> GroupPlanTemplate:
    """Polar spiral for mega-tree."""
    return GroupPlanTemplate(
        template_id="gtpl_special_polar_spiral",
        name="Polar - Spiral",
        description="Polar coordinate spiral pattern for mega-tree",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["polar", "spiral", "mega-tree", "cone"],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=2, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["spiral", "polar", "rotation"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.ROLL],
                density=0.8,
                contrast=0.9,
                color_mode=ColorMode.ANALOGOUS,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Polar - Starburst"])
def make_gtpl_special_polar_starburst() -> GroupPlanTemplate:
    """Polar starburst for mega-tree."""
    return GroupPlanTemplate(
        template_id="gtpl_special_polar_starburst",
        name="Polar - Starburst",
        description="Polar coordinate starburst for mega-tree",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["polar", "starburst", "mega-tree", "radial"],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["starburst", "radial", "explosion"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.RIPPLE, MotionVerb.PULSE],
                density=0.7,
                contrast=1.0,
                color_mode=ColorMode.FULL_SPECTRUM,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
