"""Cutout/icon asset templates - Santa, Snowman, Reindeer families."""

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
def make_atpl_cutout_santa_wave() -> AssetTemplate:
    """Santa waving."""
    return AssetTemplate(
        template_id="atpl_cutout_santa_wave",
        name="Santa - Wave",
        # description: Santa Claus waving cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["santa", "wave", "character", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="santa claus icon",
            style_block="simple cutout silhouette",
            composition="santa waving, red suit, white beard, friendly pose, clean silhouette",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["realistic", "detailed", "background", "complex"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_santa_smile() -> AssetTemplate:
    """Santa smiling."""
    return AssetTemplate(
        template_id="atpl_cutout_santa_smile",
        name="Santa - Smile",
        # description: Santa Claus smiling cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["santa", "smile", "character", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="santa claus icon",
            style_block="simple cutout silhouette",
            composition="santa smiling, jolly face, red suit, white beard, simple design",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["realistic", "detailed", "background", "waving"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_snowman_scarf() -> AssetTemplate:
    """Snowman with scarf."""
    return AssetTemplate(
        template_id="atpl_cutout_snowman_scarf",
        name="Snowman - Scarf",
        # description: Snowman with scarf cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["snowman", "scarf", "character", "cutout", "winter"],
        prompt_parts=PromptParts(
            subject="snowman icon",
            style_block="simple cutout silhouette",
            composition="snowman with scarf, three snowballs, coal buttons, carrot nose, simple design",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["realistic", "detailed", "background", "complex"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_snowman_hat() -> AssetTemplate:
    """Snowman with hat."""
    return AssetTemplate(
        template_id="atpl_cutout_snowman_hat",
        name="Snowman - Hat",
        # description: Snowman with top hat cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["snowman", "hat", "character", "cutout", "winter"],
        prompt_parts=PromptParts(
            subject="snowman icon",
            style_block="simple cutout silhouette",
            composition="snowman with top hat, three snowballs, coal buttons, friendly, classic design",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["realistic", "detailed", "background", "scarf"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_reindeer_stand() -> AssetTemplate:
    """Reindeer standing."""
    return AssetTemplate(
        template_id="atpl_cutout_reindeer_stand",
        name="Reindeer - Stand",
        # description: Reindeer standing cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["reindeer", "stand", "character", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="reindeer icon",
            style_block="simple cutout silhouette",
            composition="reindeer standing, antlers, side view, elegant pose, simple design",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["realistic", "detailed", "background", "running"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_cutout_reindeer_run() -> AssetTemplate:
    """Reindeer running."""
    return AssetTemplate(
        template_id="atpl_cutout_reindeer_run",
        name="Reindeer - Run",
        # description: Reindeer running cutout icon",
        template_type=AssetTemplateType.PNG_TRANSPARENT,
        tags=["reindeer", "run", "character", "cutout", "christmas"],
        prompt_parts=PromptParts(
            subject="reindeer icon",
            style_block="simple cutout silhouette",
            composition="reindeer running, antlers, side view, dynamic pose, motion",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.SQUARE),
        png_defaults=PNGDefaults(),
        negative_hints=["realistic", "detailed", "background", "standing"],
        template_version="1.0.0",
    )
