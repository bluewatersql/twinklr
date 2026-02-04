"""Builtin theme definitions.

Registers abstract, pattern, mood, and holiday themes with the global registry.
"""

from twinklr.core.sequencer.theming.catalog import THEME_REGISTRY
from twinklr.core.sequencer.theming.models import ThemeDefinition

COMMON_AVOID = ["constraint.no_text", "constraint.no_logos", "constraint.no_watermarks"]

COMMON_CONSTRAINTS = [
    "constraint.led_matrix_friendly",
    "constraint.low_detail",
    "constraint.high_contrast",
    "constraint.clean_edges",
    "constraint.no_thin_lines",
    "constraint.noisy_texture_avoid",
]


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
            default_tags=["motif.abstract", "motif.geometric", *COMMON_CONSTRAINTS],
            style_tags=["style.neon", "style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="core.uv_party",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.abstract.clean_vector",
            title="Abstract Clean Vector",
            description="Minimal clean vector shapes and patterns; crisp edges; LED-friendly.",
            default_tags=["motif.abstract", "motif.geometric", *COMMON_CONSTRAINTS],
            style_tags=["style.clean_vector", "style.minimal", "style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="core.mono_cool",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.geometric.retro_wave",
            title="Geometric Retro Wave",
            description="Synthwave style geometric visuals, bold and clean.",
            default_tags=["motif.geometric", "motif.grid", *COMMON_CONSTRAINTS],
            style_tags=["style.retro_wave", "style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="core.uv_party",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.cyber.grid",
            title="Cyber Grid",
            description="Cyber-tech grid and ray patterns; luminous accents; clean geometry.",
            default_tags=[
                "motif.geometric",
                "motif.grid",
                "motif.radial_rays",
                *COMMON_CONSTRAINTS,
            ],
            style_tags=["style.cyber", "style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
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
            default_tags=[
                "motif.spiral",
                "motif.helix",
                "constraint.polar_mapped",
                "constraint.loopable",
                "constraint.seam_safe_x",
                *COMMON_CONSTRAINTS,
            ],
            style_tags=["style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="core.rainbow_bright",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.pattern.starburst",
            title="Starburst Rays",
            description="Radial rays and starbursts; dramatic, center-anchored symmetry.",
            default_tags=[
                "motif.radial_rays",
                "motif.stars",
                "constraint.centered_composition",
                *COMMON_CONSTRAINTS,
            ],
            style_tags=["style.bold_shapes", "style.clean_vector"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="core.gold_warm",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.pattern.waves",
            title="Wave Bands",
            description="Wave band patterns; smooth and musical; uncluttered.",
            default_tags=[
                "motif.wave_bands",
                "motif.stripes",
                "constraint.loopable",
                "constraint.seam_safe_x",
                *COMMON_CONSTRAINTS,
            ],
            style_tags=["style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="core.ice_neon",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.pattern.particles_bokeh",
            title="Particles & Bokeh",
            description="Controlled particles and bokeh blobs; dreamy but not noisy.",
            default_tags=[
                "motif.particles",
                "motif.bokeh",
                "motif.sparkles",
                "constraint.sparse_elements",
                *COMMON_CONSTRAINTS,
            ],
            style_tags=["style.neon"],
            avoid_tags=COMMON_AVOID,
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
            default_tags=["motif.geometric", "setting.hype", *COMMON_CONSTRAINTS],
            style_tags=["style.neon", "style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="core.uv_party",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.mood.calm",
            title="Calm",
            description="Smooth minimal visuals; legible and clean.",
            default_tags=["motif.abstract", "setting.calm", *COMMON_CONSTRAINTS],
            style_tags=["style.minimal", "style.clean_vector"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="core.mono_cool",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.mood.triumphant",
            title="Triumphant",
            description="Big dramatic visuals; strong contrast and bold rays.",
            default_tags=[
                "motif.radial_rays",
                "motif.stars",
                "setting.triumphant",
                *COMMON_CONSTRAINTS,
            ],
            style_tags=["style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="spec.fire_ice",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.mood.mysterious",
            title="Mysterious",
            description="Dark, moody visuals with luminous accents; still readable.",
            default_tags=[
                "motif.cosmic",
                "motif.sparkles",
                "setting.mysterious",
                *COMMON_CONSTRAINTS,
            ],
            style_tags=["style.holographic", "style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
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
            default_tags=[
                "motif.ice",
                "motif.snowflakes",
                "constraint.sparse_elements",
                *COMMON_CONSTRAINTS,
            ],
            style_tags=["style.clean_vector", "style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="core.mono_cool",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.holiday.candy_modern",
            title="Candy Modern",
            description="Candy-stripe energy without literal characters; playful and bold.",
            default_tags=[
                "motif.candy_stripes",
                "motif.stripes",
                "setting.playful",
                "constraint.seam_safe_x",
                *COMMON_CONSTRAINTS,
            ],
            style_tags=["style.bold_shapes", "style.flat_vector"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="core.rgb_primary",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.mood.eerie",
            title="Eerie",
            description="Eerie, high-contrast abstract visuals (no horror/gore), bold and readable.",
            default_tags=["motif.cosmic", "motif.sparkles", "setting.eerie", *COMMON_CONSTRAINTS],
            style_tags=["style.neon", "style.posterized"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="spec.eerie_slime",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.mood.dreamy",
            title="Dreamy",
            description="Soft bokeh / ribbons / sparkles with clean, uncluttered composition.",
            default_tags=["motif.bokeh", "motif.ribbons", "setting.dreamy", *COMMON_CONSTRAINTS],
            style_tags=["style.glass", "style.minimal"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="spec.dreamy_pastel",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.setting.arcade",
            title="Arcade",
            description="Pixel/block vibes with punchy colors; very LED-matrix friendly.",
            default_tags=["motif.grid", "setting.arcade", *COMMON_CONSTRAINTS],
            style_tags=["style.pixel_art", "style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="spec.arcade_cabinet",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.setting.cosmic",
            title="Cosmic Night",
            description="Space/cosmic mood: stars, flares, sparkles; simplified and clean.",
            default_tags=[
                "motif.cosmic",
                "motif.stars",
                "motif.flares",
                "setting.cosmic",
                *COMMON_CONSTRAINTS,
            ],
            style_tags=["style.holographic", "style.neon"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="spec.cosmic_night",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.setting.futuristic",
            title="Futuristic Clean",
            description="Clean futuristic geometry with luminous accents; crisp and modern.",
            default_tags=["motif.geometric", "setting.futuristic", *COMMON_CONSTRAINTS],
            style_tags=["style.cyber", "style.clean_vector"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="spec.futuristic_teal",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.setting.gritty",
            title="Gritty Embers",
            description="Darker, heavier vibe using bold ember warmth (no noisy textures).",
            default_tags=["motif.lightning", "motif.flares", "setting.gritty", *COMMON_CONSTRAINTS],
            style_tags=["style.posterized", "style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="spec.gritty_embers",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.holiday.traditional",
            title="Holiday Traditional",
            description="Classic holiday color language; keep imagery optional and pattern-first.",
            default_tags=[
                "motif.stripes",
                "motif.ornaments",
                "constraint.seam_safe_x",
                *COMMON_CONSTRAINTS,
            ],
            style_tags=["style.flat_vector", "style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="core.christmas_traditional",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.holiday.peppermint",
            title="Holiday Peppermint",
            description="Candy cane stripe energy; ideal for spirals, helixes, and wave bands.",
            default_tags=[
                "motif.candy_stripes",
                "motif.spiral",
                "constraint.polar_mapped",
                "constraint.loopable",
                "constraint.seam_safe_x",
                *COMMON_CONSTRAINTS,
            ],
            style_tags=["style.clean_vector", "style.bold_shapes"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="core.peppermint",
            recommended_template_ids=[],
        )
    )

    THEME_REGISTRY.register(
        ThemeDefinition(
            theme_id="theme.style.holo_prism",
            title="Holo Prism",
            description="Prismatic holographic glow over clean geometry; avoid mud via few stops.",
            default_tags=["motif.geometric", "motif.gradient_bands", *COMMON_CONSTRAINTS],
            style_tags=["style.holographic", "style.glass"],
            avoid_tags=COMMON_AVOID,
            default_palette_id="spec.holo_prism",
            recommended_template_ids=[],
        )
    )


# Auto-register on import
_register_themes()
