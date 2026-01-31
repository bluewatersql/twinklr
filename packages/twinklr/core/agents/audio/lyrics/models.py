"""Pydantic models for Lyrics agent."""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Severity(str, Enum):
    """Issue severity levels."""

    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class Issue(BaseModel):
    """Validation or generation issue."""

    severity: Severity
    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable message")
    path: str | None = Field(default=None, description="JSONPath to field")
    hint: str | None = Field(default=None, description="Suggestion for resolution")

    model_config = ConfigDict(extra="forbid", frozen=True)


class Provenance(BaseModel):
    """Metadata about how output was generated."""

    provider_id: str = Field(description="LLM provider (e.g., 'openai')")

    model_id: str = Field(description="LLM model (e.g., 'gpt-5.2')")

    prompt_pack: str = Field(description="Prompt pack ID used")

    prompt_pack_version: str = Field(description="Prompt pack version")

    framework_version: str = Field(description="Agent framework version")

    seed: int | None = Field(default=None, description="Random seed if deterministic")

    temperature: float = Field(description="LLM temperature used")

    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO timestamp of creation",
    )

    model_config = ConfigDict(extra="forbid", frozen=True)


class StoryBeat(BaseModel):
    """Narrative moment aligned to song structure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str = Field(description="Song section identifier (e.g., 'verse_1', 'chorus')")

    timestamp_range: tuple[int, int] = Field(
        description="Time range in milliseconds (start_ms, end_ms)"
    )

    beat_type: str = Field(
        description="Narrative type: 'setup' | 'conflict' | 'climax' | 'resolution' | 'coda'"
    )

    description: str = Field(
        min_length=10, description="What happens in this narrative moment (song-specific)"
    )

    visual_opportunity: str = Field(
        min_length=10, description="Choreography hint for this story beat"
    )

    @field_validator("timestamp_range")
    @classmethod
    def validate_timestamp_range(cls, v: tuple[int, int]) -> tuple[int, int]:
        """Validate timestamp range is valid."""
        start_ms, end_ms = v
        if start_ms < 0:
            raise ValueError("start_ms must be non-negative")
        if end_ms <= start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        if end_ms - start_ms < 100:  # At least 100ms
            raise ValueError("Story beat must be at least 100ms long")
        return v

    @field_validator("beat_type")
    @classmethod
    def validate_beat_type(cls, v: str) -> str:
        """Validate beat type is from allowed values."""
        allowed = {"setup", "conflict", "climax", "resolution", "coda"}
        if v not in allowed:
            raise ValueError(f"beat_type must be one of {allowed}, got '{v}'")
        return v


class KeyPhrase(BaseModel):
    """Memorable lyric phrase with visual potential."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(min_length=1, description="Exact lyric phrase (verbatim)")

    timestamp_ms: int = Field(ge=0, description="Phrase start time in milliseconds")

    section_id: str = Field(description="Song section identifier")

    visual_hint: str = Field(
        min_length=5, description="Specific choreography suggestion for this phrase"
    )

    emphasis: str = Field(
        default="MED", description="Visual emphasis level: 'LOW' | 'MED' | 'HIGH'"
    )

    @field_validator("emphasis")
    @classmethod
    def validate_emphasis(cls, v: str) -> str:
        """Validate emphasis is from allowed values."""
        allowed = {"LOW", "MED", "HIGH"}
        if v not in allowed:
            raise ValueError(f"emphasis must be one of {allowed}, got '{v}'")
        return v


class SilentSection(BaseModel):
    """Instrumental section without lyrics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_ms: int = Field(ge=0, description="Section start time in milliseconds")

    end_ms: int = Field(gt=0, description="Section end time in milliseconds")

    duration_ms: int = Field(gt=0, description="Section duration in milliseconds")

    section_id: str | None = Field(default=None, description="Optional section identifier")

    @field_validator("end_ms")
    @classmethod
    def validate_end_ms(cls, v: int, info) -> int:
        """Validate end_ms is after start_ms."""
        start_ms = info.data.get("start_ms")
        if start_ms is not None and v <= start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return v

    @field_validator("duration_ms")
    @classmethod
    def validate_duration_ms(cls, v: int, info) -> int:
        """Validate duration_ms matches end_ms - start_ms."""
        start_ms = info.data.get("start_ms")
        end_ms = info.data.get("end_ms")
        if start_ms is not None and end_ms is not None:
            expected = end_ms - start_ms
            if v != expected:
                raise ValueError(
                    f"duration_ms must equal end_ms - start_ms, got {v}, expected {expected}"
                )
        return v


class LyricContextModel(BaseModel):
    """Narrative and thematic context from song lyrics.

    Output of the Lyrics agent (Phase 1) providing narrative, thematic, and visual
    context from song lyrics for choreography planning.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(description="Unique identifier for this agent run")

    # Core Analysis
    has_lyrics: bool = Field(description="Whether lyrics were available for analysis")

    themes: list[str] = Field(
        default_factory=list,
        description="Major themes (2-5 items, e.g., ['redemption', 'celebration'])",
    )

    mood_arc: str = Field(
        default="neutral", description="Emotional trajectory (e.g., 'melancholic → hopeful')"
    )

    genre_markers: list[str] = Field(
        default_factory=list,
        description="Genre/context markers (e.g., ['Christmas', 'gospel'])",
    )

    # Narrative (if applicable)
    has_narrative: bool = Field(default=False, description="Whether song has clear narrative")

    characters: list[str] | None = Field(
        default=None, description="Named characters or personas in the song"
    )

    story_beats: list[StoryBeat] | None = Field(
        default=None, description="Key narrative moments aligned to song structure"
    )

    # Visual Hooks
    key_phrases: list[KeyPhrase] = Field(
        default_factory=list, description="Memorable moments (5-10 items)"
    )

    recommended_visual_themes: list[str] = Field(
        default_factory=list, description="Visual design recommendations (3-5 items)"
    )

    # Density & Coverage
    lyric_density: str = Field(
        default="MED", description="Lyric pacing: 'SPARSE' | 'MED' | 'DENSE'"
    )

    vocal_coverage_pct: float = Field(
        ge=0.0, le=1.0, description="Percentage of song with vocals (0.0-1.0)"
    )

    silent_sections: list[SilentSection] = Field(
        default_factory=list, description="Instrumental sections without lyrics"
    )

    # Metadata
    provenance: Provenance | None = Field(
        default=None, description="Generation metadata (framework-injected)"
    )

    warnings: list[Issue] = Field(default_factory=list, description="Analysis warnings")

    @field_validator("themes")
    @classmethod
    def validate_themes(cls, v: list[str]) -> list[str]:
        """Validate themes count."""
        if v and (len(v) < 2 or len(v) > 5):
            raise ValueError(f"themes must contain 2-5 items, got {len(v)}")
        return v

    @field_validator("key_phrases")
    @classmethod
    def validate_key_phrases(cls, v: list[KeyPhrase]) -> list[KeyPhrase]:
        """Validate key phrases count."""
        if v and (len(v) < 5 or len(v) > 10):
            raise ValueError(f"key_phrases must contain 5-10 items, got {len(v)}")
        return v

    @field_validator("recommended_visual_themes")
    @classmethod
    def validate_visual_themes(cls, v: list[str]) -> list[str]:
        """Validate visual themes count."""
        if v and (len(v) < 3 or len(v) > 5):
            raise ValueError(f"recommended_visual_themes must contain 3-5 items, got {len(v)}")
        return v

    @field_validator("lyric_density")
    @classmethod
    def validate_lyric_density(cls, v: str) -> str:
        """Validate lyric density is from allowed values."""
        allowed = {"SPARSE", "MED", "DENSE"}
        if v not in allowed:
            raise ValueError(f"lyric_density must be one of {allowed}, got '{v}'")
        return v
