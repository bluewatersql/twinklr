from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.config.fixtures.capabilities import FixtureCapabilities
from twinklr.core.config.fixtures.presets import PoseDegrees, RigPresetLibrary
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.topology import FixtureTopology
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import MusicalPhaseMap


class FixtureContext(BaseModel):
    """Context for a single fixture.

    Attributes:
        fixture_id: Unique identifier for the fixture.
        role: Role assigned to this fixture (e.g., "FRONT_LEFT").
        physical_profile: Explicit capabilities for the moving-head renderer, if declared.
    """

    model_config = ConfigDict(extra="forbid")

    fixture_id: str
    role: str
    physical_profile: FixtureCapabilities | None = None


class ResolvedStepComponents(BaseModel):
    """One fixture's physical settings for a step that names rig presets.

    `pose` is the start aim, per axis from the step or its position reference. Each
    held channel is the step's own static state or the referenced attribute preset's,
    and None where the step drives the channel with a pulse or nothing sets it.
    `provenance` records, per channel, `{"source": "step"}` or the referenced preset,
    the preset its fallback chain resolved to and the SHA-256 of the entry used.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    pose: PoseDegrees
    shutter: str | None = None
    color: str | None = None
    gobo: str | None = None
    dimmer: float | None = Field(default=None, ge=0, le=1)
    provenance: dict[str, dict[str, str]]


class StepCompileContext(BaseModel):
    """Context for compiling a single step.

    Contains all information needed to compile a step for a specific fixture.

    Attributes:
        fixture_id: Unique identifier for the fixture.
        role: Role assigned to this fixture (e.g., "FRONT_LEFT").
        start_ms: Start time in milliseconds.
        duration_ms: Duration in milliseconds.
        beat_grid: Beat grid for timing conversions (needed for period_bars → cycles).
        physical_profile: The fixture's physical profile.
        phase_map: The song's musical phase map.
        resolved_components: The step's component references resolved for this
            fixture: its start aim, and held channels that replace the step's own;
            None for a step without references.
        phase_offset_by_channel: Cycles each phase domain lags the step phase: from
            the step's distribution over the rig topology, plus the shift by which an
            instance continuing the phase of the step's earlier instances in its
            section corrects its own frame-grid start (`_phase_shift`).
        pan_sign: Multiplies the pan displacement (not the start aim): -1 or +1 for a
            mirrored wing, 0 at an odd center.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    section_id: str
    segment_id: str
    template_id: str
    preset_id: str | None = None

    fixture_id: str
    role: str
    start_ms: int
    duration_ms: int

    beat_grid: BeatGrid  # Added for period_bars → cycles conversion
    physical_profile: FixtureCapabilities | None = None
    phase_map: MusicalPhaseMap | None = None
    resolved_components: ResolvedStepComponents | None = None
    phase_offset_by_channel: dict[ChannelName, Fraction] = Field(default_factory=dict)
    pan_sign: Literal[-1, 0, 1] = 1


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

    # The fixture group's named components.
    presets: RigPresetLibrary = Field(default_factory=RigPresetLibrary)
    # The rig's canonical topology (declared or derived), and the fixture group a
    # distribution that finds none is reported against.
    topology: FixtureTopology | None = None
    fixture_group_id: str | None = None

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
