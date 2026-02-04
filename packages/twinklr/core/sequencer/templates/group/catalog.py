"""Group template catalog builder and models.

Provides lightweight catalog interface for GroupPlanner agent.
Converts GroupTemplateRegistry → TemplateCatalog.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.templates.group.library import REGISTRY
from twinklr.core.sequencer.vocabulary import GroupTemplateType, LaneKind


class TemplateCatalogEntry(BaseModel):
    """Lightweight template catalog entry for GroupPlanner.

    Full template definitions are handled by the template system.
    This provides just enough info for GroupPlanner to select templates.

    Attributes:
        template_id: Unique template identifier.
        name: Human-readable template name.
        compatible_lanes: List of lanes this template is compatible with.
        tags: List of tags for categorization.
        description: Optional template description.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: str
    name: str
    compatible_lanes: list[LaneKind] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    description: str = ""


class TemplateCatalog(BaseModel):
    """Lightweight template catalog for GroupPlanner validation.

    Provides template_id existence checks and lane compatibility filtering.

    Attributes:
        schema_version: Catalog schema version.
        entries: List of template catalog entries.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "template-catalog.v1"
    entries: list[TemplateCatalogEntry] = Field(default_factory=list)

    def has_template(self, template_id: str) -> bool:
        """Check if template_id exists in catalog.

        Args:
            template_id: Template identifier to check.

        Returns:
            True if template exists in catalog.
        """
        return any(e.template_id == template_id for e in self.entries)

    def get_entry(self, template_id: str) -> TemplateCatalogEntry | None:
        """Get catalog entry by template_id.

        Args:
            template_id: Template identifier to lookup.

        Returns:
            TemplateCatalogEntry if found, None otherwise.
        """
        return next((e for e in self.entries if e.template_id == template_id), None)

    def list_by_lane(self, lane: LaneKind) -> list[TemplateCatalogEntry]:
        """List all templates compatible with given lane.

        Args:
            lane: Lane to filter by.

        Returns:
            List of compatible TemplateCatalogEntry instances.
        """
        return [e for e in self.entries if lane in e.compatible_lanes]


def build_template_catalog() -> TemplateCatalog:
    """Build TemplateCatalog from GroupTemplateRegistry.

    Converts registered group templates into lightweight TemplateCatalogEntry
    for GroupPlanner agent consumption.

    The mapping is:
    - template_id → template_id (direct)
    - name → name (direct)
    - template_type → compatible_lanes (1:1 mapping for BASE/RHYTHM/ACCENT)
    - tags → tags (direct)

    Note: TRANSITION and SPECIAL templates are currently excluded from the catalog
    as they are not assigned to standard lanes in the GroupPlanner v3.3 spec.

    Returns:
        TemplateCatalog with all BASE, RHYTHM, and ACCENT templates.

    Example:
        >>> from twinklr.core.sequencer.templates.group import load_builtin_group_templates
        >>> load_builtin_group_templates()
        >>> catalog = build_template_catalog()
        >>> len(catalog.entries)
        61  # BASE (14) + RHYTHM (26) + ACCENT (21)
    """
    infos = REGISTRY.list_all()

    # Map template types to lanes (only BASE, RHYTHM, ACCENT have corresponding lanes)
    type_to_lane = {
        GroupTemplateType.BASE: LaneKind.BASE,
        GroupTemplateType.RHYTHM: LaneKind.RHYTHM,
        GroupTemplateType.ACCENT: LaneKind.ACCENT,
        # TRANSITION and SPECIAL are not assigned to lanes in GroupPlanner v3.3
    }

    entries = []
    for info in infos:
        # Skip templates without lane mapping
        if info.template_type not in type_to_lane:
            continue

        entries.append(
            TemplateCatalogEntry(
                template_id=info.template_id,
                name=info.name,
                compatible_lanes=[type_to_lane[info.template_type]],
                tags=list(info.tags),
                description="",  # Can be populated from template if needed
            )
        )

    return TemplateCatalog(entries=entries)
