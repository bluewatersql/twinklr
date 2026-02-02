"""Asset template registry and registration system.

Registry stores factories so callers always get fresh instances.
Mirrors the pattern from group templates.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from twinklr.core.sequencer.templates.assets.enums import AssetTemplateType
from twinklr.core.sequencer.templates.assets.models import AssetTemplate

logger = logging.getLogger(__name__)


class AssetTemplateNotFoundError(KeyError):
    """Raised when an asset template is not found in the registry."""

    pass


def _norm_key(s: str) -> str:
    """Normalize user-provided keys to stable lookup key.

    Args:
        s: Key to normalize (template_id, name, or alias).

    Returns:
        Normalized key (lowercase, alphanumeric/underscore only).
    """
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in s).strip("_")


@dataclass(frozen=True)
class AssetTemplateInfo:
    """Lightweight metadata for listing/search without materializing instances.

    Attributes:
        template_id: Unique template identifier.
        version: Template version string.
        name: Human-readable template name.
        template_type: Asset template type.
        tags: Tuple of tags for categorization.
    """

    template_id: str
    version: str
    name: str
    template_type: AssetTemplateType
    tags: tuple[str, ...]


class AssetTemplateRegistry:
    """Registry stores factories so callers always get fresh asset template instances.

    Pattern: Factory-based registration prevents shared state bugs.
    Each get() call materializes a fresh instance from the factory.
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._factories_by_id: dict[str, Callable[[], AssetTemplate]] = {}
        self._aliases: dict[str, str] = {}  # alias_key -> template_id
        self._info_by_id: dict[str, AssetTemplateInfo] = {}

    def register(
        self,
        factory: Callable[[], AssetTemplate],
        *,
        template_id: str | None = None,
        aliases: Iterable[str] = (),
    ) -> None:
        """Register an asset template factory.

        Args:
            factory: Callable that returns an AssetTemplate.
            template_id: Optional explicit template_id (uses factory's if None).
            aliases: Additional aliases for lookup.

        Raises:
            ValueError: If template_id already registered.
        """
        # Materialize once for validation and metadata extraction
        t = factory()
        tid = template_id or t.template_id

        if tid in self._factories_by_id:
            raise ValueError(f"Asset template already registered: {tid}")

        self._factories_by_id[tid] = factory

        # Register aliases: id, name, and any provided aliases
        all_aliases = {tid, t.name, *aliases}
        for a in all_aliases:
            self._aliases[_norm_key(a)] = tid

        # Store lightweight info for list/search
        self._info_by_id[tid] = AssetTemplateInfo(
            template_id=tid,
            version=t.template_version,
            name=t.name,
            template_type=t.template_type,
            tags=tuple(t.tags),
        )

        logger.debug(f"Registered asset template: {tid}")

    def get(self, key: str, *, deep_copy: bool = True) -> AssetTemplate:
        """Lookup asset template by template_id, name, or alias.

        Args:
            key: Template identifier (id, name, or alias).
            deep_copy: Whether to return a deep copy (default: True).

        Returns:
            AssetTemplate instance.

        Raises:
            AssetTemplateNotFoundError: If template not found.
        """
        # Normalize key and lookup template_id
        tid = self._aliases.get(_norm_key(key), key)
        factory = self._factories_by_id.get(tid)

        if not factory:
            raise AssetTemplateNotFoundError(f"Unknown asset template: {key}")

        # Materialize fresh instance
        t = factory()

        # Return deep copy to prevent shared state
        return t.model_copy(deep=True) if deep_copy else t

    def list_all(self) -> list[AssetTemplateInfo]:
        """List all registered asset templates.

        Returns:
            List of AssetTemplateInfo, sorted by template_type and name.
        """
        return sorted(self._info_by_id.values(), key=lambda x: (x.template_type.value, x.name))

    def find(
        self,
        *,
        template_type: AssetTemplateType | None = None,
        has_tag: str | None = None,
        name_contains: str | None = None,
    ) -> list[AssetTemplateInfo]:
        """Find asset templates matching criteria.

        Args:
            template_type: Filter by template type.
            has_tag: Filter by tag (case-insensitive).
            name_contains: Filter by name substring (case-insensitive).

        Returns:
            List of matching AssetTemplateInfo, sorted by template_type and name.
        """
        tag_key = has_tag.lower() if has_tag else None
        name_key = name_contains.lower() if name_contains else None

        out: list[AssetTemplateInfo] = []
        for info in self._info_by_id.values():
            # Filter by template_type
            if template_type is not None and info.template_type != template_type:
                continue

            # Filter by tag
            if tag_key is not None and tag_key not in {t.lower() for t in info.tags}:
                continue

            # Filter by name substring
            if name_key is not None and name_key not in info.name.lower():
                continue

            out.append(info)

        return sorted(out, key=lambda x: (x.template_type.value, x.name))


# Global registry instance
REGISTRY = AssetTemplateRegistry()


def register_asset_template(*, aliases: Iterable[str] = ()):
    """Decorator for registering asset template factory functions.

    Usage:
        @register_asset_template(aliases=["Night Sky Simple"])
        def make_atpl_plate_night_sky_simple() -> AssetTemplate:
            return AssetTemplate(...)

    Args:
        aliases: Additional aliases for template lookup.

    Returns:
        Decorator function.
    """

    def decorator(fn: Callable[[], AssetTemplate]) -> Callable[[], AssetTemplate]:
        REGISTRY.register(fn, aliases=aliases)
        return fn

    return decorator


# Convenience functions
def get_asset_template(key: str) -> AssetTemplate:
    """Get an asset template by key (id, name, or alias).

    Args:
        key: Template identifier.

    Returns:
        AssetTemplate instance.

    Raises:
        AssetTemplateNotFoundError: If template not found.
    """
    return REGISTRY.get(key)


def list_asset_templates() -> list[AssetTemplateInfo]:
    """List all registered asset templates.

    Returns:
        List of AssetTemplateInfo.
    """
    return REGISTRY.list_all()
