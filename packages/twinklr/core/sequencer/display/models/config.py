"""Configuration models for the display renderer.

Defines composition policies, render configuration, and related enums.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class OverlapPolicy(str, Enum):
    """Policy for resolving overlapping effects within a single layer.

    Attributes:
        TRIM: Later effect trims earlier effect's end time.
        PRIORITY: Higher-priority effect wins; lower is removed.
        ERROR: Raise error on overlap (strict mode).
    """

    TRIM = "TRIM"
    PRIORITY = "PRIORITY"
    ERROR = "ERROR"


class GapPolicy(str, Enum):
    """Policy for handling gaps between effects.

    Attributes:
        DARK: Leave gaps dark (no effect).
        FILL_OFF: Insert explicit Off effects in gaps.
    """

    DARK = "DARK"
    FILL_OFF = "FILL_OFF"


class TransitionPolicy(str, Enum):
    """Policy for transitions between effects.

    Attributes:
        CUT: Hard cut between effects (no transition).
        CROSSFADE: Crossfade between consecutive effects.
    """

    CUT = "CUT"
    CROSSFADE = "CROSSFADE"


class CompositionConfig(BaseModel):
    """Configuration for the CompositionEngine.

    Controls how the composition engine resolves overlaps, transitions,
    and gaps when building the RenderPlan.

    Attributes:
        overlap_policy: How to handle overlapping effects in a layer.
        gap_policy: How to handle gaps between effects.
        transition_policy: How to handle transitions between effects.
        max_layers_per_element: Maximum effect layers per element.
        default_buffer_style: Default xLights buffer style.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    overlap_policy: OverlapPolicy = Field(
        default=OverlapPolicy.TRIM,
        description="How to resolve overlapping effects within a layer",
    )
    gap_policy: GapPolicy = Field(
        default=GapPolicy.DARK,
        description="How to handle gaps between effects",
    )
    transition_policy: TransitionPolicy = Field(
        default=TransitionPolicy.CUT,
        description="How to handle transitions between effects",
    )
    max_layers_per_element: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of effect layers per element",
    )
    default_buffer_style: str = Field(
        default="Per Model Default",
        description="Default xLights buffer style for effects",
    )


class RenderConfig(BaseModel):
    """Top-level configuration for the DisplayRenderer.

    Attributes:
        composition: Composition engine configuration.
        frame_interval_ms: Frame interval in milliseconds (xLights grid).
        asset_base_path: Base path for image/video assets.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    composition: CompositionConfig = Field(
        default_factory=CompositionConfig,
        description="Composition engine configuration",
    )
    frame_interval_ms: int = Field(
        default=20,
        ge=10,
        le=100,
        description="Frame interval in milliseconds (xLights timing grid)",
    )
    asset_base_path: str = Field(
        default="",
        description="Base path for image/video assets",
    )


__all__ = [
    "CompositionConfig",
    "GapPolicy",
    "OverlapPolicy",
    "RenderConfig",
    "TransitionPolicy",
]
