"""Builtin tag definitions.

Registers motif, style, setting, and constraint tags with the global registry.
"""

from twinklr.core.sequencer.theming.catalog import TAG_REGISTRY
from twinklr.core.sequencer.theming.enums import TagCategory
from twinklr.core.sequencer.theming.models import TagDefinition


def _register_tags() -> None:
    """Register all builtin tags."""
    # ==========================================================
    # MOTIF — visual subjects + pattern primitives
    # ==========================================================
    _motif_tags = [
        ("motif.abstract", "Non-representational visuals (shapes/patterns), no literal objects"),
        ("motif.geometric", "Geometric shapes and structured patterns"),
        ("motif.spiral", "Spiral pattern with continuous curves; good for polar mapping"),
        ("motif.helix", "Helical wrap / corkscrew banding (mega-tree friendly)"),
        ("motif.radial_rays", "Radial rays / spokes from a center (starburst-like)"),
        ("motif.concentric_rings", "Concentric circles/rings expanding from center"),
        ("motif.wave_bands", "Waves as large bands/stripes (sinusoidal feel)"),
        ("motif.zigzag", "Zig-zag bands (not too dense)"),
        ("motif.chevrons", "Chevron patterns (large, rhythmic)"),
        ("motif.stripes", "Bold stripes/bands (clean edges, simple)"),
        ("motif.gradient_bands", "Large gradient bands (few stops, not muddy)"),
        ("motif.grid", "Grid/cell structure (blocky tiles)"),
        ("motif.checker", "Checkerboard pattern (large squares, high contrast)"),
        ("motif.dots", "Large dots/blobs (sparse, legible)"),
        ("motif.confetti", "Simple confetti bits (large, sparse, clean)"),
        ("motif.particles", "Particle field with controlled density (not noisy)"),
        ("motif.bokeh", "Soft bokeh circles/blobs (large, uncluttered)"),
        ("motif.sparkles", "Sparkle/glint accents (large, sparse; avoid tiny stars)"),
        ("motif.stars", "Star shapes (simple, bold)"),
        ("motif.light_trails", "Light trail ribbons / streaks (clean, not smoky)"),
        ("motif.ribbons", "Ribbon bands (broad, flowing, high readability)"),
        ("motif.flares", "Lens flare-like blooms (controlled, not overdone)"),
        ("motif.lightning", "Stylized lightning bolts (bold, simple silhouette)"),
        ("motif.fire", "Stylized flame shapes (bold, simple, high contrast)"),
        ("motif.ice", "Icy crystalline shapes (kept large and clean)"),
        ("motif.crystals", "Geometric crystal shards (low detail, clean facets)"),
        ("motif.clouds", "Simple cloud forms (not detailed, not foggy noise)"),
        ("motif.smoke", "Stylized smoke wisps (simple, low noise)"),
        ("motif.water", "Stylized water waves (simple bands, clean)"),
        ("motif.cosmic", "Space/cosmic motifs (stars/nebula-like but simplified)"),
        # Light holiday-ish motifs
        ("motif.snowflakes", "Snowflake shapes (simple, large, high contrast)"),
        ("motif.ornaments", "Simple ornament/bauble shapes (large, uncluttered)"),
        ("motif.candy_stripes", "Candy-like stripes (no literal characters required)"),
    ]

    for tag, desc in _motif_tags:
        TAG_REGISTRY.register(TagDefinition(tag=tag, description=desc, category=TagCategory.MOTIF))

    # ==========================================================
    # STYLE — rendering / illustration style
    # ==========================================================
    _style_tags = [
        ("style.flat_vector", "Flat vector-like shapes, clean edges, minimal shading"),
        ("style.clean_vector", "Very clean vector edges; minimal/no texture"),
        ("style.bold_shapes", "Chunky bold shapes optimized for LED readability"),
        ("style.minimal", "Minimal elements; large forms; uncluttered"),
        ("style.iconic_silhouette", "Strong silhouette with minimal interior detail"),
        ("style.neon", "Neon/glow aesthetic (controlled bloom, not hazy)"),
        ("style.retro_wave", "Synthwave/retrowave vibe (bold, clean; avoid fine grids)"),
        ("style.cyber", "Cyber/tech vibe with luminous accents and geometry"),
        ("style.holographic", "Iridescent/holographic feel (simple, not noisy)"),
        ("style.metallic", "Metallic/chrome highlights (kept clean and bold)"),
        ("style.glass", "Glass-like refraction highlights (simple, legible)"),
        ("style.paper_cut", "Paper-cut layered shapes with clean edges"),
        ("style.pixel_art", "Pixel-art blocks (large pixels, limited palette)"),
        ("style.low_poly", "Low-poly facets (large facets, clean edges)"),
        ("style.posterized", "Posterized shading with few tonal steps (bold bands)"),
    ]

    for tag, desc in _style_tags:
        TAG_REGISTRY.register(TagDefinition(tag=tag, description=desc, category=TagCategory.STYLE))

    # ==========================================================
    # SETTING — mood/energy/scene context
    # ==========================================================
    _setting_tags = [
        ("setting.hype", "High-energy, punchy, concert-like vibe"),
        ("setting.calm", "Calm, smooth vibe (soft transitions, uncluttered)"),
        ("setting.triumphant", "Big, dramatic, victorious feel"),
        ("setting.mysterious", "Dark, moody, suspenseful feel (still readable)"),
        ("setting.playful", "Fun, bouncy, whimsical energy"),
        ("setting.eerie", "Eerie vibe (abstract, tasteful; no gore)"),
        ("setting.cosmic", "Space/cosmic mood (stars, nebula-like, simplified)"),
        ("setting.arcade", "Arcade/game vibe (pixels, bold icons, simple shapes)"),
        ("setting.futuristic", "Futuristic, clean, luminous, high-tech feel"),
        ("setting.gritty", "Gritty/rough feel (still controlled; avoid noisy grain)"),
        ("setting.dreamy", "Dreamy/floaty feel (soft shapes, not muddy)"),
    ]

    for tag, desc in _setting_tags:
        TAG_REGISTRY.register(
            TagDefinition(tag=tag, description=desc, category=TagCategory.SETTING)
        )

    # ==========================================================
    # CONSTRAINT — generation + LED mapping constraints
    # ==========================================================
    _constraint_tags = [
        ("constraint.no_text", "No letters, words, logos, watermarks"),
        ("constraint.no_logos", "No brand marks or identifiable logos"),
        ("constraint.no_watermarks", "No watermarks or signature marks"),
        ("constraint.low_detail", "Avoid tiny details; keep elements large and legible"),
        ("constraint.high_contrast", "High contrast for LED readability"),
        ("constraint.clean_edges", "Clean edges; avoid grain/noise/textures"),
        ("constraint.no_thin_lines", "Avoid thin linework; use filled shapes or thick strokes"),
        ("constraint.sparse_elements", "Keep element density low; avoid clutter"),
        (
            "constraint.centered_composition",
            "Primary content centered; avoid critical detail at edges",
        ),
        ("constraint.seam_safe_x", "Left/right edges tile seamlessly (horizontal seam safety)"),
        ("constraint.seam_safe_y", "Top/bottom edges tile seamlessly (vertical seam safety)"),
        ("constraint.tile_x", "Designed to tile horizontally"),
        ("constraint.tile_y", "Designed to tile vertically"),
        ("constraint.transparent_bg", "Transparent background (alpha required)"),
        ("constraint.opaque_bg", "Opaque background (no alpha required)"),
        (
            "constraint.led_matrix_friendly",
            "Optimized for LED matrices: bold shapes, low detail, high contrast",
        ),
        (
            "constraint.polar_mapped",
            "Designed for polar mapping (angle x radius), mega-tree friendly",
        ),
        ("constraint.loopable", "Designed to loop cleanly (especially for GIF overlays)"),
        ("constraint.noisy_texture_avoid", "Avoid noisy/grainy textures; keep surfaces smooth"),
    ]

    for tag, desc in _constraint_tags:
        TAG_REGISTRY.register(
            TagDefinition(tag=tag, description=desc, category=TagCategory.CONSTRAINT)
        )


# Auto-register on import
_register_tags()
