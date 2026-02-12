"""BASE lane group templates - Nature/imagery motif ambient (lightning, fire, ice, crystals, clouds, smoke, water, cosmic, snowflakes, ornaments, candy stripes)."""

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


@register_group_template(aliases=["Lightning - Ambient"])
def make_gtpl_base_motif_lightning_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing lightning motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_lightning_ambient",
        name="Lightning - Ambient",
        description="Ambient base look emphasizing lightning motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["ambient", "base", "lightning", "color_wash"],
        affinity_tags=[
            "motif.lightning",
            "style.clean_vector",
            "style.bold_shapes",
            "constraint.low_detail",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["lightning", "ambient"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.SHIMMER],
                density=0.8,
                contrast=0.7,
                color_mode=ColorMode.MONOCHROME,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Fire - Ambient"])
def make_gtpl_base_motif_fire_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing fire motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_fire_ambient",
        name="Fire - Ambient",
        description="Ambient base look emphasizing fire motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["ambient", "base", "fire", "color_wash"],
        affinity_tags=[
            "motif.fire",
            "style.clean_vector",
            "style.bold_shapes",
            "constraint.low_detail",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["fire", "ambient"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.SHIMMER],
                density=0.8,
                contrast=0.35,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Ice - Ambient"])
def make_gtpl_base_motif_ice_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing ice motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_ice_ambient",
        name="Ice - Ambient",
        description="Ambient base look emphasizing ice motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["ambient", "base", "ice", "color_wash"],
        affinity_tags=[
            "motif.ice",
            "style.clean_vector",
            "style.bold_shapes",
            "constraint.low_detail",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["ice", "ambient"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.SHIMMER],
                density=0.8,
                contrast=0.35,
                color_mode=ColorMode.ANALOGOUS,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Crystals - Ambient"])
def make_gtpl_base_motif_crystals_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing crystals motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_crystals_ambient",
        name="Crystals - Ambient",
        description="Ambient base look emphasizing crystals motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["ambient", "base", "crystals", "color_wash"],
        affinity_tags=[
            "motif.crystals",
            "style.clean_vector",
            "style.bold_shapes",
            "constraint.low_detail",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["crystals", "ambient"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.SHIMMER],
                density=0.8,
                contrast=0.35,
                color_mode=ColorMode.ANALOGOUS,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Clouds - Ambient"])
def make_gtpl_base_motif_clouds_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing clouds motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_clouds_ambient",
        name="Clouds - Ambient",
        description="Ambient base look emphasizing clouds motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["ambient", "base", "clouds", "color_wash"],
        affinity_tags=[
            "motif.clouds",
            "style.clean_vector",
            "style.bold_shapes",
            "constraint.low_detail",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["clouds", "ambient"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.FADE],
                density=0.8,
                contrast=0.35,
                color_mode=ColorMode.ANALOGOUS,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Smoke - Ambient"])
def make_gtpl_base_motif_smoke_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing smoke motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_smoke_ambient",
        name="Smoke - Ambient",
        description="Ambient base look emphasizing smoke motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["ambient", "base", "smoke", "color_wash"],
        affinity_tags=[
            "motif.smoke",
            "style.clean_vector",
            "style.bold_shapes",
            "constraint.low_detail",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["smoke", "ambient"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.FADE],
                density=0.8,
                contrast=0.35,
                color_mode=ColorMode.ANALOGOUS,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Water - Ambient"])
def make_gtpl_base_motif_water_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing water motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_water_ambient",
        name="Water - Ambient",
        description="Ambient base look emphasizing water motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["ambient", "base", "water", "color_wash"],
        affinity_tags=[
            "motif.water",
            "style.clean_vector",
            "style.bold_shapes",
            "constraint.low_detail",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["water", "ambient"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.FADE],
                density=0.8,
                contrast=0.35,
                color_mode=ColorMode.ANALOGOUS,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Cosmic - Ambient"])
def make_gtpl_base_motif_cosmic_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing cosmic motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_cosmic_ambient",
        name="Cosmic - Ambient",
        description="Ambient base look emphasizing cosmic motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["ambient", "base", "cosmic", "plasma"],
        affinity_tags=[
            "motif.cosmic",
            "style.clean_vector",
            "style.bold_shapes",
            "constraint.low_detail",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["cosmic", "ambient"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.SHIMMER],
                density=0.8,
                contrast=0.35,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Snowflakes - Ambient"])
def make_gtpl_base_motif_snowflakes_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing snowflakes motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_snowflakes_ambient",
        name="Snowflakes - Ambient",
        description="Ambient base look emphasizing snowflakes motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["ambient", "base", "snowflakes", "color_wash"],
        affinity_tags=[
            "motif.snowflakes",
            "style.clean_vector",
            "style.bold_shapes",
            "constraint.low_detail",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["snowflakes", "ambient"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.SHIMMER],
                density=0.8,
                contrast=0.35,
                color_mode=ColorMode.ANALOGOUS,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Ornaments - Ambient"])
def make_gtpl_base_motif_ornaments_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing ornaments motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_ornaments_ambient",
        name="Ornaments - Ambient",
        description="Ambient base look emphasizing ornaments motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["ambient", "base", "ornaments", "color_wash"],
        affinity_tags=[
            "motif.ornaments",
            "style.clean_vector",
            "style.bold_shapes",
            "constraint.low_detail",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["ornaments", "ambient"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.SHIMMER],
                density=0.8,
                contrast=0.35,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Candy Stripes - Ambient"])
def make_gtpl_base_motif_candy_stripes_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing candy stripes motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_candy_stripes_ambient",
        name="Candy Stripes - Ambient",
        description="Ambient base look emphasizing candy stripes motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "candy_stripes", "color_wash"],
        affinity_tags=[
            "motif.candy_stripes",
            "style.clean_vector",
            "style.bold_shapes",
            "constraint.low_detail",
            "constraint.clean_edges",
        ],
        avoid_tags=["constraint.noisy_texture_avoid"],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["candy_stripes", "ambient"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.SHIMMER],
                density=0.8,
                contrast=0.35,
                color_mode=ColorMode.DICHROME,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
