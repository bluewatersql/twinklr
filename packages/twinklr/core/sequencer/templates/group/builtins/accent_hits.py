"""ACCENT lane group templates - Hit Flash, Burst, Spark Shower families.

Focal punctuation with high intensity for emphasis moments.
"""

from twinklr.core.sequencer.templates.group.library import register_group_template
from twinklr.core.sequencer.templates.group.models import (
    GroupPlanTemplate,
    LayerRecipe,
    ProjectionSpec,
    TimingHints,
)
from twinklr.core.sequencer.vocabulary import (
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    ProjectionIntent,
    VisualDepth,
)


# Hit Flash family
@register_group_template(aliases=["Hit - White"])
def make_gtpl_accent_hit_white() -> GroupPlanTemplate:
    """White flash, short duration."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_hit_white",
        name="Hit - White",
        description="Short white flash for emphasis",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["hit", "flash", "white", "short", "emphasis"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=2),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["flash", "hit", "emphasis"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.9,
                contrast=1.0,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Hit - Color"])
def make_gtpl_accent_hit_color() -> GroupPlanTemplate:
    """Colored flash (red/green)."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_hit_color",
        name="Hit - Color",
        description="Colored flash emphasis (red/green)",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["hit", "flash", "color", "red", "green"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=2),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["flash", "hit", "color"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.9,
                contrast=0.9,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Hit - Ring"])
def make_gtpl_accent_hit_ring() -> GroupPlanTemplate:
    """Ring-out expansion flash."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_hit_ring",
        name="Hit - Ring",
        description="Ring-out expansion from center",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["hit", "ring", "expansion", "radial"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=2),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["ring", "expansion", "radial"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.RIPPLE],
                density=0.7,
                contrast=0.9,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Burst / Starburst family
@register_group_template(aliases=["Burst - Small"])
def make_gtpl_accent_burst_small() -> GroupPlanTemplate:
    """Small radial burst."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_burst_small",
        name="Burst - Small",
        description="Small radial burst from center",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["burst", "small", "radial", "starburst"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=2),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["burst", "radial", "starburst"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.RIPPLE],
                density=0.6,
                contrast=0.9,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Burst - Big"])
def make_gtpl_accent_burst_big() -> GroupPlanTemplate:
    """Large burst with tail."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_burst_big",
        name="Burst - Big",
        description="Large radial burst with trailing tail",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["burst", "big", "large", "tail"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["burst", "large", "tail"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.RIPPLE, MotionVerb.FADE],
                density=0.8,
                contrast=1.0,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Spark Shower family
@register_group_template(aliases=["Spark Shower - Up"])
def make_gtpl_accent_spark_shower_up() -> GroupPlanTemplate:
    """Sparks shooting upward."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_spark_shower_up",
        name="Spark Shower - Up",
        description="Sparks shooting upward fountain effect",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["spark", "shower", "up", "fountain"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["spark", "fountain", "upward"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SPARKLE],
                density=0.5,
                contrast=0.9,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Spark Shower - Down"])
def make_gtpl_accent_spark_shower_down() -> GroupPlanTemplate:
    """Sparks raining down."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_spark_shower_down",
        name="Spark Shower - Down",
        description="Sparks raining downward cascade",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["spark", "shower", "down", "rain"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["spark", "rain", "downward"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SPARKLE],
                density=0.5,
                contrast=0.8,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
