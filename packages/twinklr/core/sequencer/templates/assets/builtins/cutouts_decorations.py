"""Cutout/icon asset templates - Bell, Wreath, Snowflake families."""

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
def make_atpl_cutout_bell_single() -> AssetTemplate:
    """Single bell."""
    return AssetTemplate(
        template_id="atpl_cutout_bell_single",
        name="Bell - Single",
        # description: Single Christmas bell cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["bell", "single", "icon", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="christmas bell icon",
            style_block="simple single bell",
            composition="classic bell shape, simple ribbon, clean silhouette, festive",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["multiple", "realistic", "background", "complex"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_bell_double() -> AssetTemplate:
    """Double bells."""
    return AssetTemplate(
        template_id="atpl_cutout_bell_double",
        name="Bell - Double",
        # description: Double Christmas bells cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["bell", "double", "icon", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="christmas bells icon",
            style_block="two bells with ribbon",
            composition="two bells side by side, tied with ribbon, symmetrical, festive",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["single", "realistic", "background", "complex"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_wreath_simple() -> AssetTemplate:
    """Simple wreath."""
    return AssetTemplate(
        template_id="atpl_cutout_wreath_simple",
        name="Wreath - Simple",
        # description: Simple Christmas wreath cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["wreath", "simple", "icon", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="christmas wreath icon",
            style_block="simple circular wreath",
            composition="circular wreath, evergreen branches, simple design, minimal detail",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["bow", "ornaments", "realistic", "background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_wreath_bow() -> AssetTemplate:
    """Wreath with bow."""
    return AssetTemplate(
        template_id="atpl_cutout_wreath_bow",
        name="Wreath - Bow",
        # description: Christmas wreath with bow cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["wreath", "bow", "icon", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="christmas wreath icon",
            style_block="wreath with bow",
            composition="circular wreath, evergreen branches, red ribbon bow, festive",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["plain", "ornaments", "realistic", "background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_snowflake_simple() -> AssetTemplate:
    """Simple snowflake."""
    return AssetTemplate(
        template_id="atpl_cutout_snowflake_simple",
        name="Snowflake - Simple",
        # description: Simple snowflake cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["snowflake", "simple", "icon", "cutout", "winter"],
        prompt_parts=PromptParts(
            subject="snowflake icon",
            style_block="simple geometric snowflake",
            composition="six-point symmetry, simple branches, geometric, clean design",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["complex", "detailed", "realistic", "background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_snowflake_complex() -> AssetTemplate:
    """Complex snowflake."""
    return AssetTemplate(
        template_id="atpl_cutout_snowflake_complex",
        name="Snowflake - Complex",
        # description: Complex detailed snowflake cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["snowflake", "complex", "icon", "cutout", "winter"],
        prompt_parts=PromptParts(
            subject="snowflake icon",
            style_block="intricate detailed snowflake",
            composition="six-point symmetry, intricate branches, detailed patterns, elegant",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["simple", "basic", "realistic", "background"],
        template_version="1.0.0",
    )
