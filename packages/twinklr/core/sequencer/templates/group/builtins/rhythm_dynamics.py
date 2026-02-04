"""RHYTHM lane group templates - Bounce, Strobe, Sparkle families."""

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


# Bounce family
@register_group_template(aliases=["Bounce - Even"])
def make_gtpl_rhythm_bounce_even() -> GroupPlanTemplate:
    """Even timing bounce."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_bounce_even",
        name="Bounce - Even",
        description="Even timing bounce pattern for arches/matrix",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["bounce", "even", "arch", "matrix"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["bounce", "even", "arch"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.BOUNCE],
                density=0.7,
                contrast=0.7,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Bounce - Staggered"])
def make_gtpl_rhythm_bounce_staggered() -> GroupPlanTemplate:
    """Staggered with delay bounce."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_bounce_staggered",
        name="Bounce - Staggered",
        description="Staggered bounce with delay between groups",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["bounce", "staggered", "delay", "cascade"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["bounce", "stagger", "cascade"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.BOUNCE],
                density=0.7,
                contrast=0.8,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Strobe-Lite (Safe) family
@register_group_template(aliases=["Strobe - Soft"])
def make_gtpl_rhythm_strobe_soft() -> GroupPlanTemplate:
    """Soft rapid change (<8Hz)."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_strobe_soft",
        name="Strobe - Soft",
        description="Soft safe strobe effect, <8Hz rapid change",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["strobe", "soft", "safe", "rapid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["strobe", "soft", "rapid"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.STROBE],
                density=0.6,
                contrast=0.7,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Strobe - Burst"])
def make_gtpl_rhythm_strobe_burst() -> GroupPlanTemplate:
    """Burst pattern (3-beat, pause)."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_strobe_burst",
        name="Strobe - Burst",
        description="Burst strobe pattern: 3-beat rapid, then pause",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["strobe", "burst", "pattern", "pause"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["strobe", "burst", "pattern"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.STROBE],
                density=0.5,
                contrast=0.8,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Sparkle Hits family
@register_group_template(aliases=["Sparkle - Beat"])
def make_gtpl_rhythm_sparkle_beat() -> GroupPlanTemplate:
    """Sparkle on downbeats."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_sparkle_beat",
        name="Sparkle - Beat",
        description="Sparkle hits on downbeats",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["sparkle", "beat", "downbeat", "hit"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["sparkle", "beat", "hit"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SPARKLE],
                density=0.5,
                contrast=0.8,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Sparkle - Offbeat"])
def make_gtpl_rhythm_sparkle_offbeat() -> GroupPlanTemplate:
    """Sparkle on offbeats."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_sparkle_offbeat",
        name="Sparkle - Offbeat",
        description="Sparkle hits on offbeats",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["sparkle", "offbeat", "syncopated", "hit"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["sparkle", "offbeat", "hit"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SPARKLE],
                density=0.5,
                contrast=0.9,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
