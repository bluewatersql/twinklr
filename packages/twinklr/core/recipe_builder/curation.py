"""Human-in-the-loop review and selective promotion of staged recipes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import cast

from twinklr.core.recipe_builder.models import (
    AdmissionDecision,
    AdmissionReport,
    CurationSessionLog,
    CurationSessionRecord,
    HumanAdmissionDecisionType,
    Opportunity,
    PromotionResult,
    RecipeCandidate,
    RecipeCandidateCollection,
)
from twinklr.core.recipe_builder.promotion import promote_staged_recipes
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe

HumanDecisionProvider = Callable[["ReviewCandidate"], tuple[str, str]]
Clock = Callable[[], datetime]


class ReviewCandidate:
    """A staged recipe paired with its generation and automated-admission context."""

    def __init__(
        self,
        *,
        candidate: RecipeCandidate,
        recipe: EffectRecipe,
        opportunity: Opportunity,
        automated_decision: AdmissionDecision,
    ) -> None:
        self.candidate = candidate
        self.recipe = recipe
        self.opportunity = opportunity
        self.automated_decision = automated_decision


def format_review_candidate(candidate: ReviewCandidate) -> str:
    """Return the compact one-at-a-time display used by the interactive CLI."""
    layers = ", ".join(
        f"{layer.layer_depth.value}:{layer.effect_type}" for layer in candidate.recipe.layers
    )
    target = candidate.opportunity.target_element_type or "not layout-targeted"
    automated_reasons = "; ".join(candidate.automated_decision.reasons) or "none"
    return "\n".join(
        [
            f"Recipe: {candidate.recipe.name} ({candidate.recipe.recipe_id})",
            f"Effect family: {candidate.recipe.effect_family}",
            f"Energy: {candidate.recipe.style_markers.energy_affinity.value}",
            f"Template type: {candidate.recipe.template_type.value}",
            f"Target element type: {target}",
            f"Layers: {layers}",
            (f"Automated admission: {candidate.automated_decision.decision} ({automated_reasons})"),
        ]
    )


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Curation requires run artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Curation artifact is not valid JSON: {path}") from exc


def load_review_candidates(*, run_dir: Path, staged_dir: Path) -> list[ReviewCandidate]:
    """Load staged recipes with their opportunity and automated-admission context."""
    candidate_collection = RecipeCandidateCollection.model_validate(
        _load_json(run_dir / "generated_recipe_candidates.json")
    )
    opportunities_data = _load_json(run_dir / "opportunities.json")
    if not isinstance(opportunities_data, dict) or not isinstance(
        opportunities_data.get("opportunities"), list
    ):
        raise ValueError("opportunities.json must contain an opportunities list")
    opportunities = [
        Opportunity.model_validate(item) for item in opportunities_data["opportunities"]
    ]
    admission_report = AdmissionReport.model_validate(_load_json(run_dir / "admission_report.json"))

    candidates_by_id = {
        candidate.candidate_id: candidate for candidate in candidate_collection.candidates
    }
    opportunities_by_id = {opportunity.opportunity_id: opportunity for opportunity in opportunities}
    decisions_by_id = {decision.subject_id: decision for decision in admission_report.decisions}
    reviews: list[ReviewCandidate] = []
    for staged_file in sorted(staged_dir.glob("*.json")):
        candidate_id = staged_file.stem
        candidate = candidates_by_id.get(candidate_id)
        if candidate is None:
            raise ValueError(f"No generated candidate matches staged file: {staged_file.name}")
        recipe = EffectRecipe.model_validate(_load_json(staged_file))
        if recipe.recipe_id != candidate.recipe.recipe_id:
            raise ValueError(
                f"Staged recipe ID does not match generated candidate: {staged_file.name}"
            )
        opportunity = opportunities_by_id.get(candidate.source_opportunity_id)
        if opportunity is None:
            raise ValueError(f"No opportunity matches staged candidate: {candidate_id}")
        automated_decision = decisions_by_id.get(candidate_id)
        if automated_decision is None:
            raise ValueError(
                f"No automated admission decision matches staged candidate: {candidate_id}"
            )
        reviews.append(
            ReviewCandidate(
                candidate=candidate,
                recipe=recipe,
                opportunity=opportunity,
                automated_decision=automated_decision,
            )
        )
    return reviews


def record_human_decisions(
    candidates: list[ReviewCandidate],
    *,
    decide: HumanDecisionProvider,
    session_id: str,
    now: Clock = lambda: datetime.now(UTC),
) -> CurationSessionLog:
    """Require and validate one explicit human decision and reason per candidate."""
    records: list[CurationSessionRecord] = []
    for candidate in candidates:
        decision, reason = decide(candidate)
        normalized_decision = decision.strip().lower()
        normalized_reason = reason.strip()
        if normalized_decision not in {"admit", "reject"}:
            raise ValueError("Human decision must be exactly 'admit' or 'reject'")
        if not normalized_reason:
            raise ValueError("A non-empty human reason is required for every staged candidate")
        records.append(
            CurationSessionRecord(
                recipe_id=candidate.recipe.recipe_id,
                opportunity_category=candidate.opportunity.category,
                target_element_type=candidate.opportunity.target_element_type,
                automated_decision=candidate.automated_decision.decision,
                human_decision=cast("HumanAdmissionDecisionType", normalized_decision),
                reason=normalized_reason,
                timestamp=now(),
            )
        )
    return CurationSessionLog(session_id=session_id, created_at=now(), records=records)


def write_session_log(*, run_dir: Path, log: CurationSessionLog) -> Path:
    """Persist one immutable, per-session human admission log under the run directory."""
    session_dir = run_dir / "curation_sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / f"{log.session_id}.json"
    if path.exists():
        raise FileExistsError(f"Curation session log already exists: {path}")
    path.write_text(log.model_dump_json(indent=2), encoding="utf-8")
    return path


def run_curation_session(
    *,
    run_dir: Path,
    staged_dir: Path,
    templates_dir: Path,
    decide: HumanDecisionProvider,
    session_id: str,
    now: Clock = lambda: datetime.now(UTC),
) -> tuple[CurationSessionLog, PromotionResult, Path]:
    """Log explicit human decisions for every staged recipe, then promote only admits."""
    candidates = load_review_candidates(run_dir=run_dir, staged_dir=staged_dir)
    log = record_human_decisions(candidates, decide=decide, session_id=session_id, now=now)
    log_path = write_session_log(run_dir=run_dir, log=log)
    admitted_ids = {record.recipe_id for record in log.records if record.human_decision == "admit"}
    result = promote_staged_recipes(
        staged_dir=staged_dir,
        templates_dir=templates_dir,
        candidate_ids=admitted_ids,
    )
    return log, result, log_path
