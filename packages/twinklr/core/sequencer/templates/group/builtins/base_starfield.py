"""BASE lane group templates - Starfield family.

Calm, continuous foundation layers for ambient background.
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


@register_group_template(aliases=["Starfield - Slow"])
def make_gtpl_base_starfield_slow() -> GroupPlanTemplate:
    """Slow async twinkle, low density starfield."""
    return GroupPlanTemplate(
        template_id="gtpl_base_starfield_slow",
        name="Starfield - Slow",
        description="Slow async twinkle starfield, low density, calm continuous foundation",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["starfield", "twinkle", "slow", "low-density", "calm"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BACKGROUND,
                motifs=["twinkle", "starfield", "async"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.TWINKLE],
                density=0.3,  # Low density
                contrast=0.5,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Starfield - Dense"])
def make_gtpl_base_starfield_dense() -> GroupPlanTemplate:
    """Medium density starfield, slightly faster twinkle."""
    return GroupPlanTemplate(
        template_id="gtpl_base_starfield_dense",
        name="Starfield - Dense",
        description="Medium density starfield with slightly faster twinkle rate",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["starfield", "twinkle", "medium-density", "calm"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BACKGROUND,
                motifs=["twinkle", "starfield", "async"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.TWINKLE],
                density=0.6,  # Medium density
                contrast=0.6,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
