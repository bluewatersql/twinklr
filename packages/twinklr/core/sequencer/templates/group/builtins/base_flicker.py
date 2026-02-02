"""BASE lane group templates - Candle Flicker family."""

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


@register_group_template(aliases=["Candle Flicker - Subtle"])
def make_gtpl_base_flicker_subtle() -> GroupPlanTemplate:
    """Very slow random flicker (1-3% intensity)."""
    return GroupPlanTemplate(
        template_id="gtpl_base_flicker_subtle",
        name="Candle Flicker - Subtle",
        description="Very slow random flicker, 1-3% intensity variation",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["flicker", "subtle", "random", "candle", "slow"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BACKGROUND,
                motifs=["flicker", "candle", "random"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SHIMMER],
                density=0.9,
                contrast=0.2,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Candle Flicker - Pulsed"])
def make_gtpl_base_flicker_pulsed() -> GroupPlanTemplate:
    """Gentle pulse with flicker."""
    return GroupPlanTemplate(
        template_id="gtpl_base_flicker_pulsed",
        name="Candle Flicker - Pulsed",
        description="Gentle pulse combined with candle flicker",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["flicker", "pulse", "candle", "gentle", "combined"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BACKGROUND,
                motifs=["flicker", "pulse", "candle"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SHIMMER, MotionVerb.PULSE],
                density=0.9,
                contrast=0.3,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
