"""Effect metadata profile models.

Corpus-derived per-family metadata profiles that enrich the flat 6-axis
classification with duration distributions, common parameter combinations,
model-type affinities, layering behavior, and section placement patterns.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DurationDistribution(BaseModel):
    """Duration statistics for an effect family."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    p10_ms: int = Field(description="10th percentile duration in ms")
    p25_ms: int = Field(description="25th percentile duration in ms")
    p50_ms: int = Field(description="50th percentile (median) duration in ms")
    p75_ms: int = Field(description="75th percentile duration in ms")
    p90_ms: int = Field(description="90th percentile duration in ms")
    mean_ms: float = Field(description="Mean duration in ms")
    min_ms: int = Field(description="Minimum duration in ms")
    max_ms: int = Field(description="Maximum duration in ms")
    sample_count: int = Field(ge=0, description="Number of phrases sampled")


class ParamFrequency(BaseModel):
    """Most common value for a preserved parameter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    param_name: str = Field(description="Parameter name")
    value: str | float | int | bool = Field(description="Parameter value")
    frequency: float = Field(ge=0.0, le=1.0, description="Fraction of phrases with this value")
    corpus_count: int = Field(ge=0, description="Number of phrases with this value")


class ParamProfile(BaseModel):
    """Parameter distribution for an effect family."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    param_name: str = Field(description="Parameter name")
    distinct_value_count: int = Field(ge=0, description="Number of distinct values")
    top_values: tuple[ParamFrequency, ...] = Field(description="Top 5 most common values")


class LayeringBehavior(BaseModel):
    """How this family participates in stacks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    typical_layer_role: str = Field(description="Most common role (BASE, RHYTHM, ACCENT, etc.)")
    role_distribution: dict[str, float] = Field(description="Role -> fraction mapping")
    common_partners: tuple[str, ...] = Field(description="Effect families often stacked with")
    mean_stack_position: float = Field(description="Average layer_index when in stack (0=bottom)")
    solo_ratio: float = Field(ge=0.0, le=1.0, description="Fraction appearing as single-layer")


class SectionPlacement(BaseModel):
    """Section placement distribution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_distribution: dict[str, float] = Field(description="section_label -> fraction")
    preferred_sections: tuple[str, ...] = Field(description="Top 3 sections by frequency")


class EffectMetadataProfile(BaseModel):
    """Corpus-derived metadata profile for one effect family."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    effect_family: str = Field(description="Effect family identifier")
    corpus_phrase_count: int = Field(ge=0, description="Total phrases in family")
    corpus_sequence_count: int = Field(ge=0, description="Distinct sequences containing family")
    duration: DurationDistribution = Field(description="Duration statistics")
    classification: dict[str, str] = Field(description="Axis -> modal value (most common)")
    classification_distribution: dict[str, dict[str, float]] = Field(
        description="Axis -> value -> fraction"
    )
    top_params: tuple[ParamProfile, ...] = Field(
        description="Top parameter profiles from preserved_params"
    )
    model_affinities: tuple[str, ...] = Field(
        description="Top model types from propensity, sorted by frequency"
    )
    layering: LayeringBehavior = Field(description="Layering behavior profile")
    section_placement: SectionPlacement = Field(description="Section placement distribution")


class EffectMetadataProfiles(BaseModel):
    """Collection of all per-family profiles."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="v1.0.0")
    profile_count: int = Field(ge=0, description="Number of family profiles")
    total_phrase_count: int = Field(ge=0, description="Total phrases across all families")
    profiles: tuple[EffectMetadataProfile, ...] = Field(description="Per-family metadata profiles")
