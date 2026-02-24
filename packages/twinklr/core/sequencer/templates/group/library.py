"""Group template metadata models.

Provides ``TemplateInfo`` for lightweight template metadata used by
catalog, context_shaping, and AffinityScorer.
"""

from __future__ import annotations

from pydantic import ConfigDict

from twinklr.core.sequencer.templates.shared.registry import (
    BaseTemplateInfo,
    TemplateNotFoundError,
    normalize_key,
)
from twinklr.core.sequencer.vocabulary import GroupTemplateType, GroupVisualIntent, LaneKind

__all__ = [
    "TemplateInfo",
    "TemplateNotFoundError",
    "normalize_key",
]


class TemplateInfo(BaseTemplateInfo):
    """Lightweight metadata for group templates.

    Used by TemplateCatalog, AffinityScorer, and context_shaping for
    planner/judge prompt construction.

    Attributes:
        template_id: Unique template identifier.
        version: Template version string.
        name: Human-readable template name.
        template_type: Template type (lane classification).
        visual_intent: Visual intent classification.
        tags: Tuple of tags for categorization.
        description: Optional template description.
        compatible_lanes: Derived property for lane compatibility.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_type: GroupTemplateType
    visual_intent: GroupVisualIntent
    description: str = ""

    @property
    def compatible_lanes(self) -> list[LaneKind]:
        """Derive compatible lanes from template_type.

        Returns:
            List of lane kinds this template can be used in.
            Empty list for TRANSITION and SPECIAL types.
        """
        type_to_lane = {
            GroupTemplateType.BASE: LaneKind.BASE,
            GroupTemplateType.RHYTHM: LaneKind.RHYTHM,
            GroupTemplateType.ACCENT: LaneKind.ACCENT,
        }
        lane = type_to_lane.get(self.template_type)
        return [lane] if lane else []
