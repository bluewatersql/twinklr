"""Overlay GIF asset templates - Sparkle Burst, Confetti, Light Rays families."""

from twinklr.core.sequencer.templates.assets.enums import AssetTemplateType, MatrixAspect
from twinklr.core.sequencer.templates.assets.library import register_asset_template
from twinklr.core.sequencer.templates.assets.models import (
    AssetTemplate,
    GIFDefaults,
    MatrixDefaults,
    PromptParts,
    PromptPolicy,
)


@register_asset_template()
def make_atpl_overlay_sparkle_burst_small() -> AssetTemplate:
    """Small sparkle burst overlay."""
    return AssetTemplate(
        template_id="atpl_overlay_sparkle_burst_small",
        name="Sparkle Burst - Small",
        # description: Small sparkle burst animated overlay",
        template_type=AssetTemplateType.GIF_OVERLAY,
        tags=["sparkle", "burst", "small", "overlay", "animated"],
        prompt_parts=PromptParts(
            subject="sparkle burst animation",
            style_block="small scattered bursts",
            composition="small sparkle bursts, quick flash, scattered placement, transparent background",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        gif_defaults=GIFDefaults(fps=12, loop=True),
        negative_hints=["large", "slow", "constant", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_overlay_sparkle_burst_big() -> AssetTemplate:
    """Big sparkle burst overlay."""
    return AssetTemplate(
        template_id="atpl_overlay_sparkle_burst_big",
        name="Sparkle Burst - Big",
        # description: Big sparkle burst animated overlay",
        template_type=AssetTemplateType.GIF_OVERLAY,
        tags=["sparkle", "burst", "big", "overlay", "animated"],
        prompt_parts=PromptParts(
            subject="sparkle burst animation",
            style_block="large dramatic bursts",
            composition="large sparkle bursts, dramatic flash, radiating sparkles, transparent background",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        gif_defaults=GIFDefaults(fps=12, loop=True),
        negative_hints=["small", "subtle", "gentle", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_overlay_confetti_subtle() -> AssetTemplate:
    """Subtle confetti overlay."""
    return AssetTemplate(
        template_id="atpl_overlay_confetti_subtle",
        name="Confetti - Subtle",
        # description: Subtle confetti animated overlay",
        template_type=AssetTemplateType.GIF_OVERLAY,
        tags=["confetti", "subtle", "overlay", "animated", "celebration"],
        prompt_parts=PromptParts(
            subject="falling confetti animation",
            style_block="subtle gentle confetti",
            composition="sparse confetti, gentle fall, red green gold, transparent background",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        gif_defaults=GIFDefaults(fps=12, loop=True),
        negative_hints=["dense", "heavy", "fast", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_overlay_confetti_party() -> AssetTemplate:
    """Party confetti overlay."""
    return AssetTemplate(
        template_id="atpl_overlay_confetti_party",
        name="Confetti - Party",
        # description: Dense party confetti animated overlay",
        template_type=AssetTemplateType.GIF_OVERLAY,
        tags=["confetti", "party", "overlay", "animated", "celebration"],
        prompt_parts=PromptParts(
            subject="falling confetti animation",
            style_block="dense party confetti",
            composition="dense confetti, fast fall, colorful pieces, transparent background",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        gif_defaults=GIFDefaults(fps=12, loop=True),
        negative_hints=["sparse", "gentle", "slow", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_overlay_light_rays_soft() -> AssetTemplate:
    """Soft light rays overlay."""
    return AssetTemplate(
        template_id="atpl_overlay_light_rays_soft",
        name="Light Rays - Soft",
        # description: Soft light rays animated overlay",
        template_type=AssetTemplateType.GIF_OVERLAY,
        tags=["light", "rays", "soft", "overlay", "animated"],
        prompt_parts=PromptParts(
            subject="light rays animation",
            style_block="soft diffused rays",
            composition="soft light beams, gentle motion, warm glow, transparent background",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        gif_defaults=GIFDefaults(fps=12, loop=True),
        negative_hints=["sharp", "harsh", "bright", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_overlay_light_rays_sharp() -> AssetTemplate:
    """Sharp light rays overlay."""
    return AssetTemplate(
        template_id="atpl_overlay_light_rays_sharp",
        name="Light Rays - Sharp",
        # description: Sharp light rays animated overlay",
        template_type=AssetTemplateType.GIF_OVERLAY,
        tags=["light", "rays", "sharp", "overlay", "animated"],
        prompt_parts=PromptParts(
            subject="light rays animation",
            style_block="sharp dramatic rays",
            composition="crisp light beams, dramatic motion, defined edges, transparent background",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        gif_defaults=GIFDefaults(fps=12, loop=True),
        negative_hints=["soft", "diffused", "gentle", "solid background"],
        template_version="1.0.0",
    )
