"""Planning vocabulary for categorical timing.

Provides simplified timing models for LLM planning that eliminate
precision issues with beat_frac and offset_ms.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TimingHint(str, Enum):
    """Optional timing hint for subtle variations.

    These are optional micro-adjustments the renderer applies.
    Most placements should use ON_BEAT (default).
    """

    ON_BEAT = "ON_BEAT"  # Default: exactly on the beat
    AND = "AND"  # Half-beat offset (the "and" of "1 and 2 and")
    ANTICIPATE = "ANTICIPATE"  # Slight early (1/8 beat) for musical tension


class PlanningTimeRef(BaseModel):
    """Simplified time reference for LLM planning.

    Uses only bar and beat (integers) with optional timing hint.
    The renderer resolves to precise milliseconds using the BeatGrid.

    Examples:
        - PlanningTimeRef(bar=1, beat=1) -> Start of bar 1
        - PlanningTimeRef(bar=2, beat=3) -> Beat 3 of bar 2
        - PlanningTimeRef(bar=1, beat=2, timing_hint=TimingHint.AND) -> "1-and-2"
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    bar: int = Field(..., ge=1, description="Bar number (1-indexed)")
    beat: int = Field(..., ge=1, le=16, description="Beat within bar (1-indexed, typically 1-4)")
    timing_hint: TimingHint = Field(
        default=TimingHint.ON_BEAT,
        description="Optional timing micro-adjustment",
    )

    def __str__(self) -> str:
        """Human-readable representation."""
        hint = f" ({self.timing_hint.value})" if self.timing_hint != TimingHint.ON_BEAT else ""
        return f"{self.bar}:{self.beat}{hint}"

    def __lt__(self, other: "PlanningTimeRef") -> bool:
        """Compare time references for ordering."""
        if self.bar != other.bar:
            return self.bar < other.bar
        return self.beat < other.beat

    def __le__(self, other: "PlanningTimeRef") -> bool:
        """Compare time references for ordering."""
        return self == other or self < other


__all__ = [
    "PlanningTimeRef",
    "TimingHint",
]
