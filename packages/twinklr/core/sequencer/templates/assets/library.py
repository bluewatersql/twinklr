"""Asset template registry and registration system.

Registry stores factories so callers always get fresh instances.
Uses the shared TemplateRegistry infrastructure.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from twinklr.core.sequencer.templates.assets.models import AssetTemplate
from twinklr.core.sequencer.templates.shared.registry import (
    BaseTemplateInfo,
    TemplateNotFoundError,
    TemplateRegistry,
)
from twinklr.core.sequencer.vocabulary import AssetTemplateType

# Re-export for backward compatibility
__all__ = [
    "REGISTRY",
    "AssetTemplateInfo",
    "AssetTemplateNotFoundError",
    "AssetTemplateRegistry",
    "get_asset_template",
    "list_asset_templates",
    "register_asset_template",
]

# Backward compatibility alias
AssetTemplateNotFoundError = TemplateNotFoundError


@dataclass(frozen=True)
class AssetTemplateInfo(BaseTemplateInfo):
    """Lightweight metadata for asset templates.

    Extends BaseTemplateInfo with asset-specific fields.

    Attributes:
        template_id: Unique template identifier.
        version: Template version string.
        name: Human-readable template name.
        template_type: Asset template type.
        tags: Tuple of tags for categorization.
    """

    template_type: AssetTemplateType


def _make_template_info(t: AssetTemplate) -> AssetTemplateInfo:
    """Factory function to create AssetTemplateInfo from AssetTemplate."""
    return AssetTemplateInfo(
        template_id=t.template_id,
        version=t.template_version,
        name=t.name,
        template_type=t.template_type,
        tags=tuple(t.tags),
    )


class AssetTemplateRegistry(TemplateRegistry[AssetTemplate, AssetTemplateInfo]):
    """Registry for asset templates with domain-specific filtering.

    Extends generic TemplateRegistry with asset-specific find() method.
    """

    def __init__(self) -> None:
        """Initialize asset template registry."""
        super().__init__(
            info_factory=_make_template_info,
            name="asset template",
        )

    def list_all(self) -> list[AssetTemplateInfo]:
        """List all registered asset templates.

        Returns:
            List of AssetTemplateInfo, sorted by template_type and name.
        """
        return sorted(
            self._info_by_id.values(),
            key=lambda x: (x.template_type.value, x.name),
        )

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
