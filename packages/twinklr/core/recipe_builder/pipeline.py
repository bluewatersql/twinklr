"""Offline pipeline orchestration for recipe_builder.

Loads the recipe catalog, analyzes it for gaps and opportunities,
generates new recipe candidates (via LLM or deterministic fallback),
enriches existing metadata, validates, and stages outputs for review.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from twinklr.core.recipe_builder.admission import admit_candidates, write_staged_outputs
from twinklr.core.recipe_builder.enrichment import generate_enrichments
from twinklr.core.recipe_builder.evidence import (
    analyze_catalog,
    identify_opportunities,
    load_catalog,
)
from twinklr.core.recipe_builder.generation import generate_candidates
from twinklr.core.recipe_builder.models import (
    AdmissionReport,
    CatalogAnalysis,
    MetadataEnrichmentCandidate,
    MetadataEnrichmentCollection,
    Opportunity,
    PhaseStatus,
    RecipeCandidate,
    RecipeCandidateCollection,
    RunManifest,
    SummaryMetrics,
    ValidationReport,
)
from twinklr.core.recipe_builder.validation import validate_all
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe

logger = logging.getLogger(__name__)

ALL_PHASES = ("analysis", "generation", "enrichment", "validation", "admission")


@dataclass
class PipelineConfig:
    """Configuration for a recipe_builder pipeline run."""

    run_name: str
    output_dir: Path
    templates_dir: Path | None = None
    dry_run: bool = False
    llm_client: Any | None = None
    llm_model: str = "gpt-4.1"
    llm_temperature: float = 0.9
    max_opportunities: int = 10
    phases: tuple[str, ...] = field(default_factory=lambda: ALL_PHASES)


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(data, "model_dump_json"):
        path.write_text(data.model_dump_json(indent=2))
    else:
        path.write_text(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def _print_summary(manifest: RunManifest) -> None:
    m = manifest.summary_metrics
    lines = [
        "",
        "=" * 60,
        f"  recipe_builder run: {manifest.run_name}",
        "=" * 60,
        f"  Catalog size       : {m.total_recipes_in_catalog} recipes",
        f"  Opportunities      : {m.opportunities_identified} identified",
        f"  Recipe candidates  : {m.recipe_candidates_generated} generated",
        f"  Metadata candidates: {m.metadata_candidates_generated} generated",
        f"  Validation         : {m.validation_errors} errors, {m.validation_warnings} warnings",
        f"  Admission          : {m.accepted_to_stage} accepted, "
        f"{m.review_required} review_required, {m.rejected} rejected",
        "-" * 60,
    ]
    for ps in manifest.phase_status:
        icon = {
            "completed": "OK",
            "skipped": "--",
            "failed": "!!",
            "not_started": "  ",
        }.get(ps.status, "??")
        err_note = f"  [{ps.error}]" if ps.error else ""
        lines.append(f"  [{icon}] {ps.phase}{err_note}")
    lines.append("=" * 60)
    logger.info("\n".join(lines))


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def run_pipeline(config: PipelineConfig) -> RunManifest:
    """Orchestrate all recipe_builder phases and write artifacts.

    Phases:
        1. analysis  — Load catalog, analyze distributions, identify opportunities
        2. generation — Generate new recipe candidates (LLM or deterministic)
        3. enrichment — Generate metadata enrichment candidates
        4. validation — Validate all candidates deterministically
        5. admission  — Classify and stage accepted candidates

    Args:
        config: Pipeline configuration.

    Returns:
        Completed RunManifest.
    """
    started_at = datetime.now(UTC)
    run_dir = config.output_dir / config.run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting pipeline run '%s' -> %s", config.run_name, run_dir)

    phase_statuses: list[PhaseStatus] = []
    active_phases = set(config.phases)

    # State carried between phases
    catalog_recipes: list[EffectRecipe] = []
    analysis: CatalogAnalysis | None = None
    opportunities: list[Opportunity] = []
    recipe_candidates: list[RecipeCandidate] = []
    metadata_candidates: list[MetadataEnrichmentCandidate] = []
    validation_report: ValidationReport | None = None
    admission_report: AdmissionReport | None = None

    # ---- analysis ----
    if "analysis" in active_phases:
        try:
            catalog_recipes = load_catalog(config.templates_dir)
            analysis = analyze_catalog(catalog_recipes)
            opportunities = identify_opportunities(
                analysis,
                max_opportunities=config.max_opportunities,
            )

            _write_json(run_dir / "catalog_analysis.json", analysis)
            _write_json(
                run_dir / "opportunities.json",
                {"opportunities": [o.model_dump() for o in opportunities]},
            )

            phase_statuses.append(PhaseStatus(phase="analysis", status="completed"))
            logger.info(
                "Analysis: %d recipes, %d opportunities identified",
                len(catalog_recipes),
                len(opportunities),
            )
        except Exception as exc:
            logger.exception("Analysis phase failed")
            phase_statuses.append(
                PhaseStatus(phase="analysis", status="failed", error=str(exc)),
            )
    else:
        phase_statuses.append(PhaseStatus(phase="analysis", status="skipped"))

    # ---- generation ----
    if "generation" in active_phases and analysis is not None:
        try:
            recipe_candidates = generate_candidates(
                opportunities=opportunities,
                analysis=analysis,
                catalog_recipes=catalog_recipes,
                llm_client=config.llm_client,
                dry_run=config.dry_run,
                model=config.llm_model,
                temperature=config.llm_temperature,
            )

            collection = RecipeCandidateCollection(
                generated_at=datetime.now(UTC),
                candidates=recipe_candidates,
            )
            _write_json(run_dir / "generated_recipe_candidates.json", collection)

            phase_statuses.append(PhaseStatus(phase="generation", status="completed"))
            logger.info("Generation: %d recipe candidates", len(recipe_candidates))
        except Exception as exc:
            logger.exception("Generation phase failed")
            phase_statuses.append(
                PhaseStatus(phase="generation", status="failed", error=str(exc)),
            )
    elif "generation" in active_phases:
        phase_statuses.append(
            PhaseStatus(
                phase="generation",
                status="skipped",
                error="analysis not available",
            ),
        )
    else:
        phase_statuses.append(PhaseStatus(phase="generation", status="skipped"))

    # ---- enrichment ----
    if "enrichment" in active_phases:
        try:
            metadata_candidates = generate_enrichments(catalog_recipes)

            enrichment_collection = MetadataEnrichmentCollection(
                generated_at=datetime.now(UTC),
                candidates=metadata_candidates,
            )
            _write_json(
                run_dir / "metadata_enrichment_candidates.json",
                enrichment_collection,
            )

            phase_statuses.append(PhaseStatus(phase="enrichment", status="completed"))
            logger.info("Enrichment: %d metadata candidates", len(metadata_candidates))
        except Exception as exc:
            logger.exception("Enrichment phase failed")
            phase_statuses.append(
                PhaseStatus(phase="enrichment", status="failed", error=str(exc)),
            )
    else:
        phase_statuses.append(PhaseStatus(phase="enrichment", status="skipped"))

    # ---- validation ----
    if "validation" in active_phases:
        try:
            validation_report = validate_all(
                recipe_candidates,
                metadata_candidates,
                catalog_recipes,
            )
            _write_json(run_dir / "validation_report.json", validation_report)

            phase_statuses.append(PhaseStatus(phase="validation", status="completed"))
            logger.info("Validation: %s", validation_report.issue_counts)
        except Exception as exc:
            logger.exception("Validation phase failed")
            phase_statuses.append(
                PhaseStatus(phase="validation", status="failed", error=str(exc)),
            )
    else:
        phase_statuses.append(PhaseStatus(phase="validation", status="skipped"))

    # ---- admission ----
    if "admission" in active_phases and validation_report is not None:
        try:
            admission_report = admit_candidates(
                validation_report,
                recipe_candidates,
                metadata_candidates,
            )
            write_staged_outputs(
                run_dir,
                admission_report,
                recipe_candidates,
                metadata_candidates,
            )
            _write_json(run_dir / "admission_report.json", admission_report)

            phase_statuses.append(PhaseStatus(phase="admission", status="completed"))
            logger.info("Admission: %s", admission_report.counts)
        except Exception as exc:
            logger.exception("Admission phase failed")
            phase_statuses.append(
                PhaseStatus(phase="admission", status="failed", error=str(exc)),
            )
    elif "admission" in active_phases:
        phase_statuses.append(
            PhaseStatus(
                phase="admission",
                status="skipped",
                error="validation_report unavailable",
            ),
        )
    else:
        phase_statuses.append(PhaseStatus(phase="admission", status="skipped"))

    # ---- manifest ----
    completed_at = datetime.now(UTC)

    val_errors = validation_report.issue_counts.get("error", 0) if validation_report else 0
    val_warnings = validation_report.issue_counts.get("warning", 0) if validation_report else 0
    adm_counts = admission_report.counts if admission_report else {}

    summary = SummaryMetrics(
        total_recipes_in_catalog=len(catalog_recipes),
        opportunities_identified=len(opportunities),
        recipe_candidates_generated=len(recipe_candidates),
        metadata_candidates_generated=len(metadata_candidates),
        validation_errors=val_errors,
        validation_warnings=val_warnings,
        accepted_to_stage=adm_counts.get("accepted_to_stage", 0),
        review_required=adm_counts.get("review_required", 0),
        rejected=adm_counts.get("rejected", 0),
    )

    manifest = RunManifest(
        run_name=config.run_name,
        started_at=started_at,
        completed_at=completed_at,
        input_paths={
            "output_dir": str(config.output_dir),
            "templates_dir": str(config.templates_dir or "default"),
            "dry_run": str(config.dry_run),
            "llm_model": config.llm_model,
            "max_opportunities": str(config.max_opportunities),
        },
        artifact_paths={
            "run_dir": str(run_dir),
            "catalog_analysis": str(run_dir / "catalog_analysis.json"),
            "opportunities": str(run_dir / "opportunities.json"),
            "generated_recipe_candidates": str(
                run_dir / "generated_recipe_candidates.json",
            ),
            "metadata_enrichment_candidates": str(
                run_dir / "metadata_enrichment_candidates.json",
            ),
            "validation_report": str(run_dir / "validation_report.json"),
            "admission_report": str(run_dir / "admission_report.json"),
            "staged_recipes": str(run_dir / "staged_recipes"),
            "staged_metadata_patches": str(
                run_dir / "staged_metadata_patches.json",
            ),
        },
        phase_status=phase_statuses,
        summary_metrics=summary,
    )

    _write_json(run_dir / "run_manifest.json", manifest)
    _print_summary(manifest)

    logger.info("Pipeline run '%s' complete.", config.run_name)
    return manifest
