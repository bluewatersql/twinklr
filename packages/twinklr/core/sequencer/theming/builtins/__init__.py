"""Builtin theming definitions.

Importing this module registers all builtin palettes, tags, and themes
with the global registries.
"""

# Import modules to trigger registration
from twinklr.core.sequencer.theming.builtins import (
    palettes as _palettes,  # pyright: ignore[reportUnusedImport]  # noqa: F401
)
from twinklr.core.sequencer.theming.builtins import (
    tags as _tags,  # pyright: ignore[reportUnusedImport]  # noqa: F401
)
from twinklr.core.sequencer.theming.builtins import (
    themes as _themes,  # pyright: ignore[reportUnusedImport]  # noqa: F401
)

__all__: list[str] = []
