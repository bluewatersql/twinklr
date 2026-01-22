from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.sequencer.moving_heads.handlers.registry import (
    DimmerRegistry,
    GeometryRegistry,
    MovementRegistry,
)


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

    geometry_registry: GeometryRegistry
    movement_registry: MovementRegistry
    dimmer_registry: DimmerRegistry


class TemplateCompileContext(BaseModel):
    """Context for compiling a template.

    Contains all information needed to compile a template.

    Attributes:
        fixtures: List of fixture contexts to compile for.
        start_ms: Start time in milliseconds.
        window_ms: Total window duration in milliseconds.
        bpm: Beats per minute for timing calculations.
        n_samples: Number of samples for curves.
        geometry_registry: Registry of geometry handlers.
        movement_registry: Registry of movement handlers.
        dimmer_registry: Registry of dimmer handlers.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    fixtures: list[FixtureContext]
    start_ms: int = Field(default=0, ge=0)
    window_ms: int = Field(..., ge=0)
    bpm: float = Field(default=120.0, gt=0)
    n_samples: int = Field(default=64, ge=2)

    geometry_registry: GeometryRegistry
    movement_registry: MovementRegistry
    dimmer_registry: DimmerRegistry

    @property
    def ms_per_bar(self) -> float:
        """Calculate milliseconds per bar (assuming 4/4 time)."""
        ms_per_beat = 60000.0 / self.bpm
        return ms_per_beat * 4  # 4 beats per bar

    @property
    def window_bars(self) -> float:
        """Calculate window duration in bars."""
        return self.window_ms / self.ms_per_bar
