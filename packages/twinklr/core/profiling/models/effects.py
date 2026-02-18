"""Effect statistics and parameter profiling models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from twinklr.core.profiling.models.enums import ParameterValueType


class NumericValueProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    min: float
    max: float
    avg: float
    median: float


class CategoricalValueProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    distinct_values: tuple[str, ...]
    distinct_count: int

    @model_validator(mode="after")
    def validate_distinct_count(self) -> CategoricalValueProfile:
        if self.distinct_count != len(self.distinct_values):
            raise ValueError("distinct_count must equal len(distinct_values)")
        return self


class ParameterProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: ParameterValueType
    count: int
    numeric_profile: NumericValueProfile | None = None
    categorical_profile: CategoricalValueProfile | None = None


class DurationStats(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    count: int
    min_ms: int
    max_ms: int
    avg_ms: float
    median_ms: float


class EffectTypeProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    instance_count: int
    duration_stats: DurationStats
    buffer_styles: tuple[str, ...]
    parameter_names: tuple[str, ...]
    parameters: dict[str, ParameterProfile]


class EffectStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total_events: int
    distinct_effect_types: int
    total_effect_duration_ms: int
    avg_effect_duration_ms: float
    total_targets_with_effects: int
    effect_type_counts: dict[str, int]
    effect_type_durations_ms: dict[str, int]
    effect_type_profiles: dict[str, EffectTypeProfile]
    effects_per_target: dict[str, int]
    layers_per_target: dict[str, int]
