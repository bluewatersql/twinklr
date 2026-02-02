"""Background plate asset templates - Bokeh and Forest families."""

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
def make_atpl_plate_christmas_bokeh_soft() -> AssetTemplate:
    """Soft Christmas bokeh."""
    return AssetTemplate(
        template_id="atpl_plate_christmas_bokeh_soft",
        name="Christmas Bokeh - Soft",
        # description: Soft out-of-focus Christmas lights bokeh",
        template_type=AssetTemplateType.PNG_OPAQUE,
        tags=["bokeh", "lights", "soft", "christmas", "blur"],
        prompt_parts=PromptParts(
            subject="christmas lights bokeh",
            style_block="soft out-of-focus circles",
            composition="gentle circular bokeh, red green gold lights, soft edges, dark background",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        png_defaults=PNGDefaults(),
        negative_hints=["sharp", "focused", "harsh", "bright background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_plate_christmas_bokeh_bright() -> AssetTemplate:
    """Bright Christmas bokeh."""
    return AssetTemplate(
        template_id="atpl_plate_christmas_bokeh_bright",
        name="Christmas Bokeh - Bright",
        # description: Bright vibrant Christmas lights bokeh",
        template_type=AssetTemplateType.PNG_OPAQUE,
        tags=["bokeh", "lights", "bright", "christmas", "vibrant"],
        prompt_parts=PromptParts(
            subject="christmas lights bokeh",
            style_block="bright vibrant circles",
            composition="vivid circular bokeh, saturated colors, red green gold, overlapping lights",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        png_defaults=PNGDefaults(),
        negative_hints=["sharp", "focused", "dull", "muted"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_plate_forest_silhouette_left() -> AssetTemplate:
    """Forest silhouette on left."""
    return AssetTemplate(
        template_id="atpl_plate_forest_silhouette_left",
        name="Forest Silhouette - Left",
        # description: Forest silhouette positioned on left side",
        template_type=AssetTemplateType.PNG_OPAQUE,
        tags=["forest", "silhouette", "left", "trees", "winter"],
        prompt_parts=PromptParts(
            subject="winter forest silhouette",
            style_block="dark treeline on left",
            composition="pine trees on left third, dark silhouette, clear sky right side",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        png_defaults=PNGDefaults(),
        negative_hints=["centered", "bright", "detailed", "colorful"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_plate_forest_silhouette_right() -> AssetTemplate:
    """Forest silhouette on right."""
    return AssetTemplate(
        template_id="atpl_plate_forest_silhouette_right",
        name="Forest Silhouette - Right",
        # description: Forest silhouette positioned on right side",
        template_type=AssetTemplateType.PNG_OPAQUE,
        tags=["forest", "silhouette", "right", "trees", "winter"],
        prompt_parts=PromptParts(
            subject="winter forest silhouette",
            style_block="dark treeline on right",
            composition="pine trees on right third, dark silhouette, clear sky left side",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        png_defaults=PNGDefaults(),
        negative_hints=["centered", "bright", "detailed", "colorful"],
        template_version="1.0.0",
    )
