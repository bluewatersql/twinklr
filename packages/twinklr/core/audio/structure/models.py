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
