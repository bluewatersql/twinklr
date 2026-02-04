"""Theming domain - theme, palette, and tag models.

Provides models for visual theming and categorization across
the choreography system.

Usage:
    # Import models
    from twinklr.core.sequencer.theming import ThemeRef, PaletteDefinition

    # Import registries and convenience functions
    from twinklr.core.sequencer.theming import (
        get_palette, get_tag, get_theme,
        list_palettes, list_tags, list_themes,
    )

    # Access global registries directly
    from twinklr.core.sequencer.theming import PALETTE_REGISTRY, TAG_REGISTRY, THEME_REGISTRY

Note: Importing this module auto-registers all builtins.
"""

# Auto-register builtins on import
from twinklr.core.sequencer.theming import builtins as _builtins  # noqa: F401
from twinklr.core.sequencer.theming.catalog import (
    # Global registries
    PALETTE_REGISTRY,
    TAG_REGISTRY,
    THEME_REGISTRY,
    # Catalog classes
    ItemNotFoundError,
    PaletteCatalog,
    PaletteInfo,
    TagCatalog,
    TagInfo,
    ThemeInfo,
    # Convenience functions
    get_palette,
    get_tag,
    get_theme,
    list_palettes,
    list_tags,
    list_themes,
    normalize_key,
)
from twinklr.core.sequencer.theming.catalog import (
    ThemeCatalog as ThemeCatalogRegistry,
)
from twinklr.core.sequencer.theming.enums import (
    TagCategory,
    ThemeScope,
)
from twinklr.core.sequencer.theming.models import (
    ColorStop,
    PaletteDefinition,
    TagDefinition,
    ThemeCatalog,
    ThemeDefinition,
    ThemeRef,
)

__all__ = [
    # Enums
    "TagCategory",
    "ThemeScope",
    # Models
    "ColorStop",
    "PaletteDefinition",
    "TagDefinition",
    "ThemeCatalog",
    "ThemeDefinition",
    "ThemeRef",
    # Catalog classes
    "PaletteCatalog",
    "TagCatalog",
    "ThemeCatalogRegistry",
    "ItemNotFoundError",
    # Info types
    "PaletteInfo",
    "TagInfo",
    "ThemeInfo",
    # Global registries
    "PALETTE_REGISTRY",
    "TAG_REGISTRY",
    "THEME_REGISTRY",
    # Convenience functions
    "get_palette",
    "get_tag",
    "get_theme",
    "list_palettes",
    "list_tags",
    "list_themes",
    "normalize_key",
]
