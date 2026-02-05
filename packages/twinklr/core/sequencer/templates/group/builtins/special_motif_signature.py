"""SPECIAL lane group templates - Signature motif moments (high-impact layered templates for chorus/drop/finale)."""

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


@register_group_template(aliases=["Cosmic - Signature"])
def make_gtpl_special_motif_cosmic_signature() -> GroupPlanTemplate:
    """High-impact signature moment built around cosmic motif; layered for depth."""
    return GroupPlanTemplate(
        template_id="gtpl_special_motif_cosmic_signature",
        name="Cosmic - Signature",
        description="High-impact signature moment built around cosmic motif; layered for depth.",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=['special', 'signature', 'cosmic', 'kaleidoscope'],
        affinity_tags=['motif.cosmic', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=2, bars_max=24),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['cosmic', 'wash', 'bed'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.PULSE],
            density=0.85,
            contrast=0.35,
            color_mode=ColorMode.ANALOGOUS,
            notes="Big bed layer (Color Wash / Galaxy / Plasma style). Keep low detail.",
        ),
        LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['cosmic', 'pattern', 'core'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.PULSE],
            density=0.75,
            contrast=0.8,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Core pattern layer (Spirals/Bars/Lines/Kaleidoscope vibe depending on motif).",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['cosmic', 'sparkle', 'top'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.SPARKLE],
            density=0.45,
            contrast=0.95,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Top sparkle layer (Twinkle/Strobe). Dial density to avoid noise.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Fire - Signature"])
def make_gtpl_special_motif_fire_signature() -> GroupPlanTemplate:
    """High-impact signature moment built around fire motif; layered for depth."""
    return GroupPlanTemplate(
        template_id="gtpl_special_motif_fire_signature",
        name="Fire - Signature",
        description="High-impact signature moment built around fire motif; layered for depth.",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=['special', 'signature', 'fire', 'fireworks'],
        affinity_tags=['motif.fire', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=24),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['fire', 'wash', 'bed'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.PULSE],
            density=0.85,
            contrast=0.35,
            color_mode=ColorMode.ANALOGOUS,
            notes="Big bed layer (Color Wash / Galaxy / Plasma style). Keep low detail.",
        ),
        LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['fire', 'pattern', 'core'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.RIPPLE],
            density=0.75,
            contrast=0.8,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Core pattern layer (Spirals/Bars/Lines/Kaleidoscope vibe depending on motif).",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['fire', 'sparkle', 'top'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.SPARKLE],
            density=0.45,
            contrast=0.95,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Top sparkle layer (Twinkle/Strobe). Dial density to avoid noise.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Snowflakes - Signature"])
def make_gtpl_special_motif_snowflakes_signature() -> GroupPlanTemplate:
    """High-impact signature moment built around snowflakes motif; layered for depth."""
    return GroupPlanTemplate(
        template_id="gtpl_special_motif_snowflakes_signature",
        name="Snowflakes - Signature",
        description="High-impact signature moment built around snowflakes motif; layered for depth.",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=['special', 'signature', 'snowflakes', 'fireworks'],
        affinity_tags=['motif.snowflakes', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=24),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['snowflakes', 'wash', 'bed'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.PULSE],
            density=0.85,
            contrast=0.35,
            color_mode=ColorMode.ANALOGOUS,
            notes="Big bed layer (Color Wash / Galaxy / Plasma style). Keep low detail.",
        ),
        LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['snowflakes', 'pattern', 'core'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.PULSE],
            density=0.75,
            contrast=0.8,
            color_mode=ColorMode.ANALOGOUS,
            notes="Core pattern layer (Spirals/Bars/Lines/Kaleidoscope vibe depending on motif).",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['snowflakes', 'sparkle', 'top'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.SPARKLE],
            density=0.45,
            contrast=0.95,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Top sparkle layer (Twinkle/Strobe). Dial density to avoid noise.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Ornaments - Signature"])
def make_gtpl_special_motif_ornaments_signature() -> GroupPlanTemplate:
    """High-impact signature moment built around ornaments motif; layered for depth."""
    return GroupPlanTemplate(
        template_id="gtpl_special_motif_ornaments_signature",
        name="Ornaments - Signature",
        description="High-impact signature moment built around ornaments motif; layered for depth.",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=['special', 'signature', 'ornaments', 'fireworks'],
        affinity_tags=['motif.ornaments', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=24),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['ornaments', 'wash', 'bed'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.PULSE],
            density=0.85,
            contrast=0.35,
            color_mode=ColorMode.ANALOGOUS,
            notes="Big bed layer (Color Wash / Galaxy / Plasma style). Keep low detail.",
        ),
        LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['ornaments', 'pattern', 'core'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.PULSE],
            density=0.75,
            contrast=0.8,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Core pattern layer (Spirals/Bars/Lines/Kaleidoscope vibe depending on motif).",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['ornaments', 'sparkle', 'top'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.SPARKLE],
            density=0.45,
            contrast=0.95,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Top sparkle layer (Twinkle/Strobe). Dial density to avoid noise.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Candy Stripes - Signature"])
def make_gtpl_special_motif_candy_stripes_signature() -> GroupPlanTemplate:
    """High-impact signature moment built around candy stripes motif; layered for depth."""
    return GroupPlanTemplate(
        template_id="gtpl_special_motif_candy_stripes_signature",
        name="Candy Stripes - Signature",
        description="High-impact signature moment built around candy stripes motif; layered for depth.",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['special', 'signature', 'candy_stripes', 'fireworks'],
        affinity_tags=['motif.candy_stripes', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=2, bars_max=24),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['candy_stripes', 'wash', 'bed'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.PULSE],
            density=0.85,
            contrast=0.35,
            color_mode=ColorMode.ANALOGOUS,
            notes="Big bed layer (Color Wash / Galaxy / Plasma style). Keep low detail.",
        ),
        LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['candy_stripes', 'pattern', 'core'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.SWEEP],
            density=0.75,
            contrast=0.8,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Core pattern layer (Spirals/Bars/Lines/Kaleidoscope vibe depending on motif).",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['candy_stripes', 'sparkle', 'top'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.SPARKLE],
            density=0.45,
            contrast=0.95,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Top sparkle layer (Twinkle/Strobe). Dial density to avoid noise.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Radial Rays - Signature"])
def make_gtpl_special_motif_radial_rays_signature() -> GroupPlanTemplate:
    """High-impact signature moment built around radial rays motif; layered for depth."""
    return GroupPlanTemplate(
        template_id="gtpl_special_motif_radial_rays_signature",
        name="Radial Rays - Signature",
        description="High-impact signature moment built around radial rays motif; layered for depth.",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['special', 'signature', 'radial_rays', 'fireworks'],
        affinity_tags=['motif.radial_rays', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=2, bars_max=24),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['radial_rays', 'wash', 'bed'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.PULSE],
            density=0.85,
            contrast=0.35,
            color_mode=ColorMode.ANALOGOUS,
            notes="Big bed layer (Color Wash / Galaxy / Plasma style). Keep low detail.",
        ),
        LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['radial_rays', 'pattern', 'core'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.ROLL],
            density=0.75,
            contrast=0.8,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Core pattern layer (Spirals/Bars/Lines/Kaleidoscope vibe depending on motif).",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['radial_rays', 'sparkle', 'top'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.SPARKLE],
            density=0.45,
            contrast=0.95,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Top sparkle layer (Twinkle/Strobe). Dial density to avoid noise.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Spiral - Signature"])
def make_gtpl_special_motif_spiral_signature() -> GroupPlanTemplate:
    """High-impact signature moment built around spiral motif; layered for depth."""
    return GroupPlanTemplate(
        template_id="gtpl_special_motif_spiral_signature",
        name="Spiral - Signature",
        description="High-impact signature moment built around spiral motif; layered for depth.",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['special', 'signature', 'spiral', 'kaleidoscope'],
        affinity_tags=['motif.spiral', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=2, bars_max=24),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['spiral', 'wash', 'bed'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.PULSE],
            density=0.85,
            contrast=0.35,
            color_mode=ColorMode.ANALOGOUS,
            notes="Big bed layer (Color Wash / Galaxy / Plasma style). Keep low detail.",
        ),
        LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['spiral', 'pattern', 'core'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.ROLL],
            density=0.75,
            contrast=0.8,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Core pattern layer (Spirals/Bars/Lines/Kaleidoscope vibe depending on motif).",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['spiral', 'sparkle', 'top'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.SPARKLE],
            density=0.45,
            contrast=0.95,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Top sparkle layer (Twinkle/Strobe). Dial density to avoid noise.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Stars - Signature"])
def make_gtpl_special_motif_stars_signature() -> GroupPlanTemplate:
    """High-impact signature moment built around stars motif; layered for depth."""
    return GroupPlanTemplate(
        template_id="gtpl_special_motif_stars_signature",
        name="Stars - Signature",
        description="High-impact signature moment built around stars motif; layered for depth.",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['special', 'signature', 'stars', 'fireworks'],
        affinity_tags=['motif.stars', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=24),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['stars', 'wash', 'bed'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.PULSE],
            density=0.85,
            contrast=0.35,
            color_mode=ColorMode.ANALOGOUS,
            notes="Big bed layer (Color Wash / Galaxy / Plasma style). Keep low detail.",
        ),
        LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['stars', 'pattern', 'core'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SPARKLE],
            density=0.75,
            contrast=0.8,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Core pattern layer (Spirals/Bars/Lines/Kaleidoscope vibe depending on motif).",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['stars', 'sparkle', 'top'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SPARKLE],
            density=0.45,
            contrast=0.95,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Top sparkle layer (Twinkle/Strobe). Dial density to avoid noise.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Sparkles - Signature"])
def make_gtpl_special_motif_sparkles_signature() -> GroupPlanTemplate:
    """High-impact signature moment built around sparkles motif; layered for depth."""
    return GroupPlanTemplate(
        template_id="gtpl_special_motif_sparkles_signature",
        name="Sparkles - Signature",
        description="High-impact signature moment built around sparkles motif; layered for depth.",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['special', 'signature', 'sparkles', 'fireworks'],
        affinity_tags=['motif.sparkles', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=24),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['sparkles', 'wash', 'bed'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.PULSE],
            density=0.85,
            contrast=0.35,
            color_mode=ColorMode.ANALOGOUS,
            notes="Big bed layer (Color Wash / Galaxy / Plasma style). Keep low detail.",
        ),
        LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['sparkles', 'pattern', 'core'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SPARKLE],
            density=0.75,
            contrast=0.8,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Core pattern layer (Spirals/Bars/Lines/Kaleidoscope vibe depending on motif).",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['sparkles', 'sparkle', 'top'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SPARKLE],
            density=0.45,
            contrast=0.95,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Top sparkle layer (Twinkle/Strobe). Dial density to avoid noise.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Lightning - Signature"])
def make_gtpl_special_motif_lightning_signature() -> GroupPlanTemplate:
    """High-impact signature moment built around lightning motif; layered for depth."""
    return GroupPlanTemplate(
        template_id="gtpl_special_motif_lightning_signature",
        name="Lightning - Signature",
        description="High-impact signature moment built around lightning motif; layered for depth.",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=['special', 'signature', 'lightning', 'fireworks'],
        affinity_tags=['motif.lightning', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=24),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['lightning', 'wash', 'bed'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.PULSE],
            density=0.85,
            contrast=0.35,
            color_mode=ColorMode.ANALOGOUS,
            notes="Big bed layer (Color Wash / Galaxy / Plasma style). Keep low detail.",
        ),
        LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['lightning', 'pattern', 'core'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.STROBE],
            density=0.75,
            contrast=0.8,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Core pattern layer (Spirals/Bars/Lines/Kaleidoscope vibe depending on motif).",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['lightning', 'sparkle', 'top'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.STROBE],
            density=0.45,
            contrast=0.95,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Top sparkle layer (Twinkle/Strobe). Dial density to avoid noise.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Ribbons - Signature"])
def make_gtpl_special_motif_ribbons_signature() -> GroupPlanTemplate:
    """High-impact signature moment built around ribbons motif; layered for depth."""
    return GroupPlanTemplate(
        template_id="gtpl_special_motif_ribbons_signature",
        name="Ribbons - Signature",
        description="High-impact signature moment built around ribbons motif; layered for depth.",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=['special', 'signature', 'ribbons', 'fireworks'],
        affinity_tags=['motif.ribbons', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=24),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['ribbons', 'wash', 'bed'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.PULSE],
            density=0.85,
            contrast=0.35,
            color_mode=ColorMode.ANALOGOUS,
            notes="Big bed layer (Color Wash / Galaxy / Plasma style). Keep low detail.",
        ),
        LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['ribbons', 'pattern', 'core'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.PULSE],
            density=0.75,
            contrast=0.8,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Core pattern layer (Spirals/Bars/Lines/Kaleidoscope vibe depending on motif).",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['ribbons', 'sparkle', 'top'],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.SPARKLE],
            density=0.45,
            contrast=0.95,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Top sparkle layer (Twinkle/Strobe). Dial density to avoid noise.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )



@register_group_template(aliases=["Crystals - Signature"])
def make_gtpl_special_motif_crystals_signature() -> GroupPlanTemplate:
    """High-impact signature moment built around crystals motif; layered for depth."""
    return GroupPlanTemplate(
        template_id="gtpl_special_motif_crystals_signature",
        name="Crystals - Signature",
        description="High-impact signature moment built around crystals motif; layered for depth.",
        template_type=GroupTemplateType.SPECIAL,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=['special', 'signature', 'crystals', 'fireworks'],
        affinity_tags=['motif.crystals', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast', 'constraint.clean_edges'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=24),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['crystals', 'wash', 'bed'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.PULSE],
            density=0.85,
            contrast=0.35,
            color_mode=ColorMode.ANALOGOUS,
            notes="Big bed layer (Color Wash / Galaxy / Plasma style). Keep low detail.",
        ),
        LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=['crystals', 'pattern', 'core'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.PULSE],
            density=0.75,
            contrast=0.8,
            color_mode=ColorMode.ANALOGOUS,
            notes="Core pattern layer (Spirals/Bars/Lines/Kaleidoscope vibe depending on motif).",
        ),
        LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['crystals', 'sparkle', 'top'],
            visual_intent=GroupVisualIntent.IMAGERY,
            motion=[MotionVerb.SPARKLE],
            density=0.45,
            contrast=0.95,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Top sparkle layer (Twinkle/Strobe). Dial density to avoid noise.",
        ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
