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
        affinity_tags=[
            "motif.gradient_bands",
            "constraint.centered_composition",
            "style.minimal",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
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
        affinity_tags=[
            "motif.gradient_bands",
            "style.minimal",
            "constraint.clean_edges",
            "constraint.low_detail",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.centered_composition"],
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
