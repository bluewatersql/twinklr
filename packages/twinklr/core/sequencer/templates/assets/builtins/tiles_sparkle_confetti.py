"""Seam-safe tile asset templates - Sparkle Glints and Confetti families."""

from twinklr.core.sequencer.templates.assets.enums import AssetTemplateType, MatrixAspect
from twinklr.core.sequencer.templates.assets.library import register_asset_template
from twinklr.core.sequencer.templates.assets.models import (
    AssetTemplate,
    MatrixDefaults,
    PNGDefaults,
    PromptParts,
    PromptPolicy,
)


@register_asset_template()
def make_atpl_tile_sparkle_glints_soft() -> AssetTemplate:
    """Soft sparkle glints."""
    return AssetTemplate(
        template_id="atpl_tile_sparkle_glints_soft",
        name="Sparkle Glints - Soft",
        # description: Soft sparkle glints tileable texture",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["sparkle", "glints", "soft", "shimmer", "seamless"],
        prompt_parts=PromptParts(
            subject="sparkle glints texture",
            style_block="soft shimmer effect",
            composition="soft white sparkles, subtle glints, blurred edges, transparent background",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["sharp", "harsh", "large", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_tile_sparkle_glints_sharp() -> AssetTemplate:
    """Sharp sparkle glints."""
    return AssetTemplate(
        template_id="atpl_tile_sparkle_glints_sharp",
        name="Sparkle Glints - Sharp",
        # description: Sharp sparkle glints tileable texture",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["sparkle", "glints", "sharp", "bright", "seamless"],
        prompt_parts=PromptParts(
            subject="sparkle glints texture",
            style_block="sharp bright sparkles",
            composition="bright white sparkles, sharp points, crisp edges, transparent background",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["soft", "blurry", "dull", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_tile_confetti_subtle() -> AssetTemplate:
    """Subtle confetti."""
    return AssetTemplate(
        template_id="atpl_tile_confetti_subtle",
        name="Confetti - Subtle",
        # description: Subtle confetti tileable pattern",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["confetti", "subtle", "dots", "celebration", "seamless"],
        prompt_parts=PromptParts(
            subject="confetti pattern",
            style_block="subtle scattered dots",
            composition="small colored dots, sparse placement, red green gold, transparent background",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["dense", "large", "complex shapes", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_tile_confetti_party() -> AssetTemplate:
    """Dense party confetti."""
    return AssetTemplate(
        template_id="atpl_tile_confetti_party",
        name="Confetti - Party",
        # description: Dense party confetti tileable pattern",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["confetti", "party", "dense", "celebration", "seamless"],
        prompt_parts=PromptParts(
            subject="confetti pattern",
            style_block="dense party confetti",
            composition="colorful confetti pieces, dense coverage, red green gold, transparent background",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["sparse", "simple", "minimal", "solid background"],
        template_version="1.0.0",
    )
