"""BASE lane group templates - Particle motif ambient (confetti, particles, bokeh, sparkles, stars, light trails, ribbons, flares)."""

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


@register_group_template(aliases=["Confetti - Ambient"])
def make_gtpl_base_motif_confetti_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing confetti motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_confetti_ambient",
        name="Confetti - Ambient",
        description="Ambient base look emphasizing confetti motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['ambient', 'base', 'confetti', 'color_wash'],
        affinity_tags=['motif.confetti', 'style.clean_vector', 'style.bold_shapes', 'constraint.low_detail', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['confetti', 'ambient'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SHIMMER],
            density=0.8,
            contrast=0.35,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['confetti', 'sparkle_overlay'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SPARKLE],
            density=0.35,
            contrast=0.75,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Optional sparkle layer for depth; keep low density.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Particles - Ambient"])
def make_gtpl_base_motif_particles_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing particles motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_particles_ambient",
        name="Particles - Ambient",
        description="Ambient base look emphasizing particles motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['ambient', 'base', 'particles', 'color_wash'],
        affinity_tags=['motif.particles', 'style.clean_vector', 'style.bold_shapes', 'constraint.low_detail', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['particles', 'ambient'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SHIMMER],
            density=0.8,
            contrast=0.35,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['particles', 'sparkle_overlay'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SPARKLE],
            density=0.35,
            contrast=0.75,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Optional sparkle layer for depth; keep low density.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Bokeh - Ambient"])
def make_gtpl_base_motif_bokeh_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing bokeh motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_bokeh_ambient",
        name="Bokeh - Ambient",
        description="Ambient base look emphasizing bokeh motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['ambient', 'base', 'bokeh', 'color_wash'],
        affinity_tags=['motif.bokeh', 'style.clean_vector', 'style.bold_shapes', 'constraint.low_detail', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['bokeh', 'ambient'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SHIMMER],
            density=0.8,
            contrast=0.35,
            color_mode=ColorMode.MONOCHROME,
            notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['bokeh', 'sparkle_overlay'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SPARKLE],
            density=0.35,
            contrast=0.75,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Optional sparkle layer for depth; keep low density.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Sparkles - Ambient"])
def make_gtpl_base_motif_sparkles_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing sparkles motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_sparkles_ambient",
        name="Sparkles - Ambient",
        description="Ambient base look emphasizing sparkles motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['ambient', 'base', 'sparkles', 'color_wash'],
        affinity_tags=['motif.sparkles', 'style.clean_vector', 'style.bold_shapes', 'constraint.low_detail', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['sparkles', 'ambient'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SHIMMER],
            density=0.8,
            contrast=0.35,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['sparkles', 'sparkle_overlay'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SPARKLE],
            density=0.35,
            contrast=0.75,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Optional sparkle layer for depth; keep low density.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Stars - Ambient"])
def make_gtpl_base_motif_stars_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing stars motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_stars_ambient",
        name="Stars - Ambient",
        description="Ambient base look emphasizing stars motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['ambient', 'base', 'stars', 'color_wash'],
        affinity_tags=['motif.stars', 'style.clean_vector', 'style.bold_shapes', 'constraint.low_detail', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['stars', 'ambient'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SHIMMER],
            density=0.8,
            contrast=0.35,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['stars', 'sparkle_overlay'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SPARKLE],
            density=0.35,
            contrast=0.75,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Optional sparkle layer for depth; keep low density.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Light Trails - Ambient"])
def make_gtpl_base_motif_light_trails_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing light trails motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_light_trails_ambient",
        name="Light Trails - Ambient",
        description="Ambient base look emphasizing light trails motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['ambient', 'base', 'light_trails', 'color_wash'],
        affinity_tags=['motif.light_trails', 'style.clean_vector', 'style.bold_shapes', 'constraint.low_detail', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['light_trails', 'ambient'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SHIMMER],
            density=0.8,
            contrast=0.35,
            color_mode=ColorMode.MONOCHROME,
            notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['light_trails', 'sparkle_overlay'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SPARKLE],
            density=0.35,
            contrast=0.75,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Optional sparkle layer for depth; keep low density.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Ribbons - Ambient"])
def make_gtpl_base_motif_ribbons_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing ribbons motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_ribbons_ambient",
        name="Ribbons - Ambient",
        description="Ambient base look emphasizing ribbons motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['ambient', 'base', 'ribbons', 'color_wash'],
        affinity_tags=['motif.ribbons', 'style.clean_vector', 'style.bold_shapes', 'constraint.low_detail', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['ribbons', 'ambient'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SHIMMER],
            density=0.8,
            contrast=0.35,
            color_mode=ColorMode.MONOCHROME,
            notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Flares - Ambient"])
def make_gtpl_base_motif_flares_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing flares motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_flares_ambient",
        name="Flares - Ambient",
        description="Ambient base look emphasizing flares motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['ambient', 'base', 'flares', 'color_wash'],
        affinity_tags=['motif.flares', 'style.clean_vector', 'style.bold_shapes', 'constraint.low_detail', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['flares', 'ambient'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SHIMMER],
            density=0.8,
            contrast=0.35,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['flares', 'sparkle_overlay'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SPARKLE],
            density=0.35,
            contrast=0.75,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Optional sparkle layer for depth; keep low density.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )

