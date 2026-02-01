"""Planning context for GroupPlanner agent."""

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.sequencer.macro_planner.models import MacroPlan
from twinklr.core.sequencer.templates.models import TemplateRef


class DisplayGroupRef(BaseModel):
    """Reference to a display group."""

    model_config = ConfigDict(extra="forbid")

    group_id: str
    name: str
    group_type: str
    model_count: int | None = None
    tags: list[str] = Field(default_factory=list)


class GroupPlanningContext(BaseModel):
    """Complete context for GroupPlanner.

    Bundles all inputs needed for GroupPlanner to generate GroupPlan for a display group.

    This context object pattern:
    - Keeps API stable as new inputs are added
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

    # Phase 2 Output (MacroPlanner)
    macro_plan: MacroPlan = Field(description="Strategic plan from MacroPlanner")

    # Display Context
    display_group: DisplayGroupRef = Field(description="Display group being planned for")

    # Template Catalog
    available_templates: list[TemplateRef] = Field(
        default_factory=list,
        description="Available templates with metadata from catalog",
    )

    # Constraints
    max_layers: int = Field(default=3, ge=1, le=6)
    max_effects_per_section: int = Field(default=8, ge=1)
    allow_assets: bool = True
    allow_overlaps: bool = False

    # Future extensibility (commented out, not yet implemented):
    # template_catalog: TemplateCatalog | None = None  # Full catalog with presets
    # display_graph: DisplayGraph | None = None         # Complete display layout
    # user_preferences: UserPreferences | None = None   # User overrides

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

    @property
    def group_id(self) -> str:
        """Get group ID being planned for."""
        return self.display_group.group_id

    @property
    def group_type(self) -> str:
        """Get group type."""
        return self.display_group.group_type
