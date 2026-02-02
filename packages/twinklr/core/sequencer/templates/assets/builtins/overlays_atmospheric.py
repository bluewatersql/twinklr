"""Overlay GIF asset templates - Snowfall, Twinkle, Glow families."""

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
def make_atpl_overlay_snowfall_light() -> AssetTemplate:
    """Light snowfall overlay."""
    return AssetTemplate(
        template_id="atpl_overlay_snowfall_light",
        name="Snowfall - Light",
        # description: Light snowfall animated overlay",
        template_type=AssetTemplateType.GIF_OVERLAY,
        tags=["snowfall", "light", "overlay", "animated", "winter"],
        prompt_parts=PromptParts(
            subject="falling snow animation",
            style_block="light gentle snowfall",
            composition="gentle falling snow, sparse snowflakes, slow motion, transparent background",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        gif_defaults=GIFDefaults(fps=12, loop=True),
        negative_hints=["heavy", "dense", "fast", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_overlay_snowfall_heavy() -> AssetTemplate:
    """Heavy snowfall overlay."""
    return AssetTemplate(
        template_id="atpl_overlay_snowfall_heavy",
        name="Snowfall - Heavy",
        # description: Heavy snowfall animated overlay",
        template_type=AssetTemplateType.GIF_OVERLAY,
        tags=["snowfall", "heavy", "overlay", "animated", "winter"],
        prompt_parts=PromptParts(
            subject="falling snow animation",
            style_block="heavy dense snowfall",
            composition="dense falling snow, many snowflakes, medium speed, transparent background",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        gif_defaults=GIFDefaults(fps=12, loop=True),
        negative_hints=["light", "sparse", "slow", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_overlay_twinkle_slow() -> AssetTemplate:
    """Slow twinkle overlay."""
    return AssetTemplate(
        template_id="atpl_overlay_twinkle_slow",
        name="Twinkle - Slow",
        # description: Slow twinkle animated overlay",
        template_type=AssetTemplateType.GIF_OVERLAY,
        tags=["twinkle", "slow", "overlay", "animated", "sparkle"],
        prompt_parts=PromptParts(
            subject="twinkling lights animation",
            style_block="slow gentle twinkle",
            composition="scattered sparkles, slow fade in out, gentle glow, transparent background",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        gif_defaults=GIFDefaults(fps=12, loop=True),
        negative_hints=["fast", "harsh", "bright", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_overlay_twinkle_fast() -> AssetTemplate:
    """Fast twinkle overlay."""
    return AssetTemplate(
        template_id="atpl_overlay_twinkle_fast",
        name="Twinkle - Fast",
        # description: Fast twinkle animated overlay",
        template_type=AssetTemplateType.GIF_OVERLAY,
        tags=["twinkle", "fast", "overlay", "animated", "sparkle"],
        prompt_parts=PromptParts(
            subject="twinkling lights animation",
            style_block="fast energetic twinkle",
            composition="scattered sparkles, quick flicker, vibrant, transparent background",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        gif_defaults=GIFDefaults(fps=12, loop=True),
        negative_hints=["slow", "gentle", "dull", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_overlay_glow_pulse_slow() -> AssetTemplate:
    """Slow glow pulse overlay."""
    return AssetTemplate(
        template_id="atpl_overlay_glow_pulse_slow",
        name="Glow Pulse - Slow",
        # description: Slow glow pulse animated overlay",
        template_type=AssetTemplateType.GIF_OVERLAY,
        tags=["glow", "pulse", "slow", "overlay", "animated"],
        prompt_parts=PromptParts(
            subject="glowing pulse animation",
            style_block="slow breathing glow",
            composition="soft glow pulse, slow fade in out, warm atmosphere, transparent background",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        gif_defaults=GIFDefaults(fps=12, loop=True),
        negative_hints=["fast", "harsh", "cold", "solid background"],
        template_version="1.0.0",
    )


@register_asset_template()
def make_atpl_overlay_glow_pulse_beat() -> AssetTemplate:
    """Beat-synced glow pulse overlay."""
    return AssetTemplate(
        template_id="atpl_overlay_glow_pulse_beat",
        name="Glow Pulse - Beat",
        # description: Beat-synced glow pulse animated overlay",
        template_type=AssetTemplateType.GIF_OVERLAY,
        tags=["glow", "pulse", "beat", "overlay", "animated"],
        prompt_parts=PromptParts(
            subject="glowing pulse animation",
            style_block="rhythmic beat pulse",
            composition="glow pulse, quick rhythm, beat timing, transparent background",
        ),
        prompt_policy=PromptPolicy(require_seam_safe=False),
        matrix_defaults=MatrixDefaults(aspect=MatrixAspect.HD),
        gif_defaults=GIFDefaults(fps=12, loop=True),
        negative_hints=["slow", "smooth", "constant", "solid background"],
        template_version="1.0.0",
    )
