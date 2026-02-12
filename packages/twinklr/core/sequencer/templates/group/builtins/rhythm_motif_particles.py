"""RHYTHM lane group templates - Particle motif drive (confetti, particles, bokeh, sparkles, stars, light trails, ribbons, flares)."""

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


@register_group_template(aliases=["Confetti - Drive"])
def make_gtpl_rhythm_motif_confetti_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around confetti; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_confetti_drive",
        name="Confetti - Drive",
        description="Rhythmic motion pattern built around confetti; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["rhythm", "drive", "confetti", "wave"],
        affinity_tags=[
            "motif.confetti",
            "setting.hype",
            "style.bold_shapes",
            "constraint.high_contrast",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["confetti", "rhythm"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SPARKLE],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Particles - Drive"])
def make_gtpl_rhythm_motif_particles_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around particles; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_particles_drive",
        name="Particles - Drive",
        description="Rhythmic motion pattern built around particles; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["rhythm", "drive", "particles", "wave"],
        affinity_tags=[
            "motif.particles",
            "setting.hype",
            "style.bold_shapes",
            "constraint.high_contrast",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["particles", "rhythm"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SPARKLE],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Bokeh - Drive"])
def make_gtpl_rhythm_motif_bokeh_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around bokeh; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_bokeh_drive",
        name="Bokeh - Drive",
        description="Rhythmic motion pattern built around bokeh; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["rhythm", "drive", "bokeh", "wave"],
        affinity_tags=[
            "motif.bokeh",
            "setting.hype",
            "style.bold_shapes",
            "constraint.high_contrast",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["bokeh", "rhythm"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SPARKLE],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Sparkles - Drive"])
def make_gtpl_rhythm_motif_sparkles_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around sparkles; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_sparkles_drive",
        name="Sparkles - Drive",
        description="Rhythmic motion pattern built around sparkles; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["rhythm", "drive", "sparkles", "wave"],
        affinity_tags=[
            "motif.sparkles",
            "setting.hype",
            "style.bold_shapes",
            "constraint.high_contrast",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["sparkles", "rhythm"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SPARKLE],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Stars - Drive"])
def make_gtpl_rhythm_motif_stars_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around stars; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_stars_drive",
        name="Stars - Drive",
        description="Rhythmic motion pattern built around stars; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["rhythm", "drive", "stars", "wave"],
        affinity_tags=[
            "motif.stars",
            "setting.hype",
            "style.bold_shapes",
            "constraint.high_contrast",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["stars", "rhythm"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SPARKLE],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Light Trails - Drive"])
def make_gtpl_rhythm_motif_light_trails_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around light trails; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_light_trails_drive",
        name="Light Trails - Drive",
        description="Rhythmic motion pattern built around light trails; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["rhythm", "drive", "light_trails", "wave"],
        affinity_tags=[
            "motif.light_trails",
            "setting.hype",
            "style.bold_shapes",
            "constraint.high_contrast",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["light_trails", "rhythm"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Ribbons - Drive"])
def make_gtpl_rhythm_motif_ribbons_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around ribbons; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_ribbons_drive",
        name="Ribbons - Drive",
        description="Rhythmic motion pattern built around ribbons; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["rhythm", "drive", "ribbons", "wave"],
        affinity_tags=[
            "motif.ribbons",
            "setting.hype",
            "style.bold_shapes",
            "constraint.high_contrast",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["ribbons", "rhythm"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Flares - Drive"])
def make_gtpl_rhythm_motif_flares_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around flares; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_flares_drive",
        name="Flares - Drive",
        description="Rhythmic motion pattern built around flares; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["rhythm", "drive", "flares", "wave"],
        affinity_tags=[
            "motif.flares",
            "setting.hype",
            "style.bold_shapes",
            "constraint.high_contrast",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["flares", "rhythm"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SPARKLE],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
