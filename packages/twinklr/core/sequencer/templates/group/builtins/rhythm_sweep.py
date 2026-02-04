"""RHYTHM lane group templates - Sweep family."""

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


@register_group_template(aliases=["Sweep - Left to Right"])
def make_gtpl_rhythm_sweep_lr() -> GroupPlanTemplate:
    """Left to right sweep."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_sweep_lr",
        name="Sweep - L→R",
        description="Linear sweep left to right",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["sweep", "lr", "left-right", "linear"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["sweep", "linear", "lr"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SWEEP],
                density=0.8,
                contrast=0.7,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Sweep - Right to Left"])
def make_gtpl_rhythm_sweep_rl() -> GroupPlanTemplate:
    """Right to left sweep."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_sweep_rl",
        name="Sweep - R→L",
        description="Linear sweep right to left",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["sweep", "rl", "right-left", "linear"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["sweep", "linear", "rl"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SWEEP],
                density=0.8,
                contrast=0.7,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Sweep - Pingpong"])
def make_gtpl_rhythm_sweep_pingpong() -> GroupPlanTemplate:
    """Pingpong L→R→L sweep."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_sweep_pingpong",
        name="Sweep - Pingpong",
        description="Pingpong sweep L→R→L pattern",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["sweep", "pingpong", "bounce", "bidirectional"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["sweep", "pingpong", "bounce"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SWEEP, MotionVerb.BOUNCE],
                density=0.8,
                contrast=0.8,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
