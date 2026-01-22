from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.curves.registry import CurveRegistry
from blinkb0t.core.sequencer.moving_heads.handlers.registry import (
    DimmerRegistry,
    GeometryRegistry,
    MovementRegistry,
)
from blinkb0t.core.sequencer.timing.beat_grid import BeatGrid


class FixtureContext(BaseModel):
    """Context for a single fixture.

    Attributes:
        fixture_id: Unique identifier for the fixture.
        role: Role assigned to this fixture (e.g., "FRONT_LEFT").
        calibration: Fixture calibration data.
    """

    model_config = ConfigDict(extra="forbid")

    fixture_id: str
    role: str
    calibration: dict[str, Any] = Field(default_factory=dict)


class StepCompileContext(BaseModel):
    """Context for compiling a single step.

    Contains all information needed to compile a step for a specific fixture.

    Attributes:
        fixture_id: Unique identifier for the fixture.
        role: Role assigned to this fixture (e.g., "FRONT_LEFT").
        calibration: Fixture calibration data.
        start_ms: Start time in milliseconds.
        duration_ms: Duration in milliseconds.
        n_samples: Number of samples for curves.
        geometry_registry: Registry of geometry handlers.
        movement_registry: Registry of movement handlers.
        dimmer_registry: Registry of dimmer handlers.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    fixture_id: str
    role: str
    calibration: dict[str, Any]
    start_ms: int
    duration_ms: int
    n_samples: int = Field(default=64, ge=2)

    curve_registry: CurveRegistry
    geometry_registry: GeometryRegistry
    movement_registry: MovementRegistry
    dimmer_registry: DimmerRegistry


class TemplateCompileContext(BaseModel):
    """Context for compiling a template.

    Contains all information needed to compile a template.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    fixtures: list[FixtureContext]
    beat_grid: BeatGrid

    start_bar: int = Field(default=0, ge=0)
    duration_bars: int = Field(default=0, ge=0)

    n_samples: int = Field(default=64, ge=2)

    curve_registry: CurveRegistry
    geometry_registry: GeometryRegistry
    movement_registry: MovementRegistry
    dimmer_registry: DimmerRegistry

    @property
    def bpm(self) -> float:
        return self.beat_grid.tempo_bpm

    @property
    def start_ms(self) -> int:
        return self._bar_to_ms(self.start_bar)

    @property
    def end_ms(self) -> int:
        return int(self._bar_to_ms(self.start_bar + self.duration_bars))

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    @property
    def ms_per_bar(self) -> float:
        """Calculate milliseconds per bar (assuming 4/4 time)."""
        ms_per_beat = 60000.0 / self.bpm
        return ms_per_beat * 4  # 4 beats per bar

    def _bar_to_ms(self, bar: int) -> int:
        """Convert bar number to milliseconds.

        Single source of truth for bar→ms conversion.
        Bars are 1-indexed and inclusive (bar 1 = 0-2000ms, bar 2 = 2000-4000ms).

        Args:
            bar: Bar number (1-indexed, inclusive for end_bar)

        Returns:
            Time in milliseconds at the START of the bar
        """
        # Bar 1 starts at 0ms, bar 2 starts at ms_per_bar, bar 3 at 2*ms_per_bar, etc.
        # For end_bar: bar 4 ends at 4*ms_per_bar = 8000ms
        return int((bar - 1) * self.beat_grid.ms_per_bar)
