"""Unit tests for twinklr.core.recipe_builder.admission."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from twinklr.core.recipe_builder.admission import (
    _classify_decision,
    _get_decision_for,
    admit_candidates,
    write_staged_outputs,
)
from twinklr.core.recipe_builder.models import (
    AdmissionDecision,
    AdmissionReport,
    CandidateValidationResult,
    MetadataEnrichmentCandidate,
    RecipeCandidate,
    ValidationIssue,
    ValidationReport,
)
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    EffectRecipe,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    VisualDepth,
)


def _make_recipe(recipe_id: str = "test_recipe_001") -> EffectRecipe:
    return EffectRecipe(
        recipe_id=recipe_id,
        name="Test Recipe",
        description="A test recipe.",
        recipe_version="1.0.0",
        effect_family="shimmer",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["shimmer", "test"],
        timing=TimingHints(bars_min=4, bars_max=16),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="main",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="Twinkle",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                motion=[MotionVerb.SHIMMER],
                density=0.5,
            ),
        ),
        provenance=RecipeProvenance(source="generated"),
        style_markers=StyleMarkers(complexity=0.5, energy_affinity=EnergyTarget.MED),
    )


def _make_recipe_candidate(candidate_id: str = "cand_001") -> RecipeCandidate:
    return RecipeCandidate(
        candidate_id=candidate_id,
        source_opportunity_id="opp_001",
        recipe=_make_recipe(f"recipe_{candidate_id}"),
        generation_mode="deterministic",
        rationale="test",
        confidence=0.7,
    )


def _make_metadata_candidate(
    candidate_id: str = "enr_001",
    target_recipe_id: str = "existing_recipe",
) -> MetadataEnrichmentCandidate:
    return MetadataEnrichmentCandidate(
        candidate_id=candidate_id,
        target_recipe_id=target_recipe_id,
        proposed_metadata_patch={"tags": ["new_tag"]},
        rationale="test enrichment",
        confidence=0.6,
    )


def _make_clean_result(candidate_id: str) -> CandidateValidationResult:
    return CandidateValidationResult(
        candidate_id=candidate_id, issues=[], passed=True,
    )


def _make_error_result(
    candidate_id: str, message: str = "Something failed",
) -> CandidateValidationResult:
    return CandidateValidationResult(
        candidate_id=candidate_id,
        issues=[
            ValidationIssue(
                severity="error",
                check_name="test_check",
                message=message,
                subject_id=candidate_id,
            ),
        ],
        passed=False,
    )


def _make_warning_result(
    candidate_id: str, message: str = "Something suspicious",
) -> CandidateValidationResult:
    return CandidateValidationResult(
        candidate_id=candidate_id,
        issues=[
            ValidationIssue(
                severity="warning",
                check_name="test_check",
                message=message,
                subject_id=candidate_id,
            ),
        ],
        passed=True,
    )


def _make_validation_report(
    recipe_results: list[CandidateValidationResult] | None = None,
    metadata_results: list[CandidateValidationResult] | None = None,
) -> ValidationReport:
    return ValidationReport(
        generated_at=datetime.now(UTC),
        recipe_candidate_results=recipe_results or [],
        metadata_candidate_results=metadata_results or [],
        issue_counts={},
    )


class TestClassifyDecision:
    def test_clean_result_accepted(self):
        result = _make_clean_result("cand_001")
        decision = _classify_decision(result)
        assert decision.decision == "accepted_to_stage"
        assert decision.subject_id == "cand_001"

    def test_error_result_rejected(self):
        result = _make_error_result("cand_002", "Schema invalid")
        decision = _classify_decision(result)
        assert decision.decision == "rejected"
        assert "Schema invalid" in decision.reasons

    def test_warning_only_review_required(self):
        result = _make_warning_result("cand_003", "Missing tags")
        decision = _classify_decision(result)
        assert decision.decision == "review_required"
        assert "Missing tags" in decision.reasons

    def test_error_takes_priority_over_warning(self):
        result = CandidateValidationResult(
            candidate_id="cand_004",
            issues=[
                ValidationIssue(
                    severity="warning", check_name="w",
                    message="warn msg", subject_id="cand_004",
                ),
                ValidationIssue(
                    severity="error", check_name="e",
                    message="err msg", subject_id="cand_004",
                ),
            ],
            passed=False,
        )
        decision = _classify_decision(result)
        assert decision.decision == "rejected"
        assert "err msg" in decision.reasons
        assert "warn msg" not in decision.reasons

    def test_info_only_treated_as_clean(self):
        result = CandidateValidationResult(
            candidate_id="cand_006",
            issues=[
                ValidationIssue(
                    severity="info", check_name="i",
                    message="info msg", subject_id="cand_006",
                ),
            ],
            passed=True,
        )
        decision = _classify_decision(result)
        assert decision.decision == "accepted_to_stage"


class TestGetDecisionFor:
    def _make_report(self, decisions: list[AdmissionDecision]) -> AdmissionReport:
        return AdmissionReport(
            generated_at=datetime.now(UTC),
            decisions=decisions,
            counts={},
        )

    def test_found(self):
        d = AdmissionDecision(
            subject_id="cand_001", decision="accepted_to_stage", reasons=[],
        )
        report = self._make_report([d])
        result = _get_decision_for("cand_001", report)
        assert result is not None
        assert result.decision == "accepted_to_stage"

    def test_not_found_returns_none(self):
        report = self._make_report([])
        assert _get_decision_for("missing", report) is None


class TestAdmitCandidates:
    def test_all_clean_all_accepted(self):
        candidates = [_make_recipe_candidate("c1"), _make_recipe_candidate("c2")]
        report = _make_validation_report(
            recipe_results=[_make_clean_result("c1"), _make_clean_result("c2")],
        )
        result = admit_candidates(report, candidates, [])
        assert result.counts["accepted_to_stage"] == 2
        assert result.counts["rejected"] == 0

    def test_error_candidate_rejected(self):
        candidates = [_make_recipe_candidate("c1")]
        report = _make_validation_report(
            recipe_results=[_make_error_result("c1")],
        )
        result = admit_candidates(report, candidates, [])
        assert result.counts["rejected"] == 1

    def test_warning_candidate_review_required(self):
        candidates = [_make_recipe_candidate("c1")]
        report = _make_validation_report(
            recipe_results=[_make_warning_result("c1")],
        )
        result = admit_candidates(report, candidates, [])
        assert result.counts["review_required"] == 1

    def test_counts_sum_correctly(self):
        candidates = [
            _make_recipe_candidate("c1"),
            _make_recipe_candidate("c2"),
            _make_recipe_candidate("c3"),
        ]
        report = _make_validation_report(
            recipe_results=[
                _make_clean_result("c1"),
                _make_warning_result("c2"),
                _make_error_result("c3"),
            ],
        )
        result = admit_candidates(report, candidates, [])
        assert result.counts == {
            "accepted_to_stage": 1,
            "review_required": 1,
            "rejected": 1,
        }
        assert len(result.decisions) == 3


class TestWriteStagedOutputs:
    def _make_report_with_decisions(
        self, decisions: list[AdmissionDecision],
    ) -> AdmissionReport:
        counts: dict[str, int] = {
            "accepted_to_stage": 0, "review_required": 0, "rejected": 0,
        }
        for d in decisions:
            counts[d.decision] += 1
        return AdmissionReport(
            generated_at=datetime.now(UTC),
            decisions=decisions,
            counts=counts,
        )

    def test_accepted_recipe_written(self, tmp_path: Path):
        candidate = _make_recipe_candidate("c1")
        decision = AdmissionDecision(
            subject_id="c1", decision="accepted_to_stage", reasons=[],
        )
        report = self._make_report_with_decisions([decision])
        write_staged_outputs(tmp_path, report, [candidate], [])

        recipe_file = tmp_path / "staged_recipes" / "c1.json"
        assert recipe_file.exists()
        data = json.loads(recipe_file.read_text())
        assert data["recipe_id"] == "recipe_c1"

    def test_rejected_recipe_not_written(self, tmp_path: Path):
        candidate = _make_recipe_candidate("c3")
        decision = AdmissionDecision(
            subject_id="c3", decision="rejected", reasons=["bad"],
        )
        report = self._make_report_with_decisions([decision])
        write_staged_outputs(tmp_path, report, [candidate], [])
        assert not (tmp_path / "staged_recipes" / "c3.json").exists()

    def test_metadata_patch_collection_written(self, tmp_path: Path):
        meta = _make_metadata_candidate("enr_001")
        decision = AdmissionDecision(
            subject_id="enr_001", decision="accepted_to_stage", reasons=[],
        )
        report = self._make_report_with_decisions([decision])
        write_staged_outputs(tmp_path, report, [], [meta])

        patch_file = tmp_path / "staged_metadata_patches.json"
        assert patch_file.exists()
        data = json.loads(patch_file.read_text())
        assert len(data["patches"]) == 1

    def test_staged_recipes_dir_created(self, tmp_path: Path):
        report = self._make_report_with_decisions([])
        write_staged_outputs(tmp_path, report, [], [])
        assert (tmp_path / "staged_recipes").is_dir()
