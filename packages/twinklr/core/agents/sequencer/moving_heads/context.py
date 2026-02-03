"""Context model for MovingHead planning inputs.

Provides structured context for moving head choreography planning,
following V2 Agent Framework patterns (modeled after MacroPlanner/GroupPlanner).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.agents.audio.profile.models import (
    AudioProfileModel,
    SongSectionRef,
)
from twinklr.core.agents.sequencer.macro_planner.models import MacroSectionPlan


class FixtureContext(BaseModel):
    """Fixture configuration for moving heads.

    Provides structured fixture information for the planner.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    count: int = Field(ge=1, description="Number of moving head fixtures")
    groups: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Fixture group configuration (DMX mapping, positions)",
    )


class MovingHeadPlanningContext(BaseModel):
    """Complete context for moving head planning.

    Bundles all Phase 1 analysis outputs and fixture configuration
    needed for MovingHead agent to generate choreography plans.

    This context object pattern:
    - Keeps API stable as new contexts are added
    - Groups related planning inputs together
    - Makes dependencies explicit
    - Simplifies testing and mocking
    - Replaces legacy dict-based context shaping
    """

    model_config = ConfigDict(extra="forbid")

    # Phase 1 Outputs
    audio_profile: AudioProfileModel = Field(
        description="Musical analysis and creative guidance from AudioProfile agent"
    )

    lyric_context: LyricContextModel | None = Field(
        default=None,
        description="Narrative and thematic analysis from Lyrics agent (None if no lyrics)",
    )

    # Fixture Configuration
    fixtures: FixtureContext = Field(description="Moving head fixture configuration")

    # Template Library (IDs only - full definitions are in the template registry)
    available_templates: list[str] = Field(
        description="Available template IDs from template registry"
    )

    # MacroPlan integration - coordinates with overall show strategy
    # Contains per-section energy targets, motion density, choreography style
    macro_plan: list[MacroSectionPlan] | None = Field(
        default=None,
        description="MacroPlan section outputs for coordination (energy targets, motion density, style per section)",
    )

    # Convenience properties

    @property
    def has_lyrics(self) -> bool:
        """Check if lyric context is available."""
        return self.lyric_context is not None

    @property
    def has_macro_plan(self) -> bool:
        """Check if macro plan is available for coordination."""
        return self.macro_plan is not None and len(self.macro_plan) > 0

    @property
    def song_title(self) -> str | None:
        """Get song title from audio profile."""
        return self.audio_profile.song_identity.title

    @property
    def song_artist(self) -> str | None:
        """Get artist name from audio profile."""
        return self.audio_profile.song_identity.artist

    @property
    def duration_ms(self) -> int:
        """Get song duration from audio profile."""
        return self.audio_profile.song_identity.duration_ms

    @property
    def tempo(self) -> float | None:
        """Get tempo (BPM) from audio profile."""
        return self.audio_profile.song_identity.bpm

    @property
    def time_signature(self) -> str | None:
        """Get time signature from audio profile."""
        return self.audio_profile.song_identity.time_signature

    @property
    def sections(self) -> list[SongSectionRef]:
        """Get song sections from audio profile structure."""
        return self.audio_profile.structure.sections

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_bars(self) -> int:
        """Estimate total bars from section timing and tempo.

        Uses last section end time and tempo to calculate bar count.
        Falls back to section-based estimation if tempo not available.
        """
        if not self.sections:
            return 0

        last_section = self.sections[-1]
        duration_ms = last_section.end_ms

        if self.tempo and self.tempo > 0:
            # Calculate from tempo: bars = (duration_ms / 60000) * (tempo / beats_per_bar)
            # Assuming 4/4 time (4 beats per bar) if not specified
            beats_per_bar = 4
            if self.time_signature:
                try:
                    beats_per_bar = int(self.time_signature.split("/")[0])
                except (ValueError, IndexError):
                    beats_per_bar = 4

            duration_minutes = duration_ms / 60000
            total_beats = duration_minutes * self.tempo
            return int(total_beats / beats_per_bar)

        # Fallback: estimate ~8 bars per section average
        return len(self.sections) * 8

    def for_prompt(self) -> dict[str, Any]:
        """Prepare context for prompt template injection.

        Returns a simplified dict optimized for prompt templates.
        Provides structured context for MovingHead planner prompts.

        Returns:
            Dict with template-ready context values
        """
        # Beat grid info for prompt
        beat_grid = {
            "tempo": self.tempo or 120,
            "time_signature": self.time_signature or "4/4",
            "total_bars": self.total_bars,
        }

        # Song structure with sections
        song_structure = {
            "sections": [
                {
                    "name": section.name,
                    "section_id": section.section_id,
                    "start_ms": section.start_ms,
                    "end_ms": section.end_ms,
                    # Calculate bar positions from timing
                    "start_bar": self._ms_to_bar(section.start_ms),
                    "end_bar": self._ms_to_bar(section.end_ms),
                }
                for section in self.sections
            ],
            "total_bars": self.total_bars,
        }

        # Fixture info for prompt
        fixtures = {
            "count": self.fixtures.count,
            "groups": self.fixtures.groups,
        }

        # Macro plan guidance per section (if available)
        macro_guidance = None
        if self.macro_plan:
            macro_guidance = [
                {
                    "section_id": sp.section.section_id,
                    "energy_target": sp.energy_target.value
                    if hasattr(sp.energy_target, "value")
                    else str(sp.energy_target),
                    "motion_density": sp.motion_density.value
                    if hasattr(sp.motion_density, "value")
                    else str(sp.motion_density),
                    "choreography_style": sp.choreography_style.value
                    if hasattr(sp.choreography_style, "value")
                    else str(sp.choreography_style),
                    "notes": sp.notes,
                }
                for sp in self.macro_plan
            ]

        return {
            "audio_profile": self.audio_profile,
            "lyric_context": self.lyric_context,
            "song_structure": song_structure,
            "beat_grid": beat_grid,
            "fixtures": fixtures,
            "available_templates": self.available_templates,
            "macro_plan": macro_guidance,
        }

    def _ms_to_bar(self, ms: int) -> int:
        """Convert milliseconds to bar number (1-indexed).

        Args:
            ms: Time in milliseconds

        Returns:
            Bar number (1-indexed, minimum 1)
        """
        if not self.tempo or self.tempo <= 0:
            # Fallback: assume 120 BPM
            tempo = 120.0
        else:
            tempo = self.tempo

        beats_per_bar = 4
        if self.time_signature:
            try:
                beats_per_bar = int(self.time_signature.split("/")[0])
            except (ValueError, IndexError):
                beats_per_bar = 4

        # ms -> beats -> bars
        ms_per_beat = 60000 / tempo
        beat_number = ms / ms_per_beat
        bar_number = int(beat_number / beats_per_bar) + 1  # 1-indexed

        return max(1, bar_number)
