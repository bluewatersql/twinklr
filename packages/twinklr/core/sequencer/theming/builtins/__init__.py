"""Builtin theming definitions.

Importing this module registers all builtin palettes, tags, themes, and motifs
with the global registries.
"""

# Import modules to trigger registration
# IMPORTANT: Order matters - tags must be registered before motifs
from twinklr.core.sequencer.theming.builtins import (
    motifs as _motifs,  # pyright: ignore[reportUnusedImport]  # noqa: F401
)
from twinklr.core.sequencer.theming.builtins import (
    palettes as _palettes,  # pyright: ignore[reportUnusedImport]  # noqa: F401
)
from twinklr.core.sequencer.theming.builtins import (
    tags as _tags,  # pyright: ignore[reportUnusedImport]  # noqa: F401
)
from twinklr.core.sequencer.theming.builtins import (
    themes as _themes,  # pyright: ignore[reportUnusedImport]  # noqa: F401
)

# Now that all modules are imported, register motifs
# (deferred to ensure TAG_REGISTRY is fully populated)
_motifs._register_motifs()

__all__: list[str] = []
