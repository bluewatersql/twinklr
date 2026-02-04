"""Builtin theme definitions.

Registers abstract, pattern, mood, and holiday themes with the global registry.
"""

from twinklr.core.sequencer.theming.catalog import THEME_REGISTRY
from twinklr.core.sequencer.theming.models import ThemeDefinition


def _register_themes() -> None:
    """Register all builtin themes."""
    # ==========================================================
    # Abstract / geometric defaults (use these a lot)
    # ==========================================================
    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.abstract.neon",
            title="Abstract Neon",
            description="Abstract geometric patterns with neon glow accents; high readability.",
            default_tags=["motif.abstract", "motif.geometric"],
            style_tags=["style.neon", "style.bold_shapes"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="core.uv_party",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.abstract.clean_vector",
            title="Abstract Clean Vector",
            description="Minimal clean vector shapes and patterns; crisp edges; LED-friendly.",
            default_tags=["motif.abstract", "motif.geometric"],
            style_tags=["style.clean_vector", "style.minimal", "style.bold_shapes"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="core.mono_cool",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.geometric.retro_wave",
            title="Geometric Retro Wave",
            description="Synthwave style geometric visuals, bold and clean.",
            default_tags=["motif.geometric", "motif.grid"],
            style_tags=["style.retro_wave", "style.bold_shapes"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="core.uv_party",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.cyber.grid",
            title="Cyber Grid",
            description="Cyber-tech grid and ray patterns; luminous accents; clean geometry.",
            default_tags=["motif.geometric", "motif.grid", "motif.radial_rays"],
            style_tags=["style.cyber", "style.bold_shapes"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="spec.cyber_green",
            recommended_template_ids=[],
        )
    )

    # ==========================================================
    # Pattern-specific themes (great for mega-tree / matrices)
    # ==========================================================
    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.pattern.spiral_polar",
            title="Spiral Polar",
            description="Spiral/helix patterns designed for polar mapping on mega-trees.",
            default_tags=["motif.spiral", "motif.helix"],
            style_tags=["style.bold_shapes"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="core.rainbow_bright",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.pattern.starburst",
            title="Starburst Rays",
            description="Radial rays and starbursts; dramatic, center-anchored symmetry.",
            default_tags=["motif.radial_rays", "motif.stars"],
            style_tags=["style.bold_shapes", "style.clean_vector"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="core.gold_warm",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.pattern.waves",
            title="Wave Bands",
            description="Wave band patterns; smooth and musical; uncluttered.",
            default_tags=["motif.wave_bands", "motif.stripes"],
            style_tags=["style.bold_shapes"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="core.ice_neon",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.pattern.particles_bokeh",
            title="Particles & Bokeh",
            description="Controlled particles and bokeh blobs; dreamy but not noisy.",
            default_tags=["motif.particles", "motif.bokeh", "motif.sparkles"],
            style_tags=["style.neon"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="core.uv_party",
            recommended_template_ids=[],
        )
    )

    # ==========================================================
    # Mood-driven themes (use with setting tags in ThemeRef.tags)
    # ==========================================================
    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.mood.hype",
            title="Hype",
            description="High energy concert-like visuals; punchy and bold.",
            default_tags=["motif.geometric"],
            style_tags=["style.neon", "style.bold_shapes"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="core.uv_party",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.mood.calm",
            title="Calm",
            description="Smooth minimal visuals; legible and clean.",
            default_tags=["motif.abstract"],
            style_tags=["style.minimal", "style.clean_vector"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="core.mono_cool",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.mood.triumphant",
            title="Triumphant",
            description="Big dramatic visuals; strong contrast and bold rays.",
            default_tags=["motif.radial_rays", "motif.stars"],
            style_tags=["style.bold_shapes"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="spec.fire_ice",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.mood.mysterious",
            title="Mysterious",
            description="Dark, moody visuals with luminous accents; still readable.",
            default_tags=["motif.cosmic", "motif.sparkles"],
            style_tags=["style.holographic", "style.bold_shapes"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="core.ice_neon",
            recommended_template_ids=[],
        )
    )

    # ==========================================================
    # Light holiday flavor (optional, not dominant)
    # ==========================================================
    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.holiday.winter_modern",
            title="Winter Modern",
            description="Modern winter cues (snowflakes/ice) without heavy traditional imagery.",
            default_tags=["motif.ice", "motif.snowflakes"],
            style_tags=["style.clean_vector", "style.bold_shapes"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="core.mono_cool",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.holiday.candy_modern",
            title="Candy Modern",
            description="Candy-stripe energy without literal characters; playful and bold.",
            default_tags=["motif.candy_stripes", "motif.stripes"],
            style_tags=["style.bold_shapes", "style.flat_vector"],
            avoid_tags=["text", "logo", "watermark"],
            default_palette_id="core.rgb_primary",
            recommended_template_ids=[],
        )
    )


# Auto-register on import
_register_themes()
