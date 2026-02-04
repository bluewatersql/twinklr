"""RHYTHM lane group templates - Wave, Candy-Cane, Icicle, Meter families."""

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


# Wave family
@register_group_template(aliases=["Wave - L→R"])
def make_gtpl_rhythm_wave_lr() -> GroupPlanTemplate:
    """Wave left to right."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_wave_lr",
        name="Wave - L→R",
        description="Sine-like wave motion left to right",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["wave", "lr", "sine", "smooth"],
        affinity_tags=[
            "motif.wave_bands",
            "motif.water",
            "constraint.clean_edges",
            "style.minimal",
        ],
        avoid_tags=[],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["wave", "sine", "smooth"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.WAVE],
                density=0.8,
                contrast=0.6,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Wave - In→Out"])
def make_gtpl_rhythm_wave_inout() -> GroupPlanTemplate:
    """Wave center to edges."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_wave_inout",
        name="Wave - In→Out",
        description="Wave motion from center to edges",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["wave", "center", "radial", "expand"],
        affinity_tags=[
            "motif.concentric_rings",
            "motif.water",
            "constraint.centered_composition",
            "constraint.clean_edges",
        ],
        avoid_tags=[],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["wave", "radial", "expand"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.WAVE, MotionVerb.RIPPLE],
                density=0.7,
                contrast=0.7,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Candy-Cane Stripe family
@register_group_template(aliases=["Candy Stripe - Scroll"])
def make_gtpl_rhythm_candy_stripe_scroll() -> GroupPlanTemplate:
    """Scrolling diagonal candy stripe."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_candy_stripe_scroll",
        name="Candy Stripe - Scroll",
        description="Scrolling diagonal candy cane stripe pattern",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["candy", "stripe", "scroll", "diagonal"],
        affinity_tags=[
            "motif.candy_stripes",
            "motif.stripes",
            "constraint.high_contrast",
            "style.bold_shapes",
        ],
        avoid_tags=[],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["stripe", "diagonal", "scroll"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.ROLL],
                density=0.8,
                contrast=0.8,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Candy Stripe - Rotate"])
def make_gtpl_rhythm_candy_stripe_rotate() -> GroupPlanTemplate:
    """Rotating spiral candy stripe."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_candy_stripe_rotate",
        name="Candy Stripe - Rotate",
        description="Rotating spiral candy cane pattern",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["candy", "stripe", "rotate", "spiral"],
        affinity_tags=[
            "motif.candy_stripes",
            "motif.spiral",
            "constraint.high_contrast",
            "style.bold_shapes",
        ],
        avoid_tags=[],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["stripe", "spiral", "rotate"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.ROLL],
                density=0.9,
                contrast=0.8,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Icicle Drip family
@register_group_template(aliases=["Icicle - Slow"])
def make_gtpl_rhythm_icicle_drip_slow() -> GroupPlanTemplate:
    """Slow drip top-to-bottom."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_icicle_drip_slow",
        name="Icicle - Slow",
        description="Slow icicle drip effect, top to bottom",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["icicle", "drip", "slow", "vertical"],
        affinity_tags=["motif.ice", "motif.water", "constraint.clean_edges", "setting.calm"],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["drip", "vertical", "cascade"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.SWEEP],
                density=0.5,
                contrast=0.7,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Icicle - Fast"])
def make_gtpl_rhythm_icicle_drip_fast() -> GroupPlanTemplate:
    """Fast drip top-to-bottom."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_icicle_drip_fast",
        name="Icicle - Fast",
        description="Fast icicle drip effect, top to bottom",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["icicle", "drip", "fast", "vertical"],
        affinity_tags=["motif.ice", "motif.water", "constraint.clean_edges", "setting.hype"],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["drip", "vertical", "rapid"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.SWEEP],
                density=0.6,
                contrast=0.8,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Meter Change family
@register_group_template(aliases=["Meter - Half Time Hold"])
def make_gtpl_rhythm_half_time_hold() -> GroupPlanTemplate:
    """Halftime hold pattern."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_half_time_hold",
        name="Meter - Half Time Hold",
        description="Halftime hold pattern, sustained notes",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["meter", "half-time", "hold", "sustained"],
        affinity_tags=["motif.abstract", "setting.calm", "style.minimal", "constraint.low_detail"],
        avoid_tags=["constraint.high_contrast"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=16),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["hold", "sustained", "half-time"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE],
                density=0.7,
                contrast=0.6,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Meter - Double Time Push"])
def make_gtpl_rhythm_double_time_push() -> GroupPlanTemplate:
    """Double-time push pattern."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_double_time_push",
        name="Meter - Double Time Push",
        description="Double-time push pattern, increased energy",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["meter", "double-time", "push", "energy"],
        affinity_tags=[
            "motif.abstract",
            "setting.hype",
            "constraint.high_contrast",
            "style.bold_shapes",
        ],
        avoid_tags=[],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["push", "rapid", "double-time"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.8,
                contrast=0.9,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
