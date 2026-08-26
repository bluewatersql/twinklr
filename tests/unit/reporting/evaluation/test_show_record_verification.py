"""Adversarial file-backed verification for completed show records."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.integration.test_evaluation_deterministic_tier import _write_xsq
from tests.unit.reporting.evaluation.show_test_support import entry, graph, macro, mapping, trace
from tests.unit.reporting.evaluation.test_show_record import _visual_rubric
from twinklr.core.reporting.evaluation.recipe_join import evaluations_for_recipe
from twinklr.core.reporting.evaluation.show_manifest import (
    file_sha256,
    write_show_evaluation_manifest,
)
from twinklr.core.reporting.evaluation.show_record import (
    HumanCategoryScores,
    HumanShowJudgment,
    SampledFrameProvenance,
    ShowEvaluationRecord,
    ShowVisualEvidence,
    build_deterministic_report,
    compute_agreement,
    load_show_evaluation_record,
)
from twinklr.core.reporting.evaluation.vision_frames import FrameSamplerConfig


def _write_verified_record(root: Path) -> Path:
    evidence = root / "evidence"
    evidence.mkdir()
    xsq = evidence / "show.xsq"
    trace_path = evidence / "show.xsq.trace.json"
    manifest_path = evidence / "show.xsq.evaluation.json"
    _write_xsq(xsq)
    trace_path.write_text(
        trace(entry("display", 0, 500), entry("moving_head", 500, 1_000)).model_dump_json(),
        encoding="utf-8",
    )
    write_show_evaluation_manifest(
        path=manifest_path,
        xsq_path=xsq,
        trace_path=trace_path,
        macro_plan=macro(),
        choreography_graph=graph(),
        xlights_mapping=mapping(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    preview = evidence / "preview.mp4"
    frame = evidence / "frame-1.png"
    prompt = evidence / "rendered-prompt.txt"
    preview.write_bytes(b"frozen preview evidence")
    frame.write_bytes(b"frozen frame evidence")
    prompt.write_text("frozen rendered rubric-v2 prompt", encoding="utf-8")

    deterministic = build_deterministic_report(manifest_path).model_copy(
        update={"manifest_path": Path("evidence/show.xsq.evaluation.json")}
    )
    rubric = _visual_rubric()
    human_scores = HumanCategoryScores(
        musicality_by_proxy=9,
        coordination=8,
        color_palette_coherence=7,
        variety_and_pacing=8,
        cross_part_coordination=9,
    )
    record = ShowEvaluationRecord(
        deterministic=deterministic,
        visual=ShowVisualEvidence(
            rubric=rubric,
            model="visual-model",
            provider_response_id="response-1",
            preview_path="evidence/preview.mp4",
            preview_sha256=file_sha256(preview),
            sampling=FrameSamplerConfig(),
            sampled_frames=[
                SampledFrameProvenance(
                    index=1,
                    timestamp_ms=0,
                    path="evidence/frame-1.png",
                    sha256=file_sha256(frame),
                )
            ],
            rendered_prompt_path="evidence/rendered-prompt.txt",
            prompt_sha256=file_sha256(prompt),
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
    path = root / "record.json"
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return path


def test_file_backed_relative_record_loads_and_joins(tmp_path: Path) -> None:
    record_path = _write_verified_record(tmp_path)
    loaded = load_show_evaluation_record(record_path)
    assert loaded.status == "completed"
    assert evaluations_for_recipe("display-recipe", [record_path])[0][0] == record_path


def test_repository_relative_record_provenance_loads_from_nested_record(tmp_path: Path) -> None:
    record_path = _write_verified_record(tmp_path)
    (tmp_path / ".git").mkdir()
    evaluations = tmp_path / "evaluations"
    evaluations.mkdir()
    nested_record = evaluations / record_path.name
    record_path.rename(nested_record)
    assert load_show_evaluation_record(nested_record).status == "completed"


@pytest.mark.parametrize(
    "relative_path",
    [
        "evidence/preview.mp4",
        "evidence/frame-1.png",
        "evidence/rendered-prompt.txt",
        "evidence/show.xsq.evaluation.json",
    ],
)
def test_completed_record_rejects_tampered_or_missing_provenance(
    tmp_path: Path, relative_path: str
) -> None:
    record_path = _write_verified_record(tmp_path)
    (tmp_path / relative_path).write_bytes(b"tampered")
    with pytest.raises(ValueError, match=r"SHA-256|hash|deterministic"):
        load_show_evaluation_record(record_path)


def test_completed_record_rejects_stored_deterministic_claim_tampering(tmp_path: Path) -> None:
    record_path = _write_verified_record(tmp_path)
    payload = ShowEvaluationRecord.model_validate_json(record_path.read_text()).model_dump(
        mode="json"
    )
    payload["deterministic"]["recipe_ids"] = ["fabricated-recipe"]
    record_path.write_text(ShowEvaluationRecord.model_validate(payload).model_dump_json())
    with pytest.raises(ValueError, match="deterministic claims"):
        load_show_evaluation_record(record_path)


def test_completed_record_rejects_absolute_provenance_path(tmp_path: Path) -> None:
    record_path = _write_verified_record(tmp_path)
    record = ShowEvaluationRecord.model_validate_json(record_path.read_text())
    payload = record.model_dump(mode="json")
    payload["visual"]["preview_path"] = str((tmp_path / "evidence/preview.mp4").resolve())
    record_path.write_text(ShowEvaluationRecord.model_validate(payload).model_dump_json())
    with pytest.raises(ValueError, match="relative"):
        load_show_evaluation_record(record_path)
