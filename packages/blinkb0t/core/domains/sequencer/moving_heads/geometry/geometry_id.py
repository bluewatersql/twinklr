from __future__ import annotations

from collections.abc import Callable
from typing import Any
import random

from blinkb0t.core.domains.sequencer.moving_heads.geometry.role_pose import (
    RolePoseGeometryResolver,
)
from blinkb0t.core.domains.sequencer.moving_heads.models.geometry import (
    GeometryIdSpec,
    RolePoseGeometrySpec,
)
from blinkb0t.core.domains.sequencing.libraries.moving_heads.geometry import GeometryID

GeometryTransform = Callable[[object, list[str], dict[str, Any]], dict[str, tuple[int, int]]]


class GeometryIdResolver:
    def __init__(
        self,
        default_tilt_dmx: int = 128,
        role_pose_resolver: RolePoseGeometryResolver | None = None,
    ):
        self.default_tilt_dmx = default_tilt_dmx
        self.role_pose_resolver = role_pose_resolver
        self._registry: dict[GeometryID, GeometryTransform] = {
            GeometryID.AUDIENCE_SCAN_ASYM: self._audience_scan_asym,
            GeometryID.CHEVRON_V: self._chevron_v,
            GeometryID.ROLE_POSE_TILT_BIAS: self._role_pose_tilt_bias,
            GeometryID.SCATTERED_CHAOS: self._scattered_chaos,
            GeometryID.TILT_BIAS_BY_GROUP: self._tilt_bias_by_group,
        }

    def resolve_base_pose(
        self,
        rig: object,
        fixtures: list[str],
        geometry: GeometryIdSpec,
    ) -> dict[str, tuple[int, int]]:
        handler = self._registry.get(geometry.geometry_id)
        if handler is None:
            raise ValueError(f"Unsupported geometry_id: {geometry.geometry_id!r}")
        return handler(rig, fixtures, dict(geometry.geometry_params or {}))

    def _audience_scan_asym(
        self,
        rig: object,
        fixtures: list[str],
        params: dict[str, Any],
    ) -> dict[str, tuple[int, int]]:
        order_name = params.get("order", "LEFT_TO_RIGHT")
        rig_orders = getattr(rig, "orders", {}) or {}
        ordered = list(rig_orders.get(order_name, fixtures))
        ordered = [fx for fx in ordered if fx in fixtures]
        if not ordered:
            ordered = list(fixtures)

        tilt_dmx = int(params.get("tilt_dmx", self.default_tilt_dmx))
        if tilt_dmx < 0 or tilt_dmx > 255:
            raise ValueError(f"tilt_dmx out of range: {tilt_dmx}")

        pan_positions = params.get("pan_positions")
        if pan_positions is not None:
            if len(pan_positions) < len(ordered):
                raise ValueError("pan_positions must cover all fixtures in order")
            pan_values = [int(v) for v in pan_positions[: len(ordered)]]
        else:
            pan_start = int(params.get("pan_start_dmx", 96))
            pan_end = int(params.get("pan_end_dmx", 176))
            if pan_start < 0 or pan_start > 255 or pan_end < 0 or pan_end > 255:
                raise ValueError("pan_start_dmx/pan_end_dmx must be within 0..255")
            if len(ordered) == 1:
                pan_values = [pan_start]
            else:
                span = pan_end - pan_start
                pan_values = [
                    round(pan_start + (span * i / (len(ordered) - 1))) for i in range(len(ordered))
                ]

        for v in pan_values:
            if v < 0 or v > 255:
                raise ValueError(f"pan dmx out of range: {v}")

        poses: dict[str, tuple[int, int]] = {}
        for fx, pan_dmx in zip(ordered, pan_values, strict=False):
            poses[fx] = (pan_dmx, tilt_dmx)

        fallback_pan = pan_values[0] if pan_values else 128
        for fx in fixtures:
            poses.setdefault(fx, (fallback_pan, tilt_dmx))

        return poses

    def _role_pose_tilt_bias(
        self,
        rig: object,
        fixtures: list[str],
        params: dict[str, Any],
    ) -> dict[str, tuple[int, int]]:
        if self.role_pose_resolver is None:
            raise ValueError("role_pose_resolver is required for ROLE_POSE_TILT_BIAS")

        pan_pose_by_role = params.get("pan_pose_by_role")
        if not pan_pose_by_role:
            raise ValueError("pan_pose_by_role is required for ROLE_POSE_TILT_BIAS")

        tilt_pose = params.get("tilt_pose", "HORIZON")
        base_pose = self.role_pose_resolver.resolve_base_pose(
            rig=rig,
            fixtures=fixtures,
            geometry=RolePoseGeometrySpec(
                pan_pose_by_role=dict(pan_pose_by_role),
                tilt_pose=str(tilt_pose),
            ),
        )

        tilt_bias_by_group = params.get("tilt_bias_by_group", {})
        if not isinstance(tilt_bias_by_group, dict):
            raise ValueError("tilt_bias_by_group must be a mapping of group->bias")

        biases: dict[str, int] = {}
        for group_name, bias in tilt_bias_by_group.items():
            members = list(getattr(rig, "groups", {}).get(group_name, []))
            for fx in members:
                biases[fx] = int(bias)

        poses: dict[str, tuple[int, int]] = {}
        for fx in fixtures:
            pan_dmx, tilt_dmx = base_pose[fx]
            tilt_out = int(tilt_dmx) + int(biases.get(fx, 0))
            if tilt_out < 0 or tilt_out > 255:
                raise ValueError(f"tilt dmx out of range: {tilt_out}")
            poses[fx] = (int(pan_dmx), tilt_out)

        return poses

    def _chevron_v(
        self,
        rig: object,
        fixtures: list[str],
        params: dict[str, Any],
    ) -> dict[str, tuple[int, int]]:
        order_name = params.get("order", "LEFT_TO_RIGHT")
        rig_orders = getattr(rig, "orders", {}) or {}
        ordered = list(rig_orders.get(order_name, fixtures))
        ordered = [fx for fx in ordered if fx in fixtures]
        if not ordered:
            ordered = list(fixtures)

        pan_start = int(params.get("pan_start_dmx", 96))
        pan_end = int(params.get("pan_end_dmx", 176))
        if pan_start < 0 or pan_start > 255 or pan_end < 0 or pan_end > 255:
            raise ValueError("pan_start_dmx/pan_end_dmx must be within 0..255")

        if len(ordered) == 1:
            pan_values = [pan_start]
        else:
            span = pan_end - pan_start
            pan_values = [
                round(pan_start + (span * i / (len(ordered) - 1))) for i in range(len(ordered))
            ]

        tilt_base = int(params.get("tilt_base_dmx", self.default_tilt_dmx))
        tilt_inner_bias = int(params.get("tilt_inner_bias_dmx", 16))
        tilt_outer_bias = int(params.get("tilt_outer_bias_dmx", 0))

        if tilt_base < 0 or tilt_base > 255:
            raise ValueError(f"tilt_base_dmx out of range: {tilt_base}")

        n = len(ordered)
        inner_indices = {n // 2} if n % 2 == 1 else {n // 2 - 1, n // 2}

        poses: dict[str, tuple[int, int]] = {}
        for i, fx in enumerate(ordered):
            bias = tilt_inner_bias if i in inner_indices else tilt_outer_bias
            tilt_dmx = tilt_base + bias
            if tilt_dmx < 0 or tilt_dmx > 255:
                raise ValueError(f"tilt dmx out of range: {tilt_dmx}")
            poses[fx] = (pan_values[i], tilt_dmx)

        fallback = poses[ordered[0]]
        for fx in fixtures:
            poses.setdefault(fx, fallback)

        return poses

    def _scattered_chaos(
        self,
        rig: object,
        fixtures: list[str],
        params: dict[str, Any],
    ) -> dict[str, tuple[int, int]]:
        seed = int(params.get("seed", 42))
        rng = random.Random(seed)

        pan_center = int(params.get("pan_center_dmx", 128))
        pan_spread = int(params.get("pan_spread_dmx", 40))
        tilt_center = int(params.get("tilt_center_dmx", self.default_tilt_dmx))
        tilt_spread = int(params.get("tilt_spread_dmx", 20))

        for val in [pan_center, tilt_center]:
            if val < 0 or val > 255:
                raise ValueError("pan_center_dmx/tilt_center_dmx must be within 0..255")
        if pan_spread < 0 or tilt_spread < 0:
            raise ValueError("pan_spread_dmx/tilt_spread_dmx must be >= 0")

        poses: dict[str, tuple[int, int]] = {}
        for fx in fixtures:
            pan_dmx = pan_center + rng.randint(-pan_spread, pan_spread)
            tilt_dmx = tilt_center + rng.randint(-tilt_spread, tilt_spread)
            pan_dmx = max(0, min(255, pan_dmx))
            tilt_dmx = max(0, min(255, tilt_dmx))
            poses[fx] = (pan_dmx, tilt_dmx)

        return poses

    def _tilt_bias_by_group(
        self,
        rig: object,
        fixtures: list[str],
        params: dict[str, Any],
    ) -> dict[str, tuple[int, int]]:
        pan_dmx = int(params.get("pan_dmx", 128))
        tilt_base_dmx = int(params.get("tilt_base_dmx", self.default_tilt_dmx))
        if pan_dmx < 0 or pan_dmx > 255:
            raise ValueError(f"pan_dmx out of range: {pan_dmx}")
        if tilt_base_dmx < 0 or tilt_base_dmx > 255:
            raise ValueError(f"tilt_base_dmx out of range: {tilt_base_dmx}")

        tilt_bias_by_group = params.get("tilt_bias_by_group", {})
        if not isinstance(tilt_bias_by_group, dict):
            raise ValueError("tilt_bias_by_group must be a mapping of group->bias")

        biases: dict[str, int] = {}
        for group_name, bias in tilt_bias_by_group.items():
            members = list(getattr(rig, "groups", {}).get(group_name, []))
            for fx in members:
                biases[fx] = int(bias)

        poses: dict[str, tuple[int, int]] = {}
        for fx in fixtures:
            tilt_out = tilt_base_dmx + int(biases.get(fx, 0))
            if tilt_out < 0 or tilt_out > 255:
                raise ValueError(f"tilt dmx out of range: {tilt_out}")
            poses[fx] = (pan_dmx, tilt_out)

        return poses
