"""Context model for MovingHead planning inputs.

Provides structured context for moving head choreography planning,
following V2 Agent Framework patterns (modeled after MacroPlanner/GroupPlanner).
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.agents.audio.profile.models import (
    AudioProfileModel,
    SongSectionRef,
)
from twinklr.core.sequencer.planning import MacroSectionPlan
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

logger = logging.getLogger(__name__)


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


class TemplateDescription(BaseModel):
    """Brief description of a template for prompt injection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: str
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    energy_range: tuple[int, int] | None = None
    recommended_sections: list[str] = Field(default_factory=list)


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

    # The grid the renderer places effects on and the timing tracks are written from.
    # The planner numbers bars against this same grid so the bar numbers it hands back
    # name the instants the renderer will use.
    beat_grid: BeatGrid | None = Field(
        default=None,
        description="Detected beat grid; when absent, bar numbers fall back to nominal tempo",
    )

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

    # Template descriptions for prompt enrichment (optional)
    template_descriptions: list[TemplateDescription] | None = Field(
        default=None,
        description="Brief descriptions of available templates (energy, tags, recommended sections)",
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

    @property
    def beats_per_bar(self) -> int:
        """Beats per bar, from the beat grid when available, else the time signature."""
        if self.beat_grid is not None:
            return self.beat_grid.beats_per_bar

        if self.time_signature:
            try:
                return int(self.time_signature.split("/")[0])
            except (ValueError, IndexError):
                return 4
        return 4

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_bars(self) -> int:
        """Total bars in the song.

        Counts the detected downbeats when a beat grid is available — the same
        count the renderer and the "Twinklr Bars" timing track use. Without a grid,
        estimates from the last section end and the nominal tempo, and falls back to
        a per-section average if the tempo is unknown too.
        """
        if self.beat_grid is not None and self.beat_grid.bar_boundaries:
            return self.beat_grid.total_bars

        if not self.sections:
            return 0

        last_section = self.sections[-1]
        duration_ms = last_section.end_ms

        if self.tempo and self.tempo > 0:
            # Calculate from tempo: bars = (duration_ms / 60000) * (tempo / beats_per_bar)
            duration_minutes = duration_ms / 60000
            total_beats = duration_minutes * self.tempo
            return int(total_beats / self.beats_per_bar)

        # Fallback: estimate ~8 bars per section average
        return len(self.sections) * 8

    def for_prompt(self) -> dict[str, Any]:
        """Prepare context for prompt template injection.

        Returns a simplified dict optimized for prompt templates.
        Provides structured context for MovingHead planner prompts.

        Returns:
            Dict with template-ready context values
        """
        if self.beat_grid is None or not self.beat_grid.bar_boundaries:
            logger.warning(
                "No beat grid supplied to the moving-head planner; section bar numbers "
                "will be estimated from nominal tempo and may not line up with the "
                "downbeats the renderer places effects on"
            )

        # Beat grid info for prompt
        beat_grid = {
            "tempo": self.tempo or 120,
            "time_signature": self.time_signature or "4/4",
            "total_bars": self.total_bars,
        }

        # Song structure with sections
        section_entries = [
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
        ]
        self._warn_on_collapsed_sections(section_entries)

        song_structure = {
            "sections": section_entries,
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
                    "palette_id": (sp.palette.palette_id if sp.palette else None),
                    "motif_ids": sp.motif_ids,
                    "notes": sp.notes,
                }
                for sp in self.macro_plan
            ]

        # Template descriptions for prompt enrichment
        template_descs = None
        if self.template_descriptions:
            template_descs = [td.model_dump() for td in self.template_descriptions]

        return {
            "audio_profile": self.audio_profile,
            "lyric_context": self.lyric_context,
            "song_structure": song_structure,
            "beat_grid": beat_grid,
            "fixtures": fixtures,
            "available_templates": self.available_templates,
            "template_descriptions": template_descs,
            "macro_plan": macro_guidance,
        }

    @staticmethod
    def _warn_on_collapsed_sections(section_entries: list[dict[str, Any]]) -> None:
        """Report sections that rounding collapsed onto a single bar.

        Nearest-downbeat resolution can land a section shorter than a bar on the same
        downbeat as its neighbour. Ordering is preserved (the resolution is monotonic
        in time), but the section has no bars of its own to render; short-section
        rendering is P1P-T5's problem, so this records the case rather than fixing it.
        """
        previous_start: int | None = None
        for entry in section_entries:
            start_bar = int(entry["start_bar"])
            end_bar = int(entry["end_bar"])
            if start_bar == end_bar:
                logger.warning(
                    "Section '%s' (%dms-%dms) is shorter than one bar; it collapsed onto bar %d",
                    entry["name"],
                    entry["start_ms"],
                    entry["end_ms"],
                    start_bar,
                )
            if previous_start is not None and start_bar == previous_start:
                logger.warning(
                    "Section '%s' starts on bar %d, the same downbeat as the preceding section",
                    entry["name"],
                    start_bar,
                )
            previous_start = start_bar

    def _ms_to_bar(self, ms: int) -> int:
        """Convert milliseconds to bar number (1-indexed).

        Resolves to the *nearest* detected downbeat on the beat grid — the same grid
        the renderer converts these bar numbers back through. A section start 100 ms
        before a downbeat therefore names that downbeat's bar rather than being
        dragged back to the previous one.

        Without a beat grid the conversion degrades to nominal-tempo arithmetic
        (120 BPM if the tempo is unknown), still rounding to nearest. That path is
        approximate — the renderer's bars come from detected downbeats, so the two
        agree only when the audio happens to be metronomic and start on a downbeat.

        Args:
            ms: Time in milliseconds

        Returns:
            Bar number (1-indexed, minimum 1)
        """
        if self.beat_grid is not None and self.beat_grid.bar_boundaries:
            return self.beat_grid.nearest_bar_index(float(ms)) + 1

        tempo = 120.0 if not self.tempo or self.tempo <= 0 else self.tempo
        logger.debug(
            "No beat grid available; resolving %dms to a bar with nominal tempo %.1f BPM",
            ms,
            tempo,
        )

        ms_per_bar = (60000.0 / tempo) * self.beats_per_bar
        return max(1, round(ms / ms_per_bar) + 1)
