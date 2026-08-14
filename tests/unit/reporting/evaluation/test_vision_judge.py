"""Offline contract tests for the vision evaluation producer."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
import pytest

from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.prompts import PromptPackLoader
from twinklr.core.agents.providers.base import ProviderType
from twinklr.core.agents.result import AgentResult
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.models import AgentOrchestrationConfig
from twinklr.core.reporting.evaluation.vision_evaluation import plan_structure
from twinklr.core.reporting.evaluation.vision_judge import (
    BudgetExceededError,
    FrameInput,
    VisionAttemptSpend,
    VisionBudgetLedger,
    VisionJudgeConfig,
    VisionRubricResponse,
    VisionTokenUsage,
    _validate_grounding,
    build_structure_text,
    estimate_vision_cost,
    get_vision_judge_spec,
    judge_frames,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def _frame(tmp_path: Path, index: int = 1) -> FrameInput:
    path = tmp_path / f"frame_{index:03d}.png"
    Image.new("RGB", (1280, 720), "black").save(path)
    return FrameInput(index=index, timestamp_ms=(index - 1) * 500, path=path)


def test_rubric_has_no_sync_criterion() -> None:
    fields = set(VisionRubricResponse.model_fields)
    assert fields == {
        "musicality_by_proxy",
        "coordination",
        "color_palette_coherence",
        "variety_and_pacing",
    }
    spec = get_vision_judge_spec(AgentOrchestrationConfig().vision_judge_agent)
    assert spec.model == AgentOrchestrationConfig().vision_judge_agent.model
    assert spec.max_schema_repair_attempts == 0
    assert spec.provider_max_attempts == 1
    assert spec.allow_json_object_fallback is False
    provider = MagicMock()
    provider.provider_type = ProviderType.OPENAI
    runner = AsyncAgentRunner(provider, Path(__file__).parent)
    request_kwargs = runner._provider_request_kwargs(spec)
    assert request_kwargs["provider_max_attempts"] == 1
    assert request_kwargs["allow_json_object_fallback"] is False

    prompt_root = (
        Path(__file__).parents[4] / "packages" / "twinklr" / "core" / "reporting" / "evaluation"
    )
    rendered = PromptPackLoader(prompt_root).load_and_render(
        "prompts/vision_judge",
        {
            "response_schema": "{}",
            "structure_text": "chorus [00:02.000–00:04.000]",
            "frame_manifest": "Frame 1: 00:02.000",
        },
    )
    all_prompt_text = "\n".join(str(value) for value in rendered.values()).lower()
    assert "sync" not in all_prompt_text
    assert "timing accuracy" not in all_prompt_text
    assert all_prompt_text.count("musicality-by-proxy") == 1
    assert all_prompt_text.count("coordination:") == 1
    assert all_prompt_text.count("color / palette coherence") == 1
    assert all_prompt_text.count("variety & pacing") == 1


def test_structure_text_accompanies_frames(tmp_path: Path) -> None:
    text = build_structure_text(
        sections=[
            {
                "section_name": "chorus",
                "start_ms": 2000,
                "end_ms": 4000,
                "intent": "PEAK; primary palette; sweep_lr",
            }
        ],
        tempo_bpm=120.0,
        beats_per_bar=4,
        beat_count=8,
        downbeat_count=2,
    )
    assert "chorus" in text
    assert "00:02.000" in text
    assert "00:04.000" in text


@pytest.mark.asyncio
async def test_cost_estimate_blocks_over_cap_before_provider_call(tmp_path: Path) -> None:
    runner = MagicMock()
    runner.run = AsyncMock(side_effect=AssertionError("provider must not be called"))
    config = VisionJudgeConfig(per_song_cap_usd=0.0001, per_run_cap_usd=1.0)
    ledger = VisionBudgetLedger(config=config)

    with pytest.raises(BudgetExceededError, match="per-song"):
        await judge_frames(
            runner=runner,
            agent_config=AgentOrchestrationConfig().vision_judge_agent,
            frames=[_frame(tmp_path)],
            structure_text="non-empty structure",
            section_names={"chorus"},
            config=config,
            ledger=ledger,
        )
    runner.run.assert_not_called()


@pytest.mark.asyncio
async def test_judge_uses_provider_framework_images_and_exact_usage(tmp_path: Path) -> None:
    response = VisionRubricResponse.model_validate(
        {
            key: {"score": 7.0, "justification": "Frame 1 in section chorus supports this."}
            for key in VisionRubricResponse.model_fields
        }
    )
    runner = MagicMock()
    runner.run = AsyncMock(
        return_value=AgentResult(
            success=True,
            data=response,
            duration_seconds=0.2,
            tokens_used=140,
            prompt_tokens=100,
            reasoning_tokens=10,
            completion_tokens=30,
            metadata={"model": "configured-mini-tier"},
        )
    )
    config = VisionJudgeConfig(
        per_song_cap_usd=1.0,
        per_run_cap_usd=2.0,
        input_usd_per_million_tokens=1.0,
        output_usd_per_million_tokens=2.0,
    )

    judged = await judge_frames(
        runner=runner,
        agent_config=AgentOrchestrationConfig().vision_judge_agent.model_copy(
            update={"model": "configured-mini-tier"}
        ),
        frames=[_frame(tmp_path)],
        structure_text="chorus [00:00.000–00:02.000] intent: PEAK",
        section_names={"chorus"},
        config=config,
        ledger=VisionBudgetLedger(config=config),
    )

    call = runner.run.call_args
    assert call.kwargs["input_image_urls"][0].startswith("data:image/png;base64,")
    assert "structure_text" in call.kwargs["variables"]
    assert judged.usage.prompt_tokens == 100
    assert judged.usage.reasoning_tokens == 10
    assert judged.usage.completion_tokens == 30
    assert judged.actual_cost_usd == pytest.approx((100 + (10 + 30) * 2) / 1_000_000)


@pytest.mark.asyncio
async def test_failed_attempt_usage_is_settled_before_error(tmp_path: Path) -> None:
    runner = MagicMock()
    runner.run = AsyncMock(
        return_value=AgentResult(
            success=False,
            error_message="capability rejected",
            duration_seconds=0.1,
            tokens_used=70,
            prompt_tokens=50,
            reasoning_tokens=5,
            completion_tokens=15,
        )
    )
    config = VisionJudgeConfig(
        per_song_cap_usd=1.0,
        input_usd_per_million_tokens=1.0,
        output_usd_per_million_tokens=2.0,
    )
    ledger = VisionBudgetLedger(config=config)

    with pytest.raises(RuntimeError, match="capability rejected"):
        await judge_frames(
            runner=runner,
            agent_config=AgentOrchestrationConfig().vision_judge_agent,
            frames=[_frame(tmp_path)],
            structure_text="chorus",
            section_names={"chorus"},
            config=config,
            ledger=ledger,
        )

    expected = (50 + (5 + 15) * 2) / 1_000_000
    assert ledger.actual_usd == pytest.approx(expected)
    assert ledger.outstanding_estimate_usd == 0.0
    assert ledger.projected_spend_usd == pytest.approx(expected)
    assert ledger.attempts[0].success is False
    assert ledger.attempts[0].usage.total_tokens == 70


@pytest.mark.asyncio
async def test_request_image_count_and_encoded_bytes_are_hard_limited(tmp_path: Path) -> None:
    runner = MagicMock()
    runner.run = AsyncMock(side_effect=AssertionError("provider must not be called"))
    frame = _frame(tmp_path)
    config = VisionJudgeConfig(per_song_cap_usd=1000, per_run_cap_usd=1000)

    with pytest.raises(BudgetExceededError, match="1,500-image"):
        await judge_frames(
            runner=runner,
            agent_config=AgentOrchestrationConfig().vision_judge_agent,
            frames=[frame] * 1501,
            structure_text="chorus",
            section_names={"chorus"},
            config=config,
            ledger=VisionBudgetLedger(config=config),
        )

    with (
        patch(
            "twinklr.core.reporting.evaluation.vision_judge._encoded_image_bytes",
            return_value=512 * 1024 * 1024 + 1,
        ),
        pytest.raises(BudgetExceededError, match="512 MiB"),
    ):
        await judge_frames(
            runner=runner,
            agent_config=AgentOrchestrationConfig().vision_judge_agent,
            frames=[frame],
            structure_text="chorus",
            section_names={"chorus"},
            config=config,
            ledger=VisionBudgetLedger(config=config),
        )
    runner.run.assert_not_called()


@pytest.mark.asyncio
async def test_grounding_rejects_generic_and_unknown_citations(tmp_path: Path) -> None:
    bad = VisionRubricResponse.model_validate(
        {
            key: {"score": 7.0, "justification": "Frame 999 supports section nowhere."}
            for key in VisionRubricResponse.model_fields
        }
    )
    runner = MagicMock()
    runner.run = AsyncMock(
        return_value=AgentResult(
            success=True,
            data=bad,
            duration_seconds=0.1,
            tokens_used=3,
            prompt_tokens=2,
            completion_tokens=1,
            metadata={"model": "configured-mini-tier"},
        )
    )
    config = VisionJudgeConfig(per_song_cap_usd=1.0)

    with pytest.raises(RuntimeError, match="unknown frame 999"):
        await judge_frames(
            runner=runner,
            agent_config=AgentOrchestrationConfig().vision_judge_agent,
            frames=[_frame(tmp_path)],
            structure_text="chorus",
            section_names={"chorus"},
            config=config,
            ledger=VisionBudgetLedger(config=config),
        )

    generic = VisionRubricResponse.model_validate(
        {
            key: {"score": 7.0, "justification": "The frame supports section nowhere."}
            for key in VisionRubricResponse.model_fields
        }
    )
    runner.run = AsyncMock(
        return_value=AgentResult(
            success=True,
            data=generic,
            duration_seconds=0.1,
            tokens_used=3,
            prompt_tokens=2,
            completion_tokens=1,
            metadata={"model": "configured-mini-tier"},
        )
    )
    with pytest.raises(RuntimeError, match="real section name"):
        await judge_frames(
            runner=runner,
            agent_config=AgentOrchestrationConfig().vision_judge_agent,
            frames=[_frame(tmp_path)],
            structure_text="chorus",
            section_names={"chorus"},
            config=config,
            ledger=VisionBudgetLedger(config=config),
        )


def test_estimate_counts_resolution_and_bounded_output(tmp_path: Path) -> None:
    config = VisionJudgeConfig(
        image_input_usd_per_megapixel=0.5,
        estimated_output_tokens=100,
        output_usd_per_million_tokens=2.0,
    )
    estimate = estimate_vision_cost([_frame(tmp_path)], config)
    assert estimate.image_megapixels == pytest.approx(1.28 * 0.72)
    assert estimate.estimated_cost_usd == pytest.approx(0.4608 + 0.0002)


def test_run_cap_reconciles_actual_and_outstanding_estimates(tmp_path: Path) -> None:
    config = VisionJudgeConfig(per_song_cap_usd=1.0, per_run_cap_usd=0.15)
    ledger = VisionBudgetLedger(config=config)
    estimate = estimate_vision_cost([_frame(tmp_path)], config).model_copy(
        update={"estimated_cost_usd": 0.10}
    )
    reservation = ledger.reserve(estimate)
    ledger.settle(
        reservation,
        spend=VisionAttemptSpend(
            success=True,
            usage=VisionTokenUsage(
                prompt_tokens=1,
                reasoning_tokens=0,
                completion_tokens=1,
                total_tokens=2,
            ),
            actual_cost_usd=0.12,
        ),
    )
    next_estimate = estimate.model_copy(update={"estimated_cost_usd": 0.04})

    with pytest.raises(BudgetExceededError, match="per-run"):
        ledger.reserve(next_estimate)


def test_contact_sheet_frame_ranges_are_valid_grounding(tmp_path: Path) -> None:
    rubric = VisionRubricResponse.model_validate(
        {
            key: {"score": 7.0, "justification": "Frame 10 supports section chorus."}
            for key in VisionRubricResponse.model_fields
        }
    )
    contact = _frame(tmp_path).model_copy(
        update={"label": "Contact sheet 1: Frames 1–12; 00:00.000–00:05.500"}
    )

    _validate_grounding(rubric, frames=[contact], section_names={"chorus"})


def test_current_plan_shape_builds_timestamped_structure() -> None:
    plan = ChoreographyPlan.model_validate(
        {
            "sections": [
                {
                    "section_name": "chorus",
                    "start_bar": 2,
                    "end_bar": 3,
                    "template_id": "sweep_lr_fan_hold",
                }
            ]
        }
    )
    judge_sections, metric_sections = plan_structure(
        plan, BeatGrid.from_tempo(tempo_bpm=120.0, total_bars=4)
    )
    assert judge_sections[0]["start_ms"] == 2000
    assert judge_sections[0]["end_ms"] == 6000
    assert "intensity=SMOOTH" in str(judge_sections[0]["intent"])
    assert metric_sections[0].bars == 2
