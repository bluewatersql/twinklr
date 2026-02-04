"""BASE lane group templates - Subtle Shimmer family."""

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


@register_group_template(aliases=["Shimmer - Horizontal"])
def make_gtpl_base_shimmer_horizontal() -> GroupPlanTemplate:
    """Horizontal sweep, very slow."""
    return GroupPlanTemplate(
        template_id="gtpl_base_shimmer_horizontal",
        name="Shimmer - Horizontal",
        description="Horizontal shimmer sweep, very slow subtle motion",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["shimmer", "horizontal", "sweep", "slow", "subtle"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=8, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["shimmer", "sweep", "horizontal"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SWEEP],
                density=0.7,
                contrast=0.3,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Shimmer - Radial"])
def make_gtpl_base_shimmer_radial() -> GroupPlanTemplate:
    """Radial pulse, subtle."""
    return GroupPlanTemplate(
        template_id="gtpl_base_shimmer_radial",
        name="Shimmer - Radial",
        description="Radial pulse shimmer, subtle outward motion",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["shimmer", "radial", "pulse", "subtle", "outward"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=8, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["shimmer", "radial", "pulse"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.RIPPLE],
                density=0.7,
                contrast=0.4,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
