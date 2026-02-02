"""Seam-safe tile asset templates - Icicle Edge, Plaid, Holly families."""

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
def make_atpl_tile_icicle_edge_top() -> AssetTemplate:
    """Icicle edge hanging from top."""
    return AssetTemplate(
        template_id="atpl_tile_icicle_edge_top",
        name="Icicle Edge - Top",
        # description: Icicle edge hanging from top, tileable horizontally",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["icicle", "edge", "top", "hanging", "seamless"],
        prompt_parts=PromptParts(
            subject="icicle border",
            style_block="hanging from top edge",
            composition="icicles hanging down, various lengths, transparent background, horizontal seamless",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["bottom", "floating", "solid background", "vertical repeat"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_tile_icicle_edge_bottom() -> AssetTemplate:
    """Icicle edge from bottom."""
    return AssetTemplate(
        template_id="atpl_tile_icicle_edge_bottom",
        name="Icicle Edge - Bottom",
        # description: Icicle edge from bottom, tileable horizontally",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["icicle", "edge", "bottom", "frozen", "seamless"],
        prompt_parts=PromptParts(
            subject="icicle border",
            style_block="growing from bottom edge",
            composition="icicles pointing up, frozen formations, transparent background, horizontal seamless",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["top", "hanging", "solid background", "vertical repeat"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_tile_plaid_simple_red() -> AssetTemplate:
    """Red/white plaid."""
    return AssetTemplate(
        template_id="atpl_tile_plaid_simple_red",
        name="Plaid Simple - Red",
        # description: Simple red and white plaid tileable pattern",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["plaid", "red", "white", "pattern", "seamless"],
        prompt_parts=PromptParts(
            subject="plaid pattern",
            style_block="simple red white grid",
            composition="red and white plaid, crisscross lines, tartan style, clean repeating",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["complex", "green", "detailed", "irregular"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_tile_plaid_simple_green() -> AssetTemplate:
    """Green/white plaid."""
    return AssetTemplate(
        template_id="atpl_tile_plaid_simple_green",
        name="Plaid Simple - Green",
        # description: Simple green and white plaid tileable pattern",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["plaid", "green", "white", "pattern", "seamless"],
        prompt_parts=PromptParts(
            subject="plaid pattern",
            style_block="simple green white grid",
            composition="green and white plaid, crisscross lines, tartan style, clean repeating",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["complex", "red", "detailed", "irregular"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_tile_holly_scatter_sparse() -> AssetTemplate:
    """Sparse holly scatter."""
    return AssetTemplate(
        template_id="atpl_tile_holly_scatter_sparse",
        name="Holly Scatter - Sparse",
        # description: Sparse holly leaves tileable pattern",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["holly", "scatter", "sparse", "leaves", "seamless"],
        prompt_parts=PromptParts(
            subject="holly leaves pattern",
            style_block="sparse scattered holly",
            composition="simple holly leaves, red berries, sparse placement, transparent background",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["dense", "complex", "realistic", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_tile_holly_scatter_dense() -> AssetTemplate:
    """Dense holly scatter."""
    return AssetTemplate(
        template_id="atpl_tile_holly_scatter_dense",
        name="Holly Scatter - Dense",
        # description: Dense holly leaves tileable pattern",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["holly", "scatter", "dense", "leaves", "seamless"],
        prompt_parts=PromptParts(
            subject="holly leaves pattern",
            style_block="dense scattered holly",
            composition="simple holly leaves, red berries, dense coverage, transparent background",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["sparse", "gaps", "realistic", "solid background"],
        template_version="1.0.0",
    )
