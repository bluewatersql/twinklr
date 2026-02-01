"""Group template registry for template-based choreography selection.

This module provides a registry system for group templates, following the same
pattern as moving_heads/templates/library.py. Templates are registered as factory
functions that return fresh GroupPlanTemplate instances.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .models import GroupPlanTemplate, GroupTemplateType, GroupVisualIntent

logger = logging.getLogger(__name__)


class TemplateNotFoundError(KeyError):
    """Raised when a template lookup fails."""


def _norm_key(s: str) -> str:
    """Normalize user-provided keys (id/name/alias) to a stable lookup key."""
    # Convert to lowercase, replace non-alphanumeric with underscore
    normalized = "".join(ch.lower() if ch.isalnum() else "_" for ch in s)
    # Collapse multiple underscores and strip
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


@dataclass(frozen=True)
class TemplateInfo:
    """Lightweight metadata for listing/search without materializing template instances."""

    template_id: str
    name: str
    template_type: GroupTemplateType
    visual_intent: GroupVisualIntent
    tags: tuple[str, ...]
    template_version: str


class GroupTemplateRegistry:
    """
    Registry stores factories so callers always get a fresh GroupPlanTemplate instance.

    Factories return GroupPlanTemplate objects (Pydantic models).
    Follows the same pattern as moving_heads/templates/library.py for consistency.
    """

    def __init__(self) -> None:
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
        """Register a template factory with optional aliases."""
        t = factory()  # materialize once for validation + metadata
        tid = template_id or t.template_id

        if tid in self._factories_by_id:
            raise ValueError(f"Template already registered: {tid}")

        self._factories_by_id[tid] = factory

        # Add default aliases: id and display name
        all_aliases = {tid, t.name, *aliases}
        for a in all_aliases:
            self._aliases[_norm_key(a)] = tid

        # Store lightweight info for list/search
        self._info_by_id[tid] = TemplateInfo(
            template_id=tid,
            name=t.name,
            template_type=t.template_type,
            visual_intent=t.visual_intent,
            tags=tuple(t.tags),
            template_version=t.template_version,
        )

    def get(self, key: str, *, deep_copy: bool = True) -> GroupPlanTemplate:
        """
        Lookup by template_id OR name/alias (case/format insensitive).

        deep_copy=True ensures no shared state between callers.
        """
        tid = self._aliases.get(_norm_key(key), key)
        factory = self._factories_by_id.get(tid)
        if not factory:
            raise TemplateNotFoundError(f"Unknown template: {key}")

        t = factory()

        return t.model_copy(deep=True) if deep_copy else t

    def list_all(self) -> list[TemplateInfo]:
        """List all registered templates sorted by template_type and name."""
        return sorted(self._info_by_id.values(), key=lambda x: (x.template_type.value, x.name))

    def find(
        self,
        *,
        template_type: GroupTemplateType | None = None,
        visual_intent: GroupVisualIntent | None = None,
        has_tag: str | None = None,
        name_contains: str | None = None,
    ) -> list[TemplateInfo]:
        """Search templates by type, intent, tags, or name substring."""
        tag_key = has_tag.lower() if has_tag else None
        name_key = name_contains.lower() if name_contains else None

        out: list[TemplateInfo] = []
        for info in self._info_by_id.values():
            if template_type is not None and info.template_type != template_type:
                continue
            if visual_intent is not None and info.visual_intent != visual_intent:
                continue
            if tag_key is not None and tag_key not in {t.lower() for t in info.tags}:
                continue
            if name_key is not None and name_key not in info.name.lower():
                continue
            out.append(info)

        return sorted(out, key=lambda x: (x.template_type.value, x.name))


# Global registry instance (simple + ergonomic)
REGISTRY = GroupTemplateRegistry()


def register_template(*, aliases: Iterable[str] = ()) -> Callable:
    """
    Decorator for registering template factory functions.

    Usage:
        @register_template(aliases=["Cozy Village"])
        def make_template() -> GroupPlanTemplate: ...
    """

    def deco(
        fn: Callable[[], GroupPlanTemplate],
    ) -> Callable[[], GroupPlanTemplate]:
        # factory is fn; use fn() to pull template_id/name/etc
        REGISTRY.register(fn, aliases=aliases)
        return fn

    return deco


def get_template(key: str) -> GroupPlanTemplate:
    """Get a template by ID, name, or alias."""
    return REGISTRY.get(key)


def list_templates() -> list[TemplateInfo]:
    """List all registered templates."""
    return REGISTRY.list_all()


def find_templates(
    *,
    template_type: GroupTemplateType | None = None,
    visual_intent: GroupVisualIntent | None = None,
    has_tag: str | None = None,
    name_contains: str | None = None,
) -> list[TemplateInfo]:
    """Search templates by criteria."""
    return REGISTRY.find(
        template_type=template_type,
        visual_intent=visual_intent,
        has_tag=has_tag,
        name_contains=name_contains,
    )
