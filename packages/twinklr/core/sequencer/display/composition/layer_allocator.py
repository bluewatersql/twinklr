"""Layer allocator: maps LaneKind to xLights layer indices.

Also provides blend mode mapping from GPBlendMode to xLights
T_CHOICE_LayerMethod values.
"""

from __future__ import annotations

from twinklr.core.sequencer.vocabulary import GPBlendMode, LaneKind

# Default lane-to-layer mapping
_DEFAULT_LAYER_MAP: dict[LaneKind, int] = {
    LaneKind.BASE: 0,
    LaneKind.RHYTHM: 1,
    LaneKind.ACCENT: 2,
}

# GPBlendMode → xLights T_CHOICE_LayerMethod
_BLEND_MODE_MAP: dict[GPBlendMode, str] = {
    GPBlendMode.ADD: "Normal",
    GPBlendMode.MAX: "Max",
    GPBlendMode.ALPHA_OVER: "1 reveals 2",
}


class LayerAllocator:
    """Allocates xLights layer indices for lanes.

    Static mapping — each lane gets a fixed layer index.
    BASE is always the bottom layer, RHYTHM in the middle,
    and ACCENT on top.
    """

    def __init__(
        self,
        layer_map: dict[LaneKind, int] | None = None,
    ) -> None:
        """Initialize the allocator.

        Args:
            layer_map: Custom lane-to-layer mapping. Defaults to
                BASE=0, RHYTHM=1, ACCENT=2.
        """
        self._layer_map = layer_map or dict(_DEFAULT_LAYER_MAP)

    def allocate(self, lane: LaneKind) -> int:
        """Get the layer index for a lane.

        Args:
            lane: Lane kind (BASE/RHYTHM/ACCENT).

        Returns:
            xLights layer index (0-based).
        """
        return self._layer_map.get(lane, 0)

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
        """Maximum layer index that may be allocated."""
        return max(self._layer_map.values()) if self._layer_map else 0


__all__ = [
    "LayerAllocator",
]
