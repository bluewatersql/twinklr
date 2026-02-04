"""Asset template catalog builder and models.

Provides lightweight catalog interface for Asset Creation Agent.
Uses AssetTemplateInfo directly (no duplication).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.templates.assets.library import REGISTRY, AssetTemplateInfo
from twinklr.core.sequencer.vocabulary import AssetTemplateType


class AssetCatalog(BaseModel):
    """Lightweight asset template catalog for Asset Creation Agent.

    Provides template_id existence checks and type filtering.
    Uses AssetTemplateInfo directly (no duplication).

    Attributes:
        schema_version: Catalog schema version.
        entries: List of asset template info entries.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "asset-catalog.v1"
    entries: list[AssetTemplateInfo] = Field(default_factory=list)

    def has_template(self, template_id: str) -> bool:
        """Check if template_id exists in catalog.

        Args:
            template_id: Template identifier to check.

        Returns:
            True if template exists in catalog.
        """
        return any(e.template_id == template_id for e in self.entries)

    def get_entry(self, template_id: str) -> AssetTemplateInfo | None:
        """Get catalog entry by template_id.

        Args:
            template_id: Template identifier to lookup.

        Returns:
            AssetTemplateInfo if found, None otherwise.
        """
        return next((e for e in self.entries if e.template_id == template_id), None)

    def list_by_type(self, template_type: AssetTemplateType) -> list[AssetTemplateInfo]:
        """List all templates of a given type.

        Args:
            template_type: Asset template type to filter by.

        Returns:
            List of matching AssetTemplateInfo instances.
        """
        return [e for e in self.entries if e.template_type == template_type]

    def list_by_tag(self, tag: str) -> list[AssetTemplateInfo]:
        """List all templates with a given tag.

        Args:
            tag: Tag to filter by (case-insensitive).

        Returns:
            List of matching AssetTemplateInfo instances.
        """
        tag_lower = tag.lower()
        return [e for e in self.entries if tag_lower in {t.lower() for t in e.tags}]


def build_asset_catalog() -> AssetCatalog:
    """Build AssetCatalog from AssetTemplateRegistry.

    Uses AssetTemplateInfo directly without duplication.

    Returns:
        AssetCatalog with all registered asset templates.

    Example:
        >>> from twinklr.core.sequencer.templates.assets import load_builtin_asset_templates
        >>> load_builtin_asset_templates()
        >>> catalog = build_asset_catalog()
        >>> len(catalog.entries)
        42  # Example count
    """
    entries = REGISTRY.list_all()
    return AssetCatalog(entries=entries)


__all__ = [
    "AssetCatalog",
    "build_asset_catalog",
]
