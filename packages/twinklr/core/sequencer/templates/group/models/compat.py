"""Migration bridge: DisplayGraph -> ChoreographyGraph + XLightsMapping.

Factory functions that convert existing ``DisplayGraph`` instances into
the new ``ChoreographyGraph`` and ``XLightsMapping`` models.  Used during
the phased migration; will be removed once DisplayGraph is fully replaced.
"""

from __future__ import annotations

from twinklr.core.sequencer.display.xlights_mapping import (
    XLightsGroupMapping,
    XLightsMapping,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.display import DisplayGraph


def choreo_graph_from_display_graph(dg: DisplayGraph) -> ChoreographyGraph:
    """Convert a DisplayGraph into a ChoreographyGraph.

    Maps each ``DisplayGroup`` to a ``ChoreoGroup``, preserving physical
    metadata and spatial position.  Drops xLights-specific fields
    (``display_name``, ``element_type``, ``parent_group_id``).

    Tags are empty in the converted graph — they must be added manually
    or via layout parsing.

    Args:
        dg: Source DisplayGraph.

    Returns:
        Equivalent ChoreographyGraph.
    """
    groups: list[ChoreoGroup] = []
    for g in dg.groups:
        groups.append(
            ChoreoGroup(
                id=g.group_id,
                role=g.role,
                element_kind=g.element_kind,
                prominence=g.prominence,
                position=g.position,
                arrangement=g.arrangement,
                fixture_count=g.fixture_count,
                pixel_fraction=g.pixel_fraction,
                tags=[],
            )
        )

    return ChoreographyGraph(
        graph_id=dg.display_id,
        groups=groups,
    )


def xlights_mapping_from_display_graph(dg: DisplayGraph) -> XLightsMapping:
    """Convert a DisplayGraph into an XLightsMapping.

    Creates a 1:1 mapping from ``group_id`` to ``display_name`` for each
    ``DisplayGroup``.  This is the v0 mapping — tag splits and model-level
    fallback are not populated.

    Args:
        dg: Source DisplayGraph.

    Returns:
        XLightsMapping with one entry per DisplayGroup.
    """
    entries: list[XLightsGroupMapping] = []
    for g in dg.groups:
        entries.append(
            XLightsGroupMapping(
                choreo_id=g.group_id,
                group_name=g.display_name,
            )
        )

    return XLightsMapping(entries=entries)


__all__ = [
    "choreo_graph_from_display_graph",
    "xlights_mapping_from_display_graph",
]
