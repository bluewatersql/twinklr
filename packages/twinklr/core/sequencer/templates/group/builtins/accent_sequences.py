"""ACCENT lane group templates - Bell, Callout, Roll-Call families."""

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


# Bell Ring / Jingle family
@register_group_template(aliases=["Bell - Single"])
def make_gtpl_accent_bell_single() -> GroupPlanTemplate:
    """Single ring (flash + decay)."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_bell_single",
        name="Bell - Single",
        description="Single bell ring with flash and decay",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["bell", "ring", "single", "decay"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=2),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["bell", "ring", "decay"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE, MotionVerb.FADE],
                density=0.7,
                contrast=0.8,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Bell - Double"])
def make_gtpl_accent_bell_double() -> GroupPlanTemplate:
    """Double ring (ding-ding)."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_bell_double",
        name="Bell - Double",
        description="Double bell ring pattern (ding-ding)",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["bell", "ring", "double", "ding"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=2),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["bell", "double", "ding"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.7,
                contrast=0.9,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Callout family
@register_group_template(aliases=["Call - Response Simple"])
def make_gtpl_accent_call_response_simple() -> GroupPlanTemplate:
    """A calls, B responds."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_call_response_simple",
        name="Call-Response - Simple",
        description="Simple call-response: A calls, B responds",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["call", "response", "simple", "dialogue"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["call", "response", "dialogue"],
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


@register_group_template(aliases=["Call - Response Stacked"])
def make_gtpl_accent_call_response_stacked() -> GroupPlanTemplate:
    """Overlapping call-response."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_call_response_stacked",
        name="Call-Response - Stacked",
        description="Overlapping call-response pattern",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["call", "response", "stacked", "overlap"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["call", "response", "overlap"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE, MotionVerb.FADE],
                density=0.7,
                contrast=0.9,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Roll-Call family
@register_group_template(aliases=["Roll-Call - L→R"])
def make_gtpl_accent_rollcall_lr() -> GroupPlanTemplate:
    """Left-to-right sequential."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_rollcall_lr",
        name="Roll-Call - L→R",
        description="Left-to-right sequential roll-call",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["rollcall", "sequential", "lr", "order"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["rollcall", "sequential", "order"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.CHASE],
                density=0.8,
                contrast=0.9,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Roll-Call - Random"])
def make_gtpl_accent_rollcall_random() -> GroupPlanTemplate:
    """Random order roll-call."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_rollcall_random",
        name="Roll-Call - Random",
        description="Random order roll-call pattern",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["rollcall", "random", "unpredictable"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["rollcall", "random", "unpredictable"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SPARKLE],
                density=0.7,
                contrast=0.9,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
