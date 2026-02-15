"""Unit tests for the LayerAllocator."""

from __future__ import annotations

from twinklr.core.sequencer.display.composition.layer_allocator import (
    LayerAllocator,
)
from twinklr.core.sequencer.vocabulary import GPBlendMode, LaneKind, VisualDepth


class TestLayerAllocator:
    """Tests for the LayerAllocator."""

    def test_default_procedural_layers(self) -> None:
        """Simple allocate still uses backward-compatible mapping."""
        allocator = LayerAllocator()
        assert allocator.allocate(LaneKind.BASE) == 0
        assert allocator.allocate(LaneKind.RHYTHM) == 2
        assert allocator.allocate(LaneKind.ACCENT) == 4

    def test_sub_layer_allocation(self) -> None:
        """Each (lane, depth) pair gets a unique layer index."""
        allocator = LayerAllocator()
        # BASE block: layers 0-5
        assert allocator.allocate_sub_layer(LaneKind.BASE, VisualDepth.BACKGROUND) == 0
        assert allocator.allocate_sub_layer(LaneKind.BASE, VisualDepth.MIDGROUND) == 1
        assert allocator.allocate_sub_layer(LaneKind.BASE, VisualDepth.FOREGROUND) == 2
        assert allocator.allocate_sub_layer(LaneKind.BASE, VisualDepth.ACCENT) == 3
        assert allocator.allocate_sub_layer(LaneKind.BASE, VisualDepth.TEXTURE) == 4

    def test_sub_layer_cross_lane(self) -> None:
        """Sub-layers in different lanes don't overlap."""
        allocator = LayerAllocator()
        base_bg = allocator.allocate_sub_layer(LaneKind.BASE, VisualDepth.BACKGROUND)
        rhythm_bg = allocator.allocate_sub_layer(LaneKind.RHYTHM, VisualDepth.BACKGROUND)
        accent_bg = allocator.allocate_sub_layer(LaneKind.ACCENT, VisualDepth.BACKGROUND)
        assert base_bg != rhythm_bg != accent_bg

    def test_overlay_layers(self) -> None:
        """Overlay is the last slot in each lane's block."""
        allocator = LayerAllocator()
        # BASE overlay: 0 + 6 - 1 = 5
        assert allocator.allocate_overlay(LaneKind.BASE) == 5
        # RHYTHM overlay: 6 + 6 - 1 = 11
        assert allocator.allocate_overlay(LaneKind.RHYTHM) == 11
        # ACCENT overlay: 12 + 6 - 1 = 17
        assert allocator.allocate_overlay(LaneKind.ACCENT) == 17

    def test_max_layer_index(self) -> None:
        """Max layer index covers the highest possible allocation."""
        allocator = LayerAllocator()
        # ACCENT base=12, overlay=17
        assert allocator.max_layer_index == 17

    def test_resolve_blend_mode(self) -> None:
        """GPBlendMode maps to xLights layer method strings."""
        assert LayerAllocator.resolve_blend_mode(GPBlendMode.ADD) == "Normal"
        assert LayerAllocator.resolve_blend_mode(GPBlendMode.MAX) == "Max"
        assert LayerAllocator.resolve_blend_mode(GPBlendMode.ALPHA_OVER) == "1 reveals 2"
