"""ACCENT lane group templates - Nature/imagery motif hits (lightning, fire, ice, crystals, ornaments, snowflakes)."""

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


@register_group_template(aliases=["Lightning - Hit (Small)"])
def make_gtpl_accent_motif_lightning_hit_small() -> GroupPlanTemplate:
    """Small accent hit using lightning motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_lightning_hit_small",
        name="Lightning - Hit (Small)",
        description="Small accent hit using lightning motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["accent", "hit", "small", "lightning", "strobe"],
        affinity_tags=[
            "motif.lightning",
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
                motifs=["lightning", "hit", "small"],
                visual_intent=GroupVisualIntent.IMAGERY,
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


@register_group_template(aliases=["Lightning - Hit (Big)"])
def make_gtpl_accent_motif_lightning_hit_big() -> GroupPlanTemplate:
    """Big accent hit using lightning motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_lightning_hit_big",
        name="Lightning - Hit (Big)",
        description="Big accent hit using lightning motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["accent", "hit", "big", "lightning", "strobe"],
        affinity_tags=[
            "motif.lightning",
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
                motifs=["lightning", "hit", "big"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.STROBE],
                density=0.85,
                contrast=0.9,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash", "support"],
                visual_intent=GroupVisualIntent.IMAGERY,
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


@register_group_template(aliases=["Fire - Hit (Small)"])
def make_gtpl_accent_motif_fire_hit_small() -> GroupPlanTemplate:
    """Small accent hit using fire motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_fire_hit_small",
        name="Fire - Hit (Small)",
        description="Small accent hit using fire motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["accent", "hit", "small", "fire", "wipe"],
        affinity_tags=[
            "motif.fire",
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
                motifs=["fire", "hit", "small"],
                visual_intent=GroupVisualIntent.IMAGERY,
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


@register_group_template(aliases=["Fire - Hit (Big)"])
def make_gtpl_accent_motif_fire_hit_big() -> GroupPlanTemplate:
    """Big accent hit using fire motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_fire_hit_big",
        name="Fire - Hit (Big)",
        description="Big accent hit using fire motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["accent", "hit", "big", "fire", "wipe"],
        affinity_tags=[
            "motif.fire",
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
                motifs=["fire", "hit", "big"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.WIPE],
                density=0.85,
                contrast=0.9,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash", "support"],
                visual_intent=GroupVisualIntent.IMAGERY,
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


@register_group_template(aliases=["Ice - Hit (Small)"])
def make_gtpl_accent_motif_ice_hit_small() -> GroupPlanTemplate:
    """Small accent hit using ice motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_ice_hit_small",
        name="Ice - Hit (Small)",
        description="Small accent hit using ice motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["accent", "hit", "small", "ice", "wipe"],
        affinity_tags=[
            "motif.ice",
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
                motifs=["ice", "hit", "small"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.WIPE],
                density=0.55,
                contrast=0.75,
                color_mode=ColorMode.ANALOGOUS,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Ice - Hit (Big)"])
def make_gtpl_accent_motif_ice_hit_big() -> GroupPlanTemplate:
    """Big accent hit using ice motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_ice_hit_big",
        name="Ice - Hit (Big)",
        description="Big accent hit using ice motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["accent", "hit", "big", "ice", "wipe"],
        affinity_tags=[
            "motif.ice",
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
                motifs=["ice", "hit", "big"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.WIPE],
                density=0.85,
                contrast=0.9,
                color_mode=ColorMode.ANALOGOUS,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash", "support"],
                visual_intent=GroupVisualIntent.IMAGERY,
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


@register_group_template(aliases=["Crystals - Hit (Small)"])
def make_gtpl_accent_motif_crystals_hit_small() -> GroupPlanTemplate:
    """Small accent hit using crystals motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_crystals_hit_small",
        name="Crystals - Hit (Small)",
        description="Small accent hit using crystals motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["accent", "hit", "small", "crystals", "wipe"],
        affinity_tags=[
            "motif.crystals",
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
                motifs=["crystals", "hit", "small"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.WIPE],
                density=0.55,
                contrast=0.75,
                color_mode=ColorMode.ANALOGOUS,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Crystals - Hit (Big)"])
def make_gtpl_accent_motif_crystals_hit_big() -> GroupPlanTemplate:
    """Big accent hit using crystals motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_crystals_hit_big",
        name="Crystals - Hit (Big)",
        description="Big accent hit using crystals motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["accent", "hit", "big", "crystals", "wipe"],
        affinity_tags=[
            "motif.crystals",
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
                motifs=["crystals", "hit", "big"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.WIPE],
                density=0.85,
                contrast=0.9,
                color_mode=ColorMode.ANALOGOUS,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash", "support"],
                visual_intent=GroupVisualIntent.IMAGERY,
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


@register_group_template(aliases=["Ornaments - Hit (Small)"])
def make_gtpl_accent_motif_ornaments_hit_small() -> GroupPlanTemplate:
    """Small accent hit using ornaments motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_ornaments_hit_small",
        name="Ornaments - Hit (Small)",
        description="Small accent hit using ornaments motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["accent", "hit", "small", "ornaments", "wipe"],
        affinity_tags=[
            "motif.ornaments",
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
                motifs=["ornaments", "hit", "small"],
                visual_intent=GroupVisualIntent.IMAGERY,
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


@register_group_template(aliases=["Ornaments - Hit (Big)"])
def make_gtpl_accent_motif_ornaments_hit_big() -> GroupPlanTemplate:
    """Big accent hit using ornaments motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_ornaments_hit_big",
        name="Ornaments - Hit (Big)",
        description="Big accent hit using ornaments motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["accent", "hit", "big", "ornaments", "wipe"],
        affinity_tags=[
            "motif.ornaments",
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
                motifs=["ornaments", "hit", "big"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.WIPE],
                density=0.85,
                contrast=0.9,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash", "support"],
                visual_intent=GroupVisualIntent.IMAGERY,
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


@register_group_template(aliases=["Snowflakes - Hit (Small)"])
def make_gtpl_accent_motif_snowflakes_hit_small() -> GroupPlanTemplate:
    """Small accent hit using snowflakes motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_snowflakes_hit_small",
        name="Snowflakes - Hit (Small)",
        description="Small accent hit using snowflakes motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["accent", "hit", "small", "snowflakes", "wipe"],
        affinity_tags=[
            "motif.snowflakes",
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
                motifs=["snowflakes", "hit", "small"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.WIPE],
                density=0.55,
                contrast=0.75,
                color_mode=ColorMode.ANALOGOUS,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Snowflakes - Hit (Big)"])
def make_gtpl_accent_motif_snowflakes_hit_big() -> GroupPlanTemplate:
    """Big accent hit using snowflakes motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_snowflakes_hit_big",
        name="Snowflakes - Hit (Big)",
        description="Big accent hit using snowflakes motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["accent", "hit", "big", "snowflakes", "wipe"],
        affinity_tags=[
            "motif.snowflakes",
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
                motifs=["snowflakes", "hit", "big"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.WIPE],
                density=0.85,
                contrast=0.9,
                color_mode=ColorMode.ANALOGOUS,
                notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash", "support"],
                visual_intent=GroupVisualIntent.IMAGERY,
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
