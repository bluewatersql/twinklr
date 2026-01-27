"""EffectPlacement dataclass for backward compatibility.

This module provides the EffectPlacement dataclass which is used throughout
the codebase as an intermediate representation between DMX effects and XSQ effects.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EffectPlacement:
    """Represents an effect placement in an xLights sequence.

    This is a compatibility dataclass used during migration. It represents
    an effect that will be added to an XSQ sequence, including timing,
    element name, and effect metadata.

    Attributes:
        element_name: Name of the xLights element/model
        effect_name: Type of effect (e.g., "DMX", "timing")
        start_ms: Start time in milliseconds
        end_ms: End time in milliseconds
        effect_label: Optional label for the effect
        ref: Optional reference index into EffectDB
        palette: Palette index (default: 0)
        layer_index: Layer index for multi-layer effects (default: 0)
    """

    element_name: str
    effect_name: str
    start_ms: int
    end_ms: int
    effect_label: str | None = None
    ref: int | None = None
    palette: int = 0
    layer_index: int = 0
