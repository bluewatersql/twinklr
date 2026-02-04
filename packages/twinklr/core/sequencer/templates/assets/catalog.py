"""Asset template catalog builder and models.

Provides lightweight catalog interface for Asset Creation Agent.
Converts AssetTemplateRegistry → AssetCatalog.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.templates.assets.library import REGISTRY
from twinklr.core.sequencer.vocabulary import AssetTemplateType


class AssetCatalogEntry(BaseModel):
    """Lightweight asset template catalog entry for Asset Creation Agent.

    Full template definitions are handled by the template system.
    This provides just enough info for the agent to select templates.

    Attributes:
        template_id: Unique template identifier.
        name: Human-readable template name.
        template_type: Asset template type (PNG/GIF variants).
        tags: List of tags for categorization.
        description: Optional template description.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: str
    name: str
    template_type: AssetTemplateType
    tags: list[str] = Field(default_factory=list)
    description: str = ""


class AssetCatalog(BaseModel):
    """Lightweight asset template catalog for Asset Creation Agent.

    Provides template_id existence checks and type filtering.

    Attributes:
        schema_version: Catalog schema version.
        entries: List of asset catalog entries.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "asset-catalog.v1"
    entries: list[AssetCatalogEntry] = Field(default_factory=list)

    def has_template(self, template_id: str) -> bool:
        """Check if template_id exists in catalog.

        Args:
            template_id: Template identifier to check.

        Returns:
            True if template exists in catalog.
        """
        return any(e.template_id == template_id for e in self.entries)

    def get_entry(self, template_id: str) -> AssetCatalogEntry | None:
        """Get catalog entry by template_id.

        Args:
            template_id: Template identifier to lookup.

        Returns:
            AssetCatalogEntry if found, None otherwise.
        """
        return next((e for e in self.entries if e.template_id == template_id), None)

    def list_by_type(self, template_type: AssetTemplateType) -> list[AssetCatalogEntry]:
        """List all templates of a given type.

        Args:
            template_type: Asset template type to filter by.

        Returns:
            List of matching AssetCatalogEntry instances.
        """
        return [e for e in self.entries if e.template_type == template_type]

    def list_by_tag(self, tag: str) -> list[AssetCatalogEntry]:
        """List all templates with a given tag.

        Args:
            tag: Tag to filter by (case-insensitive).

        Returns:
            List of matching AssetCatalogEntry instances.
        """
        tag_lower = tag.lower()
        return [e for e in self.entries if tag_lower in {t.lower() for t in e.tags}]


def build_asset_catalog() -> AssetCatalog:
    """Build AssetCatalog from AssetTemplateRegistry.

    Converts registered asset templates into lightweight AssetCatalogEntry
    for Asset Creation Agent consumption.

    Returns:
        AssetCatalog with all registered asset templates.

    Example:
        >>> from twinklr.core.sequencer.templates.assets import load_builtin_asset_templates
        >>> load_builtin_asset_templates()
        >>> catalog = build_asset_catalog()
        >>> len(catalog.entries)
        42  # Example count
    """
    infos = REGISTRY.list_all()

    entries = [
        AssetCatalogEntry(
            template_id=info.template_id,
            name=info.name,
            template_type=info.template_type,
            tags=list(info.tags),
            description="",  # Can be populated from template if needed
        )
        for info in infos
    ]

    return AssetCatalog(entries=entries)


__all__ = [
    "AssetCatalog",
    "AssetCatalogEntry",
    "build_asset_catalog",
]
