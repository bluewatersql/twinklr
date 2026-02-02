"""Seam-safe tile asset templates - Candy Stripes, Snow Speckle, Star Dots families."""

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
def make_atpl_tile_candy_stripes_thick() -> AssetTemplate:
    """Thick diagonal candy stripes."""
    return AssetTemplate(
        template_id="atpl_tile_candy_stripes_thick",
        name="Candy Stripes - Thick",
        # description: Thick diagonal candy stripes tileable pattern",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["candy", "stripes", "thick", "diagonal", "seamless"],
        prompt_parts=PromptParts(
            subject="candy cane stripes",
            style_block="thick diagonal stripes",
            composition="red and white stripes, diagonal 45 degrees, thick bands, clean edges",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["thin", "vertical", "horizontal", "gaps"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_tile_candy_stripes_thin() -> AssetTemplate:
    """Thin diagonal candy stripes."""
    return AssetTemplate(
        template_id="atpl_tile_candy_stripes_thin",
        name="Candy Stripes - Thin",
        # description: Thin diagonal candy stripes tileable pattern",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["candy", "stripes", "thin", "diagonal", "seamless"],
        prompt_parts=PromptParts(
            subject="candy cane stripes",
            style_block="thin diagonal stripes",
            composition="red and white stripes, diagonal 45 degrees, narrow bands, crisp lines",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["thick", "vertical", "horizontal", "blurry"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_tile_snow_speckle_sparse() -> AssetTemplate:
    """Sparse snow speckle."""
    return AssetTemplate(
        template_id="atpl_tile_snow_speckle_sparse",
        name="Snow Speckle - Sparse",
        # description: Sparse snow speckle tileable texture",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["snow", "speckle", "sparse", "dots", "seamless"],
        prompt_parts=PromptParts(
            subject="snow speckle texture",
            style_block="sparse scattered dots",
            composition="small white dots, randomly scattered, sparse distribution, transparent background",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["dense", "clustered", "large dots", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_tile_snow_speckle_dense() -> AssetTemplate:
    """Dense snow speckle."""
    return AssetTemplate(
        template_id="atpl_tile_snow_speckle_dense",
        name="Snow Speckle - Dense",
        # description: Dense snow speckle tileable texture",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["snow", "speckle", "dense", "dots", "seamless"],
        prompt_parts=PromptParts(
            subject="snow speckle texture",
            style_block="dense scattered dots",
            composition="small white dots, densely scattered, even distribution, transparent background",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["sparse", "large dots", "gaps", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_tile_star_dots_small() -> AssetTemplate:
    """Small star dots."""
    return AssetTemplate(
        template_id="atpl_tile_star_dots_small",
        name="Star Dots - Small",
        # description: Small star dots tileable pattern",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["star", "dots", "small", "sparkle", "seamless"],
        prompt_parts=PromptParts(
            subject="star dots pattern",
            style_block="small scattered stars",
            composition="tiny star shapes, white sparkles, random distribution, transparent background",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["large", "complex", "detailed", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_tile_star_dots_large() -> AssetTemplate:
    """Large star dots."""
    return AssetTemplate(
        template_id="atpl_tile_star_dots_large",
        name="Star Dots - Large",
        # description: Large star dots tileable pattern",
        template_type=AssetTemplateType.PNG_TILE,
        tags=["star", "dots", "large", "sparkle", "seamless"],
        prompt_parts=PromptParts(
            subject="star dots pattern",
            style_block="larger scattered stars",
            composition="medium star shapes, bright sparkles, scattered placement, transparent background",
        ),
        prompt_policy=PromptPolicy(
            require_seam_safe=True,
        ),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["tiny", "complex", "realistic", "solid background"],
        template_version="1.0.0",
    )
