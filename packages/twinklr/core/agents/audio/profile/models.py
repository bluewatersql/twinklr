"""Pydantic models for AudioProfile agent."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Severity(StrEnum):
    """Issue severity levels."""

    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class Issue(BaseModel):
    """Validation or generation issue."""

    severity: Severity
    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable message")
    path: str | None = Field(description="JSONPath to field, or null")
    hint: str | None = Field(description="Suggestion for resolution, or null")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized.setdefault("path", None)
        normalized.setdefault("hint", None)
        return normalized


class Provenance(BaseModel):
    """Metadata about how output was generated."""

    provider_id: str = Field(description="LLM provider (e.g., 'openai')")

    model_id: str = Field(description="LLM model identifier")

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


class SongIdentity(BaseModel):
    """Basic song metadata and identity."""

    title: str | None = Field(description="Song title if available, or null")

    artist: str | None = Field(description="Artist name if available, or null")

    duration_ms: int = Field(gt=0, description="Song duration in milliseconds")

    bpm: float | None = Field(gt=0, lt=300, description="Beats per minute if detected, or null")

    key: str | None = Field(description="Musical key (e.g., 'C major', 'A minor'), or null")

    time_signature: str | None = Field(description="Time signature (e.g., '4/4', '3/4'), or null")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for key in ("title", "artist", "bpm", "key", "time_signature"):
            normalized.setdefault(key, None)
        return normalized

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

    section_id: str = Field(
        description=(
            "Unique section identifier — must be distinct across ALL sections "
            "(e.g., 'intro', 'chorus_1', 'chorus_2', 'verse_1', 'verse_2', 'break_1', 'outro'). "
            "Append _N suffix when a section type repeats."
        )
    )

    name: str = Field(
        description=(
            "Generic section type label (e.g., 'intro', 'verse', 'chorus', 'bridge', "
            "'instrumental', 'outro'). NOT the unique ID — use the same label for "
            "repeated types (both chorus_1 and chorus_2 have name='chorus')."
        )
    )

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

    model_config = ConfigDict(extra="forbid")


class MacroEnergy(StrEnum):
    """Overall energy level of song."""

    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"
    DYNAMIC = "DYNAMIC"


class EnergyPoint(BaseModel):
    """Point on energy curve."""

    t_ms: int = Field(ge=0, description="Timestamp in milliseconds")
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
        description="Section energy characteristics (e.g., 'building', 'drop', 'sustained', 'peak')",
    )

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized.setdefault("characteristics", [])
        return normalized

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
        max_length=10,
        description="Major energy peaks/climaxes across song (top 10 max)",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized.setdefault("peaks", [])
        return normalized


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

    notes: list[str] = Field(description="Additional notes about lyric data quality")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized.setdefault("notes", [])
        return normalized


class Contrast(StrEnum):
    """Visual contrast level."""

    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"


class MotionDensity(StrEnum):
    """Motion density level."""

    SPARSE = "SPARSE"
    MED = "MED"
    BUSY = "BUSY"


class AssetUsage(StrEnum):
    """Legacy asset-usage vocabulary retained for import compatibility."""

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

    palette_color_guidance: list[str] = Field(
        max_length=5,
        description="Color characteristic hints for palette selection (e.g., 'warm', 'cool', 'high-contrast', 'vibrant')",
    )

    cautions: list[str] = Field(
        description="Specific cautions for planners (e.g., 'avoid strobing', 'respect quiet sections')",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized.setdefault("palette_color_guidance", [])
        normalized.setdefault("cautions", [])
        return normalized


class SectionObjectives(BaseModel):
    """Objectives for one section without a free-form JSON object map."""

    section_id: str = Field(description="Section identifier")
    objectives: list[str] = Field(description="Planner objectives for the section")

    model_config = ConfigDict(extra="forbid", frozen=True)


class PlannerHints(BaseModel):
    """Specific hints for downstream planning agents."""

    section_objectives: list[SectionObjectives] = Field(
        description="Per-section objectives as strict key/value entries",
    )

    avoid_patterns: list[str] = Field(
        description="Patterns to avoid (e.g., 'repetitive pan/tilt', 'strobing in quiet sections')",
    )

    emphasize_groups: list[str] = Field(
        description="Fixture groups to emphasize (group IDs or names)",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        objectives = normalized.setdefault("section_objectives", [])
        if isinstance(objectives, dict):
            normalized["section_objectives"] = [
                {"section_id": section_id, "objectives": section_objectives}
                for section_id, section_objectives in objectives.items()
            ]
        normalized.setdefault("avoid_patterns", [])
        normalized.setdefault("emphasize_groups", [])
        return normalized


class AudioProfileModel(BaseModel):
    """Canonical song intent profile produced by AudioProfile agent.

    This is the primary output of the AudioProfile agent, providing
    a complete understanding of song characteristics for downstream
    planning agents.

    Framework metadata is deliberately excluded from this response model so the
    strict schema cannot contradict prompts about framework-populated fields.
    """

    warnings: list[Issue] = Field(
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

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized.setdefault("warnings", [])
        return normalized
