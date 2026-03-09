"""Staging-only admission decisions."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from twinklr.core.recipe_builder.models import (
    AdmissionDecision,
    AdmissionReport,
    CandidateValidationResult,
    MetadataEnrichmentCandidate,
    RecipeCandidate,
    StagedMetadataPatch,
    StagedMetadataPatchCollection,
    ValidationReport,
)

logger = logging.getLogger(__name__)


def _classify_decision(result: CandidateValidationResult) -> AdmissionDecision:
    errors = [i for i in result.issues if i.severity == "error"]
    warnings = [i for i in result.issues if i.severity == "warning"]

    if errors:
        return AdmissionDecision(
            subject_id=result.candidate_id,
            decision="rejected",
            reasons=[i.message for i in errors],
        )
    if warnings:
        return AdmissionDecision(
            subject_id=result.candidate_id,
            decision="review_required",
            reasons=[i.message for i in warnings],
        )
    return AdmissionDecision(
        subject_id=result.candidate_id,
        decision="accepted_to_stage",
        reasons=["Passed all validation checks"],
    )


def _get_decision_for(candidate_id: str, report: AdmissionReport) -> AdmissionDecision | None:
    for decision in report.decisions:
        if decision.subject_id == candidate_id:
            return decision
    return None


def admit_candidates(
    validation_report: ValidationReport,
    recipe_candidates: list[RecipeCandidate],
    metadata_candidates: list[MetadataEnrichmentCandidate],
) -> AdmissionReport:
    result_by_id: dict[str, CandidateValidationResult] = {}
    for r in validation_report.recipe_candidate_results:
        result_by_id[r.candidate_id] = r
    for r in validation_report.metadata_candidate_results:
        result_by_id[r.candidate_id] = r

    decisions: list[AdmissionDecision] = []

    for candidate in recipe_candidates:
        result = result_by_id.get(candidate.candidate_id)
        if result is None:
            result = CandidateValidationResult(candidate_id=candidate.candidate_id, issues=[], passed=True)
        decisions.append(_classify_decision(result))

    for candidate in metadata_candidates:
        result = result_by_id.get(candidate.candidate_id)
        if result is None:
            result = CandidateValidationResult(candidate_id=candidate.candidate_id, issues=[], passed=True)
        decisions.append(_classify_decision(result))

    counts = {"accepted_to_stage": 0, "review_required": 0, "rejected": 0}
    for d in decisions:
        counts[d.decision] += 1

    logger.info(
        "Admission complete: %d accepted, %d review_required, %d rejected",
        counts["accepted_to_stage"],
        counts["review_required"],
        counts["rejected"],
    )

    return AdmissionReport(
        generated_at=datetime.now(UTC),
        decisions=decisions,
        counts=counts,
    )


def write_staged_outputs(
    run_dir: Path,
    admission_report: AdmissionReport,
    recipe_candidates: list[RecipeCandidate],
    metadata_candidates: list[MetadataEnrichmentCandidate],
) -> None:
    staged_recipes_dir = run_dir / "staged_recipes"
    staged_recipes_dir.mkdir(parents=True, exist_ok=True)

    for candidate in recipe_candidates:
        decision = _get_decision_for(candidate.candidate_id, admission_report)
        if decision is not None and decision.decision in ("accepted_to_stage", "review_required"):
            out_path = staged_recipes_dir / f"{candidate.candidate_id}.json"
            out_path.write_text(candidate.recipe.model_dump_json(indent=2))
            logger.debug("Wrote staged recipe: %s", out_path)

    patches: list[StagedMetadataPatch] = []
    for candidate in metadata_candidates:
        decision = _get_decision_for(candidate.candidate_id, admission_report)
        if decision is not None and decision.decision != "rejected":
            patches.append(
                StagedMetadataPatch(
                    candidate_id=candidate.candidate_id,
                    target_recipe_id=candidate.target_recipe_id,
                    decision=decision.decision,
                    patch=candidate.proposed_metadata_patch,
                    reasons=decision.reasons,
                )
            )

    patch_collection = StagedMetadataPatchCollection(
        generated_at=datetime.now(UTC),
        patches=patches,
    )
    patch_path = run_dir / "staged_metadata_patches.json"
    patch_path.write_text(patch_collection.model_dump_json(indent=2))
    logger.info("Wrote %d staged metadata patches to %s", len(patches), patch_path)
