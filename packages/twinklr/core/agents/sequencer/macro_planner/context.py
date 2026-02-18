"""Planning context model for MacroPlanner inputs."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.agents.audio.profile.models import AudioProfileModel


class PlanningContext(BaseModel):
    """Complete context for macro planning.

    Bundles all Phase 1 analysis outputs and display configuration
    needed for MacroPlanner to generate choreography plans.

    This context object pattern:
    - Keeps API stable as new contexts are added
    - Groups related planning inputs together
    - Makes dependencies explicit
    - Simplifies testing and mocking
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

    # Display Configuration
    display_groups: list[dict[str, Any]] = Field(
        description="Available display groups with concrete IDs and capabilities"
    )

    # Future extensibility (commented out, not yet implemented):
    # metadata: MetadataBundle | None = None  # Phase 4: Enhanced metadata
    # phonemes: PhonemeBundle | None = None   # Phase 4: Phoneme timing
    # user_preferences: UserPreferences | None = None  # User overrides/constraints

    @property
    def has_lyrics(self) -> bool:
        """Check if lyric context is available."""
        return self.lyric_context is not None

    @property
    def song_title(self) -> str | None:
        """Get song title from audio profile."""
        return self.audio_profile.song_identity.title

    @property
    def song_duration_ms(self) -> int:
        """Get song duration from audio profile."""
        return self.audio_profile.song_identity.duration_ms
