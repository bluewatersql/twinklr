"""TRANSITION lane group templates - Nature motif transitions (smoke, clouds, water)."""

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


@register_group_template(aliases=["Smoke - Fade Transition"])
def make_gtpl_transition_motif_smoke_fade() -> GroupPlanTemplate:
    """Transition using smoke motif; fade for clean scene change."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_motif_smoke_fade",
        name="Smoke - Fade Transition",
        description="Transition using smoke motif; fade for clean scene change.",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=['transition', 'fade', 'smoke', 'fade'],
        affinity_tags=['motif.smoke', 'style.clean_vector', 'constraint.clean_edges', 'constraint.low_detail'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['smoke', 'fade', 'transition'],
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



@register_group_template(aliases=["Clouds - Fade Transition"])
def make_gtpl_transition_motif_clouds_fade() -> GroupPlanTemplate:
    """Transition using clouds motif; fade for clean scene change."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_motif_clouds_fade",
        name="Clouds - Fade Transition",
        description="Transition using clouds motif; fade for clean scene change.",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=['transition', 'fade', 'clouds', 'fade'],
        affinity_tags=['motif.clouds', 'style.clean_vector', 'constraint.clean_edges', 'constraint.low_detail'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['clouds', 'fade', 'transition'],
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



@register_group_template(aliases=["Water - Ripple Transition"])
def make_gtpl_transition_motif_water_ripple() -> GroupPlanTemplate:
    """Transition using water motif; ripple for clean scene change."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_motif_water_ripple",
        name="Water - Ripple Transition",
        description="Transition using water motif; ripple for clean scene change.",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=['transition', 'ripple', 'water', 'ripple'],
        affinity_tags=['motif.water', 'style.clean_vector', 'constraint.clean_edges', 'constraint.low_detail'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['water', 'ripple', 'transition'],
            visual_intent=GroupVisualIntent.IMAGERY,
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

