"""ACCENT lane group templates - Abstract motif hits (confetti, light trails, ribbons)."""

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


@register_group_template(aliases=["Confetti - Hit (Small)"])
def make_gtpl_accent_motif_confetti_hit_small() -> GroupPlanTemplate:
    """Small accent hit using confetti motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_confetti_hit_small",
        name="Confetti - Hit (Small)",
        description="Small accent hit using confetti motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['accent', 'hit', 'small', 'confetti', 'wipe'],
        affinity_tags=['motif.confetti', 'setting.playful', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['confetti', 'hit', 'small'],
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



@register_group_template(aliases=["Confetti - Hit (Big)"])
def make_gtpl_accent_motif_confetti_hit_big() -> GroupPlanTemplate:
    """Big accent hit using confetti motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_confetti_hit_big",
        name="Confetti - Hit (Big)",
        description="Big accent hit using confetti motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['accent', 'hit', 'big', 'confetti', 'wipe'],
        affinity_tags=['motif.confetti', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['confetti', 'hit', 'big'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.WIPE],
            density=0.85,
            contrast=0.9,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
        ),
        LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['wash', 'support'],
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



@register_group_template(aliases=["Light Trails - Hit (Small)"])
def make_gtpl_accent_motif_light_trails_hit_small() -> GroupPlanTemplate:
    """Small accent hit using light trails motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_light_trails_hit_small",
        name="Light Trails - Hit (Small)",
        description="Small accent hit using light trails motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['accent', 'hit', 'small', 'light_trails', 'wipe'],
        affinity_tags=['motif.light_trails', 'setting.playful', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['light_trails', 'hit', 'small'],
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



@register_group_template(aliases=["Light Trails - Hit (Big)"])
def make_gtpl_accent_motif_light_trails_hit_big() -> GroupPlanTemplate:
    """Big accent hit using light trails motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_light_trails_hit_big",
        name="Light Trails - Hit (Big)",
        description="Big accent hit using light trails motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['accent', 'hit', 'big', 'light_trails', 'wipe'],
        affinity_tags=['motif.light_trails', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['light_trails', 'hit', 'big'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.WIPE],
            density=0.85,
            contrast=0.9,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
        ),
        LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['wash', 'support'],
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



@register_group_template(aliases=["Ribbons - Hit (Small)"])
def make_gtpl_accent_motif_ribbons_hit_small() -> GroupPlanTemplate:
    """Small accent hit using ribbons motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_ribbons_hit_small",
        name="Ribbons - Hit (Small)",
        description="Small accent hit using ribbons motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['accent', 'hit', 'small', 'ribbons', 'wipe'],
        affinity_tags=['motif.ribbons', 'setting.playful', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['ribbons', 'hit', 'small'],
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



@register_group_template(aliases=["Ribbons - Hit (Big)"])
def make_gtpl_accent_motif_ribbons_hit_big() -> GroupPlanTemplate:
    """Big accent hit using ribbons motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_ribbons_hit_big",
        name="Ribbons - Hit (Big)",
        description="Big accent hit using ribbons motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['accent', 'hit', 'big', 'ribbons', 'wipe'],
        affinity_tags=['motif.ribbons', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['ribbons', 'hit', 'big'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.WIPE],
            density=0.85,
            contrast=0.9,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
        ),
        LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['wash', 'support'],
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
