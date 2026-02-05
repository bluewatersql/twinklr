"""STRAND lane group templates - Single-strand (1D) effect templates for outlines, mini trees, arches, etc."""

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


@register_group_template(aliases=["Strand - Chase"])
def make_gtpl_rhythm_strand_chase() -> GroupPlanTemplate:
    """Single-strand 1D effect: Chase. Good for outlines and 1D props."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_strand_chase",
        name="Strand - Chase",
        description="Single-strand 1D effect: Chase. Good for outlines and 1D props.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['strand', '1d', 'chase', 'chase'],
        affinity_tags=['motif.stripes', 'style.bold_shapes', 'constraint.clean_edges', 'constraint.low_detail'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['strand', 'chase'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.SWEEP],
            density=0.7,
            contrast=0.85,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Render as 1D chase/pulse; map segments to beats with value curves.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Strand - Bounce / Ping-Pong"])
def make_gtpl_rhythm_strand_pingpong() -> GroupPlanTemplate:
    """Single-strand 1D effect: Bounce / Ping-Pong. Good for outlines and 1D props."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_strand_pingpong",
        name="Strand - Bounce / Ping-Pong",
        description="Single-strand 1D effect: Bounce / Ping-Pong. Good for outlines and 1D props.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['strand', '1d', 'pingpong', 'pingpong'],
        affinity_tags=['motif.stripes', 'style.bold_shapes', 'constraint.clean_edges', 'constraint.low_detail'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['strand', 'pingpong'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.BOUNCE],
            density=0.7,
            contrast=0.85,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Render as 1D chase/pulse; map segments to beats with value curves.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Strand - Comet / Meteor"])
def make_gtpl_rhythm_strand_comet() -> GroupPlanTemplate:
    """Single-strand 1D effect: Comet / Meteor. Good for outlines and 1D props."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_strand_comet",
        name="Strand - Comet / Meteor",
        description="Single-strand 1D effect: Comet / Meteor. Good for outlines and 1D props.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['strand', '1d', 'comet', 'comet'],
        affinity_tags=['motif.stripes', 'style.bold_shapes', 'constraint.clean_edges', 'constraint.low_detail'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['strand', 'comet'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.SWEEP],
            density=0.7,
            contrast=0.85,
            color_mode=ColorMode.MONOCHROME,
            notes="Render as 1D chase/pulse; map segments to beats with value curves.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Strand - Color Wipe"])
def make_gtpl_rhythm_strand_color_wipe() -> GroupPlanTemplate:
    """Single-strand 1D effect: Color Wipe. Good for outlines and 1D props."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_strand_color_wipe",
        name="Strand - Color Wipe",
        description="Single-strand 1D effect: Color Wipe. Good for outlines and 1D props.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['strand', '1d', 'color_wipe', 'color_wipe'],
        affinity_tags=['motif.stripes', 'style.bold_shapes', 'constraint.clean_edges', 'constraint.low_detail'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['strand', 'color_wipe'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.WIPE],
            density=0.7,
            contrast=0.85,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Render as 1D chase/pulse; map segments to beats with value curves.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Strand - Alternating Blocks"])
def make_gtpl_rhythm_strand_alt_blocks() -> GroupPlanTemplate:
    """Single-strand 1D effect: Alternating Blocks. Good for outlines and 1D props."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_strand_alt_blocks",
        name="Strand - Alternating Blocks",
        description="Single-strand 1D effect: Alternating Blocks. Good for outlines and 1D props.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['strand', '1d', 'alt_blocks', 'alt_blocks'],
        affinity_tags=['motif.stripes', 'style.bold_shapes', 'constraint.clean_edges', 'constraint.low_detail'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['strand', 'alt_blocks'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.SWEEP],
            density=0.7,
            contrast=0.85,
            color_mode=ColorMode.DICHROME,
            notes="Render as 1D chase/pulse; map segments to beats with value curves.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Strand - Sparkle Along Strand"])
def make_gtpl_rhythm_strand_sparkle_along() -> GroupPlanTemplate:
    """Single-strand 1D effect: Sparkle Along Strand. Good for outlines and 1D props."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_strand_sparkle_along",
        name="Strand - Sparkle Along Strand",
        description="Single-strand 1D effect: Sparkle Along Strand. Good for outlines and 1D props.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['strand', '1d', 'sparkle_along', 'sparkle_along'],
        affinity_tags=['motif.stripes', 'style.bold_shapes', 'constraint.clean_edges', 'constraint.low_detail'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['strand', 'sparkle_along'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.SPARKLE],
            density=0.7,
            contrast=0.85,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Render as 1D chase/pulse; map segments to beats with value curves.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Strand - Segment Pulses"])
def make_gtpl_rhythm_strand_segment_pulses() -> GroupPlanTemplate:
    """Single-strand 1D effect: Segment Pulses. Good for outlines and 1D props."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_strand_segment_pulses",
        name="Strand - Segment Pulses",
        description="Single-strand 1D effect: Segment Pulses. Good for outlines and 1D props.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['strand', '1d', 'segment_pulses', 'segment_pulses'],
        affinity_tags=['motif.stripes', 'style.bold_shapes', 'constraint.clean_edges', 'constraint.low_detail'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['strand', 'segment_pulses'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.PULSE],
            density=0.7,
            contrast=0.85,
            color_mode=ColorMode.DICHROME,
            notes="Render as 1D chase/pulse; map segments to beats with value curves.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Strand - Gradient Scroll"])
def make_gtpl_rhythm_strand_gradient_scroll() -> GroupPlanTemplate:
    """Single-strand 1D effect: Gradient Scroll. Good for outlines and 1D props."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_strand_gradient_scroll",
        name="Strand - Gradient Scroll",
        description="Single-strand 1D effect: Gradient Scroll. Good for outlines and 1D props.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['strand', '1d', 'gradient_scroll', 'gradient_scroll'],
        affinity_tags=['motif.stripes', 'style.bold_shapes', 'constraint.clean_edges', 'constraint.low_detail'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['strand', 'gradient_scroll'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.SWEEP],
            density=0.7,
            contrast=0.85,
            color_mode=ColorMode.ANALOGOUS,
            notes="Render as 1D chase/pulse; map segments to beats with value curves.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Strand - Level Meter (1D VU)"])
def make_gtpl_rhythm_strand_level_meter() -> GroupPlanTemplate:
    """Single-strand 1D effect: Level Meter (1D VU). Good for outlines and 1D props."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_strand_level_meter",
        name="Strand - Level Meter (1D VU)",
        description="Single-strand 1D effect: Level Meter (1D VU). Good for outlines and 1D props.",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['strand', '1d', 'level_meter', 'level_meter'],
        affinity_tags=['motif.stripes', 'style.bold_shapes', 'constraint.clean_edges', 'constraint.low_detail'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['strand', 'level_meter'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.PULSE],
            density=0.7,
            contrast=0.85,
            color_mode=ColorMode.MONOCHROME,
            notes="Render as 1D chase/pulse; map segments to beats with value curves.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Strand - Random Color Chase"])
def make_gtpl_rhythm_strand_random_chase() -> GroupPlanTemplate:
    """Single-strand 1D effect: Random Color Chase. Good for outlines and 1D props."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_strand_random_chase",
        name="Strand - Random Color Chase",
        description="Single-strand 1D effect: Random Color Chase. Good for outlines and 1D props.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['strand', '1d', 'random_chase', 'random_chase'],
        affinity_tags=['motif.stripes', 'style.bold_shapes', 'constraint.clean_edges', 'constraint.low_detail'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=16),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['strand', 'random_chase'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.SWEEP],
            density=0.7,
            contrast=0.85,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Render as 1D chase/pulse; map segments to beats with value curves.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
