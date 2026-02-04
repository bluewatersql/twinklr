"""Group template catalog builder and models.

Provides lightweight catalog interface for GroupPlanner agent.
Uses TemplateInfo directly (no duplication).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.templates.group.library import REGISTRY, TemplateInfo
from twinklr.core.sequencer.vocabulary import GroupTemplateType, LaneKind


class TemplateCatalog(BaseModel):
    """Lightweight template catalog for GroupPlanner validation.

    Provides template_id existence checks and lane compatibility filtering.
    Uses TemplateInfo directly (no duplication).

    Attributes:
        schema_version: Catalog schema version.
        entries: List of template info entries.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "template-catalog.v1"
    entries: list[TemplateInfo] = Field(default_factory=list)

    def has_template(self, template_id: str) -> bool:
        """Check if template_id exists in catalog.

        Args:
            template_id: Template identifier to check.

        Returns:
            True if template exists in catalog.
        """
        return any(e.template_id == template_id for e in self.entries)

    def get_entry(self, template_id: str) -> TemplateInfo | None:
        """Get catalog entry by template_id.

        Args:
            template_id: Template identifier to lookup.

        Returns:
            TemplateInfo if found, None otherwise.
        """
        return next((e for e in self.entries if e.template_id == template_id), None)

    def list_by_lane(self, lane: LaneKind) -> list[TemplateInfo]:
        """List all templates compatible with given lane.

        Args:
            lane: Lane to filter by.

        Returns:
            List of compatible TemplateInfo instances.
        """
        return [e for e in self.entries if lane in e.compatible_lanes]


def build_template_catalog() -> TemplateCatalog:
    """Build TemplateCatalog from GroupTemplateRegistry.

    Filters registry templates to only include those with lane assignments
    (BASE, RHYTHM, ACCENT). Uses TemplateInfo directly without duplication.

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

    # Filter to only templates with lane assignments
    lane_assigned_types = {
        GroupTemplateType.BASE,
        GroupTemplateType.RHYTHM,
        GroupTemplateType.ACCENT,
    }

    entries = [info for info in infos if info.template_type in lane_assigned_types]

    return TemplateCatalog(entries=entries)
