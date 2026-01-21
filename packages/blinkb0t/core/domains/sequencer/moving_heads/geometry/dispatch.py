from __future__ import annotations

from blinkb0t.core.domains.sequencer.moving_heads.geometry.geometry_id import (
    GeometryIdResolver,
)
from blinkb0t.core.domains.sequencer.moving_heads.geometry.role_pose import (
    RolePoseGeometryResolver,
)
from blinkb0t.core.domains.sequencer.moving_heads.models.geometry import (
    GeometryType,
    RolePoseGeometry,
)


class GeometryDispatchResolver:
    def __init__(
        self,
        role_pose_resolver: RolePoseGeometryResolver,
        geometry_id_resolver: GeometryIdResolver,
    ):
        self.role_pose_resolver = role_pose_resolver
        self.geometry_id_resolver = geometry_id_resolver

    def resolve_base_pose(self, rig: object, fixtures: list[str], geometry):
        if isinstance(geometry, RolePoseGeometry):
            return self.role_pose_resolver.resolve_base_pose(
                rig=rig, fixtures=fixtures, geometry=geometry
            )
        if isinstance(geometry, GeometryType):
            return self.geometry_id_resolver.resolve_base_pose(
                rig=rig, fixtures=fixtures, geometry=geometry
            )
        raise ValueError(f"Unsupported geometry spec: {type(geometry).__name__}")
