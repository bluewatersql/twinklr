"""Combined record and calibration tests."""

import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
from pydantic import ValidationError
import pytest

from twinklr.core.agents.result import AgentResult
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.models import AgentOrchestrationConfig
from twinklr.core.reporting.evaluation.calibration import (
    CalibrationBatch,
    OwnerCalibrationArtifact,
    _descending_average_ranks,
    calculate_calibration,
)
from twinklr.core.reporting.evaluation.render import write_vision_evaluation_json
from twinklr.core.reporting.evaluation.sync_metrics import (
    BoundaryAlignment,
    DeterministicSyncMetrics,
    GridStartAlignment,
    OffsetDistribution,
)
from twinklr.core.reporting.evaluation.vision_evaluation import (
    VisionEvaluationResult,
    evaluate_preview,
)
from twinklr.core.reporting.evaluation.vision_frames import (
    FrameSamplerConfig,
    SampledFrame,
)
from twinklr.core.reporting.evaluation.vision_judge import (
    JudgedFrames,
    VisionCostEstimate,
    VisionRubricResponse,
    VisionTokenUsage,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def _rubric(score: float) -> VisionRubricResponse:
    return VisionRubricResponse.model_validate(
        {
            field: {"score": score, "justification": "Frame 1 supports section chorus."}
            for field in VisionRubricResponse.model_fields
        }
    )


def _distribution() -> OffsetDistribution:
    return OffsetDistribution(
        count=0,
        signed_offsets_ms=[],
        mean_absolute_ms=0,
        median_absolute_ms=0,
        p95_absolute_ms=0,
        mean_signed_ms=0,
        standard_deviation_ms=0,
    )


def _sync() -> DeterministicSyncMetrics:
    grid = GridStartAlignment(
        tolerance_ms=50,
        on_grid_count=0,
        effect_count=0,
        on_grid_rate=0,
        offsets=_distribution(),
    )
    return DeterministicSyncMetrics(
        beat_starts=grid,
        downbeat_starts=grid,
        section_boundaries=BoundaryAlignment(
            tolerance_ms=50,
            aligned_count=0,
            boundary_count=0,
            alignment_rate=0,
            offsets=_distribution(),
        ),
        section_density=[],
    )


def _result_payload() -> dict[str, object]:
    return {
        "created_at": "2026-08-14T00:00:00+00:00",
        "artifact_path": Path("show.xsq"),
        "artifact_sha256": "a" * 64,
        "preview_path": Path("preview.mp4"),
        "preview_sha256": "b" * 64,
        "plan_sha256": "c" * 64,
        "evaluation_config_sha256": "d" * 64,
        "sampled_frame_count": 9,
        "judge_image_count": 1,
        "sampling": FrameSamplerConfig(),
        "visual": JudgedFrames(
            rubric=_rubric(7),
            model="configured-mini-tier",
            estimate=VisionCostEstimate(
                image_count=1,
                image_megapixels=0.9,
                image_cost_usd=0.1,
                output_allowance_usd=0.001,
                estimated_cost_usd=0.101,
            ),
            actual_cost_usd=0.09,
            usage=VisionTokenUsage(
                prompt_tokens=100,
                reasoning_tokens=5,
                completion_tokens=20,
                total_tokens=125,
            ),
        ),
        "deterministic": _sync(),
    }


def _owner_artifact(decision: str) -> OwnerCalibrationArtifact:
    samples = [
        {
            "sequence_id": f"show-{index}",
            "owner_rank": index,
            "owner_scores": {
                "musicality_by_proxy": 11 - index,
                "coordination": 11 - index,
                "color_palette_coherence": 11 - index,
                "variety_and_pacing": 11 - index,
            },
            "vision_scores": _rubric(11 - index),
            "artifact_sha256": f"{index:x}" * 64,
            "preview_sha256": f"{index + 5:x}" * 64,
            "actual_cost_usd": 0.1,
        }
        for index in range(1, 6)
    ]
    batch = CalibrationBatch.model_validate(
        {
            "samples": [
                {
                    key: sample[key]
                    for key in ("sequence_id", "owner_rank", "owner_scores", "vision_scores")
                }
                for sample in samples
            ]
        }
    )
    return OwnerCalibrationArtifact.model_validate(
        {
            "recorded_at": "2026-08-14T12:00:00+00:00",
            "owner_identity": "owner@example.test",
            "decision": decision,
            "rubric_version": "lighting-automv-v1",
            "sampling": FrameSamplerConfig().model_dump(mode="json"),
            "samples": samples,
            "report": calculate_calibration(batch),
        }
    )


def test_result_record_round_trip_through_evaluation_writer(tmp_path: Path) -> None:
    result = VisionEvaluationResult(
        created_at="2026-08-14T00:00:00+00:00",
        artifact_path=Path("show.xsq"),
        artifact_sha256="a" * 64,
        preview_path=Path("preview.mp4"),
        preview_sha256="b" * 64,
        plan_sha256="c" * 64,
        evaluation_config_sha256="d" * 64,
        sampled_frame_count=9,
        judge_image_count=1,
        sampling=FrameSamplerConfig(),
        visual=JudgedFrames(
            rubric=_rubric(7),
            model="configured-mini-tier",
            estimate=VisionCostEstimate(
                image_count=1,
                image_megapixels=0.9,
                image_cost_usd=0.1,
                output_allowance_usd=0.001,
                estimated_cost_usd=0.101,
            ),
            actual_cost_usd=0.09,
            usage=VisionTokenUsage(
                prompt_tokens=100, reasoning_tokens=5, completion_tokens=20, total_tokens=125
            ),
        ),
        deterministic=_sync(),
    )
    path = tmp_path / "vision_evaluation.json"
    write_vision_evaluation_json(result, path)
    loaded = VisionEvaluationResult.model_validate_json(path.read_text(encoding="utf-8"))
    assert loaded == result
    assert json.loads(path.read_text(encoding="utf-8"))["calibration_status"] == "uncalibrated"


def test_calibration_requires_five_owner_ranked_sequences() -> None:
    samples = [
        {
            "sequence_id": f"show-{index}",
            "owner_rank": index,
            "owner_scores": {
                "musicality_by_proxy": 11 - index,
                "coordination": 11 - index,
                "color_palette_coherence": 11 - index,
                "variety_and_pacing": 11 - index,
            },
            "vision_scores": _rubric(11 - index),
        }
        for index in range(1, 6)
    ]
    report = calculate_calibration(CalibrationBatch.model_validate({"samples": samples}))
    assert report.sample_count == 5
    assert report.spearman_rank_correlation == pytest.approx(1.0)
    assert report.owner_decision == "pending"
    assert report.permutation_count == 120
    assert set(report.category_mean_absolute_error) == set(VisionRubricResponse.model_fields)

    with pytest.raises(ValidationError):
        CalibrationBatch.model_validate({"samples": samples[:4]})


def test_calibration_uses_tie_aware_average_ranks() -> None:
    assert _descending_average_ranks([9.0, 9.0, 7.0, 6.0, 5.0]) == [1.5, 1.5, 3.0, 4.0, 5.0]


def test_result_cannot_self_declare_calibrated() -> None:
    with pytest.raises(ValidationError, match="owner's calibration record"):
        VisionEvaluationResult(
            created_at="2026-08-14T00:00:00+00:00",
            artifact_path=Path("show.xsq"),
            artifact_sha256="a" * 64,
            preview_path=Path("preview.mp4"),
            preview_sha256="b" * 64,
            plan_sha256="c" * 64,
            evaluation_config_sha256="d" * 64,
            sampled_frame_count=9,
            judge_image_count=1,
            sampling=FrameSamplerConfig(),
            visual=JudgedFrames(
                rubric=_rubric(7),
                model="configured-mini-tier",
                estimate=VisionCostEstimate(
                    image_count=1,
                    image_megapixels=0.9,
                    image_cost_usd=0.1,
                    output_allowance_usd=0.001,
                    estimated_cost_usd=0.101,
                ),
                actual_cost_usd=0.09,
                usage=VisionTokenUsage(
                    prompt_tokens=100,
                    reasoning_tokens=5,
                    completion_tokens=20,
                    total_tokens=125,
                ),
            ),
            deterministic=_sync(),
            calibration_status="calibrated",
        )


def test_calibrated_result_rejects_nonexistent_owner_record(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="does not exist"):
        VisionEvaluationResult(
            created_at="2026-08-14T00:00:00+00:00",
            artifact_path=Path("show.xsq"),
            artifact_sha256="a" * 64,
            preview_path=Path("preview.mp4"),
            preview_sha256="b" * 64,
            plan_sha256="c" * 64,
            evaluation_config_sha256="d" * 64,
            sampled_frame_count=9,
            judge_image_count=1,
            sampling=FrameSamplerConfig(),
            visual=JudgedFrames(
                rubric=_rubric(7),
                model="configured-mini-tier",
                estimate=VisionCostEstimate(
                    image_count=1,
                    image_megapixels=0.9,
                    image_cost_usd=0.1,
                    output_allowance_usd=0.001,
                    estimated_cost_usd=0.101,
                ),
                actual_cost_usd=0.09,
                usage=VisionTokenUsage(
                    prompt_tokens=100,
                    reasoning_tokens=5,
                    completion_tokens=20,
                    total_tokens=125,
                ),
            ),
            deterministic=_sync(),
            calibration_status="calibrated",
            calibration_record=tmp_path / "missing.json",
        )


@pytest.mark.asyncio
async def test_deterministic_preflight_fails_before_paid_call(tmp_path: Path) -> None:
    preview = tmp_path / "preview.mp4"
    preview.write_bytes(b"preview")
    artifact = tmp_path / "broken.xsq"
    artifact.write_text("not XML", encoding="utf-8")
    frame_path = tmp_path / "frame.png"
    Image.new("RGB", (320, 180), "black").save(frame_path)
    runner = MagicMock()
    runner.run = AsyncMock(side_effect=AssertionError("paid provider must not be called"))
    plan = ChoreographyPlan.model_validate(
        {
            "sections": [
                {
                    "section_name": "chorus",
                    "start_bar": 1,
                    "end_bar": 1,
                    "template_id": "sweep_lr_fan_hold",
                }
            ]
        }
    )

    with (
        patch(
            "twinklr.core.reporting.evaluation.vision_evaluation.FrameSampler.sample",
            return_value=[
                SampledFrame(
                    index=1,
                    timestamp_ms=0,
                    path=frame_path,
                    width=320,
                    height=180,
                )
            ],
        ),
        pytest.raises(ValueError, match="Malformed XML"),
    ):
        await evaluate_preview(
            runner=runner,
            agent_config=AgentOrchestrationConfig().vision_judge_agent,
            preview_path=preview,
            artifact_path=artifact,
            plan=plan,
            beat_grid=BeatGrid.from_tempo(tempo_bpm=120, total_bars=1),
            output_dir=tmp_path / "output",
        )

    runner.run.assert_not_called()


@pytest.mark.asyncio
async def test_combined_record_hashes_preview_plan_and_config(tmp_path: Path) -> None:
    preview = tmp_path / "preview.mp4"
    preview.write_bytes(b"preview-v1")
    artifact = tmp_path / "show.xsq"
    artifact.write_text(
        """<?xml version="1.0"?><xsequence><head><version>2026.15</version>
        <mediaFile>song.mp3</mediaFile><sequenceDuration>2.000</sequenceDuration></head>
        <nextid>1</nextid><ElementEffects>
        <Element type="timing" name="Twinklr Beats"><EffectLayer>
        <Effect label="1.1" startTime="0" endTime="1" />
        <Effect label="1.2" startTime="500" endTime="501" />
        <Effect label="1.3" startTime="1000" endTime="1001" />
        <Effect label="1.4" startTime="1500" endTime="1501" />
        </EffectLayer></Element>
        <Element type="timing" name="Twinklr Bars"><EffectLayer>
        <Effect label="Bar 1" startTime="0" endTime="1" />
        </EffectLayer></Element>
        <Element type="model" name="Head 1"><EffectLayer>
        <Effect name="On" startTime="0" endTime="500" palette="0" />
        </EffectLayer></Element></ElementEffects></xsequence>""",
        encoding="utf-8",
    )
    frame_path = tmp_path / "frame.png"
    Image.new("RGB", (320, 180), "black").save(frame_path)
    runner = MagicMock()
    runner.run = AsyncMock(
        return_value=AgentResult(
            success=True,
            data=_rubric(7),
            duration_seconds=0.1,
            tokens_used=12,
            prompt_tokens=10,
            completion_tokens=2,
            metadata={"model": "configured-mini-tier"},
        )
    )
    plan = ChoreographyPlan.model_validate(
        {
            "sections": [
                {
                    "section_name": "chorus",
                    "start_bar": 1,
                    "end_bar": 1,
                    "template_id": "sweep_lr_fan_hold",
                }
            ]
        }
    )

    with patch(
        "twinklr.core.reporting.evaluation.vision_evaluation.FrameSampler.sample",
        return_value=[
            SampledFrame(
                index=1,
                timestamp_ms=0,
                path=frame_path,
                width=320,
                height=180,
            )
        ],
    ):
        result = await evaluate_preview(
            runner=runner,
            agent_config=AgentOrchestrationConfig().vision_judge_agent,
            preview_path=preview,
            artifact_path=artifact,
            plan=plan,
            beat_grid=BeatGrid.from_tempo(tempo_bpm=120, total_bars=1),
            output_dir=tmp_path / "output",
        )

    assert result.preview_sha256 == hashlib.sha256(preview.read_bytes()).hexdigest()
    assert result.artifact_sha256 == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert len(result.plan_sha256) == 64
    assert len(result.evaluation_config_sha256) == 64
    runner.run.assert_awaited_once()


def test_only_hash_pinned_owner_accepted_calibration_can_mark_result(tmp_path: Path) -> None:
    accepted_path = tmp_path / "accepted.json"
    accepted_path.write_text(_owner_artifact("accepted").model_dump_json(), encoding="utf-8")
    accepted_hash = hashlib.sha256(accepted_path.read_bytes()).hexdigest()
    result = VisionEvaluationResult.model_validate(
        {
            **_result_payload(),
            "calibration_status": "calibrated",
            "calibration_record": accepted_path,
            "calibration_record_sha256": accepted_hash,
        }
    )
    assert result.calibration_status == "calibrated"

    rejected_path = tmp_path / "rejected.json"
    rejected_path.write_text(_owner_artifact("rejected").model_dump_json(), encoding="utf-8")
    rejected_hash = hashlib.sha256(rejected_path.read_bytes()).hexdigest()
    with pytest.raises(ValidationError, match="decision is not accepted"):
        VisionEvaluationResult.model_validate(
            {
                **_result_payload(),
                "calibration_status": "calibrated",
                "calibration_record": rejected_path,
                "calibration_record_sha256": rejected_hash,
            }
        )


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("artifact_sha256", "artifact_sha256 values must be unique"),
        ("preview_sha256", "preview_sha256 values must be unique"),
    ],
)
def test_owner_calibration_rejects_duplicate_sequence_hashes(field: str, message: str) -> None:
    payload = _owner_artifact("accepted").model_dump(mode="json")
    payload["samples"][1][field] = payload["samples"][0][field]

    with pytest.raises(ValidationError, match=message):
        OwnerCalibrationArtifact.model_validate(payload)
