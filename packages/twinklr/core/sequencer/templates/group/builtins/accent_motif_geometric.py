"""ACCENT lane group templates - Geometric motif hits (radial rays, concentric rings, candy stripes, zigzag, chevrons, stripes)."""

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


@register_group_template(aliases=["Radial Rays - Hit (Small)"])
def make_gtpl_accent_motif_radial_rays_hit_small() -> GroupPlanTemplate:
    """Small accent hit using radial rays motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_radial_rays_hit_small",
        name="Radial Rays - Hit (Small)",
        description="Small accent hit using radial rays motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['accent', 'hit', 'small', 'radial_rays', 'wipe'],
        affinity_tags=['motif.radial_rays', 'setting.playful', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['radial_rays', 'hit', 'small'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
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



@register_group_template(aliases=["Radial Rays - Hit (Big)"])
def make_gtpl_accent_motif_radial_rays_hit_big() -> GroupPlanTemplate:
    """Big accent hit using radial rays motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_radial_rays_hit_big",
        name="Radial Rays - Hit (Big)",
        description="Big accent hit using radial rays motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['accent', 'hit', 'big', 'radial_rays', 'wipe'],
        affinity_tags=['motif.radial_rays', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['radial_rays', 'hit', 'big'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.WIPE],
            density=0.85,
            contrast=0.9,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
        ),
        LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['wash', 'support'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
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



@register_group_template(aliases=["Concentric Rings - Hit (Small)"])
def make_gtpl_accent_motif_concentric_rings_hit_small() -> GroupPlanTemplate:
    """Small accent hit using concentric rings motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_concentric_rings_hit_small",
        name="Concentric Rings - Hit (Small)",
        description="Small accent hit using concentric rings motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['accent', 'hit', 'small', 'concentric_rings', 'wipe'],
        affinity_tags=['motif.concentric_rings', 'setting.playful', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['concentric_rings', 'hit', 'small'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
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



@register_group_template(aliases=["Concentric Rings - Hit (Big)"])
def make_gtpl_accent_motif_concentric_rings_hit_big() -> GroupPlanTemplate:
    """Big accent hit using concentric rings motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_concentric_rings_hit_big",
        name="Concentric Rings - Hit (Big)",
        description="Big accent hit using concentric rings motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['accent', 'hit', 'big', 'concentric_rings', 'wipe'],
        affinity_tags=['motif.concentric_rings', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['concentric_rings', 'hit', 'big'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.WIPE],
            density=0.85,
            contrast=0.9,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
        ),
        LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['wash', 'support'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
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



@register_group_template(aliases=["Candy Stripes - Hit (Small)"])
def make_gtpl_accent_motif_candy_stripes_hit_small() -> GroupPlanTemplate:
    """Small accent hit using candy stripes motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_candy_stripes_hit_small",
        name="Candy Stripes - Hit (Small)",
        description="Small accent hit using candy stripes motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['accent', 'hit', 'small', 'candy_stripes', 'wipe'],
        affinity_tags=['motif.candy_stripes', 'setting.playful', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['candy_stripes', 'hit', 'small'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
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



@register_group_template(aliases=["Candy Stripes - Hit (Big)"])
def make_gtpl_accent_motif_candy_stripes_hit_big() -> GroupPlanTemplate:
    """Big accent hit using candy stripes motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_candy_stripes_hit_big",
        name="Candy Stripes - Hit (Big)",
        description="Big accent hit using candy stripes motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['accent', 'hit', 'big', 'candy_stripes', 'wipe'],
        affinity_tags=['motif.candy_stripes', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.POLAR),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['candy_stripes', 'hit', 'big'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.WIPE],
            density=0.85,
            contrast=0.9,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
        ),
        LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['wash', 'support'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
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



@register_group_template(aliases=["Zigzag - Hit (Small)"])
def make_gtpl_accent_motif_zigzag_hit_small() -> GroupPlanTemplate:
    """Small accent hit using zigzag motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_zigzag_hit_small",
        name="Zigzag - Hit (Small)",
        description="Small accent hit using zigzag motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['accent', 'hit', 'small', 'zigzag', 'wipe'],
        affinity_tags=['motif.zigzag', 'setting.playful', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['zigzag', 'hit', 'small'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
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



@register_group_template(aliases=["Zigzag - Hit (Big)"])
def make_gtpl_accent_motif_zigzag_hit_big() -> GroupPlanTemplate:
    """Big accent hit using zigzag motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_zigzag_hit_big",
        name="Zigzag - Hit (Big)",
        description="Big accent hit using zigzag motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['accent', 'hit', 'big', 'zigzag', 'wipe'],
        affinity_tags=['motif.zigzag', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['zigzag', 'hit', 'big'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.WIPE],
            density=0.85,
            contrast=0.9,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
        ),
        LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['wash', 'support'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
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



@register_group_template(aliases=["Chevrons - Hit (Small)"])
def make_gtpl_accent_motif_chevrons_hit_small() -> GroupPlanTemplate:
    """Small accent hit using chevrons motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_chevrons_hit_small",
        name="Chevrons - Hit (Small)",
        description="Small accent hit using chevrons motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['accent', 'hit', 'small', 'chevrons', 'wipe'],
        affinity_tags=['motif.chevrons', 'setting.playful', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['chevrons', 'hit', 'small'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
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



@register_group_template(aliases=["Chevrons - Hit (Big)"])
def make_gtpl_accent_motif_chevrons_hit_big() -> GroupPlanTemplate:
    """Big accent hit using chevrons motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_chevrons_hit_big",
        name="Chevrons - Hit (Big)",
        description="Big accent hit using chevrons motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['accent', 'hit', 'big', 'chevrons', 'wipe'],
        affinity_tags=['motif.chevrons', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['chevrons', 'hit', 'big'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.WIPE],
            density=0.85,
            contrast=0.9,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
        ),
        LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['wash', 'support'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
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



@register_group_template(aliases=["Stripes - Hit (Small)"])
def make_gtpl_accent_motif_stripes_hit_small() -> GroupPlanTemplate:
    """Small accent hit using stripes motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_stripes_hit_small",
        name="Stripes - Hit (Small)",
        description="Small accent hit using stripes motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['accent', 'hit', 'small', 'stripes', 'wipe'],
        affinity_tags=['motif.stripes', 'setting.playful', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['stripes', 'hit', 'small'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
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



@register_group_template(aliases=["Stripes - Hit (Big)"])
def make_gtpl_accent_motif_stripes_hit_big() -> GroupPlanTemplate:
    """Big accent hit using stripes motif; strobe/sparkle wipe emphasis."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_motif_stripes_hit_big",
        name="Stripes - Hit (Big)",
        description="Big accent hit using stripes motif; strobe/sparkle wipe emphasis.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=['accent', 'hit', 'big', 'stripes', 'wipe'],
        affinity_tags=['motif.stripes', 'setting.triumphant', 'style.bold_shapes', 'constraint.high_contrast'],
        avoid_tags=['constraint.noisy_texture_avoid', 'constraint.no_text'],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=8),
        layer_recipe=[
            LayerRecipe(
            layer=VisualDepth.FOREGROUND,
            motifs=['stripes', 'hit', 'big'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.WIPE],
            density=0.85,
            contrast=0.9,
            color_mode=ColorMode.FULL_SPECTRUM,
            notes="Use on drum hits/lyrics accents; keep duration 0.5–2 bars.",
        ),
        LayerRecipe(
            layer=VisualDepth.BACKGROUND,
            motifs=['wash', 'support'],
            visual_intent=GroupVisualIntent.GEOMETRIC,
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

