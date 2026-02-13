"""Unit tests for the LayerAllocator."""

from __future__ import annotations

from twinklr.core.sequencer.display.composition.layer_allocator import (
    LayerAllocator,
)
from twinklr.core.sequencer.vocabulary import GPBlendMode, LaneKind


class TestLayerAllocator:
    """Tests for the LayerAllocator."""

    def test_default_procedural_layers(self) -> None:
        """Default mapping: BASE=0, RHYTHM=2, ACCENT=4."""
        allocator = LayerAllocator()
        assert allocator.allocate(LaneKind.BASE) == 0
        assert allocator.allocate(LaneKind.RHYTHM) == 2
        assert allocator.allocate(LaneKind.ACCENT) == 4

    def test_default_overlay_layers(self) -> None:
        """Overlay is always procedural + 1."""
        allocator = LayerAllocator()
        assert allocator.allocate_overlay(LaneKind.BASE) == 1
        assert allocator.allocate_overlay(LaneKind.RHYTHM) == 3
        assert allocator.allocate_overlay(LaneKind.ACCENT) == 5

    def test_max_layer_index_includes_overlay(self) -> None:
        """Max layer index accounts for the overlay slot."""
        allocator = LayerAllocator()
        assert allocator.max_layer_index == 5  # ACCENT=4, overlay=5

    def test_custom_layer_map(self) -> None:
        """Custom layer map is respected for both procedural and overlay."""
        custom = {LaneKind.BASE: 0, LaneKind.RHYTHM: 4}
        allocator = LayerAllocator(layer_map=custom)
        assert allocator.allocate(LaneKind.BASE) == 0
        assert allocator.allocate_overlay(LaneKind.BASE) == 1
        assert allocator.allocate(LaneKind.RHYTHM) == 4
        assert allocator.allocate_overlay(LaneKind.RHYTHM) == 5

    def test_unknown_lane_defaults_to_zero(self) -> None:
        """Unknown lane kind falls back to layer 0."""
        allocator = LayerAllocator(layer_map={LaneKind.BASE: 0})
        assert allocator.allocate(LaneKind.ACCENT) == 0
        assert allocator.allocate_overlay(LaneKind.ACCENT) == 1

    def test_resolve_blend_mode(self) -> None:
        """GPBlendMode maps to xLights layer method strings."""
        assert LayerAllocator.resolve_blend_mode(GPBlendMode.ADD) == "Normal"
        assert LayerAllocator.resolve_blend_mode(GPBlendMode.MAX) == "Max"
        assert (
            LayerAllocator.resolve_blend_mode(GPBlendMode.ALPHA_OVER)
            == "1 reveals 2"
        )

    def test_single_lane_map_max_index(self) -> None:
        """Single-lane map max_layer_index includes overlay slot."""
        allocator = LayerAllocator(layer_map={LaneKind.BASE: 0})
        assert allocator.max_layer_index == 1  # 0 (procedural) + 1 (overlay)
