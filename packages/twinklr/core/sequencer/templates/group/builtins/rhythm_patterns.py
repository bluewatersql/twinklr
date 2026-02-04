"""RHYTHM lane group templates - Chase, Ripple, Alternator families."""

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


# Chase / Marquee family
@register_group_template(aliases=["Chase - Single"])
def make_gtpl_rhythm_chase_single() -> GroupPlanTemplate:
    """Single chase line."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_chase_single",
        name="Chase - Single",
        description="Single chase line pattern",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["chase", "single", "marquee", "sequential"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["chase", "marquee", "sequential"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.CHASE],
                density=0.6,
                contrast=0.8,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Chase - Dual"])
def make_gtpl_rhythm_chase_dual() -> GroupPlanTemplate:
    """Dual chase (mirrored)."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_chase_dual",
        name="Chase - Dual",
        description="Dual mirrored chase pattern",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["chase", "dual", "mirrored", "sequential"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["chase", "dual", "mirrored"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.CHASE],
                density=0.7,
                contrast=0.8,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Ripple family
@register_group_template(aliases=["Ripple - Tight"])
def make_gtpl_rhythm_ripple_tight() -> GroupPlanTemplate:
    """Tight, fast propagation ripple."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_ripple_tight",
        name="Ripple - Tight",
        description="Tight fast ripple propagation",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["ripple", "tight", "fast", "propagation"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["ripple", "tight", "fast"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.RIPPLE],
                density=0.7,
                contrast=0.8,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Ripple - Wide"])
def make_gtpl_rhythm_ripple_wide() -> GroupPlanTemplate:
    """Wide, slower propagation ripple."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_ripple_wide",
        name="Ripple - Wide",
        description="Wide slow ripple propagation",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["ripple", "wide", "slow", "propagation"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["ripple", "wide", "slow"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.RIPPLE],
                density=0.6,
                contrast=0.7,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Alternator family
@register_group_template(aliases=["Alternate - A/B"])
def make_gtpl_rhythm_alternate_ab() -> GroupPlanTemplate:
    """Simple A/B alternation."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_alternate_ab",
        name="Alternate - A/B",
        description="Simple A/B group alternation",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["alternate", "ab", "toggle", "groups"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["alternate", "toggle", "ab"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.8,
                contrast=0.8,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Alternate - Triplet"])
def make_gtpl_rhythm_alternate_triplet() -> GroupPlanTemplate:
    """A/B/C triplet alternation."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_alternate_triplet",
        name="Alternate - Triplet",
        description="A/B/C triplet group alternation",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["alternate", "triplet", "abc", "groups"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["alternate", "triplet", "abc"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.9,
                contrast=0.8,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
