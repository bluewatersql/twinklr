"""Offline recipe_builder subsystem.

Analyzes the existing recipe catalog for gaps and creative opportunities,
generates new EffectRecipe candidates via LLM (or deterministic fallback),
enriches existing recipe metadata, and stages outputs for manual review.
The live library is never modified by this package.
"""

from twinklr.core.recipe_builder.models import (
    AdmissionDecision,
    AdmissionReport,
    CatalogAnalysis,
    DistributionEntry,
    MetadataEnrichmentCandidate,
    Opportunity,
    RecipeCandidate,
    RunManifest,
    ValidationIssue,
    ValidationReport,
)

__all__ = [
    "AdmissionDecision",
    "AdmissionReport",
    "CatalogAnalysis",
    "DistributionEntry",
    "MetadataEnrichmentCandidate",
    "Opportunity",
    "RecipeCandidate",
    "RunManifest",
    "ValidationIssue",
    "ValidationReport",
]
