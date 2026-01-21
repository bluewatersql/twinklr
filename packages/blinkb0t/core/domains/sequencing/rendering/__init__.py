"""Rendering pipeline for moving head sequences.

This module provides the core rendering infrastructure that converts
agent implementations into xLights sequence files (XSQ).

Key components:
- models: Core data models (SequencedEffect, RenderedEffect, etc.)
- channel_overlay: Channel overlay resolution
- segment_renderer: Per-fixture segment rendering (Phase 3)
- gap_renderer: Gap fill rendering (Phase 3)
- curve_pipeline: Curve rendering with Native/Custom support (Phase 4)
- xlights_provider: xLights format conversion and file writing (Phase 4)
- pipeline: Main orchestration (Phase 5)
"""

from .channel_overlay import resolve_channel_overlays
from .curve_pipeline import CurvePipeline
from .gap_renderer import GapRenderer
from .models import (
    BoundaryInfo,
    ChannelOverlay,
    ChannelSpecs,
    RenderedChannels,
    RenderedEffect,
    SequencedEffect,
)
from .pipeline import RenderingPipeline
from .segment_renderer import SegmentRenderer
from .xlights_provider import XlightsProvider

__all__ = [
    "BoundaryInfo",
    "ChannelOverlay",
    "ChannelSpecs",
    "CurvePipeline",
    "GapRenderer",
    "RenderedChannels",
    "RenderedEffect",
    "RenderingPipeline",
    "SegmentRenderer",
    "SequencedEffect",
    "XlightsProvider",
    "resolve_channel_overlays",
]
