"""Group template catalog builder and models.

Provides lightweight catalog interface for GroupPlanner agent.
Uses TemplateInfo directly (no duplication).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.templates.group.library import TemplateInfo
from twinklr.core.sequencer.vocabulary import GroupTemplateType, LaneKind

if TYPE_CHECKING:
    from twinklr.core.sequencer.templates.group.store import TemplateStore

_LANE_ASSIGNED_TYPES = {
    GroupTemplateType.BASE,
    GroupTemplateType.RHYTHM,
    GroupTemplateType.ACCENT,
}


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


def build_template_catalog_from_store(store: TemplateStore) -> TemplateCatalog:
    """Build TemplateCatalog from a TemplateStore.

    Converts TemplateStoreEntry instances to TemplateInfo for compatibility
    with existing planner/agent infrastructure.

    Args:
        store: TemplateStore loaded from JSON index.

    Returns:
        TemplateCatalog with lane-assigned templates (BASE, RHYTHM, ACCENT).
    """
    entries: list[TemplateInfo] = []
    for e in store.entries:
        if e.template_type not in _LANE_ASSIGNED_TYPES:
            continue
        entries.append(
            TemplateInfo(
                template_id=e.recipe_id,
                version="1.0.0",
                name=e.name,
                template_type=e.template_type,
                visual_intent=e.visual_intent,
                tags=e.tags,
            )
        )
    return TemplateCatalog(entries=entries)
