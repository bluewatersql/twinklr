"""BASE lane group templates - Geometric motif ambient (abstract, geometric, spiral, helix, radial rays, concentric rings, wave bands, zigzag, chevrons, stripes, gradient bands, grid, checker, dots)."""

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


@register_group_template(aliases=["Abstract - Ambient"])
def make_gtpl_base_motif_abstract_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing abstract motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_abstract_ambient",
        name="Abstract - Ambient",
        description="Ambient base look emphasizing abstract motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["ambient", "base", "abstract", "plasma"],
        affinity_tags=[
            "motif.abstract",
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
                motifs=["abstract", "ambient"],
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


@register_group_template(aliases=["Geometric - Ambient"])
def make_gtpl_base_motif_geometric_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing geometric motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_geometric_ambient",
        name="Geometric - Ambient",
        description="Ambient base look emphasizing geometric motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "geometric", "color_wash"],
        affinity_tags=[
            "motif.geometric",
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
                motifs=["geometric", "ambient"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
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


@register_group_template(aliases=["Spiral - Ambient"])
def make_gtpl_base_motif_spiral_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing spiral motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_spiral_ambient",
        name="Spiral - Ambient",
        description="Ambient base look emphasizing spiral motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "spiral", "color_wash"],
        affinity_tags=[
            "motif.spiral",
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
                motifs=["spiral", "ambient"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
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


@register_group_template(aliases=["Helix - Ambient"])
def make_gtpl_base_motif_helix_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing helix motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_helix_ambient",
        name="Helix - Ambient",
        description="Ambient base look emphasizing helix motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "helix", "color_wash"],
        affinity_tags=[
            "motif.helix",
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
                motifs=["helix", "ambient"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
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


@register_group_template(aliases=["Radial Rays - Ambient"])
def make_gtpl_base_motif_radial_rays_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing radial rays motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_radial_rays_ambient",
        name="Radial Rays - Ambient",
        description="Ambient base look emphasizing radial rays motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "radial_rays", "color_wash"],
        affinity_tags=[
            "motif.radial_rays",
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
                motifs=["radial_rays", "ambient"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
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


@register_group_template(aliases=["Concentric Rings - Ambient"])
def make_gtpl_base_motif_concentric_rings_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing concentric rings motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_concentric_rings_ambient",
        name="Concentric Rings - Ambient",
        description="Ambient base look emphasizing concentric rings motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "concentric_rings", "color_wash"],
        affinity_tags=[
            "motif.concentric_rings",
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
                motifs=["concentric_rings", "ambient"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
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


@register_group_template(aliases=["Wave Bands - Ambient"])
def make_gtpl_base_motif_wave_bands_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing wave bands motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_wave_bands_ambient",
        name="Wave Bands - Ambient",
        description="Ambient base look emphasizing wave bands motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "wave_bands", "color_wash"],
        affinity_tags=[
            "motif.wave_bands",
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
                motifs=["wave_bands", "ambient"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
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


@register_group_template(aliases=["Zigzag - Ambient"])
def make_gtpl_base_motif_zigzag_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing zigzag motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_zigzag_ambient",
        name="Zigzag - Ambient",
        description="Ambient base look emphasizing zigzag motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "zigzag", "color_wash"],
        affinity_tags=[
            "motif.zigzag",
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
                motifs=["zigzag", "ambient"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
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


@register_group_template(aliases=["Chevrons - Ambient"])
def make_gtpl_base_motif_chevrons_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing chevrons motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_chevrons_ambient",
        name="Chevrons - Ambient",
        description="Ambient base look emphasizing chevrons motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "chevrons", "color_wash"],
        affinity_tags=[
            "motif.chevrons",
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
                motifs=["chevrons", "ambient"],
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


@register_group_template(aliases=["Stripes - Ambient"])
def make_gtpl_base_motif_stripes_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing stripes motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_stripes_ambient",
        name="Stripes - Ambient",
        description="Ambient base look emphasizing stripes motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "stripes", "color_wash"],
        affinity_tags=[
            "motif.stripes",
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
                motifs=["stripes", "ambient"],
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


@register_group_template(aliases=["Gradient Bands - Ambient"])
def make_gtpl_base_motif_gradient_bands_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing gradient bands motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_gradient_bands_ambient",
        name="Gradient Bands - Ambient",
        description="Ambient base look emphasizing gradient bands motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "gradient_bands", "color_wash"],
        affinity_tags=[
            "motif.gradient_bands",
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
                motifs=["gradient_bands", "ambient"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
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


@register_group_template(aliases=["Grid - Ambient"])
def make_gtpl_base_motif_grid_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing grid motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_grid_ambient",
        name="Grid - Ambient",
        description="Ambient base look emphasizing grid motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "grid", "color_wash"],
        affinity_tags=[
            "motif.grid",
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
                motifs=["grid", "ambient"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.SHIMMER],
                density=0.6,
                contrast=0.35,
                color_mode=ColorMode.MONOCHROME,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Checker - Ambient"])
def make_gtpl_base_motif_checker_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing checker motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_checker_ambient",
        name="Checker - Ambient",
        description="Ambient base look emphasizing checker motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "checker", "color_wash"],
        affinity_tags=[
            "motif.checker",
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
                motifs=["checker", "ambient"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.SHIMMER],
                density=0.6,
                contrast=0.35,
                color_mode=ColorMode.DICHROME,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Dots - Ambient"])
def make_gtpl_base_motif_dots_ambient() -> GroupPlanTemplate:
    """Ambient base look emphasizing dots motif; slow shimmer/fade for continuity."""
    return GroupPlanTemplate(
        template_id="gtpl_base_motif_dots_ambient",
        name="Dots - Ambient",
        description="Ambient base look emphasizing dots motif; slow shimmer/fade for continuity.",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["ambient", "base", "dots", "color_wash"],
        affinity_tags=[
            "motif.dots",
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
                motifs=["dots", "ambient"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.SHIMMER],
                density=0.6,
                contrast=0.35,
                color_mode=ColorMode.MONOCHROME,
                notes="xLights-friendly base; pairs well with RHYTHM/ACCENT overlays.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
