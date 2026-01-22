from pydantic import BaseModel, ConfigDict, Field


class ScheduledInstance(BaseModel):
    """A scheduled instance of a template step.

    Represents a single occurrence of a step within the playback window.

    Attributes:
        step_id: The step identifier.
        start_bars: Start time in bars from window start.
        end_bars: End time in bars from window start.
        cycle_number: Which cycle this instance belongs to (0-indexed).

    Example:
        >>> instance = ScheduledInstance(
        ...     step_id="step1",
        ...     start_bars=0.0,
        ...     end_bars=2.0,
        ...     cycle_number=0,
        ... )
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str = Field(...)
    start_bars: float = Field(..., ge=0.0)
    end_bars: float = Field(..., ge=0.0)
    cycle_number: int = Field(..., ge=0)

    @property
    def duration_bars(self) -> float:
        """Get the duration of this instance in bars."""
        return self.end_bars - self.start_bars
