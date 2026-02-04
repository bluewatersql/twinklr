"""Display graph models.

Models for defining display topology and group configurations.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field


class GroupPosition(BaseModel):
    """Normalized spatial position for a display group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    z: float = Field(default=0.0, ge=0.0, le=1.0)
    zone: str | None = None


class DisplayGroup(BaseModel):
    """Single display group definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    role: str
    display_name: str

    position: GroupPosition | None = None
    capabilities: list[str] = Field(default_factory=list)
    fixture_count: int = Field(default=1, ge=1)


class DisplayGraph(BaseModel):
    """Complete display configuration with group-to-role mapping.

    Provides groups_by_role computed property for role expansion.
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
    "GroupPosition",
]
