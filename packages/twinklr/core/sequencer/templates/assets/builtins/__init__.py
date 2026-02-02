"""Builtin asset templates.

This package contains all builtin asset template definitions.
Importing this package triggers auto-registration of all templates.
"""

# Background Plates (6 families × 2 variants = 12 templates)
# Seam-Safe Tiles (8 families × 2 variants = 16 templates)
# Cutouts/Icons (9 families × 2 variants = 18 templates)
# Overlays/GIF (6 families × 2 variants = 12 templates)
from twinklr.core.sequencer.templates.assets.builtins import (  # noqa: F401  # noqa: F401  # noqa: F401  # noqa: F401
    cutouts_characters,
    cutouts_decorations,
    cutouts_symbols,
    overlays_atmospheric,
    overlays_effects,
    plates_bokeh_forest,
    plates_night_snow,
    plates_village_candy,
    tiles_basic,
    tiles_edge_plaid,
    tiles_sparkle_confetti,
)
