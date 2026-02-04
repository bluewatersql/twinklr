"""Cutout/icon asset templates - Tree, Star, Candy Cane families."""

from twinklr.core.sequencer.templates.assets.library import register_asset_template
from twinklr.core.sequencer.templates.assets.models import (
    AssetTemplate,
    MatrixDefaults,
    PNGDefaults,
    PromptParts,
    PromptPolicy,
)
from twinklr.core.sequencer.vocabulary import AssetTemplateType, MatrixAspect


@register_asset_template()
def make_atpl_cutout_tree_simple() -> AssetTemplate:
    """Simple tree."""
    return AssetTemplate(
        template_id="atpl_cutout_tree_simple",
        name="Tree - Simple",
        # description: Simple Christmas tree cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["tree", "simple", "icon", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="christmas tree icon",
            style_block="simple cutout silhouette",
            composition="simple pine tree, triangular shape, minimal detail, clean lines",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["realistic", "detailed", "background", "ornaments"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_tree_decorated() -> AssetTemplate:
    """Decorated tree."""
    return AssetTemplate(
        template_id="atpl_cutout_tree_decorated",
        name="Tree - Decorated",
        # description: Decorated Christmas tree cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["tree", "decorated", "icon", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="christmas tree icon",
            style_block="simple cutout with ornaments",
            composition="decorated tree, simple ornaments, star on top, festive, flat design",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["realistic", "complex", "background", "3d"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_star_classic() -> AssetTemplate:
    """Classic star."""
    return AssetTemplate(
        template_id="atpl_cutout_star_classic",
        name="Star - Classic",
        # description: Classic five-point star cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["star", "classic", "icon", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="star icon",
            style_block="simple classic star",
            composition="five-point star, clean edges, symmetrical, simple shape",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["complex", "detailed", "background", "3d"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_star_burst() -> AssetTemplate:
    """Burst star."""
    return AssetTemplate(
        template_id="atpl_cutout_star_burst",
        name="Star - Burst",
        # description: Burst style star cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["star", "burst", "icon", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="star burst icon",
            style_block="radiating points starburst",
            composition="multiple radiating points, starburst shape, symmetrical, dynamic",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["simple", "five-point", "background", "3d"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_candy_cane_single() -> AssetTemplate:
    """Single candy cane."""
    return AssetTemplate(
        template_id="atpl_cutout_candy_cane_single",
        name="Candy Cane - Single",
        # description: Single candy cane cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["candy", "cane", "single", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="candy cane icon",
            style_block="simple single candy cane",
            composition="red and white stripes, hook shape, classic candy cane, clean design",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["multiple", "crossed", "background", "3d"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_candy_cane_crossed() -> AssetTemplate:
    """Crossed candy canes."""
    return AssetTemplate(
        template_id="atpl_cutout_candy_cane_crossed",
        name="Candy Cane - Crossed",
        # description: Crossed candy canes cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["candy", "cane", "crossed", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="crossed candy canes icon",
            style_block="two candy canes crossed",
            composition="red and white stripes, crossed X shape, symmetrical, festive",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["single", "parallel", "background", "3d"],
        template_version="1.0.0",
    )
