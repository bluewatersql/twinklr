"""Shared hard request boundary and contact-sheet grounding for rubric-v2."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from tests.unit.reporting.evaluation.show_test_support import entry, manifest, trace
from twinklr.core.config.models import AgentConfig
from twinklr.core.reporting.evaluation.show_judge import (
    CrossPartCoordinationScore,
    ShowVisionRubricResponse,
    VisualCriterionScore,
    build_show_judge_payload_from_models,
    judge_show_frames,
    validate_show_grounding,
)
from twinklr.core.reporting.evaluation.vision_judge import (
    MAX_REQUEST_BYTES,
    BudgetExceededError,
    FrameInput,
    RubricCategoryScore,
    VisionBudgetLedger,
    VisionJudgeConfig,
    validate_vision_request_payload,
)


def _rubric(citation: str) -> ShowVisionRubricResponse:
    category = RubricCategoryScore(score=8, justification=citation)
    criterion = VisualCriterionScore(applicability="scored", score=8, justification=citation)
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


def test_shared_preflight_rejects_more_than_1500_images_before_file_reads(tmp_path: Path) -> None:
    missing = tmp_path / "not-read.png"
    frames = [
        FrameInput(index=index + 1, timestamp_ms=index, path=missing) for index in range(1501)
    ]
    with pytest.raises(BudgetExceededError, match="1,500-image"):
        validate_vision_request_payload(frames, context_text="{}")


@pytest.mark.asyncio
async def test_show_preflight_runs_before_reservation_and_provider(tmp_path: Path) -> None:
    frames = [
        FrameInput(index=index + 1, timestamp_ms=index, path=tmp_path / "missing.png")
        for index in range(1501)
    ]
    ledger = VisionBudgetLedger(config=VisionJudgeConfig())
    runner = AsyncMock()
    with pytest.raises(BudgetExceededError, match="1,500-image"):
        await judge_show_frames(
            runner=runner,
            agent_config=AgentConfig(model="test-model"),
            frames=frames,
            payload=build_show_judge_payload_from_models(
                manifest(), trace(entry("display", 0, 500), entry("moving_head", 500, 1_000))
            ),
            section_names={"Section"},
            config=VisionJudgeConfig(),
            ledger=ledger,
        )
    assert ledger.song_count == 0
    runner.run.assert_not_awaited()


def test_shared_preflight_rejects_encoded_payload_over_512_mib(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(b"x")
    monkeypatch.setattr(
        "twinklr.core.reporting.evaluation.vision_judge._encoded_image_bytes",
        lambda _path: MAX_REQUEST_BYTES + 1,
    )
    with pytest.raises(BudgetExceededError, match="512 MiB"):
        validate_vision_request_payload(
            [FrameInput(index=1, timestamp_ms=0, path=image)], context_text="{}"
        )


def test_show_grounding_accepts_frame_inside_contact_sheet_range(tmp_path: Path) -> None:
    frame = FrameInput(
        index=1,
        timestamp_ms=0,
        path=tmp_path / "sheet.png",
        label="Contact sheet 1: Frames 1–12",
    )
    validate_show_grounding(
        _rubric("Frame 10 shows a clear Section exchange."),
        frames=[frame],
        section_names={"Section"},
    )


def test_show_grounding_rejects_frame_outside_contact_sheet_range(tmp_path: Path) -> None:
    frame = FrameInput(
        index=1,
        timestamp_ms=0,
        path=tmp_path / "sheet.png",
        label="Contact sheet 1: Frames 1–12",
    )
    with pytest.raises(RuntimeError, match="unknown frame"):
        validate_show_grounding(
            _rubric("Frame 13 shows a clear Section exchange."),
            frames=[frame],
            section_names={"Section"},
        )
