"""Group template registry and registration system.

Registry stores factories so callers always get fresh instances.
Uses the shared TemplateRegistry infrastructure.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from twinklr.core.sequencer.templates.group.models import GroupPlanTemplate
from twinklr.core.sequencer.templates.shared.registry import (
    BaseTemplateInfo,
    TemplateNotFoundError,
    TemplateRegistry,
    normalize_key,
)
from twinklr.core.sequencer.vocabulary import GroupTemplateType

# Re-export for backward compatibility
__all__ = [
    "REGISTRY",
    "GroupTemplateRegistry",
    "TemplateInfo",
    "TemplateNotFoundError",
    "get_group_template",
    "list_group_templates",
    "normalize_key",
    "register_group_template",
]

# Backward compat alias
_norm_key = normalize_key


@dataclass(frozen=True)
class TemplateInfo(BaseTemplateInfo):
    """Lightweight metadata for group templates.

    Extends BaseTemplateInfo with group-specific fields.

    Attributes:
        template_id: Unique template identifier.
        version: Template version string.
        name: Human-readable template name.
        template_type: Template type (lane classification).
        tags: Tuple of tags for categorization.
    """

    template_type: GroupTemplateType


def _make_template_info(t: GroupPlanTemplate) -> TemplateInfo:
    """Factory function to create TemplateInfo from GroupPlanTemplate."""
    return TemplateInfo(
        template_id=t.template_id,
        version=t.template_version,
        name=t.name,
        template_type=t.template_type,
        tags=tuple(t.tags),
    )


class GroupTemplateRegistry(TemplateRegistry[GroupPlanTemplate, TemplateInfo]):
    """Registry for group templates with domain-specific filtering.

    Extends generic TemplateRegistry with group-specific find() method.
    """

    def __init__(self) -> None:
        """Initialize group template registry."""
        super().__init__(
            info_factory=_make_template_info,
            name="group template",
        )

    def list_all(self) -> list[TemplateInfo]:
        """List all registered templates.

        Returns:
            List of TemplateInfo, sorted by template_type and name.
        """
        return sorted(
            self._info_by_id.values(),
            key=lambda x: (x.template_type.value, x.name),
        )

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
