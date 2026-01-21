"""Transition context - dependency injection for transition handlers.

Follows established pattern from ResolverContext.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
    from blinkb0t.core.domains.sequencing.infrastructure.timing.resolver import TimeResolver
    from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement


@dataclass
class TransitionContext:
    """Context for transition rendering.

    Contains all dependencies needed by transition handlers.
    Follows same pattern as ResolverContext.

    Supports two modes:
    1. Legacy: from_effects + to_effects (for backward compatibility)
    2. New: from_position + to_position (for unified gap filling)
    """

    # Transition configuration
    mode: str  # "snap", "crossfade", "fade_through_black", "gap_fill"
    duration_bars: float
    curve: str | None

    # Timing
    start_ms: float
    end_ms: float
    duration_ms: float

    # Effects to blend (legacy mode)
    from_effects: list[EffectPlacement] | None = None
    to_effects: list[EffectPlacement] | None = None

    # Anchor positions (new gap filling mode)
    from_position: tuple[float, float] | None = None  # (pan_deg, tilt_deg)
    to_position: tuple[float, float] | None = None  # (pan_deg, tilt_deg)

    # Fixture context
    fixture_id: str = ""

    # Injected dependencies (framework components)
    dmx_curve_mapper: DMXCurveMapper | None = None
    time_resolver: TimeResolver | None = None
