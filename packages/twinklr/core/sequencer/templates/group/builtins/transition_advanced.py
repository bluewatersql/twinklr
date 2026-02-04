"""TRANSITION lane group templates - Ramp, Texture Swap, Build families."""

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


# Ramp Intensity family
@register_group_template(aliases=["Ramp Up"])
def make_gtpl_transition_ramp_up() -> GroupPlanTemplate:
    """0→100% over 2-4 bars."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_ramp_up",
        name="Ramp Up",
        description="Intensity ramp from 0 to 100% over 2-4 bars",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["ramp", "up", "build", "intensity"],
        affinity_tags=["motif.abstract", "style.minimal", "setting.hype", "constraint.clean_edges"],
        avoid_tags=[],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["ramp", "build", "crescendo"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE],
                density=0.9,
                contrast=0.6,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Ramp Down"])
def make_gtpl_transition_ramp_down() -> GroupPlanTemplate:
    """100→0% intensity."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_ramp_down",
        name="Ramp Down",
        description="Intensity ramp from 100 to 0%",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["ramp", "down", "decay", "intensity"],
        affinity_tags=["motif.abstract", "style.minimal", "setting.calm", "constraint.clean_edges"],
        avoid_tags=[],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["ramp", "decay", "diminuendo"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE],
                density=0.9,
                contrast=0.6,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Texture Swap family
@register_group_template(aliases=["Texture Swap - Forward"])
def make_gtpl_transition_texture_swap() -> GroupPlanTemplate:
    """Swap base, hold rhythm."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_texture_swap",
        name="Texture Swap",
        description="Swap base layer texture while holding rhythm",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["texture", "swap", "change", "base"],
        affinity_tags=["motif.abstract", "style.minimal", "constraint.clean_edges"],
        avoid_tags=[],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=2),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["swap", "texture", "change"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE],
                density=0.8,
                contrast=0.5,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Texture Swap - Reverse"])
def make_gtpl_transition_texture_swap_reverse() -> GroupPlanTemplate:
    """Reverse direction swap."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_texture_swap_reverse",
        name="Texture Swap - Reverse",
        description="Reverse direction texture swap",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["texture", "swap", "reverse", "change"],
        affinity_tags=[
            "motif.abstract",
            "style.minimal",
            "constraint.clean_edges",
            "setting.playful",
        ],
        avoid_tags=[],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=2),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["swap", "reverse", "texture"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE, MotionVerb.FLIP],
                density=0.8,
                contrast=0.5,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Pre-Chorus Build family
@register_group_template(aliases=["Build - Short"])
def make_gtpl_transition_build_short() -> GroupPlanTemplate:
    """Short build (1 bar)."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_build_short",
        name="Build - Short",
        description="Short 1-bar pre-chorus build",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["build", "short", "pre-chorus", "anticipation"],
        affinity_tags=[
            "motif.abstract",
            "setting.hype",
            "constraint.high_contrast",
            "style.bold_shapes",
        ],
        avoid_tags=[],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=2),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["build", "crescendo", "anticipation"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE, MotionVerb.FADE],
                density=0.7,
                contrast=0.7,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Build - Long"])
def make_gtpl_transition_build_long() -> GroupPlanTemplate:
    """Extended build (4 bars)."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_build_long",
        name="Build - Long",
        description="Extended 4-bar pre-chorus build",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["build", "long", "extended", "anticipation"],
        affinity_tags=[
            "motif.abstract",
            "setting.hype",
            "setting.triumphant",
            "constraint.high_contrast",
        ],
        avoid_tags=[],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["build", "crescendo", "extended"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE, MotionVerb.RIPPLE],
                density=0.8,
                contrast=0.8,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
