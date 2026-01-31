"""Pydantic models for song section detection.

These models provide type-safe data structures for section detection outputs
with validation and serialization support.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Valid section labels
SectionLabel = Literal[
    "intro",
    "verse",
    "pre_chorus",
    "chorus",
    "post_chorus",
    "bridge",
    "break",
    "outro",
]


class Section(BaseModel):
    """A song section with semantic label and descriptors.

    Represents a contiguous time segment of a song with a functional label
    (e.g., chorus, verse) and associated audio descriptors.

    Examples:
        >>> section = Section(
        ...     section_id=0,
        ...     start_s=0.0,
        ...     end_s=15.5,
        ...     label="intro",
        ...     confidence=0.85,
        ...     energy=0.3,
        ...     repetition=0.2,
        ... )
        >>> section.duration_s
        15.5
    """

    model_config = ConfigDict(frozen=True)

    section_id: int = Field(..., ge=0, description="Section index (0-based)")
    start_s: float = Field(..., ge=0.0, description="Start time in seconds")
    end_s: float = Field(..., gt=0.0, description="End time in seconds")
    label: SectionLabel = Field(..., description="Functional section label")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Label confidence score [0..1]"
    )

    # Audio descriptors (normalized [0, 1])
    energy: float = Field(..., ge=0.0, le=1.0, description="RMS energy level")
    repetition: float = Field(..., ge=0.0, le=1.0, description="Similarity to other sections")
    vocal_density: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Proportion of time with vocals"
    )
    harmonic_complexity: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Chord change density"
    )

    # Context flags
    has_drop: bool = Field(default=False, description="Overlaps with energy drop")
    has_build: bool = Field(default=False, description="Overlaps with energy build")

    @field_validator("end_s")
    @classmethod
    def end_after_start(cls, v: float, info) -> float:
        """Validate that end_s > start_s."""
        if "start_s" in info.data and v <= info.data["start_s"]:
            raise ValueError(f"end_s ({v}) must be greater than start_s ({info.data['start_s']})")
        return v

    @property
    def duration_s(self) -> float:
        """Section duration in seconds."""
        return self.end_s - self.start_s


class SectionDiagnostics(BaseModel):
    """Diagnostic data for debugging and visualization.

    Contains detailed timing information and feature curves aligned to the beat grid.
    Useful for understanding why sections were detected at specific boundaries.

    Examples:
        >>> diagnostics = SectionDiagnostics(
        ...     tempo_bpm=120.0,
        ...     beat_times_s=[0.0, 0.5, 1.0, 1.5],
        ...     duration_s=30.0,
        ...     novelty=[0.1, 0.8, 0.3, 0.2],
        ...     repetition=[0.5, 0.6, 0.7, 0.6],
        ...     rms=[0.4, 0.5, 0.6, 0.5],
        ...     onset=[0.3, 0.7, 0.4, 0.3],
        ...     boundary_beats=[0, 2],
        ...     boundary_strengths=[1.0, 0.8],
        ... )
    """

    model_config = ConfigDict(frozen=True)

    # Timing information
    tempo_bpm: float = Field(..., gt=0.0, description="Detected tempo")
    beat_times_s: list[float] = Field(..., min_length=1, description="Beat times in seconds")
    bar_times_s: list[float] | None = Field(
        default=None, description="Downbeat/bar times in seconds"
    )
    duration_s: float = Field(..., gt=0.0, description="Total audio duration")

    # Feature curves (aligned to beat grid, length = num_beats)
    novelty: list[float] = Field(..., description="Novelty curve [0..1] per beat")
    repetition: list[float] = Field(..., description="Repetition score [0..1] per beat")
    rms: list[float] = Field(..., description="Beat-sync RMS energy")
    onset: list[float] = Field(..., description="Beat-sync onset strength")

    # Boundary information
    boundary_beats: list[int] = Field(..., description="Boundary indices on beat grid")
    boundary_strengths: list[float] = Field(..., description="Novelty strength at each boundary")

    # Optional: Full SSM for visualization
    ssm: list[list[float]] | None = Field(
        default=None, description="Self-similarity matrix (num_beats x num_beats)"
    )

    @field_validator("novelty", "repetition", "rms", "onset")
    @classmethod
    def check_curve_length(cls, v: list[float], info) -> list[float]:
        """Validate that curves have same length as beat grid."""
        if "beat_times_s" in info.data:
            expected_len = len(info.data["beat_times_s"])
            if len(v) != expected_len:
                raise ValueError(
                    f"Curve length ({len(v)}) must match beat grid length ({expected_len})"
                )
        return v


class SectioningPreset(BaseModel):
    """Genre-specific parameters for section detection.

    Controls the sensitivity and behavior of the section detection algorithm.
    Different genres require different tuning (e.g., EDM needs longer minimum
    section lengths to avoid micro-segmentation of drops).

    Examples:
        >>> preset = SectioningPreset(
        ...     genre="edm",
        ...     min_sections=12,
        ...     max_sections=18,
        ...     min_len_beats=16,
        ...     novelty_L_beats=16,
        ...     peak_delta=0.07,
        ... )
    """

    model_config = ConfigDict(frozen=True)

    genre: str = Field(..., description="Genre name (edm, pop, country, christmas, etc.)")

    # Section count control
    min_sections: int = Field(..., ge=2, le=50, description="Minimum number of sections")
    max_sections: int = Field(..., ge=2, le=50, description="Maximum number of sections")
    min_len_beats: int = Field(
        ..., ge=1, description="Minimum section length in beats (prevents micro-segments)"
    )

    # Novelty detection parameters
    novelty_L_beats: int = Field(
        ..., ge=2, description="Half-kernel size for Foote novelty (larger = macro structure)"
    )
    peak_delta: float = Field(
        ..., ge=0.0, le=1.0, description="Peak-picking sensitivity (lower = more boundaries)"
    )
    pre_avg: int = Field(..., ge=1, description="Pre-smoothing window in beats")
    post_avg: int = Field(..., ge=1, description="Post-smoothing window in beats")

    # Context weights (how much to trust external context)
    context_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "drops_weight": 0.5,
            "builds_weight": 0.4,
            "vocals_weight": 0.5,
            "chords_weight": 0.3,
        },
        description="Weights for context enhancement (0=ignore, 1=trust fully)",
    )

    @field_validator("max_sections")
    @classmethod
    def max_gte_min(cls, v: int, info) -> int:
        """Validate that max_sections >= min_sections."""
        if "min_sections" in info.data and v < info.data["min_sections"]:
            raise ValueError(
                f"max_sections ({v}) must be >= min_sections ({info.data['min_sections']})"
            )
        return v

    @field_validator("context_weights")
    @classmethod
    def validate_weights(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate that weights are in [0, 1]."""
        for key, weight in v.items():
            if not 0.0 <= weight <= 1.0:
                raise ValueError(f"Weight '{key}' must be in [0, 1], got {weight}")
        return v
