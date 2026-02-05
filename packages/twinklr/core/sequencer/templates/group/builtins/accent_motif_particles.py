"""ACCENT lane group templates - Particle motif hits (sparkles, stars, flares, particles)."""

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


@register_group_template(aliases=["Sparkles - Hit (Small)"])
def make_gtpl_accent_motif_sparkles_hit_small() -> GroupPlanTemplate:
    """Small accent hit using sparkles motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_sparkles_hit_small",
        name="Sparkles - Hit (Small)",
        description="Small accent hit using sparkles motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["accent", "hit", "small", "sparkles", "strobe"],
        affinity_tags=[
            "motif.sparkles",
            "setting.playful",
            "style.bold_shapes",
            "constraint.high_contrast",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["sparkles", "hit", "small"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.STROBE],
                density=0.55,
                contrast=0.75,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Sparkles - Hit (Big)"])
def make_gtpl_accent_motif_sparkles_hit_big() -> GroupPlanTemplate:
    """Big accent hit using sparkles motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_sparkles_hit_big",
        name="Sparkles - Hit (Big)",
        description="Big accent hit using sparkles motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["accent", "hit", "big", "sparkles", "strobe"],
        affinity_tags=[
            "motif.sparkles",
            "setting.triumphant",
            "style.bold_shapes",
            "constraint.high_contrast",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["sparkles", "hit", "big"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.STROBE],
                density=0.85,
                contrast=0.9,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash", "support"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.6,
                contrast=0.25,
                color_mode=ColorMode.ANALOGOUS,
                notes="Support wash to make the hit feel larger without adding detail.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Stars - Hit (Small)"])
def make_gtpl_accent_motif_stars_hit_small() -> GroupPlanTemplate:
    """Small accent hit using stars motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_stars_hit_small",
        name="Stars - Hit (Small)",
        description="Small accent hit using stars motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["accent", "hit", "small", "stars", "strobe"],
        affinity_tags=[
            "motif.stars",
            "setting.playful",
            "style.bold_shapes",
            "constraint.high_contrast",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["stars", "hit", "small"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.STROBE],
                density=0.55,
                contrast=0.75,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Stars - Hit (Big)"])
def make_gtpl_accent_motif_stars_hit_big() -> GroupPlanTemplate:
    """Big accent hit using stars motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_stars_hit_big",
        name="Stars - Hit (Big)",
        description="Big accent hit using stars motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["accent", "hit", "big", "stars", "strobe"],
        affinity_tags=[
            "motif.stars",
            "setting.triumphant",
            "style.bold_shapes",
            "constraint.high_contrast",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["stars", "hit", "big"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.STROBE],
                density=0.85,
                contrast=0.9,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash", "support"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.6,
                contrast=0.25,
                color_mode=ColorMode.ANALOGOUS,
                notes="Support wash to make the hit feel larger without adding detail.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Flares - Hit (Small)"])
def make_gtpl_accent_motif_flares_hit_small() -> GroupPlanTemplate:
    """Small accent hit using flares motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_flares_hit_small",
        name="Flares - Hit (Small)",
        description="Small accent hit using flares motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["accent", "hit", "small", "flares", "strobe"],
        affinity_tags=[
            "motif.flares",
            "setting.playful",
            "style.bold_shapes",
            "constraint.high_contrast",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["flares", "hit", "small"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.STROBE],
                density=0.55,
                contrast=0.75,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Flares - Hit (Big)"])
def make_gtpl_accent_motif_flares_hit_big() -> GroupPlanTemplate:
    """Big accent hit using flares motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_flares_hit_big",
        name="Flares - Hit (Big)",
        description="Big accent hit using flares motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["accent", "hit", "big", "flares", "strobe"],
        affinity_tags=[
            "motif.flares",
            "setting.triumphant",
            "style.bold_shapes",
            "constraint.high_contrast",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["flares", "hit", "big"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.STROBE],
                density=0.85,
                contrast=0.9,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash", "support"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.6,
                contrast=0.25,
                color_mode=ColorMode.ANALOGOUS,
                notes="Support wash to make the hit feel larger without adding detail.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Particles - Hit (Small)"])
def make_gtpl_accent_motif_particles_hit_small() -> GroupPlanTemplate:
    """Small accent hit using particles motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_particles_hit_small",
        name="Particles - Hit (Small)",
        description="Small accent hit using particles motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["accent", "hit", "small", "particles", "wipe"],
        affinity_tags=[
            "motif.particles",
            "setting.playful",
            "style.bold_shapes",
            "constraint.high_contrast",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["particles", "hit", "small"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.WIPE],
                density=0.55,
                contrast=0.75,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Particles - Hit (Big)"])
def make_gtpl_accent_motif_particles_hit_big() -> GroupPlanTemplate:
    """Big accent hit using particles motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_particles_hit_big",
        name="Particles - Hit (Big)",
        description="Big accent hit using particles motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["accent", "hit", "big", "particles", "wipe"],
        affinity_tags=[
            "motif.particles",
            "setting.triumphant",
            "style.bold_shapes",
            "constraint.high_contrast",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["particles", "hit", "big"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.WIPE],
                density=0.85,
                contrast=0.9,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash", "support"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.6,
                contrast=0.25,
                color_mode=ColorMode.ANALOGOUS,
                notes="Support wash to make the hit feel larger without adding detail.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
