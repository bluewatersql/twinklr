"""Pydantic models for song section detection.

These models provide type-safe data structures for section detection outputs
with validation and serialization support.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
        ...     novelty_l_beats=16,
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
    novelty_l_beats: int = Field(
        ..., ge=2, description="Half-kernel size for Foote novelty (larger = macro structure)"
    )
    peak_delta: float = Field(
        ..., ge=0.0, le=1.0, description="Peak-picking sensitivity (lower = more boundaries)"
    )
    pre_avg: int = Field(..., ge=1, description="Pre-smoothing window in beats")
    post_avg: int = Field(..., ge=1, description="Post-smoothing window in beats")

    @field_validator("max_sections")
    @classmethod
    def max_gte_min(cls, v: int, info) -> int:
        """Validate that max_sections >= min_sections."""
        if "min_sections" in info.data and v < info.data["min_sections"]:
            raise ValueError(
                f"max_sections ({v}) must be >= min_sections ({info.data['min_sections']})"
            )
        return v
