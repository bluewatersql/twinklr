"""Context model for MovingHead planning inputs.

Provides structured context for moving head choreography planning,
following V2 Agent Framework patterns (modeled after MacroPlanner/GroupPlanner).
"""

from __future__ import annotations

import bisect
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, computed_field

from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.agents.audio.profile.models import (
    AudioProfileModel,
    SongSectionRef,
)
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.moving_heads.song_intent import (
    RigOffer,
    SectionPalette,
    offer_for_prompt,
    section_palettes,
)
from twinklr.core.sequencer.planning import MacroPlan
from twinklr.core.sequencer.theming.catalog import get_palette
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import build_musical_phase_map

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
    _beyond_grid_logged: bool = PrivateAttr(default=False)
    """Whether `song_structure` has warned about the song's tail beyond the beat grid."""

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
    macro_plan: MacroPlan | None = Field(
        default=None,
        description="Full typed MacroPlan coordination contract",
    )

    macro_planning_enabled: bool = Field(
        default=True,
        description="Whether the macro-planning graph arm was enabled for this plan",
    )

    # What the rig can show of the song intent, from the pre-planning gate
    rig_offer: RigOffer | None = Field(
        default=None,
        description="The rig's offer (colours, gobos, strobes, hit, wheel change time); "
        "None when no pre-planning gate ran",
    )

    # The moving heads' macro focal role per section, under `twinklr show` only
    head_focal_roles: dict[str, str] | None = Field(
        default=None,
        description="The moving heads' macro focal role (LEAD, SUPPORT, REST) by section id, "
        "which the show render applies to each section's intensity; None outside a show",
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
        return self.macro_plan is not None and bool(self.macro_plan.sections)

    @property
    def palettes(self) -> dict[str, SectionPalette]:
        """Each section's macro palette, which its palette roles resolve through."""
        return section_palettes(self.macro_plan)

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

        song_structure = self.song_structure()

        # Fixture info for prompt
        fixtures = {
            "count": self.fixtures.count,
            "groups": self.fixtures.groups,
        }

        # Macro plan guidance per section (if available), for the sections the planner may
        # plan: one beyond the beat grid is not shown, as it is not in the song structure.
        plannable = {entry["section_id"] for entry in song_structure["sections"]}
        macro_guidance = None
        macro_contract = None
        if self.macro_plan:
            macro_contract = self.macro_plan.reader_projection()
            macro_contract["sections"] = [
                section
                for section in macro_contract["sections"]
                if section["section"]["section_id"] in plannable
            ]
            macro_contract["focal_arc"] = [
                focus for focus in macro_contract["focal_arc"] if focus["section_id"] in plannable
            ]
            macro_guidance = macro_contract["sections"]
            for section in macro_guidance:
                section_id = section["section"]["section_id"]
                section["section_id"] = section_id
                palette_id = self.macro_plan.palette_for_section(str(section_id)).palette_id
                section["palette_id"] = palette_id
                # The palette's colours, so a colour role is chosen knowing what it shows.
                section["palette_colors"] = [
                    {"hex": stop.hex, "name": stop.name} for stop in get_palette(palette_id).stops
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
            "macro_palette_arc": macro_contract["palette_arc"] if macro_contract else None,
            "macro_motif_continuity": (
                macro_contract["motif_continuity"] if macro_contract else None
            ),
            "macro_focal_arc": macro_contract["focal_arc"] if macro_contract else None,
            "head_focal_roles": (
                None
                if self.head_focal_roles is None
                else {
                    section_id: role
                    for section_id, role in self.head_focal_roles.items()
                    if section_id in plannable
                }
            ),
            "rig_offer": (
                None
                if self.rig_offer is None
                else offer_for_prompt(
                    self.rig_offer,
                    self.palettes,
                    # The sections the planner may plan: none beyond the beat grid.
                    [entry["section_id"] for entry in song_structure["sections"]],
                    self._boundary_half_beats(song_structure["sections"]),
                )
            ),
        }

    def _boundary_half_beats(self, sections: list[dict[str, Any]]) -> list[float] | None:
        """Half the beat before each section boundary (each section's first bar but the
        song's first), on the beat grid; None without one."""
        if self.beat_grid is None or len(self.beat_grid.beat_boundaries) < 2:
            return None
        bars, beats = self.beat_grid.bar_boundaries, self.beat_grid.beat_boundaries
        halves = []
        for entry in sections[1:]:
            index = int(entry["start_bar"]) - 1
            if not 0 <= index < len(bars):
                continue
            at = min(max(bisect.bisect_left(beats, bars[index]), 1), len(beats) - 1)
            halves.append((beats[at] - beats[at - 1]) / 2)
        return halves

    def song_structure(self) -> dict[str, Any]:
        """The song's sections in the bars the renderer can play: the one computation
        of section bars that the planning prompt, the validator and the selector read.

        A section's bars are inclusive: it starts on the bar its start time resolves to
        and ends on the bar before the one its end time resolves to (the next section's
        first bar, or the bar after the song's last), so consecutive sections share no
        bar. Bars are clamped to ``1..total_bars``: when the beat grid stops before the
        audio ends, the last section starting inside the grid ends on ``total_bars``,
        and a section starting beyond it is left out (it has no bar to render) and
        named under ``beyond_grid``: where the render goes dark (the end of the beat
        grid's covered span, on the frame grid, as the renderer's cue limits put it) and
        the seconds of song it leaves dark. ``beyond_grid`` is None when nothing was
        clamped or left out. The warning is logged once per context (one per run).
        """
        total_bars = self.total_bars
        section_entries: list[dict[str, Any]] = []
        omitted: list[str] = []
        clamped = False
        for section in self.sections:
            start_bar = self._ms_to_bar(section.start_ms)
            next_bar = self._ms_to_bar(section.end_ms)
            if start_bar > total_bars:
                omitted.append(section.section_id)
                continue
            end_bar = max(start_bar, next_bar - 1)
            if end_bar > total_bars:
                end_bar = total_bars
                clamped = True
            section_entries.append(
                {
                    "name": section.name,
                    "section_id": section.section_id,
                    "start_ms": section.start_ms,
                    "end_ms": section.end_ms,
                    "start_bar": start_bar,
                    "end_bar": end_bar,
                    "_collapsed": next_bar <= start_bar,
                }
            )
        self._warn_on_collapsed_sections(section_entries)
        for entry in section_entries:
            del entry["_collapsed"]

        beyond_grid: dict[str, Any] | None = None
        if omitted or clamped:
            grid_end_ms = self._dark_from_ms(total_bars)
            song_end_ms = self.sections[-1].end_ms
            beyond_grid = {
                "from_ms": round(grid_end_ms),
                "seconds": round(max(0.0, song_end_ms - grid_end_ms) / 1000, 1),
                "section_ids": omitted,
            }
        if beyond_grid is not None and not self._beyond_grid_logged:
            self._beyond_grid_logged = True
            logger.warning(
                "The beat grid ends at bar %d and the render goes dark at %.1f s, %.1f s before "
                "the song ends; section bars are clamped to it%s",
                total_bars,
                beyond_grid["from_ms"] / 1000,
                beyond_grid["seconds"],
                f" and {', '.join(omitted)} left unplanned" if omitted else "",
            )

        return {
            "sections": section_entries,
            "total_bars": total_bars,
            "beyond_grid": beyond_grid,
        }

    def _dark_from_ms(self, bar: int) -> float:
        """Where the render goes dark at the song's end: the beat grid's covered span's end
        (its last beat plus one beat interval, or the song's edge), on the frame grid, as
        the renderer's cue limits put it; without a grid, the end of 1-indexed ``bar`` at
        nominal tempo."""
        if self.beat_grid is not None and len(self.beat_grid.beat_boundaries) >= 2:
            covered = build_musical_phase_map(self.beat_grid).covered_end_ms
            frame = EFFECT_GRID_MS
            return min(
                int(self.beat_grid.duration_ms) // frame * frame,
                int(covered // frame * frame),
            )
        tempo = 120.0 if not self.tempo or self.tempo <= 0 else self.tempo
        return bar * self.beats_per_bar * 60_000.0 / tempo

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
            if entry["_collapsed"]:
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
