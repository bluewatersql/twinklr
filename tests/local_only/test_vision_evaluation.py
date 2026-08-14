"""Owner-controlled paid/local proof for P2P-T6.

This test consumes a preview already exported through P2P-T5. It never starts or
drives xLights itself and it makes exactly one OpenAI Responses request.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.providers.openai import OpenAIProvider
from twinklr.core.config.models import AgentOrchestrationConfig
from twinklr.core.reporting.evaluation.collect import extract_plan, load_checkpoint
from twinklr.core.reporting.evaluation.sync_metrics import beat_grid_from_xsq
from twinklr.core.reporting.evaluation.vision_evaluation import evaluate_preview


@pytest.mark.local_only
@pytest.mark.asyncio
async def test_end_to_end_score_one_song(tmp_path: Path) -> None:
    """Score one owner-supplied real preview under the hard $0.20 cap."""
    if os.getenv("TWINKLR_RUN_LIVE_VISION_TESTS") != "1":
        pytest.skip("Set TWINKLR_RUN_LIVE_VISION_TESTS=1 for the one-call paid proof")
    api_key = os.getenv("OPENAI_API_KEY")
    preview = os.getenv("TWINKLR_VISION_PREVIEW")
    xsq = os.getenv("TWINKLR_VISION_XSQ")
    checkpoint = os.getenv("TWINKLR_VISION_CHECKPOINT")
    if not all((api_key, preview, xsq, checkpoint)):
        pytest.skip(
            "Set OPENAI_API_KEY, TWINKLR_VISION_PREVIEW, TWINKLR_VISION_XSQ, and "
            "TWINKLR_VISION_CHECKPOINT"
        )

    assert api_key is not None and preview is not None and xsq is not None
    assert checkpoint is not None
    provider = OpenAIProvider(api_key=api_key)
    runner = AsyncAgentRunner(
        provider, Path(__file__).parents[3] / "packages/twinklr/core/reporting/evaluation"
    )
    plan = extract_plan(load_checkpoint(Path(checkpoint)))
    result = await evaluate_preview(
        runner=runner,
        agent_config=AgentOrchestrationConfig().vision_judge_agent,
        preview_path=Path(preview),
        artifact_path=Path(xsq),
        plan=plan,
        beat_grid=beat_grid_from_xsq(Path(xsq)),
        output_dir=tmp_path,
    )

    assert result.visual.actual_cost_usd <= 0.20
    assert result.visual.logical_request_count == 1
    assert result.visual.provider_attempt_cap == 1
    assert result.calibration_status == "uncalibrated"
    assert (tmp_path / "vision_evaluation.json").is_file()
