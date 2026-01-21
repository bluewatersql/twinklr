"""
Sequencing v2 geometry models.

Option A (MVP): ROLE_POSE geometry
- Deterministic base pan/tilt per fixture derived from fixture role
- No time logic, no curves, no movement coupling
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from blinkb0t.core.domains.sequencing.libraries.moving_heads.geometry import GeometryID


class GeometryType(BaseModel):
    type: Literal["GEOMETRY_ID"] = "GEOMETRY_ID"
    geometry_id: GeometryID
    geometry_params: dict[str, Any] = Field(default_factory=dict)


class RolePoseGeometry(BaseModel):
    """ROLE_POSE geometry spec.

    pan_pose_by_role maps a *role name* (from RigProfile.role_bindings) to a pose token
    understood by the resolver's pan_pose_table.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["ROLE_POSE"] = "ROLE_POSE"

    pan_pose_by_role: dict[str, str] = Field(
        ...,
        description="Map from role name -> pan pose token (e.g. OUTER_LEFT -> WIDE_LEFT).",
        min_length=1,
    )

    tilt_pose: str = Field(
        "HORIZON",
        description="Tilt pose token understood by the resolver's tilt_pose_table.",
        min_length=1,
    )

    @model_validator(mode="after")
    def _validate_non_empty(self) -> RolePoseGeometry:
        if not self.pan_pose_by_role:
            raise ValueError("pan_pose_by_role must not be empty")
        return self


Geometry = Annotated[
    RolePoseGeometry | GeometryType,
    Field(discriminator="type"),
]
