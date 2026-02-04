"""BASE lane group templates - Snow Haze family."""

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


@register_group_template(aliases=["Snow Haze - Low"])
def make_gtpl_base_snow_haze_low() -> GroupPlanTemplate:
    """Low-density falling snow haze."""
    return GroupPlanTemplate(
        template_id="gtpl_base_snow_haze_low",
        name="Snow Haze - Low",
        description="Low-density falling snow haze, subtle ambient",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.TEXTURE,
        tags=["snow", "haze", "low-density", "falling", "ambient"],
        affinity_tags=[
            "motif.snowflakes",
            "constraint.sparse_elements",
            "setting.calm",
            "constraint.low_detail",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.high_contrast"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["snow", "falling", "haze"],
                visual_intent=GroupVisualIntent.TEXTURE,
                motion=[MotionVerb.FADE],
                density=0.3,
                contrast=0.4,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Snow Haze - High"])
def make_gtpl_base_snow_haze_high() -> GroupPlanTemplate:
    """Medium-density snow with drift."""
    return GroupPlanTemplate(
        template_id="gtpl_base_snow_haze_high",
        name="Snow Haze - High",
        description="Medium-density falling snow with drift effect",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.TEXTURE,
        tags=["snow", "haze", "medium-density", "drift", "ambient"],
        affinity_tags=[
            "motif.snowflakes",
            "setting.calm",
            "setting.dreamy",
            "constraint.low_detail",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.high_contrast"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["snow", "falling", "drift"],
                visual_intent=GroupVisualIntent.TEXTURE,
                motion=[MotionVerb.FADE],
                density=0.5,
                contrast=0.5,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
