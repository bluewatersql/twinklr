"""Strict completed record and recipe-join public seams."""

from __future__ import annotations

from datetime import UTC, datetime
import json

from click.testing import CliRunner
from pydantic import ValidationError
import pytest

from tests.unit.reporting.evaluation.show_test_support import entry, grid, manifest, trace
from twinklr.core.reporting.evaluation.cli import eval_report_cli
from twinklr.core.reporting.evaluation.recipe_join import evaluations_for_recipe
from twinklr.core.reporting.evaluation.show_judge import (
    CrossPartCoordinationScore,
    ShowVisionRubricResponse,
    VisualCriterionScore,
)
from twinklr.core.reporting.evaluation.show_metrics import (
    ShowMetrics,
    score_cross_part_alignment,
)
from twinklr.core.reporting.evaluation.show_record import (
    HumanCategoryScores,
    HumanShowJudgment,
    SampledFrameProvenance,
    ShowDeterministicReport,
    ShowEvaluationRecord,
    ShowVisualEvidence,
    compute_agreement,
    load_show_evaluation_record,
)
from twinklr.core.reporting.evaluation.sync_metrics import (
    StructureSection,
    score_sync_metrics,
)
from twinklr.core.reporting.evaluation.vision_frames import FrameSamplerConfig
from twinklr.core.reporting.evaluation.vision_judge import RubricCategoryScore


def _visual_rubric() -> ShowVisionRubricResponse:
    category = RubricCategoryScore(score=8, justification="Section is visually clear.")
    criterion = VisualCriterionScore(
        applicability="scored",
        score=8,
        justification="Section reads clearly in frame 1.",
    )
    return ShowVisionRubricResponse(
        musicality_by_proxy=category,
        coordination=category,
        color_palette_coherence=category,
        variety_and_pacing=category,
        cross_part_coordination=CrossPartCoordinationScore(
            focal_clarity=criterion,
            call_response_legibility=criterion,
            cross_part_palette_agreement=criterion,
            section_transition_agreement=criterion,
            mutual_complement=criterion,
        ),
    )


def _record() -> ShowEvaluationRecord:
    show_manifest = manifest()
    show_trace = trace(entry("display", 0, 500), entry("moving_head", 500, 1_000))
    metrics = ShowMetrics(
        sync=score_sync_metrics(
            beat_grid=grid(),
            effects=[],
            sections=[StructureSection(name="Section", start_ms=0, end_ms=2_000, bars=1)],
        ),
        cross_part=score_cross_part_alignment(
            manifest=show_manifest,
            trace=show_trace,
            beat_grid=grid(),
        ),
    )
    deterministic = ShowDeterministicReport(
        manifest_path="show.xsq.evaluation.json",
        manifest_sha256="1" * 64,
        artifact_sha256="2" * 64,
        trace_sha256="3" * 64,
        capability=show_manifest.capability,
        metrics=metrics,
        recipe_ids=["display-recipe"],
        moving_head_template_ids=["mh-template"],
    )
    rubric = _visual_rubric()
    human_scores = HumanCategoryScores(
        musicality_by_proxy=9,
        coordination=8,
        color_palette_coherence=7,
        variety_and_pacing=8,
        cross_part_coordination=9,
    )
    return ShowEvaluationRecord(
        deterministic=deterministic,
        visual=ShowVisualEvidence(
            rubric=rubric,
            model="visual-model",
            provider_response_id="response-1",
            preview_path="preview.mp4",
            preview_sha256="4" * 64,
            sampling=FrameSamplerConfig(),
            sampled_frames=[
                SampledFrameProvenance(
                    index=1,
                    timestamp_ms=0,
                    path="frame-1.png",
                    sha256="5" * 64,
                )
            ],
            rendered_prompt_path="rendered-prompt.txt",
            prompt_sha256="6" * 64,
            actual_cost_usd=0.12,
        ),
        human=HumanShowJudgment(
            reviewer="owner",
            recorded_at=datetime.now(UTC),
            scores=human_scores,
            free_text="The exchange reads clearly and the parts complement one another.",
        ),
        agreement=compute_agreement(rubric, human_scores),
    )


def test_fixture_only_completed_record_fails_verified_load(tmp_path) -> None:
    path = tmp_path / "record.json"
    path.write_text(_record().model_dump_json(indent=2), encoding="utf-8")
    with pytest.raises((FileNotFoundError, ValueError)):
        load_show_evaluation_record(path)


def test_completed_record_rejects_tampered_agreement_and_v1_shape() -> None:
    payload = _record().model_dump(mode="json")
    payload["agreement"]["coordination"] = 9
    with pytest.raises(ValidationError, match="tampered"):
        ShowEvaluationRecord.model_validate(payload)
    payload["agreement"] = _record().agreement.model_dump(mode="json")
    payload["schema_version"] = "twinklr-show-evaluation-record.v1"
    with pytest.raises(ValidationError, match="literal_error"):
        ShowEvaluationRecord.model_validate(payload)


def test_incomplete_offline_report_is_not_a_completed_record() -> None:
    payload = _record().deterministic.model_dump(mode="json")
    with pytest.raises(ValidationError):
        ShowEvaluationRecord.model_validate(payload)


def test_recipe_join_rejects_fixture_only_completed_records(tmp_path) -> None:
    matching = tmp_path / "matching.json"
    other = tmp_path / "other.json"
    matching.write_text(_record().model_dump_json(), encoding="utf-8")
    payload = _record().model_dump(mode="json")
    payload["deterministic"]["recipe_ids"] = ["other-recipe"]
    other.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises((FileNotFoundError, ValueError)):
        evaluations_for_recipe("display-recipe", [other, matching])


def test_eval_report_rejects_unverified_positional_completed_record(tmp_path) -> None:
    path = tmp_path / "record.json"
    path.write_text(_record().model_dump_json(), encoding="utf-8")
    result = CliRunner().invoke(eval_report_cli, [str(path)])
    assert result.exit_code != 0
