"""Layer allocator: maps LaneKind to xLights layer indices.

Also provides blend mode mapping from GPBlendMode to xLights
T_CHOICE_LayerMethod values.

Supports dual-layer allocation for asset overlays: when a placement
has resolved assets, the procedural effect goes on the base layer
and the Pictures overlay goes on the next layer up.
"""

from __future__ import annotations

from twinklr.core.sequencer.vocabulary import GPBlendMode, LaneKind

# Default lane-to-layer mapping (procedural layers only)
_DEFAULT_LAYER_MAP: dict[LaneKind, int] = {
    LaneKind.BASE: 0,
    LaneKind.RHYTHM: 2,
    LaneKind.ACCENT: 4,
}

# GPBlendMode → xLights T_CHOICE_LayerMethod
_BLEND_MODE_MAP: dict[GPBlendMode, str] = {
    GPBlendMode.ADD: "Normal",
    GPBlendMode.MAX: "Max",
    GPBlendMode.ALPHA_OVER: "1 reveals 2",
}


class LayerAllocator:
    """Allocates xLights layer indices for lanes.

    Each lane gets a pair of layer indices: one for the procedural
    effect and one for an optional asset overlay (Pictures).

    Default mapping with asset overlay support::

        BASE:   procedural=0, overlay=1
        RHYTHM: procedural=2, overlay=3
        ACCENT: procedural=4, overlay=5

    When no placements have assets, the overlay layers remain empty
    and xLights ignores them.
    """

    def __init__(
        self,
        layer_map: dict[LaneKind, int] | None = None,
    ) -> None:
        """Initialize the allocator.

        Args:
            layer_map: Custom lane-to-layer mapping for procedural layers.
                Overlay layers are always procedural_index + 1.
                Defaults to BASE=0, RHYTHM=2, ACCENT=4.
        """
        self._layer_map = layer_map or dict(_DEFAULT_LAYER_MAP)

    def allocate(self, lane: LaneKind) -> int:
        """Get the procedural layer index for a lane.

        Args:
            lane: Lane kind (BASE/RHYTHM/ACCENT).

        Returns:
            xLights layer index (0-based) for the procedural effect.
        """
        return self._layer_map.get(lane, 0)

    def allocate_overlay(self, lane: LaneKind) -> int:
        """Get the asset overlay layer index for a lane.

        Always one above the procedural layer for the same lane.

        Args:
            lane: Lane kind (BASE/RHYTHM/ACCENT).

        Returns:
            xLights layer index (0-based) for the asset overlay.
        """
        return self.allocate(lane) + 1

    @staticmethod
    def resolve_blend_mode(blend_mode: GPBlendMode) -> str:
        """Map a GPBlendMode to an xLights layer method string.

        Args:
            blend_mode: Planning blend mode.

        Returns:
            xLights T_CHOICE_LayerMethod value.
        """
        return _BLEND_MODE_MAP.get(blend_mode, "Normal")

    @property
    def max_layer_index(self) -> int:
        """Maximum layer index that may be allocated (including overlays)."""
        if not self._layer_map:
            return 0
        return max(self._layer_map.values()) + 1


__all__ = [
    "LayerAllocator",
]
