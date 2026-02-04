"""BASE lane group templates - Night Sky Vignette family."""

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


@register_group_template(aliases=["Vignette - Center"])
def make_gtpl_base_vignette_center() -> GroupPlanTemplate:
    """Dark edges, bright center."""
    return GroupPlanTemplate(
        template_id="gtpl_base_vignette_center",
        name="Vignette - Center",
        description="Night sky vignette with dark edges, bright center",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["vignette", "center", "dark-edges", "bright-center", "focus"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["vignette", "gradient", "focus"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.NONE],
                density=0.8,
                contrast=0.6,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Vignette - Edge"])
def make_gtpl_base_vignette_edge() -> GroupPlanTemplate:
    """Bright edges, dark center."""
    return GroupPlanTemplate(
        template_id="gtpl_base_vignette_edge",
        name="Vignette - Edge",
        description="Night sky vignette with bright edges, dark center",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["vignette", "edge", "bright-edges", "dark-center", "rim"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["vignette", "gradient", "rim"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.NONE],
                density=0.8,
                contrast=0.6,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
