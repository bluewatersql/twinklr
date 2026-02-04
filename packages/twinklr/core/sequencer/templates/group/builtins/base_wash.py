"""BASE lane group templates - Gradient Wash family."""

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


@register_group_template(aliases=["Gradient Wash - Soft"])
def make_gtpl_base_wash_soft() -> GroupPlanTemplate:
    """Gentle single gradient wash."""
    return GroupPlanTemplate(
        template_id="gtpl_base_wash_soft",
        name="Gradient Wash - Soft",
        description="Gentle single gradient wash across display, low intensity",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["wash", "gradient", "soft", "calm", "continuous"],
        affinity_tags=[
            "motif.gradient_bands",
            "style.minimal",
            "setting.calm",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.high_contrast"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["gradient", "wash", "smooth"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE],
                density=0.8,
                contrast=0.4,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Gradient Wash - Split"])
def make_gtpl_base_wash_split() -> GroupPlanTemplate:
    """Dual gradient with center split."""
    return GroupPlanTemplate(
        template_id="gtpl_base_wash_split",
        name="Gradient Wash - Split",
        description="Dual gradient with center split, higher contrast",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["wash", "gradient", "split", "dual", "continuous"],
        affinity_tags=[
            "motif.gradient_bands",
            "motif.stripes",
            "constraint.clean_edges",
            "style.bold_shapes",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["gradient", "wash", "split"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE],
                density=0.9,
                contrast=0.6,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
