"""
Timeline data models for transitions and gap filling.

This module defines the core data structures used in the two-phase
transitions and gap filling system:

- Phase 1 (Spatial Planning): Templates create Timeline with gaps
- Phase 2 (Temporal Rendering): Processor fills gaps with transitions

Models:
    - GapType: Enum for types of gaps (start, mid, inter, end)
    - TimelineGap: Represents a gap that needs filling
    - TimelineEffect: Represents a main effect with anchor positions
    - Timeline: Type alias for list[TimelineEffect | TimelineGap]
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement
from blinkb0t.core.domains.sequencing.models.templates import TransitionConfig


class GapType(str, Enum):
    """
    Types of gaps in the timeline.

    Gaps can occur in different contexts and require different handling:
    - START: Sequence start to first effect (0ms → first section)
    - MID_SEQUENCE: Between effects in same template (step transitions)
    - INTER_SECTION: Between sections (section boundaries)
    - END: Last effect to sequence end (last section → song duration)
    """

    START = "start"
    MID_SEQUENCE = "mid"
    INTER_SECTION = "inter"
    END = "end"


@dataclass
class TimelineGap:
    """
    Represents a gap in the timeline that needs to be filled.

    Gaps can have 0, 1, or 2 transition configs:
    - 0 configs: Implicit gap (sequence start/end, section boundaries)
    - 1 config: Explicit transition from template (entry or exit)
    - 2 configs: Adjacent transitions (exit + entry collapsed)

    Attributes:
        start_ms: Gap start time in milliseconds
        end_ms: Gap end time in milliseconds
        gap_type: Type of gap (START, MID_SEQUENCE, INTER_SECTION, END)
        fixture_id: Fixture this gap applies to
        transition_out_config: Optional transition from previous step
        transition_in_config: Optional transition to next step
        from_position: Optional anchor position from previous effect (pan, tilt)
        to_position: Optional anchor position to next effect (pan, tilt)

    Properties:
        duration_ms: Gap duration in milliseconds
        has_transition_config: True if any transition config is present

    Priority Resolution:
        When both configs are present:
        1. transition_in_config (highest priority)
        2. transition_out_config
        3. gap_fill (fallback if no configs)

    Example:
        >>> gap = TimelineGap(
        ...     start_ms=1000.0,
        ...     end_ms=1500.0,
        ...     gap_type=GapType.MID_SEQUENCE,
        ...     fixture_id="MH1",
        ...     transition_in_config=TransitionConfig(mode="crossfade", duration_bars=0.5),
        ...     from_position=(45.0, 30.0),
        ...     to_position=(90.0, 60.0)
        ... )
        >>> gap.duration_ms
        500.0
        >>> gap.has_transition_config
        True
    """

    start_ms: float
    end_ms: float
    gap_type: GapType
    fixture_id: str
    transition_out_config: TransitionConfig | None = None
    transition_in_config: TransitionConfig | None = None
    from_position: tuple[float, float] | None = None  # (pan_deg, tilt_deg)
    to_position: tuple[float, float] | None = None  # (pan_deg, tilt_deg)

    @property
    def duration_ms(self) -> float:
        """Calculate gap duration in milliseconds."""
        return self.end_ms - self.start_ms

    @property
    def has_transition_config(self) -> bool:
        """Check if gap has any explicit transition configuration."""
        return self.transition_in_config is not None or self.transition_out_config is not None


@dataclass
class TimelineEffect:
    """
    Represents a main movement effect in the timeline.

    Contains anchor positions (start and end pan/tilt) that are used by
    adjacent transitions to create smooth motion between effects.

    Attributes:
        start_ms: Effect start time in milliseconds
        end_ms: Effect end time in milliseconds
        fixture_id: Fixture this effect applies to
        effect: The actual EffectPlacement for XSQ export
        pan_start: Pan position at effect start (degrees)
        pan_end: Pan position at effect end (degrees, calculated from curve)
        tilt_start: Tilt position at effect start (degrees)
        tilt_end: Tilt position at effect end (degrees, calculated from curve)
        step_index: Index of template step this effect came from
        template_id: ID of template this effect belongs to

    The end positions (pan_end, tilt_end) are calculated based on:
    - Curve type (sine, ramp, triangle, etc.)
    - Effect duration
    - Movement amplitude
    - Curve frequency

    These anchors enable smooth transitions by providing accurate
    start/end positions rather than assuming all effects return to center.

    Example:
        >>> effect = TimelineEffect(
        ...     start_ms=1000.0,
        ...     end_ms=3000.0,
        ...     fixture_id="MH1",
        ...     effect=effect_placement,
        ...     pan_start=0.0,
        ...     pan_end=45.0,  # Calculated: partial sine cycle ends at +45°
        ...     tilt_start=0.0,
        ...     tilt_end=30.0,  # Calculated: partial sine cycle ends at +30°
        ...     step_index=0,
        ...     template_id="verse_sweep_pulse"
        ... )
    """

    start_ms: float
    end_ms: float
    fixture_id: str
    effect: EffectPlacement
    pan_start: float  # Degrees
    pan_end: float  # Degrees (calculated from curve + duration)
    tilt_start: float  # Degrees
    tilt_end: float  # Degrees (calculated from curve + duration)
    step_index: int
    template_id: str
    # Optional fields for rendering (Phase 1 → Phase 2 handoff)
    template_metadata: dict | None = None  # Template metadata for context
    pattern_step: Any | None = None  # Original PatternStep for rendering


# Type alias for timeline (mix of effects and gaps)
Timeline = list[TimelineEffect | TimelineGap]
