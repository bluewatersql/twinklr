"""RHYTHM lane group templates - Pulse family.

Beat-driven motion, medium intensity rhythmic patterns.
"""

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


@register_group_template(aliases=["Pulse - Even"])
def make_gtpl_rhythm_pulse_even() -> GroupPlanTemplate:
    """Even pulse on downbeats."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_pulse_even",
        name="Pulse - Even",
        description="Even beat-synced pulse on downbeats",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["pulse", "beat", "downbeat", "even", "rhythm"],
        affinity_tags=[
            "motif.abstract",
            "constraint.clean_edges",
            "style.minimal",
            "constraint.loopable",
        ],
        avoid_tags=[],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["pulse", "beat", "rhythm"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.7,
                contrast=0.7,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Pulse - Syncopated"])
def make_gtpl_rhythm_pulse_syncopated() -> GroupPlanTemplate:
    """Offbeat pulse."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_pulse_syncopated",
        name="Pulse - Syncopated",
        description="Offbeat syncopated pulse pattern",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["pulse", "syncopated", "offbeat", "rhythm"],
        affinity_tags=[
            "motif.abstract",
            "setting.playful",
            "constraint.clean_edges",
            "style.minimal",
        ],
        avoid_tags=[],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["pulse", "syncopated", "offbeat"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.6,
                contrast=0.8,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Pulse - Half Time"])
def make_gtpl_rhythm_pulse_half_time() -> GroupPlanTemplate:
    """Half-time pulse."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_pulse_half_time",
        name="Pulse - Half Time",
        description="Half-time pulse pattern, slower tempo feel",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["pulse", "half-time", "slow", "rhythm"],
        affinity_tags=["motif.abstract", "setting.calm", "style.minimal", "constraint.clean_edges"],
        avoid_tags=["constraint.high_contrast"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["pulse", "half-time"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.7,
                contrast=0.6,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
