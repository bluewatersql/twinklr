"""RHYTHM lane group templates - Nature/imagery motif drive (lightning, fire, ice, crystals, clouds, smoke, water, cosmic, snowflakes, ornaments, candy stripes)."""

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


@register_group_template(aliases=["Lightning - Drive"])
def make_gtpl_rhythm_motif_lightning_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around lightning; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_lightning_drive",
        name="Lightning - Drive",
        description="Rhythmic motion pattern built around lightning; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["rhythm", "drive", "lightning", "wave"],
        affinity_tags=[
            "motif.lightning",
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
                motifs=["lightning", "rhythm"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.STROBE],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Fire - Drive"])
def make_gtpl_rhythm_motif_fire_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around fire; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_fire_drive",
        name="Fire - Drive",
        description="Rhythmic motion pattern built around fire; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["rhythm", "drive", "fire", "wave"],
        affinity_tags=[
            "motif.fire",
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
                motifs=["fire", "rhythm"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.RIPPLE],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Ice - Drive"])
def make_gtpl_rhythm_motif_ice_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around ice; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_ice_drive",
        name="Ice - Drive",
        description="Rhythmic motion pattern built around ice; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["rhythm", "drive", "ice", "wave"],
        affinity_tags=[
            "motif.ice",
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
                motifs=["ice", "rhythm"],
                visual_intent=GroupVisualIntent.IMAGERY,
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


@register_group_template(aliases=["Crystals - Drive"])
def make_gtpl_rhythm_motif_crystals_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around crystals; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_crystals_drive",
        name="Crystals - Drive",
        description="Rhythmic motion pattern built around crystals; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["rhythm", "drive", "crystals", "wave"],
        affinity_tags=[
            "motif.crystals",
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
                motifs=["crystals", "rhythm"],
                visual_intent=GroupVisualIntent.IMAGERY,
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


@register_group_template(aliases=["Clouds - Drive"])
def make_gtpl_rhythm_motif_clouds_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around clouds; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_clouds_drive",
        name="Clouds - Drive",
        description="Rhythmic motion pattern built around clouds; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["rhythm", "drive", "clouds", "wave"],
        affinity_tags=[
            "motif.clouds",
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
                motifs=["clouds", "rhythm"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.WAVE],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Smoke - Drive"])
def make_gtpl_rhythm_motif_smoke_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around smoke; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_smoke_drive",
        name="Smoke - Drive",
        description="Rhythmic motion pattern built around smoke; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["rhythm", "drive", "smoke", "wave"],
        affinity_tags=[
            "motif.smoke",
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
                motifs=["smoke", "rhythm"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.WAVE],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Water - Drive"])
def make_gtpl_rhythm_motif_water_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around water; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_water_drive",
        name="Water - Drive",
        description="Rhythmic motion pattern built around water; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["rhythm", "drive", "water", "wave"],
        affinity_tags=[
            "motif.water",
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
                motifs=["water", "rhythm"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.WAVE],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Cosmic - Drive"])
def make_gtpl_rhythm_motif_cosmic_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around cosmic; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_cosmic_drive",
        name="Cosmic - Drive",
        description="Rhythmic motion pattern built around cosmic; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["rhythm", "drive", "cosmic", "wave"],
        affinity_tags=[
            "motif.cosmic",
            "setting.hype",
            "style.bold_shapes",
            "constraint.high_contrast",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=2, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["cosmic", "rhythm"],
                visual_intent=GroupVisualIntent.IMAGERY,
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


@register_group_template(aliases=["Snowflakes - Drive"])
def make_gtpl_rhythm_motif_snowflakes_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around snowflakes; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_snowflakes_drive",
        name="Snowflakes - Drive",
        description="Rhythmic motion pattern built around snowflakes; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["rhythm", "drive", "snowflakes", "wave"],
        affinity_tags=[
            "motif.snowflakes",
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
                motifs=["snowflakes", "rhythm"],
                visual_intent=GroupVisualIntent.IMAGERY,
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


@register_group_template(aliases=["Ornaments - Drive"])
def make_gtpl_rhythm_motif_ornaments_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around ornaments; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_ornaments_drive",
        name="Ornaments - Drive",
        description="Rhythmic motion pattern built around ornaments; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["rhythm", "drive", "ornaments", "wave"],
        affinity_tags=[
            "motif.ornaments",
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
                motifs=["ornaments", "rhythm"],
                visual_intent=GroupVisualIntent.IMAGERY,
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


@register_group_template(aliases=["Candy Stripes - Drive"])
def make_gtpl_rhythm_motif_candy_stripes_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around candy stripes; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_candy_stripes_drive",
        name="Candy Stripes - Drive",
        description="Rhythmic motion pattern built around candy stripes; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "candy_stripes", "wave"],
        affinity_tags=[
            "motif.candy_stripes",
            "setting.hype",
            "style.bold_shapes",
            "constraint.high_contrast",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=2, bars_max=32),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["candy_stripes", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.SWEEP],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.DICHROME,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
