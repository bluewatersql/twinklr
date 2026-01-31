"""Pydantic models for AudioProfile agent."""

from datetime import datetime
from enum import Enum
from typing import Any

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
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO timestamp of creation",
    )

    model_config = ConfigDict(extra="forbid", frozen=True)


class SongIdentity(BaseModel):
    """Basic song metadata and identity."""

    title: str | None = Field(default=None, description="Song title if available")

    artist: str | None = Field(default=None, description="Artist name if available")

    duration_ms: int = Field(gt=0, description="Song duration in milliseconds")

    bpm: float | None = Field(
        default=None, gt=0, lt=300, description="Beats per minute if detected"
    )

    key: str | None = Field(default=None, description="Musical key (e.g., 'C major', 'A minor')")

    time_signature: str | None = Field(
        default=None, description="Time signature (e.g., '4/4', '3/4')"
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("duration_ms")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        """Validate duration is within reasonable bounds."""
        if v < 1000:  # Less than 1 second
            raise ValueError("Duration too short (< 1s)")
        if v > 1800000:  # More than 30 minutes
            raise ValueError("Duration too long (> 30min)")
        return v


class SongSectionRef(BaseModel):
    """Reference to a song section with timing."""

    section_id: str = Field(description="Unique section identifier")

    name: str = Field(description="Section name (e.g., 'verse_1', 'chorus', 'bridge')")

    start_ms: int = Field(ge=0, description="Section start time in milliseconds")

    end_ms: int = Field(gt=0, description="Section end time in milliseconds")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("end_ms")
    @classmethod
    def validate_end_after_start(cls, v: int, info: Any) -> int:
        """Validate end_ms is greater than start_ms."""
        start_ms = info.data.get("start_ms")
        if start_ms is not None and v <= start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return v


class Structure(BaseModel):
    """Song structure with sections."""

    sections: list[SongSectionRef] = Field(
        min_length=1, description="List of song sections in temporal order"
    )

    structure_confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in structure analysis (0-1)"
    )

    notes: list[str] = Field(default_factory=list, description="Additional notes about structure")

    model_config = ConfigDict(extra="forbid")


class MacroEnergy(str, Enum):
    """Overall energy level of song."""

    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"
    DYNAMIC = "DYNAMIC"


class EnergyPoint(BaseModel):
    """Point on energy curve."""

    t_ms: int = Field(ge=0, description="Timestamp in milliseconds")
    energy_0_1: float = Field(ge=0.0, le=1.0, description="Energy value 0-1")

    model_config = ConfigDict(extra="forbid", frozen=True)


class EnergyPeak(BaseModel):
    """Energy peak or climax."""

    start_ms: int = Field(ge=0, description="Peak start time")
    end_ms: int = Field(gt=0, description="Peak end time")
    energy: float = Field(ge=0.0, le=1.0, description="Peak energy level")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("end_ms")
    @classmethod
    def validate_end_after_start(cls, v: int, info: Any) -> int:
        """Validate end_ms is greater than start_ms."""
        start_ms = info.data.get("start_ms")
        if start_ms is not None and v <= start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return v


class SectionEnergyProfile(BaseModel):
    """Energy profile for a single section with preserved intra-section dynamics."""

    section_id: str = Field(description="Section identifier (matches SongSectionRef.section_id)")

    start_ms: int = Field(ge=0, description="Section start time")

    end_ms: int = Field(gt=0, description="Section end time")

    energy_curve: list[EnergyPoint] = Field(
        min_length=3,
        max_length=15,
        description="Energy curve for this section (5-10 points typical, preserves shape)",
    )

    mean_energy: float = Field(ge=0.0, le=1.0, description="Average energy across section")

    peak_energy: float = Field(ge=0.0, le=1.0, description="Maximum energy in section")

    characteristics: list[str] = Field(
        default_factory=list,
        description="Section energy characteristics (e.g., 'building', 'drop', 'sustained', 'peak')",
    )

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("end_ms")
    @classmethod
    def validate_end_after_start(cls, v: int, info: Any) -> int:
        """Validate end_ms is greater than start_ms."""
        start_ms = info.data.get("start_ms")
        if start_ms is not None and v <= start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return v


class EnergyProfile(BaseModel):
    """Song energy characteristics with per-section fidelity.

    Per-section downsampling preserves intra-section dynamics (builds, drops, peaks)
    which are critical for choreography planning. Each section gets 5-10 curve points
    maintaining shape while achieving 10-15x token reduction vs. raw timeline.
    """

    macro_energy: MacroEnergy = Field(description="Overall energy level classification")

    section_profiles: list[SectionEnergyProfile] = Field(
        min_length=1,
        description="Per-section energy curves preserving intra-section dynamics",
    )

    peaks: list[EnergyPeak] = Field(
        default_factory=list,
        max_length=10,
        description="Major energy peaks/climaxes across song (top 10 max)",
    )

    overall_mean: float = Field(ge=0.0, le=1.0, description="Mean energy across entire song")

    energy_confidence: float = Field(ge=0.0, le=1.0, description="Confidence in energy analysis")

    model_config = ConfigDict(extra="forbid")


class LyricProfile(BaseModel):
    """Lyrics and phoneme data availability."""

    has_plain_lyrics: bool = Field(description="Whether plain text lyrics available")

    has_timed_words: bool = Field(
        description="Whether word-level timing available (e.g., from LRC)"
    )

    has_phonemes: bool = Field(description="Whether phoneme-level timing available")

    lyric_confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in lyric detection/extraction"
    )

    phoneme_confidence: float = Field(ge=0.0, le=1.0, description="Confidence in phoneme timing")

    notes: list[str] = Field(
        default_factory=list, description="Additional notes about lyric data quality"
    )

    model_config = ConfigDict(extra="forbid")


class Contrast(str, Enum):
    """Visual contrast level."""

    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"


class MotionDensity(str, Enum):
    """Motion density level."""

    SPARSE = "SPARSE"
    MED = "MED"
    BUSY = "BUSY"


class AssetUsage(str, Enum):
    """Asset usage recommendation."""

    NONE = "NONE"
    SPARSE = "SPARSE"
    HEAVY = "HEAVY"


class CreativeGuidance(BaseModel):
    """High-level creative recommendations for planners."""

    recommended_layer_count: int = Field(
        ge=1, le=3, description="Recommended number of choreography layers"
    )

    recommended_contrast: Contrast = Field(description="Recommended visual contrast level")

    recommended_motion_density: MotionDensity = Field(
        description="Recommended motion density/business"
    )

    recommended_asset_usage: AssetUsage = Field(
        description="Recommended asset (images/shaders) usage level"
    )

    recommended_color_story: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Recommended color palette themes (e.g., 'warm', 'cool', 'vibrant')",
    )

    cautions: list[str] = Field(
        default_factory=list,
        description="Specific cautions for planners (e.g., 'avoid strobing', 'respect quiet sections')",
    )

    model_config = ConfigDict(extra="forbid")


class PlannerHints(BaseModel):
    """Specific hints for downstream planning agents."""

    section_objectives: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Per-section objectives (section_id → list of objectives)",
    )

    avoid_patterns: list[str] = Field(
        default_factory=list,
        description="Patterns to avoid (e.g., 'repetitive pan/tilt', 'strobing in quiet sections')",
    )

    emphasize_groups: list[str] = Field(
        default_factory=list,
        description="Fixture groups to emphasize (group IDs or names)",
    )

    model_config = ConfigDict(extra="forbid")


class AudioProfileModel(BaseModel):
    """Canonical song intent profile produced by AudioProfile agent.

    This is the primary output of the AudioProfile agent, providing
    a complete understanding of song characteristics for downstream
    planning agents.

    NOTE: provenance is injected by the framework after LLM generation,
    not generated by the LLM itself.
    """

    # Metadata
    schema_version: str = Field(
        default="2.0", description="Schema version for compatibility tracking"
    )

    agent_id: str = Field(
        default="audio_profile.v2", description="Agent that produced this profile"
    )

    run_id: str = Field(description="Unique identifier for this agent run")

    provenance: Provenance | None = Field(
        default=None,
        description="Metadata about how this profile was generated (injected by framework after LLM generation)",
    )

    warnings: list[Issue] = Field(
        default_factory=list,
        description="Non-fatal issues encountered during generation",
    )

    # Core Profile Data (placeholders for now, will be typed properly in later tasks)
    song_identity: SongIdentity = Field(description="Basic song metadata and identity")

    structure: Structure = Field(description="Song structure with sections and confidence")

    energy_profile: EnergyProfile = Field(description="Energy characteristics and dynamics")

    lyric_profile: LyricProfile = Field(description="Lyrics and phoneme data availability")

    creative_guidance: CreativeGuidance = Field(description="High-level creative recommendations")

    planner_hints: PlannerHints = Field(description="Specific hints for downstream planners")

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        frozen=False,
    )
