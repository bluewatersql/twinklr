"""Theming catalog registry.

Provides a unified registry for palettes, tags, and themes with
consistent lookup, filtering, and registration APIs.

Unlike TemplateRegistry, this uses direct registration (not factories)
since theming items are immutable frozen models.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from twinklr.core.sequencer.theming.enums import TagCategory
from twinklr.core.sequencer.theming.models import (
    MotifDefinition,
    PaletteDefinition,
    TagDefinition,
    ThemeDefinition,
)

logger = logging.getLogger(__name__)


def normalize_key(s: str) -> str:
    """Normalize key for lookup (lowercase, alphanumeric/underscore only)."""
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in s).strip("_")


class ItemNotFoundError(KeyError):
    """Raised when a catalog item is not found."""

    pass


@dataclass(frozen=True)
class PaletteInfo:
    """Lightweight palette metadata for listing."""

    palette_id: str
    title: str
    description: str | None


@dataclass(frozen=True)
class TagInfo:
    """Lightweight tag metadata for listing."""

    tag: str
    description: str | None
    category: TagCategory | None


@dataclass(frozen=True)
class ThemeInfo:
    """Lightweight theme metadata for listing."""

    theme_id: str
    title: str
    description: str | None
    default_palette_id: str | None


@dataclass(frozen=True)
class MotifInfo:
    """Lightweight motif metadata for listing."""

    motif_id: str
    tags: tuple[str, ...]
    description: str | None
    preferred_energy: tuple[str, ...]  # Stored as strings for serialization


class PaletteCatalog:
    """Registry for color palettes.

    Example:
        >>> catalog = PaletteCatalog()
        >>> catalog.register(my_palette)
        >>> palette = catalog.get("core.rgb_primary")
    """

    def __init__(self) -> None:
        """Initialize empty catalog."""
        self._items: dict[str, PaletteDefinition] = {}
        self._aliases: dict[str, str] = {}  # normalized_key -> palette_id
        self._info: dict[str, PaletteInfo] = {}

    def register(
        self,
        item: PaletteDefinition,
        *,
        aliases: Iterable[str] = (),
    ) -> None:
        """Register a palette.

        Args:
            item: Palette definition to register.
            aliases: Additional aliases for lookup.

        Raises:
            ValueError: If palette_id already registered.
        """
        pid = item.palette_id

        if pid in self._items:
            raise ValueError(f"Palette already registered: {pid}")

        self._items[pid] = item

        # Register aliases
        all_aliases = {pid, item.title, *aliases}
        for a in all_aliases:
            self._aliases[normalize_key(a)] = pid

        # Store lightweight info
        self._info[pid] = PaletteInfo(
            palette_id=pid,
            title=item.title,
            description=item.description,
        )

        logger.debug(f"Registered palette: {pid}")

    def get(self, key: str) -> PaletteDefinition:
        """Lookup palette by id or alias.

        Args:
            key: Palette identifier or alias.

        Returns:
            PaletteDefinition (immutable, no copy needed).

        Raises:
            ItemNotFoundError: If palette not found.
        """
        pid = self._aliases.get(normalize_key(key), key)
        item = self._items.get(pid)

        if not item:
            raise ItemNotFoundError(f"Unknown palette: {key}")

        return item

    def has(self, key: str) -> bool:
        """Check if palette exists."""
        pid = self._aliases.get(normalize_key(key), key)
        return pid in self._items

    def list_all(self) -> list[PaletteInfo]:
        """List all registered palettes."""
        return sorted(self._info.values(), key=lambda x: x.palette_id)

    def list_ids(self) -> list[str]:
        """List all registered palette IDs."""
        return sorted(self._items.keys())

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: str) -> bool:
        return self.has(key)


class TagCatalog:
    """Registry for tag definitions.

    Example:
        >>> catalog = TagCatalog()
        >>> catalog.register(my_tag)
        >>> tag = catalog.get("motif.spiral")
    """

    def __init__(self) -> None:
        """Initialize empty catalog."""
        self._items: dict[str, TagDefinition] = {}
        self._aliases: dict[str, str] = {}
        self._info: dict[str, TagInfo] = {}

    def register(
        self,
        item: TagDefinition,
        *,
        aliases: Iterable[str] = (),
    ) -> None:
        """Register a tag.

        Args:
            item: Tag definition to register.
            aliases: Additional aliases for lookup.

        Raises:
            ValueError: If tag already registered.
        """
        tid = item.tag

        if tid in self._items:
            raise ValueError(f"Tag already registered: {tid}")

        self._items[tid] = item

        # Register aliases
        all_aliases = {tid, *aliases}
        for a in all_aliases:
            self._aliases[normalize_key(a)] = tid

        # Store lightweight info
        self._info[tid] = TagInfo(
            tag=tid,
            description=item.description,
            category=item.category,
        )

        logger.debug(f"Registered tag: {tid}")

    def get(self, key: str) -> TagDefinition:
        """Lookup tag by id or alias.

        Args:
            key: Tag identifier or alias.

        Returns:
            TagDefinition (immutable, no copy needed).

        Raises:
            ItemNotFoundError: If tag not found.
        """
        tid = self._aliases.get(normalize_key(key), key)
        item = self._items.get(tid)

        if not item:
            raise ItemNotFoundError(f"Unknown tag: {key}")

        return item

    def has(self, key: str) -> bool:
        """Check if tag exists."""
        tid = self._aliases.get(normalize_key(key), key)
        return tid in self._items

    def list_all(self) -> list[TagInfo]:
        """List all registered tags."""
        return sorted(self._info.values(), key=lambda x: x.tag)

    def list_ids(self) -> list[str]:
        """List all registered tag IDs."""
        return sorted(self._items.keys())

    def find_by_category(self, category: TagCategory) -> list[TagInfo]:
        """Find tags by category.

        Args:
            category: Category to filter by.

        Returns:
            List of TagInfo matching the category.
        """
        return [info for info in self._info.values() if info.category == category]

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: str) -> bool:
        return self.has(key)


class ThemeCatalog:
    """Registry for theme definitions.

    Example:
        >>> catalog = ThemeCatalog()
        >>> catalog.register(my_theme)
        >>> theme = catalog.get("theme.abstract.neon")
    """

    def __init__(self) -> None:
        """Initialize empty catalog."""
        self._items: dict[str, ThemeDefinition] = {}
        self._aliases: dict[str, str] = {}
        self._info: dict[str, ThemeInfo] = {}

    def register(
        self,
        item: ThemeDefinition,
        *,
        aliases: Iterable[str] = (),
    ) -> None:
        """Register a theme.

        Args:
            item: Theme definition to register.
            aliases: Additional aliases for lookup.

        Raises:
            ValueError: If theme already registered.
        """
        tid = item.theme_id

        if tid in self._items:
            raise ValueError(f"Theme already registered: {tid}")

        self._items[tid] = item

        # Register aliases
        all_aliases = {tid, item.title, *aliases}
        for a in all_aliases:
            self._aliases[normalize_key(a)] = tid

        # Store lightweight info
        self._info[tid] = ThemeInfo(
            theme_id=tid,
            title=item.title,
            description=item.description,
            default_palette_id=item.default_palette_id,
        )

        logger.debug(f"Registered theme: {tid}")

    def get(self, key: str) -> ThemeDefinition:
        """Lookup theme by id or alias.

        Args:
            key: Theme identifier or alias.

        Returns:
            ThemeDefinition (immutable, no copy needed).

        Raises:
            ItemNotFoundError: If theme not found.
        """
        tid = self._aliases.get(normalize_key(key), key)
        item = self._items.get(tid)

        if not item:
            raise ItemNotFoundError(f"Unknown theme: {key}")

        return item

    def has(self, key: str) -> bool:
        """Check if theme exists."""
        tid = self._aliases.get(normalize_key(key), key)
        return tid in self._items

    def list_all(self) -> list[ThemeInfo]:
        """List all registered themes."""
        return sorted(self._info.values(), key=lambda x: x.theme_id)

    def list_ids(self) -> list[str]:
        """List all registered theme IDs."""
        return sorted(self._items.keys())

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: str) -> bool:
        return self.has(key)


class MotifCatalog:
    """Registry for motif definitions.

    Motifs are derived from motif.* tags and provide structured metadata
    for visual content guidance.

    Example:
        >>> catalog = MotifCatalog()
        >>> catalog.register(my_motif)
        >>> motif = catalog.get("spiral")
    """

    def __init__(self) -> None:
        """Initialize empty catalog."""
        self._items: dict[str, MotifDefinition] = {}
        self._aliases: dict[str, str] = {}
        self._info: dict[str, MotifInfo] = {}

    def register(
        self,
        item: MotifDefinition,
        *,
        aliases: Iterable[str] = (),
    ) -> None:
        """Register a motif.

        Args:
            item: Motif definition to register.
            aliases: Additional aliases for lookup.

        Raises:
            ValueError: If motif already registered.
        """
        mid = item.motif_id

        if mid in self._items:
            raise ValueError(f"Motif already registered: {mid}")

        self._items[mid] = item

        # Register aliases
        all_aliases = {mid, *aliases}
        for a in all_aliases:
            self._aliases[normalize_key(a)] = mid

        # Store lightweight info (convert enums to strings for serialization)
        self._info[mid] = MotifInfo(
            motif_id=mid,
            tags=tuple(item.tags),
            description=item.description,
            preferred_energy=tuple(
                e.value if hasattr(e, "value") else str(e) for e in item.preferred_energy
            ),
        )

        logger.debug(f"Registered motif: {mid}")

    def get(self, key: str) -> MotifDefinition:
        """Lookup motif by id or alias.

        Args:
            key: Motif identifier or alias.

        Returns:
            MotifDefinition (immutable, no copy needed).

        Raises:
            ItemNotFoundError: If motif not found.
        """
        mid = self._aliases.get(normalize_key(key), key)
        item = self._items.get(mid)

        if not item:
            raise ItemNotFoundError(f"Unknown motif: {key}")

        return item

    def has(self, key: str) -> bool:
        """Check if motif exists."""
        mid = self._aliases.get(normalize_key(key), key)
        return mid in self._items

    def list_all(self) -> list[MotifInfo]:
        """List all registered motifs."""
        return sorted(self._info.values(), key=lambda x: x.motif_id)

    def list_ids(self) -> list[str]:
        """List all registered motif IDs."""
        return sorted(self._items.keys())

    def find_by_tag(self, tag: str) -> list[MotifInfo]:
        """Find motifs that include a specific tag.

        Args:
            tag: Tag to search for.

        Returns:
            List of MotifInfo matching the tag.
        """
        return [info for info in self._info.values() if tag in info.tags]

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: str) -> bool:
        return self.has(key)


# =============================================================================
# Global registries (populated by builtins on import)
# =============================================================================

PALETTE_REGISTRY = PaletteCatalog()
TAG_REGISTRY = TagCatalog()
THEME_REGISTRY = ThemeCatalog()
MOTIF_REGISTRY = MotifCatalog()


# =============================================================================
# Convenience functions
# =============================================================================


def get_palette(key: str) -> PaletteDefinition:
    """Get palette from global registry."""
    return PALETTE_REGISTRY.get(key)


def get_tag(key: str) -> TagDefinition:
    """Get tag from global registry."""
    return TAG_REGISTRY.get(key)


def get_theme(key: str) -> ThemeDefinition:
    """Get theme from global registry."""
    return THEME_REGISTRY.get(key)


def list_palettes() -> list[PaletteInfo]:
    """List all palettes from global registry."""
    return PALETTE_REGISTRY.list_all()


def list_tags() -> list[TagInfo]:
    """List all tags from global registry."""
    return TAG_REGISTRY.list_all()


def list_themes() -> list[ThemeInfo]:
    """List all themes from global registry."""
    return THEME_REGISTRY.list_all()


def get_motif(key: str) -> MotifDefinition:
    """Get motif from global registry."""
    return MOTIF_REGISTRY.get(key)


def list_motifs() -> list[MotifInfo]:
    """List all motifs from global registry."""
    return MOTIF_REGISTRY.list_all()


__all__ = [
    # Catalog classes
    "PaletteCatalog",
    "TagCatalog",
    "ThemeCatalog",
    "MotifCatalog",
    # Info types
    "PaletteInfo",
    "TagInfo",
    "ThemeInfo",
    "MotifInfo",
    # Errors
    "ItemNotFoundError",
    # Global registries
    "PALETTE_REGISTRY",
    "TAG_REGISTRY",
    "THEME_REGISTRY",
    "MOTIF_REGISTRY",
    # Convenience functions
    "get_palette",
    "get_tag",
    "get_theme",
    "get_motif",
    "list_palettes",
    "list_tags",
    "list_themes",
    "list_motifs",
    # Utilities
    "normalize_key",
]
