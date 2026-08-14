"""Offline tests for coverage-targeted human recipe curation."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from twinklr.core.recipe_builder.models import (
    AdmissionDecision,
    AdmissionReport,
    Opportunity,
    RecipeCandidate,
    RecipeCandidateCollection,
)
from twinklr.core.recipe_builder.promotion import promote_staged_recipes


def test_opportunities_from_coverage_gaps_map_cells_and_prominence() -> None:
    from twinklr.core.recipe_builder.coverage import opportunities_from_coverage_gaps

    report = {
        "element_types": [
            {"element_type": "megatree", "pixel_count": 900, "prominence_share": 0.9},
            {"element_type": "arch", "pixel_count": 100, "prominence_share": 0.1},
        ],
        "gaps": [
            {"element_type": "arch", "role": "ACCENT", "energy": "HIGH", "is_gap": True},
            {"element_type": "megatree", "role": "BASE", "energy": "LOW", "is_gap": True},
        ],
    }

    opportunities = opportunities_from_coverage_gaps(report)

    assert [opportunity.target_element_type for opportunity in opportunities] == [
        "megatree",
        "arch",
    ]
    assert opportunities[0].category == "missing_layout_coverage"
    assert opportunities[0].target_template_type == "BASE"
    assert opportunities[0].target_energy == "LOW"
    assert opportunities[0].priority == pytest.approx(1.0)
    assert opportunities[1].priority == pytest.approx(0.1 / 0.9)


def test_target_element_type_reaches_llm_prompt(
    sample_opportunity, sample_analysis, sample_recipes
) -> None:
    from twinklr.core.recipe_builder.generation import _build_user_prompt

    opportunity = sample_opportunity.model_copy(update={"target_element_type": "megatree"})

    prompt = _build_user_prompt(opportunity, sample_analysis, sample_recipes)

    assert 'display element type MUST be: "megatree"' in prompt


def test_pipeline_adds_coverage_gaps_to_existing_generation_opportunities(tmp_path: Path) -> None:
    from twinklr.core.recipe_builder.pipeline import PipelineConfig, run_pipeline

    coverage_report = tmp_path / "coverage.json"
    coverage_report.write_text(
        json.dumps(
            {
                "element_types": [
                    {"element_type": "megatree", "pixel_count": 10, "prominence_share": 1.0}
                ],
                "gaps": [
                    {
                        "element_type": "megatree",
                        "role": "BASE",
                        "energy": "LOW",
                        "is_gap": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = run_pipeline(
        PipelineConfig(
            run_name="coverage-targeted",
            output_dir=tmp_path / "runs",
            dry_run=True,
            coverage_report_path=coverage_report,
        )
    )

    run_dir = tmp_path / "runs" / "coverage-targeted"
    opportunities = json.loads((run_dir / "opportunities.json").read_text(encoding="utf-8"))[
        "opportunities"
    ]
    generated = json.loads(
        (run_dir / "generated_recipe_candidates.json").read_text(encoding="utf-8")
    )["candidates"]
    assert any(item["target_element_type"] == "megatree" for item in opportunities)
    assert any(
        candidate["recipe"]["model_affinities"] == [{"model_type": "megatree", "score": 1.0}]
        for candidate in generated
    )
    assert manifest.summary_metrics.opportunities_identified == len(opportunities)


def test_review_staged_recipes_command_requires_a_run_dir() -> None:
    from twinklr.cli.main import build_arg_parser

    args = build_arg_parser().parse_args(
        ["review-staged-recipes", "--run-dir", "/tmp/recipe-builder-run"]
    )

    assert args.cmd == "review-staged-recipes"
    assert args.staged_dir is None


def test_selective_promotion_only_promotes_human_admitted_recipe_ids(tmp_path: Path) -> None:
    from tests.unit.recipe_builder.test_promotion import _setup_dirs, _write_staged

    staged_dir, templates_dir, builtins_dir = _setup_dirs(tmp_path)
    _write_staged(staged_dir, "admit_me_v1")
    _write_staged(staged_dir, "reject_me_v1")

    result = promote_staged_recipes(
        staged_dir=staged_dir,
        templates_dir=templates_dir,
        candidate_ids={"admit_me_v1"},
    )

    assert result.promoted_ids == ["admit_me_v1"]
    assert result.skipped_ids == ["reject_me_v1"]
    assert (builtins_dir / "admit_me_v1.json").exists()
    assert not (builtins_dir / "reject_me_v1.json").exists()


def test_promotion_without_candidate_ids_keeps_legacy_promote_everything(tmp_path: Path) -> None:
    from tests.unit.recipe_builder.test_promotion import _setup_dirs, _write_staged

    staged_dir, templates_dir, builtins_dir = _setup_dirs(tmp_path)
    _write_staged(staged_dir, "first_v1")
    _write_staged(staged_dir, "second_v1")

    result = promote_staged_recipes(staged_dir=staged_dir, templates_dir=templates_dir)

    assert result.promoted_ids == ["first_v1", "second_v1"]
    assert (builtins_dir / "first_v1.json").exists()
    assert (builtins_dir / "second_v1.json").exists()


def _write_run_artifacts(tmp_path: Path, sample_recipe) -> tuple[Path, Path, Path]:
    run_dir = tmp_path / "run"
    staged_dir = run_dir / "staged_recipes"
    staged_dir.mkdir(parents=True)
    templates_dir = tmp_path / "templates"
    (templates_dir / "builtins").mkdir(parents=True)
    (templates_dir / "index.json").write_text(
        json.dumps({"schema_version": "template-index.v1", "total": 0, "entries": []}),
        encoding="utf-8",
    )

    admitted_recipe = sample_recipe.model_copy(update={"recipe_id": "human_admit_v1"})
    rejected_recipe = sample_recipe.model_copy(update={"recipe_id": "human_reject_v1"})
    candidates = [
        RecipeCandidate(
            candidate_id="candidate-admit",
            source_opportunity_id="gap-megatree-base-low",
            recipe=admitted_recipe,
            generation_mode="deterministic",
        ),
        RecipeCandidate(
            candidate_id="candidate-reject",
            source_opportunity_id="gap-arch-accent-high",
            recipe=rejected_recipe,
            generation_mode="deterministic",
        ),
    ]
    for candidate in candidates:
        (staged_dir / f"{candidate.candidate_id}.json").write_text(
            candidate.recipe.model_dump_json(indent=2), encoding="utf-8"
        )
    (run_dir / "generated_recipe_candidates.json").write_text(
        RecipeCandidateCollection(
            generated_at=datetime.now(UTC), candidates=candidates
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    opportunities = [
        Opportunity(
            opportunity_id="gap-megatree-base-low",
            category="missing_layout_coverage",
            description="Fill megatree BASE LOW coverage.",
            priority=1.0,
            target_element_type="megatree",
            target_template_type="BASE",
            target_energy="LOW",
        ),
        Opportunity(
            opportunity_id="gap-arch-accent-high",
            category="missing_layout_coverage",
            description="Fill arch ACCENT HIGH coverage.",
            priority=0.5,
            target_element_type="arch",
            target_template_type="ACCENT",
            target_energy="HIGH",
        ),
    ]
    (run_dir / "opportunities.json").write_text(
        json.dumps({"opportunities": [item.model_dump() for item in opportunities]}),
        encoding="utf-8",
    )
    report = AdmissionReport(
        generated_at=datetime.now(UTC),
        decisions=[
            AdmissionDecision(
                subject_id="candidate-admit", decision="accepted_to_stage", reasons=["valid"]
            ),
            AdmissionDecision(
                subject_id="candidate-reject", decision="review_required", reasons=["needs review"]
            ),
        ],
        counts={"accepted_to_stage": 1, "review_required": 1, "rejected": 0},
    )
    (run_dir / "admission_report.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    return run_dir, staged_dir, templates_dir


def test_scripted_human_session_logs_each_reason_and_promotes_only_admitted(
    tmp_path: Path, sample_recipe
) -> None:
    from twinklr.core.recipe_builder.curation import run_curation_session

    run_dir, staged_dir, templates_dir = _write_run_artifacts(tmp_path, sample_recipe)
    decisions = iter(
        [("admit", "Fits the tree's low-energy base."), ("reject", "Too busy for arch.")]
    )

    log, result, log_path = run_curation_session(
        run_dir=run_dir,
        staged_dir=staged_dir,
        templates_dir=templates_dir,
        decide=lambda _: next(decisions),
        session_id="scripted-session",
        now=lambda: datetime(2026, 8, 14, tzinfo=UTC),
    )

    assert [record.human_decision for record in log.records] == ["admit", "reject"]
    assert [record.reason for record in log.records] == [
        "Fits the tree's low-energy base.",
        "Too busy for arch.",
    ]
    assert result.promoted_ids == ["human_admit_v1"]
    assert not (templates_dir / "builtins" / "human_reject_v1.json").exists()
    persisted = json.loads(log_path.read_text(encoding="utf-8"))
    assert len(persisted["records"]) == 2
    assert persisted["records"][0]["target_element_type"] == "megatree"


def test_session_rejects_missing_reason_before_writing_or_promoting(
    tmp_path: Path, sample_recipe
) -> None:
    from twinklr.core.recipe_builder.curation import run_curation_session

    run_dir, staged_dir, templates_dir = _write_run_artifacts(tmp_path, sample_recipe)

    with pytest.raises(ValueError, match="reason"):
        run_curation_session(
            run_dir=run_dir,
            staged_dir=staged_dir,
            templates_dir=templates_dir,
            decide=lambda _: ("admit", ""),
            session_id="invalid-session",
        )

    assert not (run_dir / "curation_sessions" / "invalid-session.json").exists()
    assert not list((templates_dir / "builtins").glob("*.json"))


@pytest.mark.parametrize("interrupt", [EOFError(), KeyboardInterrupt()])
def test_interactive_interrupt_aborts_cleanly_without_log_or_promotion(
    tmp_path: Path, sample_recipe, monkeypatch: pytest.MonkeyPatch, capsys, interrupt: BaseException
) -> None:
    from twinklr.cli.curation_cmd import run_review_staged_recipes_command

    run_dir, staged_dir, templates_dir = _write_run_artifacts(tmp_path, sample_recipe)
    responses = iter(["admit", "First candidate is suitable.", interrupt])

    def interrupted_input(_: str) -> str:
        response = next(responses)
        if isinstance(response, BaseException):
            raise response
        return response

    monkeypatch.setattr("builtins.input", interrupted_input)
    args = argparse.Namespace(
        run_dir=run_dir,
        staged_dir=staged_dir,
        templates_dir=templates_dir,
        session_id="interrupted-session",
    )

    assert run_review_staged_recipes_command(args) == 130
    output = capsys.readouterr().out
    assert "no session log was written" in output
    assert "no recipes were promoted" in output
    assert not (run_dir / "curation_sessions" / "interrupted-session.json").exists()
    assert not list((templates_dir / "builtins").glob("*.json"))
