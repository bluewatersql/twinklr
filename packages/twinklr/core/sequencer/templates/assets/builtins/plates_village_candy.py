"""Background plate asset templates - Village and Candy families."""

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
def make_atpl_plate_village_wide_calm() -> AssetTemplate:
    """Calm village wide view."""
    return AssetTemplate(
        template_id="atpl_plate_village_wide_calm",
        name="Village Wide - Calm",
        # description: Calm wide village scene background",
        template_type=AssetTemplateType.PNG_OPAQUE,
        tags=["village", "wide", "calm", "houses", "winter"],
        prompt_parts=PromptParts(
            subject="winter village panorama",
            style_block="wide calm scene",
            composition="distant houses, snow covered roofs, soft blue hour lighting, peaceful",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        png_defaults=PNGDefaults(),
        negative_hints=["busy", "bright lights", "close up", "complex"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_plate_village_wide_glow() -> AssetTemplate:
    """Village with warm glow."""
    return AssetTemplate(
        template_id="atpl_plate_village_wide_glow",
        name="Village Wide - Glow",
        # description: Village scene with warm window glow",
        template_type=AssetTemplateType.PNG_OPAQUE,
        tags=["village", "wide", "glow", "warm", "lights"],
        prompt_parts=PromptParts(
            subject="winter village panorama",
            style_block="warm glowing windows",
            composition="cozy window lights, warm orange glow, dusk atmosphere, welcoming",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        png_defaults=PNGDefaults(),
        negative_hints=["dark", "cold", "bright", "harsh"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_plate_candy_red_dark_subtle() -> AssetTemplate:
    """Subtle dark candy red."""
    return AssetTemplate(
        template_id="atpl_plate_candy_red_dark_subtle",
        name="Candy Red Dark - Subtle",
        # description: Subtle dark candy red background",
        template_type=AssetTemplateType.PNG_OPAQUE,
        tags=["candy", "red", "dark", "subtle", "gradient"],
        prompt_parts=PromptParts(
            subject="candy red gradient",
            style_block="dark subtle background",
            composition="deep candy red, dark vignette, subtle gradient, minimal texture",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        png_defaults=PNGDefaults(),
        negative_hints=["bright", "white", "patterns", "complex"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_plate_candy_red_dark_contrast() -> AssetTemplate:
    """Dark candy red with contrast."""
    return AssetTemplate(
        template_id="atpl_plate_candy_red_dark_contrast",
        name="Candy Red Dark - Contrast",
        # description: Dark candy red with high contrast",
        template_type=AssetTemplateType.PNG_OPAQUE,
        tags=["candy", "red", "dark", "contrast", "dramatic"],
        prompt_parts=PromptParts(
            subject="candy red gradient",
            style_block="dark dramatic background",
            composition="rich candy red, high contrast, dark edges, dramatic gradient",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        png_defaults=PNGDefaults(),
        negative_hints=["soft", "muted", "flat", "low contrast"],
        template_version="1.0.0",
    )
