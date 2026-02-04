"""BASE lane group templates - Static Holiday Glow family."""

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


@register_group_template(aliases=["Static Glow - Warm"])
def make_gtpl_base_glow_warm() -> GroupPlanTemplate:
    """Warm glow (amber/gold)."""
    return GroupPlanTemplate(
        template_id="gtpl_base_glow_warm",
        name="Static Glow - Warm",
        description="Warm static glow in amber/gold tones",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["glow", "warm", "amber", "gold", "static"],
        affinity_tags=["motif.abstract", "style.minimal", "setting.calm", "constraint.low_detail"],
        avoid_tags=["constraint.high_contrast"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["glow", "static", "warm"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.NONE],
                density=0.9,
                contrast=0.3,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Static Glow - Cool"])
def make_gtpl_base_glow_cool() -> GroupPlanTemplate:
    """Cool glow (blue/white)."""
    return GroupPlanTemplate(
        template_id="gtpl_base_glow_cool",
        name="Static Glow - Cool",
        description="Cool static glow in blue/white tones",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["glow", "cool", "blue", "white", "static"],
        affinity_tags=["motif.abstract", "motif.ice", "style.minimal", "setting.calm"],
        avoid_tags=["constraint.high_contrast"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["glow", "static", "cool"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.NONE],
                density=0.9,
                contrast=0.4,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
