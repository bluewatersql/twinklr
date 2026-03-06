"""Pydantic models for active learning taxonomy review pipeline."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UncertaintySamplerOptions(BaseModel):
    """Configuration for uncertainty sampling."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )
    min_frequency_threshold: int = Field(default=3, ge=1)
    max_batch_size: int = Field(default=50, ge=1)
    include_unknown_families: bool = True
    include_unknown_motions: bool = True


class UncertaintyCandidate(BaseModel):
    """A taxonomy row selected for review due to high uncertainty."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    effect_type: str
    normalized_key: str
    current_family: str
    current_motion: str
    map_confidence: float = Field(ge=0.0, le=1.0)
    occurrence_count: int = Field(ge=1)
    uncertainty_score: float = Field(ge=0.0, le=1.0)
    uncertainty_reasons: tuple[str, ...]
    sample_phrase_ids: tuple[str, ...]


class ReviewItem(BaseModel):
    """A single item in a review batch with contextual information."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate: UncertaintyCandidate
    context_phrases: tuple[str, ...] = ()
    suggested_family: str | None = None
    suggested_motion: str | None = None
    suggestion_source: str | None = None


class ReviewBatch(BaseModel):
    """A batch of items ready for LLM or human review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_id: str
    items: tuple[ReviewItem, ...]
    total_candidates: int = Field(ge=0)


class TaxonomyCorrectionResult(BaseModel):
    """Result of LLM review for a single candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    original_family: str
    original_motion: str
    corrected_family: str | None = None
    corrected_motion: str | None = None
    correction_confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""
    approved: bool = False


class CorrectionRecord(BaseModel):
    """Historical record of an applied correction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    effect_type: str
    before_family: str
    before_motion: str
    after_family: str
    after_motion: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


class CorrectionReport(BaseModel):
    """Summary report after applying a batch of corrections."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1.0.0"
    total_candidates: int = Field(ge=0)
    total_approved: int = Field(ge=0)
    total_applied: int = Field(ge=0)
    corrections: tuple[CorrectionRecord, ...] = ()
    mean_confidence_before: float = Field(ge=0.0, le=1.0, default=0.0)
    mean_confidence_after: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence_uplift: float = 0.0
    unknown_ratio_before: float = Field(ge=0.0, le=1.0, default=0.0)
    unknown_ratio_after: float = Field(ge=0.0, le=1.0, default=0.0)
