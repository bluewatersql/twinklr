"""Bootstrap asset template pack - Traditional Holiday (v1).

This module provides 8+ asset templates for traditional Christmas displays,
following the factory pattern with @register_template decorators.
"""

from __future__ import annotations

from .library import register_template
from .models import (
    AssetTemplate,
    BackgroundMode,
    GifDefaults,
    MatrixDefaults,
    OverlayEffect,
    PngDefaults,
    ProjectionDefaults,
    PromptParts,
    PromptStyle,
    TemplateProjectionHint,
    TemplateType,
)


@register_template(aliases=["Ornament Icon", "ornament traditional"])
def tpl_png_icon_ornament_trad() -> AssetTemplate:
    """PNG icon: Centered ornament, transparent, LED-matrix safe."""
    return AssetTemplate(
        template_id="tpl_png_icon_ornament_trad",
        name="PNG Icon — Ornament (Traditional)",
        description="Centered ornament icon, transparent, LED-matrix safe.",
        template_type=TemplateType.PNG_PROMPT,
        tags=[
            "holiday_christmas_traditional",
            "ornaments",
            "icon_friendly",
            "matrix_safe",
            "high_contrast",
            "low_detail",
        ],
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(
            subject="A classic Christmas ornament icon, centered, simplified.",
            style_block="Style: flat illustration with clean vector-like edges. Theme: traditional Christmas.",
            composition="Composition: centered, subject fills ~75% of frame, symmetrical.",
            background="Background: transparent.",
            lighting="Lighting: soft highlight, no harsh shadows.",
            constraints="Avoid: heavy gradients, busy textures.",
            output_intent="Output intent: designed for an LED matrix at low resolution.",
        ),
        matrix_defaults=MatrixDefaults(base_size=256, aspect="1:1"),
        projection_defaults=ProjectionDefaults(mode=TemplateProjectionHint.FLAT),
        png_defaults=PngDefaults(background=BackgroundMode.TRANSPARENT),
        negative_hints=["busy textures", "tiny details", "thin outlines"],
    )


@register_template(aliases=["Santa Waving", "santa cutout"])
def tpl_png_cutout_santa_wave() -> AssetTemplate:
    """PNG cutout: Santa character waving, transparent."""
    return AssetTemplate(
        template_id="tpl_png_cutout_santa_wave",
        name="PNG Cutout — Santa Waving",
        description="Traditional Santa character cutout for overlays.",
        template_type=TemplateType.PNG_PROMPT,
        tags=[
            "holiday_christmas_traditional",
            "santa",
            "character",
            "cutout",
            "matrix_safe",
            "center_focused",
        ],
        prompt_style=PromptStyle.FLAT_ILLUSTRATION,
        prompt_parts=PromptParts(
            subject="Santa Claus character, friendly and traditional, waving with one hand.",
            style_block="Style: cartoon flat illustration, bold shapes, clean edges. Theme: traditional Christmas.",
            composition="Composition: centered full-body, large silhouette, minimal interior detail.",
            background="Background: transparent.",
            lighting="Lighting: simple shading only.",
            constraints="Avoid: fur texture detail, tiny patterns.",
            output_intent="Output intent: LED matrix friendly character cutout.",
        ),
        matrix_defaults=MatrixDefaults(base_size=256, aspect="1:1"),
        projection_defaults=ProjectionDefaults(mode=TemplateProjectionHint.FLAT),
        png_defaults=PngDefaults(background=BackgroundMode.TRANSPARENT),
        negative_hints=["complex fabric texture", "small repeating patterns"],
    )


@register_template(aliases=["Village Background", "cozy village"])
def tpl_png_bg_village_cozy() -> AssetTemplate:
    """PNG background: Cozy village night scene, opaque."""
    return AssetTemplate(
        template_id="tpl_png_bg_village_cozy",
        name="PNG Background — Cozy Village Night",
        description="Storybook village background plate, low detail, strong contrast.",
        template_type=TemplateType.PNG_PROMPT,
        tags=[
            "holiday_christmas_traditional",
            "winter_scene",
            "background",
            "storybook",
            "matrix_safe",
            "low_detail",
        ],
        prompt_style=PromptStyle.STORYBOOK,
        prompt_parts=PromptParts(
            subject="A cozy snowy village at night with warm glowing windows and a decorated Christmas tree.",
            style_block="Style: storybook illustration, simplified, low detail. Theme: traditional Christmas.",
            composition="Composition: uncluttered, large shapes, clear horizon, no tiny details.",
            background="Background: opaque.",
            lighting="Lighting: warm window glow against cool snow, strong contrast.",
            constraints="Avoid: dense brick detail, tiny snowflakes.",
            output_intent="Output intent: LED matrix background plate.",
        ),
        matrix_defaults=MatrixDefaults(base_size=256, aspect="2:1"),
        projection_defaults=ProjectionDefaults(mode=TemplateProjectionHint.FLAT),
        png_defaults=PngDefaults(background=BackgroundMode.OPAQUE),
        negative_hints=["dense textures", "micro-detail"],
    )


@register_template(aliases=["Tree Radial Starburst", "polar radial pattern"])
def tpl_png_tree_polar_radial_starburst() -> AssetTemplate:
    """Tree polar: Seam-safe radial starburst for mega-tree."""
    return AssetTemplate(
        template_id="tpl_png_tree_polar_radial_starburst",
        name="Tree Polar — Radial Starburst (Seam-safe)",
        description="Seam-safe radial pattern for mega-tree polar mapping.",
        template_type=TemplateType.PNG_PROMPT,
        tags=[
            "holiday_christmas_traditional",
            "tree_polar",
            "seam_safe",
            "radial",
            "pattern",
            "matrix_safe",
        ],
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(
            subject="A radial Christmas starburst pattern with repeating rays and small ornaments arranged in circular symmetry.",
            style_block="Style: flat vector-like illustration, bold shapes, clean edges. Theme: traditional Christmas.",
            composition="Composition: perfect radial symmetry, center anchored.",
            background="Background: dark, simple, low texture.",
            lighting="Lighting: minimal; emphasize contrast.",
            constraints="Seam safety: left and right edges must match seamlessly when tiled horizontally. No important elements near left/right edges.",
            output_intent="Output intent: mapped in polar space on a cone mega-tree (angle x radius).",
        ),
        matrix_defaults=MatrixDefaults(base_size=256, aspect="2:1"),
        projection_defaults=ProjectionDefaults(
            mode=TemplateProjectionHint.TREE_POLAR,
            seam_safe=True,
            center_x=0.5,
            center_y=0.5,
        ),
        png_defaults=PngDefaults(background=BackgroundMode.OPAQUE),
        negative_hints=["thin lines", "tiny details", "complex gradients"],
    )


@register_template(aliases=["Tree Candy Cane Spiral", "spiral candy pattern"])
def tpl_png_tree_spiral_candy_cane() -> AssetTemplate:
    """Tree spiral: Seam-safe candy cane swirl for mega-tree."""
    return AssetTemplate(
        template_id="tpl_png_tree_spiral_candy_cane",
        name="Tree Spiral — Candy Cane Swirl (Seam-safe)",
        description="Spiral-friendly candy cane pattern for mega-tree mapping.",
        template_type=TemplateType.PNG_PROMPT,
        tags=[
            "holiday_christmas_traditional",
            "candy_cane",
            "tree_spiral",
            "seam_safe",
            "pattern",
            "high_contrast",
        ],
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(
            subject="A bold candy cane spiral swirl pattern, continuous and smooth, wrapping around the center.",
            style_block="Style: flat illustration, bold red and white stripes, clean edges. Theme: traditional Christmas.",
            composition="Composition: centered spiral, continuous curves, no small details.",
            background="Background: dark simple background, minimal texture.",
            lighting="Lighting: minimal; emphasize crisp stripes.",
            constraints="Seam safety: left and right edges must tile seamlessly.",
            output_intent="Output intent: polar-mapped mega-tree spiral loop (angle x radius).",
        ),
        matrix_defaults=MatrixDefaults(base_size=256, aspect="2:1"),
        projection_defaults=ProjectionDefaults(
            mode=TemplateProjectionHint.TREE_SPIRAL,
            seam_safe=True,
            center_x=0.5,
            center_y=0.5,
        ),
        png_defaults=PngDefaults(background=BackgroundMode.OPAQUE),
        negative_hints=["noisy textures", "thin lines"],
    )


@register_template(aliases=["Snowfall Loop", "falling snow gif"])
def tpl_gif_snowfall_from_png() -> AssetTemplate:
    """GIF: Snowfall loop from base PNG with procedural overlay."""
    return AssetTemplate(
        template_id="tpl_gif_snowfall_from_png",
        name="GIF — Snowfall Loop (Base PNG + Overlay)",
        description="Clean base frame then apply procedural snowfall overlay for a loop.",
        template_type=TemplateType.GIF_FROM_PNG_OVERLAY,
        tags=[
            "holiday_christmas_traditional",
            "gif",
            "falling_snow",
            "loop",
            "matrix_safe",
            "low_detail",
        ],
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(
            subject="A simple Christmas tree silhouette with a star topper, centered, on a dark night sky.",
            style_block="Style: flat illustration, bold shapes, clean edges. Theme: traditional Christmas.",
            composition="Composition: centered tree filling ~70% of frame, clear silhouette.",
            background="Background: opaque dark blue with extremely subtle gradient.",
            lighting="Lighting: simple highlights only.",
            constraints="Keep background clean and uncluttered for snowfall overlay.",
            output_intent="Output intent: base frame for an animated LED matrix loop.",
        ),
        matrix_defaults=MatrixDefaults(base_size=256, aspect="1:1"),
        projection_defaults=ProjectionDefaults(mode=TemplateProjectionHint.FLAT),
        png_defaults=PngDefaults(background=BackgroundMode.OPAQUE),
        gif_defaults=GifDefaults(
            duration_ms=2000, fps=12, loop=True, overlay_effect=OverlayEffect.SNOW
        ),
        negative_hints=["busy textures", "tiny ornaments", "fine garland lines"],
    )


@register_template(aliases=["Twinkle Loop", "sparkle gif"])
def tpl_gif_twinkle_from_png() -> AssetTemplate:
    """GIF: Twinkle loop from base PNG with sparkle overlay."""
    return AssetTemplate(
        template_id="tpl_gif_twinkle_from_png",
        name="GIF — Twinkle Loop (Base PNG + Overlay)",
        description="Clean base frame then procedural sparkle/twinkle overlay.",
        template_type=TemplateType.GIF_FROM_PNG_OVERLAY,
        tags=[
            "holiday_christmas_traditional",
            "gif",
            "twinkle",
            "loop",
            "matrix_safe",
        ],
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(
            subject="A wreath with a red bow, centered, bold silhouette.",
            style_block="Style: flat illustration, bold shapes, clean edges. Theme: traditional Christmas.",
            composition="Composition: centered wreath, large shapes, minimal detail.",
            background="Background: transparent.",
            lighting="Lighting: simple shading only.",
            constraints="Keep interior of wreath simple for twinkle overlay.",
            output_intent="Output intent: base frame for an animated twinkle loop.",
        ),
        matrix_defaults=MatrixDefaults(base_size=256, aspect="1:1"),
        projection_defaults=ProjectionDefaults(mode=TemplateProjectionHint.FLAT),
        png_defaults=PngDefaults(background=BackgroundMode.TRANSPARENT),
        gif_defaults=GifDefaults(
            duration_ms=2000, fps=12, loop=True, overlay_effect=OverlayEffect.TWINKLE
        ),
        negative_hints=["tiny leaves detail", "thin outlines"],
    )


@register_template(aliases=["Pulse Loop", "glow pulse gif"])
def tpl_gif_pulse_from_png() -> AssetTemplate:
    """GIF: Gentle pulse loop from base PNG with brightness overlay."""
    return AssetTemplate(
        template_id="tpl_gif_pulse_from_png",
        name="GIF — Gentle Pulse Loop (Base PNG + Overlay)",
        description="Clean base frame then procedural brightness pulse.",
        template_type=TemplateType.GIF_FROM_PNG_OVERLAY,
        tags=[
            "holiday_christmas_traditional",
            "gif",
            "gentle_pulse",
            "loop",
            "matrix_safe",
        ],
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(
            subject="A glowing Christmas star, centered, bold and simple.",
            style_block="Style: flat illustration, bold shapes, clean edges. Theme: traditional Christmas.",
            composition="Composition: centered star filling ~60% of frame.",
            background="Background: transparent.",
            lighting="Lighting: simple glow, no texture noise.",
            constraints="Keep glow clean and uncluttered for pulse effect.",
            output_intent="Output intent: base frame for a gentle pulse animation loop.",
        ),
        matrix_defaults=MatrixDefaults(base_size=256, aspect="1:1"),
        projection_defaults=ProjectionDefaults(mode=TemplateProjectionHint.FLAT),
        png_defaults=PngDefaults(background=BackgroundMode.TRANSPARENT),
        gif_defaults=GifDefaults(
            duration_ms=2000, fps=12, loop=True, overlay_effect=OverlayEffect.PULSE
        ),
        negative_hints=["grain", "noisy gradients", "tiny sparkles everywhere"],
    )
