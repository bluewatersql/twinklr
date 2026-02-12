"""RHYTHM lane group templates - Geometric motif drive (abstract, geometric, spiral, helix, radial rays, concentric rings, wave bands, zigzag, chevrons, stripes, gradient bands, grid, checker, dots)."""

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


@register_group_template(aliases=["Abstract - Drive"])
def make_gtpl_rhythm_motif_abstract_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around abstract; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_abstract_drive",
        name="Abstract - Drive",
        description="Rhythmic motion pattern built around abstract; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["rhythm", "drive", "abstract", "wave"],
        affinity_tags=[
            "motif.abstract",
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
                motifs=["abstract", "rhythm"],
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


@register_group_template(aliases=["Geometric - Drive"])
def make_gtpl_rhythm_motif_geometric_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around geometric; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_geometric_drive",
        name="Geometric - Drive",
        description="Rhythmic motion pattern built around geometric; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "geometric", "wave"],
        affinity_tags=[
            "motif.geometric",
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
                motifs=["geometric", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
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


@register_group_template(aliases=["Spiral - Drive"])
def make_gtpl_rhythm_motif_spiral_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around spiral; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_spiral_drive",
        name="Spiral - Drive",
        description="Rhythmic motion pattern built around spiral; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "spiral", "wave"],
        affinity_tags=[
            "motif.spiral",
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
                motifs=["spiral", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.ROLL],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["spiral", "wash"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.PULSE],
                density=0.55,
                contrast=0.35,
                color_mode=ColorMode.ANALOGOUS,
                notes="Add gentle pulsing wash behind the polar pattern for readability.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Helix - Drive"])
def make_gtpl_rhythm_motif_helix_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around helix; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_helix_drive",
        name="Helix - Drive",
        description="Rhythmic motion pattern built around helix; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "helix", "wave"],
        affinity_tags=[
            "motif.helix",
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
                motifs=["helix", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.ROLL],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["helix", "wash"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.PULSE],
                density=0.55,
                contrast=0.35,
                color_mode=ColorMode.ANALOGOUS,
                notes="Add gentle pulsing wash behind the polar pattern for readability.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Radial Rays - Drive"])
def make_gtpl_rhythm_motif_radial_rays_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around radial rays; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_radial_rays_drive",
        name="Radial Rays - Drive",
        description="Rhythmic motion pattern built around radial rays; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "radial_rays", "wave"],
        affinity_tags=[
            "motif.radial_rays",
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
                motifs=["radial_rays", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.ROLL],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["radial_rays", "wash"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.PULSE],
                density=0.55,
                contrast=0.35,
                color_mode=ColorMode.ANALOGOUS,
                notes="Add gentle pulsing wash behind the polar pattern for readability.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Concentric Rings - Drive"])
def make_gtpl_rhythm_motif_concentric_rings_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around concentric rings; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_concentric_rings_drive",
        name="Concentric Rings - Drive",
        description="Rhythmic motion pattern built around concentric rings; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "concentric_rings", "wave"],
        affinity_tags=[
            "motif.concentric_rings",
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
                motifs=["concentric_rings", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.ROLL],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["concentric_rings", "wash"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.PULSE],
                density=0.55,
                contrast=0.35,
                color_mode=ColorMode.ANALOGOUS,
                notes="Add gentle pulsing wash behind the polar pattern for readability.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Wave Bands - Drive"])
def make_gtpl_rhythm_motif_wave_bands_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around wave bands; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_wave_bands_drive",
        name="Wave Bands - Drive",
        description="Rhythmic motion pattern built around wave bands; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "wave_bands", "wave"],
        affinity_tags=[
            "motif.wave_bands",
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
                motifs=["wave_bands", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
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


@register_group_template(aliases=["Zigzag - Drive"])
def make_gtpl_rhythm_motif_zigzag_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around zigzag; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_zigzag_drive",
        name="Zigzag - Drive",
        description="Rhythmic motion pattern built around zigzag; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "zigzag", "wave"],
        affinity_tags=[
            "motif.zigzag",
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
                motifs=["zigzag", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.SWEEP],
                density=0.7,
                contrast=0.8,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Chevrons - Drive"])
def make_gtpl_rhythm_motif_chevrons_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around chevrons; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_chevrons_drive",
        name="Chevrons - Drive",
        description="Rhythmic motion pattern built around chevrons; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "chevrons", "bars"],
        affinity_tags=[
            "motif.chevrons",
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
                motifs=["chevrons", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.SWEEP],
                density=0.7,
                contrast=0.8,
                color_mode=ColorMode.DICHROME,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Stripes - Drive"])
def make_gtpl_rhythm_motif_stripes_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around stripes; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_stripes_drive",
        name="Stripes - Drive",
        description="Rhythmic motion pattern built around stripes; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "stripes", "bars"],
        affinity_tags=[
            "motif.stripes",
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
                motifs=["stripes", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.SWEEP],
                density=0.7,
                contrast=0.8,
                color_mode=ColorMode.DICHROME,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Gradient Bands - Drive"])
def make_gtpl_rhythm_motif_gradient_bands_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around gradient bands; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_gradient_bands_drive",
        name="Gradient Bands - Drive",
        description="Rhythmic motion pattern built around gradient bands; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "gradient_bands", "wave"],
        affinity_tags=[
            "motif.gradient_bands",
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
                motifs=["gradient_bands", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
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


@register_group_template(aliases=["Grid - Drive"])
def make_gtpl_rhythm_motif_grid_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around grid; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_grid_drive",
        name="Grid - Drive",
        description="Rhythmic motion pattern built around grid; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "grid", "bars"],
        affinity_tags=[
            "motif.grid",
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
                motifs=["grid", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.SWEEP],
                density=0.7,
                contrast=0.8,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Checker - Drive"])
def make_gtpl_rhythm_motif_checker_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around checker; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_checker_drive",
        name="Checker - Drive",
        description="Rhythmic motion pattern built around checker; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "checker", "wave"],
        affinity_tags=[
            "motif.checker",
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
                motifs=["checker", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.SWEEP],
                density=0.7,
                contrast=0.8,
                color_mode=ColorMode.DICHROME,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Dots - Drive"])
def make_gtpl_rhythm_motif_dots_drive() -> GroupPlanTemplate:
    """Rhythmic motion pattern built around dots; designed for beat-synced movement."""
    return GroupPlanTemplate(
        template_id="gtpl_rhythm_motif_dots_drive",
        name="Dots - Drive",
        description="Rhythmic motion pattern built around dots; designed for beat-synced movement.",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["rhythm", "drive", "dots", "wave"],
        affinity_tags=[
            "motif.dots",
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
                motifs=["dots", "rhythm"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.SWEEP],
                density=0.7,
                contrast=0.65,
                color_mode=ColorMode.FULL_SPECTRUM,
                notes="Primary rhythm layer; vary speed via value curves; stack with BASE ambient.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
