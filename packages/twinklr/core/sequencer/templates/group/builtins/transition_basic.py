"""TRANSITION lane group templates - Fade, Crossfade, Wipe families.

Section transition templates for smooth scene changes.
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


# Fade In/Out family
@register_group_template(aliases=["Fade In"])
def make_gtpl_transition_fade_in() -> GroupPlanTemplate:
    """Fade in from black."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_fade_in",
        name="Fade In",
        description="Smooth fade in from black",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["fade", "in", "black", "transition"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BACKGROUND,
                motifs=["fade", "in", "transition"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE],
                density=1.0,
                contrast=0.5,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Fade Out"])
def make_gtpl_transition_fade_out() -> GroupPlanTemplate:
    """Fade out to black."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_fade_out",
        name="Fade Out",
        description="Smooth fade out to black",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["fade", "out", "black", "transition"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BACKGROUND,
                motifs=["fade", "out", "transition"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE],
                density=1.0,
                contrast=0.5,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Crossfade Bed Change family
@register_group_template(aliases=["Crossfade - Soft"])
def make_gtpl_transition_crossfade_soft() -> GroupPlanTemplate:
    """Soft crossfade (2 bars)."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_crossfade_soft",
        name="Crossfade - Soft",
        description="Soft 2-bar crossfade between layers",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["crossfade", "soft", "blend", "smooth"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BACKGROUND,
                motifs=["crossfade", "blend", "soft"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE],
                density=0.9,
                contrast=0.4,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Crossfade - Hard"])
def make_gtpl_transition_crossfade_hard() -> GroupPlanTemplate:
    """Fast crossfade (1 bar)."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_crossfade_hard",
        name="Crossfade - Hard",
        description="Fast 1-bar crossfade between layers",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["crossfade", "hard", "fast", "quick"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=2),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BACKGROUND,
                motifs=["crossfade", "fast", "hard"],
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


# Wipe family
@register_group_template(aliases=["Wipe - L→R"])
def make_gtpl_transition_wipe_lr() -> GroupPlanTemplate:
    """Left-to-right wipe."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_wipe_lr",
        name="Wipe - L→R",
        description="Left-to-right wipe transition",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["wipe", "lr", "left-right", "transition"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BACKGROUND,
                motifs=["wipe", "linear", "lr"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.WIPE],
                density=1.0,
                contrast=0.7,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Wipe - Radial"])
def make_gtpl_transition_wipe_radial() -> GroupPlanTemplate:
    """Center-out radial wipe."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_wipe_radial",
        name="Wipe - Radial",
        description="Center-out radial wipe transition",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["wipe", "radial", "center", "expand"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BACKGROUND,
                motifs=["wipe", "radial", "expand"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.WIPE, MotionVerb.RIPPLE],
                density=1.0,
                contrast=0.7,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
