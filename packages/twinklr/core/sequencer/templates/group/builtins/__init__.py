"""Builtin group templates.

This package contains all builtin group template definitions.
Importing this package triggers auto-registration of all templates.
"""

# BASE lane templates (7 families × 2 variants = 14 templates)
# RHYTHM lane templates (12 families × 2-3 variants = 26 templates)
# ACCENT lane templates (10 families × 2 variants = 21 templates)
# TRANSITION lane templates (6 families × 2 variants = 12 templates)
# SPECIAL lane templates (5 families × 2 variants = 10 templates)
from twinklr.core.sequencer.templates.group.builtins import (  # noqa: F401  # noqa: F401  # noqa: F401  # noqa: F401  # noqa: F401
    accent_effects,
    accent_hits,
    accent_sequences,
    base_flicker,
    base_glow,
    base_shimmer,
    base_snow,
    base_starfield,
    base_vignette,
    base_wash,
    rhythm_dynamics,
    rhythm_patterns,
    rhythm_pulse,
    rhythm_special,
    rhythm_sweep,
    special_moments,
    transition_advanced,
    transition_basic,
)
