"""
ROLE_POSE geometry resolver (MVP).

Responsibilities:
- Resolve base pan/tilt DMX per fixture based on the fixture's role binding
- Deterministic, repeat-safe, side-effect free
- No movement logic, no time logic, no curves

Inject:
- pan_pose_table: dict[str,int]
- tilt_pose_table: dict[str,int]
"""

from __future__ import annotations

from blinkb0t.core.domains.sequencer.moving_heads.models.geometry import RolePoseGeometry


class RolePoseGeometryResolver:
    def __init__(
        self,
        pan_pose_table: dict[str, int],
        tilt_pose_table: dict[str, int],
        default_pan_pose: str = "CENTER",
        default_tilt_pose: str = "HORIZON",
    ):
        self.pan_pose_table = pan_pose_table
        self.tilt_pose_table = tilt_pose_table
        self.default_pan_pose = default_pan_pose
        self.default_tilt_pose = default_tilt_pose

    def resolve_base_pose(
        self,
        rig: object,
        fixtures: list[str],
        geometry: RolePoseGeometry,
    ) -> dict[str, tuple[int, int]]:
        """Return {fixture_id: (pan_dmx, tilt_dmx)} for each fixture."""

        role_bindings = getattr(rig, "role_bindings", {}) or {}

        tilt_token = geometry.tilt_pose or self.default_tilt_pose
        tilt_dmx = self._lookup_tilt(tilt_token)

        out: dict[str, tuple[int, int]] = {}
        for fx in fixtures:
            role = role_bindings.get(fx)
            pan_token = geometry.pan_pose_by_role.get(role, None) if role else None
            if not pan_token:
                pan_token = self.default_pan_pose
            pan_dmx = self._lookup_pan(pan_token)
            out[fx] = (pan_dmx, tilt_dmx)
        return out

    def _lookup_pan(self, token: str) -> int:
        if token not in self.pan_pose_table:
            raise ValueError(f"Unknown pan pose token: {token!r}")
        v = int(self.pan_pose_table[token])
        if v < 0 or v > 255:
            raise ValueError(f"Pan DMX out of range for token {token!r}: {v}")
        return v

    def _lookup_tilt(self, token: str) -> int:
        if token not in self.tilt_pose_table:
            raise ValueError(f"Unknown tilt pose token: {token!r}")
        v = int(self.tilt_pose_table[token])
        if v < 0 or v > 255:
            raise ValueError(f"Tilt DMX out of range for token {token!r}: {v}")
        return v
