"""TRANSITION lane group templates - Geometric motif transitions (gradient bands, stripes, wave bands, grid, checker, spiral, helix, cosmic, abstract)."""

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


@register_group_template(aliases=["Gradient Bands - Fade Transition"])
def make_gtpl_transition_motif_gradient_bands_fade() -> GroupPlanTemplate:
    """Transition using gradient bands motif; fade for clean scene change."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_motif_gradient_bands_fade",
        name="Gradient Bands - Fade Transition",
        description="Transition using gradient bands motif; fade for clean scene change.",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["transition", "fade", "gradient_bands", "fade"],
        affinity_tags=[
            "motif.gradient_bands",
            "style.clean_vector",
            "constraint.clean_edges",
            "constraint.low_detail",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["gradient_bands", "fade", "transition"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.FADE],
                density=0.7,
                contrast=0.5,
                color_mode=ColorMode.ANALOGOUS,
                notes="Use 1–4 bars at section boundaries; keep clean edges and high readability.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Stripes - Wipe Transition"])
def make_gtpl_transition_motif_stripes_wipe() -> GroupPlanTemplate:
    """Transition using stripes motif; wipe for clean scene change."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_motif_stripes_wipe",
        name="Stripes - Wipe Transition",
        description="Transition using stripes motif; wipe for clean scene change.",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["transition", "wipe", "stripes", "wipe"],
        affinity_tags=[
            "motif.stripes",
            "style.clean_vector",
            "constraint.clean_edges",
            "constraint.low_detail",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["stripes", "wipe", "transition"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.WIPE],
                density=0.7,
                contrast=0.5,
                color_mode=ColorMode.DICHROME,
                notes="Use 1–4 bars at section boundaries; keep clean edges and high readability.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Wave Bands - Ripple Transition"])
def make_gtpl_transition_motif_wave_bands_ripple() -> GroupPlanTemplate:
    """Transition using wave bands motif; ripple for clean scene change."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_motif_wave_bands_ripple",
        name="Wave Bands - Ripple Transition",
        description="Transition using wave bands motif; ripple for clean scene change.",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["transition", "ripple", "wave_bands", "ripple"],
        affinity_tags=[
            "motif.wave_bands",
            "style.clean_vector",
            "constraint.clean_edges",
            "constraint.low_detail",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["wave_bands", "ripple", "transition"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.RIPPLE],
                density=0.7,
                contrast=0.5,
                color_mode=ColorMode.DICHROME,
                notes="Use 1–4 bars at section boundaries; keep clean edges and high readability.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Cosmic - Fade Transition"])
def make_gtpl_transition_motif_cosmic_fade() -> GroupPlanTemplate:
    """Transition using cosmic motif; fade for clean scene change."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_motif_cosmic_fade",
        name="Cosmic - Fade Transition",
        description="Transition using cosmic motif; fade for clean scene change.",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["transition", "fade", "cosmic", "warp"],
        affinity_tags=[
            "motif.cosmic",
            "style.clean_vector",
            "constraint.clean_edges",
            "constraint.low_detail",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["cosmic", "fade", "transition"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.FADE],
                density=0.7,
                contrast=0.5,
                color_mode=ColorMode.ANALOGOUS,
                notes="Use 1–4 bars at section boundaries; keep clean edges and high readability.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Spiral - Fade Transition"])
def make_gtpl_transition_motif_spiral_fade() -> GroupPlanTemplate:
    """Transition using spiral motif; fade for clean scene change."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_motif_spiral_fade",
        name="Spiral - Fade Transition",
        description="Transition using spiral motif; fade for clean scene change.",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["transition", "fade", "spiral", "fade"],
        affinity_tags=[
            "motif.spiral",
            "style.clean_vector",
            "constraint.clean_edges",
            "constraint.low_detail",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["spiral", "fade", "transition"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.FADE],
                density=0.7,
                contrast=0.5,
                color_mode=ColorMode.ANALOGOUS,
                notes="Use 1–4 bars at section boundaries; keep clean edges and high readability.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Helix - Fade Transition"])
def make_gtpl_transition_motif_helix_fade() -> GroupPlanTemplate:
    """Transition using helix motif; fade for clean scene change."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_motif_helix_fade",
        name="Helix - Fade Transition",
        description="Transition using helix motif; fade for clean scene change.",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["transition", "fade", "helix", "fade"],
        affinity_tags=[
            "motif.helix",
            "style.clean_vector",
            "constraint.clean_edges",
            "constraint.low_detail",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["helix", "fade", "transition"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.FADE],
                density=0.7,
                contrast=0.5,
                color_mode=ColorMode.ANALOGOUS,
                notes="Use 1–4 bars at section boundaries; keep clean edges and high readability.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Grid - Wipe Transition"])
def make_gtpl_transition_motif_grid_wipe() -> GroupPlanTemplate:
    """Transition using grid motif; wipe for clean scene change."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_motif_grid_wipe",
        name="Grid - Wipe Transition",
        description="Transition using grid motif; wipe for clean scene change.",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["transition", "wipe", "grid", "wipe"],
        affinity_tags=[
            "motif.grid",
            "style.clean_vector",
            "constraint.clean_edges",
            "constraint.low_detail",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["grid", "wipe", "transition"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.WIPE],
                density=0.7,
                contrast=0.5,
                color_mode=ColorMode.DICHROME,
                notes="Use 1–4 bars at section boundaries; keep clean edges and high readability.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Checker - Wipe Transition"])
def make_gtpl_transition_motif_checker_wipe() -> GroupPlanTemplate:
    """Transition using checker motif; wipe for clean scene change."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_motif_checker_wipe",
        name="Checker - Wipe Transition",
        description="Transition using checker motif; wipe for clean scene change.",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["transition", "wipe", "checker", "wipe"],
        affinity_tags=[
            "motif.checker",
            "style.clean_vector",
            "constraint.clean_edges",
            "constraint.low_detail",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["checker", "wipe", "transition"],
                visual_intent=GroupVisualIntent.GEOMETRIC,
                motion=[MotionVerb.WIPE],
                density=0.7,
                contrast=0.5,
                color_mode=ColorMode.DICHROME,
                notes="Use 1–4 bars at section boundaries; keep clean edges and high readability.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Abstract - Fade Transition"])
def make_gtpl_transition_motif_abstract_fade() -> GroupPlanTemplate:
    """Transition using abstract motif; fade for clean scene change."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_motif_abstract_fade",
        name="Abstract - Fade Transition",
        description="Transition using abstract motif; fade for clean scene change.",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["transition", "fade", "abstract", "warp"],
        affinity_tags=[
            "motif.abstract",
            "style.clean_vector",
            "constraint.clean_edges",
            "constraint.low_detail",
        ],
        avoid_tags=["constraint.noisy_texture_avoid", "constraint.no_text"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.MIDGROUND,
                motifs=["abstract", "fade", "transition"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE],
                density=0.7,
                contrast=0.5,
                color_mode=ColorMode.ANALOGOUS,
                notes="Use 1–4 bars at section boundaries; keep clean edges and high readability.",
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
