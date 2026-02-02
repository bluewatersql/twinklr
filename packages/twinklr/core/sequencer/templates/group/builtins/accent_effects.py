"""ACCENT lane group templates - Pop-In, Lyric, Wipe, Dropout families."""

from twinklr.core.sequencer.templates.group.enums import (
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    LayerRole,
    MotionVerb,
    ProjectionIntent,
)
from twinklr.core.sequencer.templates.group.library import register_group_template
from twinklr.core.sequencer.templates.group.models import (
    GroupPlanTemplate,
    LayerRecipe,
    ProjectionSpec,
    TimingHints,
)


# Pop-In Icon family
@register_group_template(aliases=["Pop-In - Single"])
def make_gtpl_accent_icon_pop_single() -> GroupPlanTemplate:
    """Single icon pop-in."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_icon_pop_single",
        name="Pop-In - Single",
        description="Single icon pop-in emphasis",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["pop", "icon", "single", "emphasis"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["pop", "icon", "emphasis"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.PULSE],
                density=0.3,
                contrast=1.0,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Pop-In - Triplet"])
def make_gtpl_accent_icon_pop_triplet() -> GroupPlanTemplate:
    """Triplet sequence pop-in."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_icon_pop_triplet",
        name="Pop-In - Triplet",
        description="Triplet icon pop-in sequence",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.IMAGERY,
        tags=["pop", "icon", "triplet", "sequence"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["pop", "triplet", "sequence"],
                visual_intent=GroupVisualIntent.IMAGERY,
                motion=[MotionVerb.PULSE],
                density=0.4,
                contrast=0.9,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Lyric Cue Highlight family
@register_group_template(aliases=["Lyric - Underline"])
def make_gtpl_accent_lyric_underline() -> GroupPlanTemplate:
    """Bottom-up flash."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_lyric_underline",
        name="Lyric - Underline",
        description="Bottom-up flash for lyric emphasis",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["lyric", "underline", "bottom", "emphasis"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=2),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["underline", "flash", "emphasis"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SWEEP],
                density=0.7,
                contrast=0.9,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Lyric - Spotlight"])
def make_gtpl_accent_lyric_spotlight() -> GroupPlanTemplate:
    """Spotlight on center."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_lyric_spotlight",
        name="Lyric - Spotlight",
        description="Center spotlight for lyric emphasis",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["lyric", "spotlight", "center", "emphasis"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["spotlight", "center", "focus"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.5,
                contrast=1.0,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Wipe Accent family
@register_group_template(aliases=["Wipe - Fast"])
def make_gtpl_accent_wipe_fast() -> GroupPlanTemplate:
    """Fast L→R with trail."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_wipe_fast",
        name="Wipe - Fast",
        description="Fast left-to-right wipe with trail",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["wipe", "fast", "trail", "lr"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=2),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["wipe", "fast", "trail"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.WIPE],
                density=0.9,
                contrast=1.0,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Wipe - Slam"])
def make_gtpl_accent_wipe_slam() -> GroupPlanTemplate:
    """Instant wipe + hold."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_wipe_slam",
        name="Wipe - Slam",
        description="Instant wipe with hold sustain",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["wipe", "slam", "instant", "hold"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["wipe", "slam", "hold"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.WIPE],
                density=1.0,
                contrast=1.0,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


# Dropout + Return family
@register_group_template(aliases=["Dropout - To Black"])
def make_gtpl_accent_cut_to_black() -> GroupPlanTemplate:
    """All off, snap back."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_cut_to_black",
        name="Dropout - To Black",
        description="Cut to black, then snap back on",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["dropout", "black", "cut", "snap"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["dropout", "cut", "blackout"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=1.0,
                contrast=1.0,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )


@register_group_template(aliases=["Dropout - To Sparkle"])
def make_gtpl_accent_cut_to_sparkle() -> GroupPlanTemplate:
    """All off, sparkle return."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_cut_to_sparkle",
        name="Dropout - To Sparkle",
        description="Cut to black, sparkle cascade return",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["dropout", "sparkle", "return", "cascade"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=2, bars_max=8),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.FOREGROUND,
                motifs=["dropout", "sparkle", "return"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SPARKLE],
                density=0.6,
                contrast=0.9,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        asset_slots=[],
        template_version="1.0.0",
    )
