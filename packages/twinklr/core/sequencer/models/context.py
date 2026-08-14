from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.handlers.registry import (
    ColorRegistry,
    DimmerRegistry,
    GeometryRegistry,
    GoboRegistry,
    MovementRegistry,
    ShutterRegistry,
)
from twinklr.core.sequencer.moving_heads.libraries.color import ColorPreset
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def _default_color_registry() -> ColorRegistry:
    from twinklr.core.sequencer.moving_heads.handlers.defaults import create_default_color_registry

    return create_default_color_registry()


def _default_shutter_registry() -> ShutterRegistry:
    from twinklr.core.sequencer.moving_heads.handlers.defaults import (
        create_default_shutter_registry,
    )

    return create_default_shutter_registry()


def _default_gobo_registry() -> GoboRegistry:
    from twinklr.core.sequencer.moving_heads.handlers.defaults import create_default_gobo_registry

    return create_default_gobo_registry()


class TimedChannelIntent(BaseModel):
    """Renderer-neutral discrete wheel change placed on the authoritative grid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    at_ms: int = Field(ge=0)
    pattern_id: str = Field(min_length=1)


class SectionRenderIntent(BaseModel):
    """Plan intent already translated into renderer-owned vocabulary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intensity: Intensity | None = None
    color: ColorPreset | None = None
    shutter_events: list[TimedChannelIntent] = Field(default_factory=list)
    gobo_events: list[TimedChannelIntent] = Field(default_factory=list)


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
        beat_grid: Beat grid for timing conversions (needed for period_bars → cycles).
        template_defaults: The template's own `defaults` (after preset merge). Carries
            the declared `dimmer_floor_dmx` / `dimmer_ceiling_dmx` anti-flicker bounds
            to the handlers, which is the only route by which they reach the output.
        geometry_registry: Registry of geometry handlers.
        movement_registry: Registry of movement handlers.
        dimmer_registry: Registry of dimmer handlers.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    section_id: str
    segment_id: str
    template_id: str
    preset_id: str | None = None

    fixture_id: str
    role: str
    calibration: dict[str, Any]
    template_defaults: dict[str, Any] = Field(default_factory=dict)
    start_ms: int
    duration_ms: int
    n_samples: int = Field(default=64, ge=2)

    beat_grid: BeatGrid  # Added for period_bars → cycles conversion
    curve_registry: CurveRegistry
    geometry_registry: GeometryRegistry
    movement_registry: MovementRegistry
    dimmer_registry: DimmerRegistry
    color_registry: ColorRegistry = Field(default_factory=_default_color_registry)
    shutter_registry: ShutterRegistry = Field(default_factory=_default_shutter_registry)
    gobo_registry: GoboRegistry = Field(default_factory=_default_gobo_registry)


class TemplateCompileContext(BaseModel):
    """Context for compiling a template.

    Contains all information needed to compile a template.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    section_id: str
    template_id: str
    preset_id: str | None = None
    fixtures: list[FixtureContext]
    beat_grid: BeatGrid

    start_bar: int = Field(default=0, ge=0)
    duration_bars: int = Field(default=0, ge=0)

    n_samples: int = Field(default=64, ge=2)

    curve_registry: CurveRegistry
    geometry_registry: GeometryRegistry
    movement_registry: MovementRegistry
    dimmer_registry: DimmerRegistry
    color_registry: ColorRegistry = Field(default_factory=_default_color_registry)
    shutter_registry: ShutterRegistry = Field(default_factory=_default_shutter_registry)
    gobo_registry: GoboRegistry = Field(default_factory=_default_gobo_registry)
    intent: SectionRenderIntent = Field(default_factory=SectionRenderIntent)

    @property
    def bpm(self) -> float:
        return self.beat_grid.tempo_bpm

    @property
    def start_ms(self) -> int:
        return self._bar_to_ms(self.start_bar)

    @property
    def end_ms(self) -> int:
        return self._bar_to_ms(self.start_bar + self.duration_bars)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def bar_offset_to_ms(self, offset_bars: float) -> int:
        """Convert a bar offset measured from this section's start to absolute ms.

        Steps and step boundaries are positioned in bars relative to the section;
        this resolves them against the same detected downbeats `_bar_to_ms` uses, so
        a step half a bar into a section lands half of *that bar's* real duration in.

        Args:
            offset_bars: Bars after the section's first downbeat (may be fractional)

        Returns:
            Absolute time in milliseconds
        """
        return int(self.beat_grid.get_bar_start_ms(self.start_bar - 1 + offset_bars))

    def _bar_to_ms(self, bar: int) -> int:
        """Convert bar number to milliseconds.

        Single source of truth for bar→ms conversion.

        Uses the beat grid's detected downbeats to stay synced with the actual
        music, not a tempo-derived average anchored at 0 ms, which drifts and
        ignores the lead-in before the first downbeat. Bar 1 therefore starts at
        `bar_boundaries[0]`, which is where the "Twinklr Bars" timing track puts it.

        Bars are 1-indexed and inclusive, so `bar` used as an end bar names the
        downbeat the section ends on (exclusive).

        Args:
            bar: Bar number (1-indexed, inclusive for end_bar)

        Returns:
            Time in milliseconds at the START of the bar
        """
        return int(self.beat_grid.get_bar_start_ms(bar - 1))
