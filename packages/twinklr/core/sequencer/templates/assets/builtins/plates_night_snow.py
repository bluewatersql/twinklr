"""Background plate asset templates - Night Sky and Snow Field families."""

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
def make_atpl_plate_night_sky_simple_cool() -> AssetTemplate:
    """Cool tones night sky."""
    return AssetTemplate(
        template_id="atpl_plate_night_sky_simple_cool",
        name="Night Sky Simple - Cool",
        # description: Simple night sky with cool blue/navy tones",
        template_type=AssetTemplateType.PNG_OPAQUE,
        tags=["night", "sky", "cool", "blue", "stars"],
        prompt_parts=PromptParts(
            subject="night sky",
            style_block="simple gradient stars",
            composition="deep blue gradient, navy to midnight blue, sparse distant stars",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        png_defaults=PNGDefaults(),
        negative_hints=["clouds", "moon", "complex", "bright"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_plate_night_sky_simple_warm() -> AssetTemplate:
    """Warm tones night sky."""
    return AssetTemplate(
        template_id="atpl_plate_night_sky_simple_warm",
        name="Night Sky Simple - Warm",
        # description: Simple night sky with warm purple/orange tones",
        template_type=AssetTemplateType.PNG_OPAQUE,
        tags=["night", "sky", "warm", "purple", "orange"],
        prompt_parts=PromptParts(
            subject="night sky",
            style_block="simple gradient stars",
            composition="warm purple gradient, orange to deep purple, sparse twinkling stars",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        png_defaults=PNGDefaults(),
        negative_hints=["clouds", "moon", "complex", "cold tones"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_plate_snow_field_gradient_blue() -> AssetTemplate:
    """Blue snow field gradient."""
    return AssetTemplate(
        template_id="atpl_plate_snow_field_gradient_blue",
        name="Snow Field Gradient - Blue",
        # description: Snow field with blue gradient",
        template_type=AssetTemplateType.PNG_OPAQUE,
        tags=["snow", "field", "gradient", "blue", "winter"],
        prompt_parts=PromptParts(
            subject="snow covered field",
            style_block="soft gradient background",
            composition="light blue to white gradient, smooth snow texture, minimal detail",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        png_defaults=PNGDefaults(),
        negative_hints=["trees", "objects", "shadows", "complex"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_plate_snow_field_gradient_warm() -> AssetTemplate:
    """Warm snow field gradient."""
    return AssetTemplate(
        template_id="atpl_plate_snow_field_gradient_warm",
        name="Snow Field Gradient - Warm",
        # description: Snow field with warm gradient",
        template_type=AssetTemplateType.PNG_OPAQUE,
        tags=["snow", "field", "gradient", "warm", "sunset"],
        prompt_parts=PromptParts(
            subject="snow covered field",
            style_block="soft gradient background",
            composition="warm orange to pink gradient, soft sunset glow, smooth snow texture",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        png_defaults=PNGDefaults(),
        negative_hints=["trees", "objects", "shadows", "complex"],
        template_version="1.0.0",
    )
