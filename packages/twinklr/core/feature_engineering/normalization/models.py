"""Pydantic models for unknown effect normalization artifacts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UnknownEffectEntry(BaseModel):
    """A single unknown effect type with contextual metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    effect_type: str
    normalized_key: str
    count: int
    sample_params: tuple[dict[str, Any], ...] = ()
    context_text: str


class UnknownEffectCorpus(BaseModel):
    """Structured corpus of unknown effect entries for embedding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1.0.0"
    entries: tuple[UnknownEffectEntry, ...]
    total_unknown_phrases: int
    unknown_effect_family_ratio: float
    unknown_motion_ratio: float


class AliasClusterGroup(BaseModel):
    """A cluster of effect names suspected to be aliases."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cluster_id: str
    members: tuple[str, ...]
    member_counts: tuple[int, ...]
    centroid_similarity: float = Field(ge=0.0, le=1.0)
    suggested_canonical: str


class AliasReviewResult(BaseModel):
    """LLM review verdict for an alias cluster."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cluster_id: str
    approved: bool
    canonical_label: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    members: tuple[str, ...]
    suggested_effect_family: str | None = None
    suggested_motion_class: str | None = None


class ResolvedEffect(BaseModel):
    """A resolved mapping from unknown effect type to canonical name."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    original_effect_type: str
    canonical_name: str
    effect_family: str | None = None
    motion_class: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class AliasClusteringOptions(BaseModel):
    """Configuration for alias clustering."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_cluster_size: int = 2
    min_similarity: float = 0.75
    method: str = "agglomerative"


class TaxonomyRulePatch(BaseModel):
    """A suggested addition to the taxonomy rule config."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    effect_type: str
    canonical_name: str
    effect_family: str | None = None
    motion_class: str | None = None
    source_cluster_id: str
    confidence: float = Field(ge=0.0, le=1.0)
