"""Group template registry and registration system.

Registry stores factories so callers always get fresh instances.
Mirrors the pattern from moving_heads/templates/library.py.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from twinklr.core.sequencer.templates.group.enums import GroupTemplateType
from twinklr.core.sequencer.templates.group.models import GroupPlanTemplate

logger = logging.getLogger(__name__)


class TemplateNotFoundError(KeyError):
    """Raised when a template is not found in the registry."""

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
class TemplateInfo:
    """Lightweight metadata for listing/search without materializing instances.

    Attributes:
        template_id: Unique template identifier.
        version: Template version string.
        name: Human-readable template name.
        template_type: Template type (lane classification).
        tags: Tuple of tags for categorization.
    """

    template_id: str
    version: str
    name: str
    template_type: GroupTemplateType
    tags: tuple[str, ...]


class GroupTemplateRegistry:
    """Registry stores factories so callers always get fresh template instances.

    Pattern: Factory-based registration prevents shared state bugs.
    Each get() call materializes a fresh instance from the factory.
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._factories_by_id: dict[str, Callable[[], GroupPlanTemplate]] = {}
        self._aliases: dict[str, str] = {}  # alias_key -> template_id
        self._info_by_id: dict[str, TemplateInfo] = {}

    def register(
        self,
        factory: Callable[[], GroupPlanTemplate],
        *,
        template_id: str | None = None,
        aliases: Iterable[str] = (),
    ) -> None:
        """Register a template factory.

        Args:
            factory: Callable that returns a GroupPlanTemplate.
            template_id: Optional explicit template_id (uses factory's if None).
            aliases: Additional aliases for lookup.

        Raises:
            ValueError: If template_id already registered.
        """
        # Materialize once for validation and metadata extraction
        t = factory()
        tid = template_id or t.template_id

        if tid in self._factories_by_id:
            raise ValueError(f"Template already registered: {tid}")

        self._factories_by_id[tid] = factory

        # Register aliases: id, name, and any provided aliases
        all_aliases = {tid, t.name, *aliases}
        for a in all_aliases:
            self._aliases[_norm_key(a)] = tid

        # Store lightweight info for list/search
        self._info_by_id[tid] = TemplateInfo(
            template_id=tid,
            version=t.template_version,
            name=t.name,
            template_type=t.template_type,
            tags=tuple(t.tags),
        )

        logger.debug(f"Registered group template: {tid}")

    def get(self, key: str, *, deep_copy: bool = True) -> GroupPlanTemplate:
        """Lookup template by template_id, name, or alias.

        Args:
            key: Template identifier (id, name, or alias).
            deep_copy: Whether to return a deep copy (default: True).

        Returns:
            GroupPlanTemplate instance.

        Raises:
            TemplateNotFoundError: If template not found.
        """
        # Normalize key and lookup template_id
        tid = self._aliases.get(_norm_key(key), key)
        factory = self._factories_by_id.get(tid)

        if not factory:
            raise TemplateNotFoundError(f"Unknown template: {key}")

        # Materialize fresh instance
        t = factory()

        # Return deep copy to prevent shared state
        return t.model_copy(deep=True) if deep_copy else t

    def list_all(self) -> list[TemplateInfo]:
        """List all registered templates.

        Returns:
            List of TemplateInfo, sorted by template_type and name.
        """
        return sorted(self._info_by_id.values(), key=lambda x: (x.template_type.value, x.name))

    def find(
        self,
        *,
        template_type: GroupTemplateType | None = None,
        has_tag: str | None = None,
        name_contains: str | None = None,
    ) -> list[TemplateInfo]:
        """Find templates matching criteria.

        Args:
            template_type: Filter by template type.
            has_tag: Filter by tag (case-insensitive).
            name_contains: Filter by name substring (case-insensitive).

        Returns:
            List of matching TemplateInfo, sorted by template_type and name.
        """
        tag_key = has_tag.lower() if has_tag else None
        name_key = name_contains.lower() if name_contains else None

        out: list[TemplateInfo] = []
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
REGISTRY = GroupTemplateRegistry()


def register_group_template(*, aliases: Iterable[str] = ()):
    """Decorator for registering group template factory functions.

    Usage:
        @register_group_template(aliases=["Starfield Slow"])
        def make_gtpl_base_starfield_slow() -> GroupPlanTemplate:
            return GroupPlanTemplate(...)

    Args:
        aliases: Additional aliases for template lookup.

    Returns:
        Decorator function.
    """

    def decorator(fn: Callable[[], GroupPlanTemplate]) -> Callable[[], GroupPlanTemplate]:
        REGISTRY.register(fn, aliases=aliases)
        return fn

    return decorator


# Convenience functions
def get_group_template(key: str) -> GroupPlanTemplate:
    """Get a group template by key (id, name, or alias).

    Args:
        key: Template identifier.

    Returns:
        GroupPlanTemplate instance.

    Raises:
        TemplateNotFoundError: If template not found.
    """
    return REGISTRY.get(key)


def list_group_templates() -> list[TemplateInfo]:
    """List all registered group templates.

    Returns:
        List of TemplateInfo.
    """
    return REGISTRY.list_all()
