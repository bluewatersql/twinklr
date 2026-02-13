"""Display graph models.

Models for defining display topology and group configurations.

xLights supports two kinds of targetable elements:
- **Individual models** (e.g., "Arch 1") — a single physical element.
- **Model groups** (e.g., "61 - Arches") — a set of models sequenced as one.

Both use ``type="model"`` in the XSQ XML; the distinction is semantic.

Each ``DisplayGroup`` entry maps 1:1 to an xLights element. The plan
references these entries by ``group_id``, and the ``TargetResolver``
maps that to the xLights ``display_name``.

In V0 (group-based), most entries will be ``MODEL_GROUP`` — the plan
targets groups like ``ARCHES`` and the renderer places effects on the
corresponding xLights group element (``"61 - Arches"``).

For per-model targeting (future), entries can use ``element_type=MODEL``
to target individual models within a group (e.g., odds/evens with
different effect configs).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, computed_field


class ElementType(str, Enum):
    """xLights element targeting type.

    Determines how effects are placed in the sequence:
    - MODEL: Effect targets a single physical model.
    - MODEL_GROUP: Effect targets a group; xLights renders across all
      member models as a single canvas.
    """

    MODEL = "model"
    MODEL_GROUP = "model_group"


class GroupPosition(BaseModel):
    """Normalized spatial position for a display group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    z: float = Field(default=0.0, ge=0.0, le=1.0)
    zone: str | None = None


class DisplayGroup(BaseModel):
    """Single display group definition.

    Represents a targetable xLights element — either an individual model
    or a model group. Each entry maps 1:1 to an element that the plan
    can target by ``group_id``.

    The ``display_name`` must match the exact xLights element name
    (e.g., ``"61 - Arches"``) since groups cannot be created in the
    sequence file alone — they must already exist in the xLights layout.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    role: str
    display_name: str
    element_type: ElementType = Field(
        default=ElementType.MODEL_GROUP,
        description="Whether this entry targets a model group or individual model",
    )

    position: GroupPosition | None = None
    capabilities: list[str] = Field(default_factory=list)
    fixture_count: int = Field(default=1, ge=1)


class DisplayGraph(BaseModel):
    """Complete display configuration with group-to-role mapping.

    Each entry in ``groups`` maps 1:1 to an xLights element. The
    mapping from ``group_id`` to ``display_name`` is provided
    externally (e.g., from a fixture config or user mapping file).

    The renderer does NOT create or infer groups — the xLights layout
    defines what groups exist, and this graph mirrors that.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "display-graph.v1"
    display_id: str
    display_name: str
    groups: list[DisplayGroup] = Field(min_length=1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def groups_by_role(self) -> dict[str, list[str]]:
        """Map role -> list of group_ids."""
        result: dict[str, list[str]] = {}
        for g in self.groups:
            result.setdefault(g.role, []).append(g.group_id)
        return result

    def get_group(self, group_id: str) -> DisplayGroup | None:
        """Get group by ID, or None if not found."""
        return next((g for g in self.groups if g.group_id == group_id), None)


__all__ = [
    "DisplayGraph",
    "DisplayGroup",
    "ElementType",
    "GroupPosition",
]
