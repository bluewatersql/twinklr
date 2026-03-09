"""Pydantic contracts for the recipe_builder subsystem.

Defines catalog analysis, opportunity identification, recipe generation,
validation, admission, and run manifest models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.templates.group.recipe import EffectRecipe

SCHEMA_VERSION = "2.0.0"


# ---------------------------------------------------------------------------
# Catalog analysis
# ---------------------------------------------------------------------------


class DistributionEntry(BaseModel):
    """A single entry in a distribution histogram."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    count: int = 0
    percentage: float = Field(default=0.0, ge=0.0, le=100.0)


class CatalogAnalysis(BaseModel):
    """Comprehensive analysis of the existing recipe catalog.

    Captures distributions across every dimension of the recipe schema
    to identify gaps, overrepresentation, and creative opportunities.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    generated_at: datetime
    total_recipes: int = 0

    effect_type_distribution: list[DistributionEntry] = Field(default_factory=list)
    energy_distribution: list[DistributionEntry] = Field(default_factory=list)
    template_type_distribution: list[DistributionEntry] = Field(default_factory=list)
    motion_verb_usage: list[DistributionEntry] = Field(default_factory=list)
    visual_intent_distribution: list[DistributionEntry] = Field(default_factory=list)
    color_mode_distribution: list[DistributionEntry] = Field(default_factory=list)
    layer_count_distribution: list[DistributionEntry] = Field(default_factory=list)
    effect_family_distribution: list[DistributionEntry] = Field(default_factory=list)

    underutilized_effects: list[str] = Field(default_factory=list)
    underutilized_motions: list[str] = Field(default_factory=list)
    missing_energy_combos: list[str] = Field(
        default_factory=list,
        description="effect_type × energy combinations with zero recipes",
    )

    summary: str = ""


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------


class Opportunity(BaseModel):
    """A specific creative opportunity identified from catalog analysis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_id: str
    category: Literal[
        "missing_effect_type",
        "missing_energy_variant",
        "underutilized_motion",
        "missing_template_type",
        "low_layer_diversity",
        "missing_visual_intent",
        "general_diversity",
    ]
    description: str
    priority: float = Field(ge=0.0, le=1.0)
    target_effect_type: str | None = None
    target_energy: str | None = None
    target_template_type: str | None = None
    target_motions: list[str] = Field(default_factory=list)
    context: str = ""


# ---------------------------------------------------------------------------
# Recipe candidates
# ---------------------------------------------------------------------------


class RecipeCandidate(BaseModel):
    """A newly generated EffectRecipe candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SCHEMA_VERSION
    candidate_id: str
    source_opportunity_id: str
    recipe: EffectRecipe
    generation_mode: Literal["llm", "deterministic"] = "llm"
    rationale: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class RecipeCandidateCollection(BaseModel):
    """Persisted collection of generated recipe candidates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    candidates: list[RecipeCandidate] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Metadata enrichment
# ---------------------------------------------------------------------------


class MetadataEnrichmentCandidate(BaseModel):
    """Staged metadata-only update for an existing recipe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SCHEMA_VERSION
    candidate_id: str
    target_recipe_id: str
    proposed_metadata_patch: dict[str, Any]
    rationale: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class MetadataEnrichmentCollection(BaseModel):
    """Persisted collection of metadata enrichment candidates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    candidates: list[MetadataEnrichmentCandidate] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class ValidationIssue(BaseModel):
    """One validation finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: Literal["error", "warning", "info"]
    check_name: str
    message: str
    subject_id: str


class CandidateValidationResult(BaseModel):
    """Validation result for a single candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    issues: list[ValidationIssue] = Field(default_factory=list)
    passed: bool = True


class ValidationReport(BaseModel):
    """Aggregate deterministic validation outcomes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    recipe_candidate_results: list[CandidateValidationResult] = Field(
        default_factory=list,
    )
    metadata_candidate_results: list[CandidateValidationResult] = Field(
        default_factory=list,
    )
    issue_counts: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Admission
# ---------------------------------------------------------------------------

AdmissionDecisionType = Literal["accepted_to_stage", "review_required", "rejected"]


class AdmissionDecision(BaseModel):
    """One staged admission outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_id: str
    decision: AdmissionDecisionType
    reasons: list[str] = Field(default_factory=list)


class AdmissionReport(BaseModel):
    """Aggregate admission decisions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    decisions: list[AdmissionDecision] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Staged metadata patches
# ---------------------------------------------------------------------------


class StagedMetadataPatch(BaseModel):
    """One staged metadata patch for an existing recipe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    target_recipe_id: str
    decision: AdmissionDecisionType
    patch: dict[str, Any]
    reasons: list[str] = Field(default_factory=list)


class StagedMetadataPatchCollection(BaseModel):
    """Persisted staged metadata patches."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    patches: list[StagedMetadataPatch] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Run manifest
# ---------------------------------------------------------------------------


class PhaseStatus(BaseModel):
    """Status of a single pipeline phase."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    phase: str
    status: Literal["completed", "skipped", "failed", "not_started"] = "not_started"
    error: str | None = None


class PromotionResult(BaseModel):
    """Outcome of promoting staged recipes into the template catalog."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    promoted: int = 0
    skipped: int = 0
    promoted_ids: list[str] = Field(default_factory=list)
    skipped_ids: list[str] = Field(default_factory=list)


class SummaryMetrics(BaseModel):
    """Summary metrics for a pipeline run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_recipes_in_catalog: int = 0
    opportunities_identified: int = 0
    recipe_candidates_generated: int = 0
    metadata_candidates_generated: int = 0
    validation_errors: int = 0
    validation_warnings: int = 0
    accepted_to_stage: int = 0
    review_required: int = 0
    rejected: int = 0


class RunManifest(BaseModel):
    """Source of truth for one recipe_builder run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SCHEMA_VERSION
    run_name: str
    started_at: datetime
    completed_at: datetime | None = None
    input_paths: dict[str, str] = Field(default_factory=dict)
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    phase_status: list[PhaseStatus] = Field(default_factory=list)
    summary_metrics: SummaryMetrics = Field(default_factory=SummaryMetrics)
