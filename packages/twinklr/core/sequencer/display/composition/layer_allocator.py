"""Layer allocator: maps LaneKind to xLights layer indices.

Also provides blend mode mapping from GPBlendMode to xLights
T_CHOICE_LayerMethod values.

Supports:
- **Multi-depth layers**: When a template emits effects at multiple
  ``VisualDepth`` levels, each ``(lane, depth)`` pair gets its own
  xLights layer via :meth:`allocate_sub_layer`.
- **Asset overlay layers**: When a placement has resolved assets, the
  procedural effect goes on the base layer and the Pictures overlay
  goes on the next layer up.
"""

from __future__ import annotations

from twinklr.core.sequencer.vocabulary import GPBlendMode, LaneKind, VisualDepth

# Default lane-to-base-layer mapping.  Each lane is given a block of
# layers large enough for up to 5 visual depths + 1 overlay layer.
_LANE_BLOCK_SIZE = 6  # 5 depths + 1 overlay

_DEFAULT_LANE_BASE: dict[LaneKind, int] = {
    LaneKind.BASE: 0 * _LANE_BLOCK_SIZE,  # layers 0-5
    LaneKind.RHYTHM: 1 * _LANE_BLOCK_SIZE,  # layers 6-11
    LaneKind.ACCENT: 2 * _LANE_BLOCK_SIZE,  # layers 12-17
}

# VisualDepth → offset within the lane's block.
# Ordered from back to front so xLights stacks them correctly:
# BACKGROUND is rendered first (lowest layer), ACCENT on top.
_DEPTH_OFFSET: dict[VisualDepth, int] = {
    VisualDepth.BACKGROUND: 0,
    VisualDepth.MIDGROUND: 1,
    VisualDepth.FOREGROUND: 2,
    VisualDepth.ACCENT: 3,
    VisualDepth.TEXTURE: 4,
}

# GPBlendMode → xLights T_CHOICE_LayerMethod
_BLEND_MODE_MAP: dict[GPBlendMode, str] = {
    GPBlendMode.ADD: "Normal",
    GPBlendMode.MAX: "Max",
    GPBlendMode.ALPHA_OVER: "1 reveals 2",
}

# Backward-compatible simple lane map (for callers that haven't migrated)
_COMPAT_LAYER_MAP: dict[LaneKind, int] = {
    LaneKind.BASE: 0,
    LaneKind.RHYTHM: 2,
    LaneKind.ACCENT: 4,
}


class LayerAllocator:
    """Allocates xLights layer indices for lanes and visual depths.

    Supports two allocation strategies:

    1. **Simple** (``allocate``): backward-compatible single layer per
       lane.  Used for code paths that haven't migrated to the
       template compiler yet.
    2. **Sub-layer** (``allocate_sub_layer``): one layer per
       ``(lane, VisualDepth)`` pair.  Used by the template compiler
       path where templates emit multiple effects at different depths.

    The sub-layer strategy reserves a block of 6 layers per lane
    (5 visual depths + 1 asset overlay)::

        BASE:   layers 0-5   (BG=0, MG=1, FG=2, ACC=3, TEX=4, overlay=5)
        RHYTHM: layers 6-11
        ACCENT: layers 12-17
    """

    def __init__(
        self,
        layer_map: dict[LaneKind, int] | None = None,
    ) -> None:
        """Initialize the allocator.

        Args:
            layer_map: Custom lane-to-layer mapping for simple allocation.
                Defaults to BASE=0, RHYTHM=2, ACCENT=4.
        """
        self._layer_map = layer_map or dict(_COMPAT_LAYER_MAP)

    def allocate(self, lane: LaneKind) -> int:
        """Get the simple procedural layer index for a lane.

        Backward-compatible: returns a single layer per lane.

        Args:
            lane: Lane kind (BASE/RHYTHM/ACCENT).

        Returns:
            xLights layer index (0-based).
        """
        return self._layer_map.get(lane, 0)

    def allocate_sub_layer(
        self,
        lane: LaneKind,
        depth: VisualDepth,
    ) -> int:
        """Get the layer index for a ``(lane, depth)`` pair.

        Each ``(lane, VisualDepth)`` combination maps to a unique
        xLights layer, allowing multi-depth template output.

        Args:
            lane: Lane kind (BASE/RHYTHM/ACCENT).
            depth: Visual depth from the LayerRecipe.

        Returns:
            xLights layer index (0-based).
        """
        base = _DEFAULT_LANE_BASE.get(lane, 0)
        offset = _DEPTH_OFFSET.get(depth, 0)
        return base + offset

    def allocate_overlay(self, lane: LaneKind) -> int:
        """Get the asset overlay layer index for a lane.

        Uses the sub-layer block: overlay is always the last slot
        in the lane's block.

        Args:
            lane: Lane kind (BASE/RHYTHM/ACCENT).

        Returns:
            xLights layer index (0-based) for the asset overlay.
        """
        base = _DEFAULT_LANE_BASE.get(lane, 0)
        return base + _LANE_BLOCK_SIZE - 1

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
        max_base = max(_DEFAULT_LANE_BASE.values()) if _DEFAULT_LANE_BASE else 0
        return max_base + _LANE_BLOCK_SIZE - 1


__all__ = [
    "LayerAllocator",
]
