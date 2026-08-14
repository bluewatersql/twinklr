"""P2P-T13 manifest, orchestration, blinding, budget, and parity tests."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import pytest

from twinklr.core.agents.sequencer.moving_heads.deterministic_selector import SelectorSection
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.agents.shared.judge.controller import IterationCallRecord, IterationCallUsage
from twinklr.core.reporting.evaluation.calibration import (
    CalibrationBatch,
    OwnerCalibrationArtifact,
    calculate_calibration,
)
from twinklr.core.reporting.evaluation.render import write_comparison_report_json
from twinklr.core.reporting.evaluation.sync_metrics import (
    BoundaryAlignment,
    DeterministicSyncMetrics,
    GridStartAlignment,
    OffsetDistribution,
)
from twinklr.core.reporting.evaluation.three_arm import (
    AnalysisSnapshot,
    Arm,
    ArmCallRecord,
    ArmExecutionRequest,
    ArmRunResult,
    BlindReviewItem,
    BlindReviewPacket,
    ComparisonExperimentRunner,
    ComparisonManifest,
    ComparisonReport,
    ExperimentBlockedError,
    HeldConstantIdentity,
    HumanRanking,
    PreCallSpendGate,
    PricingIdentity,
    ProviderOperationError,
    RoleExecutionConfig,
    RubricScores,
    SequenceScore,
    SongManifestEntry,
    SpendPolicy,
    SyncScores,
    VisionEvaluationEvidence,
    _planning_cache_key,
    _planning_input_identity,
    arm_call_records_from_iteration,
    build_blind_review,
    compute_comparison_report,
    stage_blind_review_packet,
    write_human_ranking,
    write_reveal_key_after_ranking,
)
from twinklr.core.reporting.evaluation.three_arm_cli import _run_owner, build_parser
from twinklr.core.reporting.evaluation.vision_evaluation import VisionEvaluationResult
from twinklr.core.reporting.evaluation.vision_frames import FrameSamplerConfig
from twinklr.core.reporting.evaluation.vision_judge import (
    JudgedFrames,
    VisionCostEstimate,
    VisionRubricResponse,
    VisionTokenUsage,
)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _identity_sha(value: object) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _call(role: str, *, cost: float = 0, succeeded: bool = True) -> ArmCallRecord:
    is_vision = role == "vision_judge"
    if is_vision:
        model, reasoning, temperature, pricing_id = "vision-model", "low", 0.0, "vision-price"
        rates = (0.2, 1.2, 1.2)
    elif "macro" in role:
        model, reasoning, temperature, pricing_id = "macro-model", "high", 0.3, "macro-price"
        rates = (1.0, 2.0, 3.0)
    else:
        model, reasoning, temperature, pricing_id = "moving-model", "medium", 0.7, "moving-price"
        rates = (4.0, 5.0, 6.0)
    prompt, reasoning_tokens, completion = (100, 5, 20) if is_vision else (1, 0, 0)
    priced = (prompt * rates[0] + reasoning_tokens * rates[1] + completion * rates[2]) / 1_000_000
    actual_cost = priced if cost == 0 else cost
    return ArmCallRecord(
        role=role,
        model=model,
        reasoning_effort=reasoning,
        temperature=temperature,
        pricing_id=pricing_id,
        logical_requests=1,
        provider_attempts=1,
        prompt_tokens=prompt,
        reasoning_tokens=reasoning_tokens,
        completion_tokens=completion,
        total_tokens=prompt + reasoning_tokens + completion,
        cost_usd=actual_cost,
        succeeded=succeeded,
        failure=None if succeeded else "provider_timeout",
    )


def _calibrated_manifest(tmp_path: Path) -> ComparisonManifest:
    calibration = tmp_path / "calibration.json"
    calibration.write_text(
        _owner_artifact().model_dump_json(exclude_computed_fields=True), encoding="utf-8"
    )
    return _manifest(tmp_path, calibration_path=calibration)


def _rubric(score: float) -> VisionRubricResponse:
    return VisionRubricResponse.model_validate(
        {
            field: {"score": score, "justification": "Frame 1 supports section chorus."}
            for field in VisionRubricResponse.model_fields
        }
    )


def _owner_artifact() -> OwnerCalibrationArtifact:
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
            "decision": "accepted",
            "rubric_version": "lighting-automv-v1",
            "sampling": FrameSamplerConfig().model_dump(mode="json"),
            "samples": samples,
            "report": calculate_calibration(batch),
        }
    )


def _sync(rate: float) -> DeterministicSyncMetrics:
    distribution = OffsetDistribution(
        count=0,
        signed_offsets_ms=[],
        mean_absolute_ms=0,
        median_absolute_ms=0,
        p95_absolute_ms=0,
        mean_signed_ms=0,
        standard_deviation_ms=0,
    )
    grid = GridStartAlignment(
        tolerance_ms=50,
        on_grid_count=0,
        effect_count=0,
        on_grid_rate=rate,
        offsets=distribution,
    )
    return DeterministicSyncMetrics(
        beat_starts=grid,
        downbeat_starts=grid,
        section_boundaries=BoundaryAlignment(
            tolerance_ms=50,
            aligned_count=0,
            boundary_count=0,
            alignment_rate=rate,
            offsets=distribution,
        ),
        section_density=[],
    )


def _vision(
    calibration_path: Path,
    calibration_sha: str,
    evaluation_sha: str,
    *,
    plan: ChoreographyPlan,
    preview_path: Path,
    preview_sha256: str,
    rubric_score: float,
    sync_rate: float,
) -> VisionEvaluationEvidence:
    result = VisionEvaluationResult(
        created_at="2026-08-14T00:00:00+00:00",
        artifact_path=preview_path,
        artifact_sha256=preview_sha256,
        preview_path=preview_path,
        preview_sha256=preview_sha256,
        plan_sha256=_identity_sha(plan.model_dump(mode="json")),
        evaluation_config_sha256=evaluation_sha,
        sampled_frame_count=9,
        judge_image_count=1,
        sampling=FrameSamplerConfig(),
        visual=JudgedFrames(
            rubric=_rubric(rubric_score),
            model="vision-model",
            estimate=VisionCostEstimate(
                image_count=1,
                image_megapixels=0.9,
                image_cost_usd=0.1,
                output_allowance_usd=0.001,
                estimated_cost_usd=0.101,
            ),
            actual_cost_usd=0.00005,
            usage=VisionTokenUsage(
                prompt_tokens=100,
                reasoning_tokens=5,
                completion_tokens=20,
                total_tokens=125,
            ),
        ),
        deterministic=_sync(sync_rate),
        calibration_status="calibrated",
        calibration_record=calibration_path,
        calibration_record_sha256=calibration_sha,
    )
    return VisionEvaluationEvidence.from_vision(
        result,
        calibration_record_sha256=calibration_sha,
        evaluation_config_sha256=evaluation_sha,
    )


def _songs(tmp_path: Path) -> list[SongManifestEntry]:
    songs = []
    for index in range(8):
        path = tmp_path / f"song-{index}.wav"
        path.write_bytes(f"audio-{index}".encode())
        songs.append(
            SongManifestEntry(
                song_id=f"s{index}",
                name=f"Song {index}",
                audio_path=path,
                audio_sha256=_sha(path.read_bytes()),
                genres=["rock" if index < 4 else "electronic"],
                prominent_lyrics=index == 0,
                instrumental=index == 1,
                non_four_four_or_tempo_varying=index == 2,
                owner_familiar=index == 3,
            )
        )
    return songs


def _manifest(tmp_path: Path, *, calibration_path: Path | None = None) -> ComparisonManifest:
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    return ComparisonManifest(
        experiment_id="p2p-t13-fixture",
        frozen_at=datetime.now(UTC),
        songs=_songs(tmp_path),
        seed=44,
        macro_planner=RoleExecutionConfig(
            model="macro-model",
            reasoning_effort="high",
            temperature=0.3,
            pricing=PricingIdentity(
                pricing_id="macro-price",
                prompt_per_million_usd=1,
                reasoning_per_million_usd=2,
                completion_per_million_usd=3,
            ),
        ),
        moving_head_planner=RoleExecutionConfig(
            model="moving-model",
            reasoning_effort="medium",
            temperature=0.7,
            pricing=PricingIdentity(
                pricing_id="moving-price",
                prompt_per_million_usd=4,
                reasoning_per_million_usd=5,
                completion_per_million_usd=6,
            ),
        ),
        vision_judge=RoleExecutionConfig(
            model="vision-model",
            reasoning_effort="low",
            temperature=0,
            pricing=PricingIdentity(
                pricing_id="vision-price",
                prompt_per_million_usd=0.2,
                reasoning_per_million_usd=1.2,
                completion_per_million_usd=1.2,
            ),
        ),
        llm_runs_per_song=2,
        grid_source="dsp@5",
        stems_setting="disabled",
        fixture_config_path=fixture,
        fixture_config_sha256=_sha(fixture.read_bytes()),
        evaluation_harness_version="lighting-automv-v1",
        calibration_record=calibration_path,
        calibration_record_sha256=(
            _sha(calibration_path.read_bytes()) if calibration_path is not None else None
        ),
        spend=SpendPolicy(),
    )


class _Backend:
    def __init__(self) -> None:
        self.requests: list[ArmExecutionRequest] = []
        self.analysis_calls = 0

    async def analyze(self, song: SongManifestEntry) -> AnalysisSnapshot:
        self.analysis_calls += 1
        return AnalysisSnapshot(
            song_id=song.song_id,
            cache_key=f"analysis:{song.audio_sha256}",
            payload_sha256=_sha(song.song_id.encode()),
            selector_sections=[
                SelectorSection(
                    section_id="verse_1", role="verse", start_bar=1, end_bar=4, energy=45
                )
            ],
            beat_grid_sha256="b" * 64,
            stems_sha256="c" * 64,
            template_set_sha256="d" * 64,
            renderer_sha256="e" * 64,
            evaluation_config_sha256="f" * 64,
        )

    async def execute(self, request: ArmExecutionRequest) -> ArmRunResult:
        self.requests.append(request)
        calls = []
        if request.arm is Arm.B:
            calls = [
                _call("macro_planner"),
                _call("moving_head_planner"),
            ]
        elif request.arm is Arm.C:
            calls = [_call("moving_head_planner")]
        calls.append(_call("vision_judge"))
        for call in calls:
            authorization = request.spend_gate.authorize(
                role=call.role,
                kind="judging" if call.role == "vision_judge" else "planning",
                maximum_cost_usd=0.20 if call.role == "vision_judge" else 0.01,
            )
            request.spend_gate.settle(authorization, call)
        plan = request.plan or ChoreographyPlan.model_validate(
            {
                "sections": [
                    {
                        "section_name": "verse_1",
                        "start_bar": 1,
                        "end_bar": 4,
                        "section_role": "verse",
                        "energy_level": 45,
                        "template_id": "fan_pulse",
                        "intensity": "SMOOTH",
                        "color_intent": {
                            "selection": {
                                "kind": "PALETTE_ROLE",
                                "palette_role": "PRIMARY",
                                "explicit_color": None,
                            }
                        },
                        "shutter_events": [],
                        "gobo_events": [],
                        "moment_cues": [],
                    }
                ],
                "overall_strategy": "fixture",
            }
        )
        return ArmRunResult(
            run_id=f"{request.song.song_id}-{request.arm}-{request.replicate}",
            song_id=request.song.song_id,
            arm=request.arm,
            replicate=request.replicate,
            analysis_cache_key=request.analysis.cache_key,
            analysis_payload_sha256=request.analysis.payload_sha256,
            held_constant=request.held_constant,
            regeneration_nonce=(None if request.arm is Arm.A else request.regeneration_nonce),
            planning_input_sha256=request.planning_input_sha256,
            planning_cache_key=request.planning_cache_key,
            plan=plan,
            plan_sha256=_identity_sha(plan.model_dump(mode="json")),
            call_records=calls,
            planning_spend_usd=sum(call.cost_usd for call in calls if call.role != "vision_judge"),
            judging_spend_usd=sum(call.cost_usd for call in calls if call.role == "vision_judge"),
            score=SequenceScore(
                rubric=RubricScores(
                    musicality_by_proxy=7,
                    coordination=7,
                    color_palette_coherence=7,
                    variety_and_pacing=7,
                ),
                sync=SyncScores(beat=1, downbeat=1, section_boundary=1),
            ),
            vision_evaluation=_vision(
                request.calibration_record,
                request.calibration_record_sha256,
                request.held_constant.evaluation_config_sha256,
                plan=plan,
                preview_path=request.song.audio_path,
                preview_sha256=request.song.audio_sha256,
                rubric_score=7,
                sync_rate=1,
            ),
            review_artifact_path=request.song.audio_path,
            review_artifact_sha256=request.song.audio_sha256,
        )


@pytest.mark.asyncio
async def test_uncalibrated_gate_fails_before_any_experiment_work(tmp_path: Path) -> None:
    backend = _Backend()
    runner = ComparisonExperimentRunner(manifest=_manifest(tmp_path), backend=backend)
    with pytest.raises(ExperimentBlockedError, match="accepted P2P-T6 calibration"):
        await runner.run(owner_opt_in=True)
    assert backend.analysis_calls == 0
    assert backend.requests == []


@pytest.mark.asyncio
async def test_runner_holds_analysis_constant_and_ablates_macro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The calibration parser is tested by P2P-T6. Patch only this experiment gate so
    # this offline orchestration test never invents a fake owner artifact on disk.
    backend = _Backend()
    runner = ComparisonExperimentRunner(manifest=_calibrated_manifest(tmp_path), backend=backend)
    monkeypatch.setattr(runner, "_assert_calibrated", lambda: None)

    results = await runner.run(owner_opt_in=True)

    assert len(results) == 40
    assert backend.analysis_calls == 8
    by_song: dict[str, set[tuple[str, str]]] = {}
    for result in results:
        by_song.setdefault(result.song_id, set()).add(
            (result.analysis_cache_key, result.analysis_payload_sha256)
        )
    assert all(len(identities) == 1 for identities in by_song.values())

    arm_c = [result for result in results if result.arm is Arm.C]
    assert arm_c
    assert all(
        "macro_planner" not in {call.role for call in result.call_records} for result in arm_c
    )
    arm_a = [result for result in results if result.arm is Arm.A]
    assert all({call.role for call in result.call_records} == {"vision_judge"} for result in arm_a)


@pytest.mark.asyncio
async def test_runner_rejects_macro_call_in_arm_c(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _Backend()
    original = backend.execute

    async def bad_execute(request: ArmExecutionRequest) -> ArmRunResult:
        result = await original(request)
        if request.arm is Arm.C:
            macro_call = _call("macro_planner")
            authorization = request.spend_gate.authorize(
                role="macro_planner", kind="planning", maximum_cost_usd=0.01
            )
            request.spend_gate.settle(authorization, macro_call)
            return result.model_copy(update={"call_records": [*result.call_records, macro_call]})
        return result

    backend.execute = bad_execute  # type: ignore[method-assign]
    runner = ComparisonExperimentRunner(manifest=_calibrated_manifest(tmp_path), backend=backend)
    monkeypatch.setattr(runner, "_assert_calibrated", lambda: None)
    with pytest.raises(ExperimentBlockedError, match="Arm C call record contains macro"):
        await runner.run(owner_opt_in=True)


def test_pre_call_gate_counts_and_durably_journals_failed_and_repair_spend(
    tmp_path: Path,
) -> None:
    journal = tmp_path / "partial-attempts.json"
    gate = PreCallSpendGate(
        policy=SpendPolicy(),
        planning_cap_usd=0.10,
        judging_cap_usd=0.20,
        whole_remaining_usd=0.30,
        journal_path=journal,
    )
    failed = gate.authorize(role="moving_head_planner", kind="planning", maximum_cost_usd=0.05)
    gate.settle(
        failed,
        _call("moving_head_planner", cost=0.04, succeeded=False).model_copy(
            update={"provider_attempts": 3}
        ),
    )
    persisted = [ArmCallRecord.model_validate(item) for item in json.loads(journal.read_text())]
    assert persisted == [
        _call("moving_head_planner", cost=0.04, succeeded=False).model_copy(
            update={"provider_attempts": 3}
        )
    ]
    repair = gate.authorize(role="moving_head_repair", kind="planning", maximum_cost_usd=0.05)
    gate.settle(
        repair,
        _call("moving_head_repair", cost=0.05),
    )
    with pytest.raises(ExperimentBlockedError, match="hard reservation"):
        gate.authorize(role="moving_head_repair", kind="planning", maximum_cost_usd=0.02)
    assert sum(record.cost_usd for record in gate.records) == pytest.approx(0.09)
    assert len(json.loads(journal.read_text())) == 2


def test_pre_call_gate_rejects_outstanding_and_cross_kind_authorizations(
    tmp_path: Path,
) -> None:
    gate = PreCallSpendGate(
        policy=SpendPolicy(),
        planning_cap_usd=1,
        judging_cap_usd=1,
        whole_remaining_usd=2,
        journal_path=tmp_path / "calls.json",
    )
    first = gate.authorize(role="moving_head_planner", kind="planning", maximum_cost_usd=0.01)
    with pytest.raises(ExperimentBlockedError, match="outstanding"):
        gate.authorize(role="moving_head_repair", kind="planning", maximum_cost_usd=0.01)
    gate.settle(first, _call("moving_head_planner"))
    with pytest.raises(ExperimentBlockedError, match="must use the judging"):
        gate.authorize(role="vision_judge", kind="planning", maximum_cost_usd=0.01)
    with pytest.raises(ExperimentBlockedError, match="must use the planning"):
        gate.authorize(role="moving_head_planner", kind="judging", maximum_cost_usd=0.01)


@pytest.mark.asyncio
async def test_provider_wrapper_rejects_parallel_authorization(tmp_path: Path) -> None:
    gate = PreCallSpendGate(
        policy=SpendPolicy(),
        planning_cap_usd=1,
        judging_cap_usd=1,
        whole_remaining_usd=2,
        journal_path=tmp_path / "calls.json",
    )
    entered = asyncio.Event()
    release = asyncio.Event()
    fallback = _call("moving_head_planner", succeeded=False).model_copy(
        update={
            "prompt_tokens": 0,
            "reasoning_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0,
            "failure": "provider_exception_usage_unavailable",
        }
    )

    async def held_call() -> ArmCallRecord:
        entered.set()
        await release.wait()
        return _call("moving_head_planner")

    task = asyncio.create_task(
        gate.run_provider_call(
            role="moving_head_planner",
            kind="planning",
            maximum_cost_usd=0.01,
            operation=held_call,
            unknown_failure_record=fallback,
        )
    )
    await entered.wait()
    with pytest.raises(ExperimentBlockedError, match="outstanding"):
        await gate.run_provider_call(
            role="moving_head_repair",
            kind="planning",
            maximum_cost_usd=0.01,
            operation=lambda: asyncio.sleep(0, result=_call("moving_head_repair")),
            unknown_failure_record=fallback.model_copy(update={"role": "moving_head_repair"}),
        )
    release.set()
    await task


@pytest.mark.asyncio
async def test_provider_exception_is_settled_journaled_and_rethrown(tmp_path: Path) -> None:
    journal = tmp_path / "calls.json"
    gate = PreCallSpendGate(
        policy=SpendPolicy(),
        planning_cap_usd=1,
        judging_cap_usd=1,
        whole_remaining_usd=2,
        journal_path=journal,
    )
    exact_failure = _call("moving_head_planner", succeeded=False)
    unknown_failure = exact_failure.model_copy(
        update={
            "prompt_tokens": 0,
            "reasoning_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0,
            "failure": "provider_exception_usage_unavailable",
        }
    )

    async def explode() -> ArmCallRecord:
        raise ProviderOperationError("provider failed", call_record=exact_failure)

    with pytest.raises(ProviderOperationError, match="provider failed"):
        await gate.run_provider_call(
            role="moving_head_planner",
            kind="planning",
            maximum_cost_usd=0.01,
            operation=explode,
            unknown_failure_record=unknown_failure,
        )
    assert gate.records == (exact_failure,)
    assert [ArmCallRecord.model_validate(item) for item in json.loads(journal.read_text())] == [
        exact_failure
    ]
    followup = gate.authorize(role="moving_head_repair", kind="planning", maximum_cost_usd=0.01)
    gate.settle(followup, _call("moving_head_repair"))
    with pytest.raises(ExperimentBlockedError, match="already-settled"):
        gate.settle(followup, _call("moving_head_repair"))

    unknown_journal = tmp_path / "unknown-calls.json"
    unknown_gate = PreCallSpendGate(
        policy=SpendPolicy(),
        planning_cap_usd=1,
        judging_cap_usd=1,
        whole_remaining_usd=2,
        journal_path=unknown_journal,
    )

    async def explode_without_usage() -> ArmCallRecord:
        raise RuntimeError("usage unavailable")

    with pytest.raises(RuntimeError, match="usage unavailable"):
        await unknown_gate.run_provider_call(
            role="moving_head_planner",
            kind="planning",
            maximum_cost_usd=0.01,
            operation=explode_without_usage,
            unknown_failure_record=unknown_failure,
        )
    assert unknown_gate.records == (unknown_failure,)
    assert json.loads(unknown_journal.read_text())[0]["failure"] == (
        "provider_exception_usage_unavailable"
    )

    invalid_gate = PreCallSpendGate(
        policy=SpendPolicy(),
        planning_cap_usd=1,
        judging_cap_usd=1,
        whole_remaining_usd=2,
        journal_path=tmp_path / "invalid-result.json",
    )

    async def wrong_role_result() -> ArmCallRecord:
        return _call("macro_planner")

    with pytest.raises(ExperimentBlockedError, match="role does not match"):
        await invalid_gate.run_provider_call(
            role="moving_head_planner",
            kind="planning",
            maximum_cost_usd=0.01,
            operation=wrong_role_result,
            unknown_failure_record=unknown_failure,
        )
    assert invalid_gate.records == (unknown_failure,)
    next_authorization = invalid_gate.authorize(
        role="moving_head_planner", kind="planning", maximum_cost_usd=0.01
    )
    invalid_gate.settle(next_authorization, _call("moving_head_planner"))


@pytest.mark.parametrize("invalid_return", [None, object()])
@pytest.mark.asyncio
async def test_provider_wrapper_closes_and_journals_malformed_normal_return(
    tmp_path: Path, invalid_return: object
) -> None:
    journal = tmp_path / f"malformed-{type(invalid_return).__name__}.json"
    gate = PreCallSpendGate(
        policy=SpendPolicy(),
        planning_cap_usd=1,
        judging_cap_usd=1,
        whole_remaining_usd=2,
        journal_path=journal,
    )
    unknown = _call("moving_head_planner", succeeded=False).model_copy(
        update={
            "prompt_tokens": 0,
            "reasoning_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0,
            "failure": "provider_exception_usage_unavailable",
        }
    )

    async def malformed() -> ArmCallRecord:
        return invalid_return  # type: ignore[return-value]

    with pytest.raises(ExperimentBlockedError, match="invalid call evidence"):
        await gate.run_provider_call(
            role="moving_head_planner",
            kind="planning",
            maximum_cost_usd=0.01,
            operation=malformed,
            unknown_failure_record=unknown,
        )
    assert gate.records == (unknown,)
    assert [ArmCallRecord.model_validate(item) for item in json.loads(journal.read_text())] == [
        unknown
    ]
    next_authorization = gate.authorize(
        role="moving_head_planner", kind="planning", maximum_cost_usd=0.01
    )
    gate.settle(next_authorization, _call("moving_head_planner"))
    assert gate.records == (unknown, _call("moving_head_planner"))


@pytest.mark.parametrize("construction", ["model_construct", "model_copy"])
@pytest.mark.asyncio
async def test_provider_wrapper_revalidates_malformed_arm_call_record_instance(
    tmp_path: Path, construction: str
) -> None:
    valid = _call("moving_head_planner")
    if construction == "model_construct":
        payload = valid.model_dump()
        payload.update({"prompt_tokens": 9, "total_tokens": 0})
        invalid = ArmCallRecord.model_construct(**payload)
    else:
        invalid = valid.model_copy(update={"prompt_tokens": 9, "total_tokens": 0})
    unknown = _call("moving_head_planner", succeeded=False).model_copy(
        update={
            "prompt_tokens": 0,
            "reasoning_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0,
            "failure": "provider_exception_usage_unavailable",
        }
    )
    journal = tmp_path / f"{construction}.json"
    gate = PreCallSpendGate(
        policy=SpendPolicy(),
        planning_cap_usd=1,
        judging_cap_usd=1,
        whole_remaining_usd=2,
        journal_path=journal,
    )

    async def malformed() -> ArmCallRecord:
        return invalid

    with pytest.raises(ExperimentBlockedError, match="invalid call evidence"):
        await gate.run_provider_call(
            role="moving_head_planner",
            kind="planning",
            maximum_cost_usd=0.01,
            operation=malformed,
            unknown_failure_record=unknown,
        )
    assert gate.records == (unknown,)
    assert [ArmCallRecord.model_validate(item) for item in json.loads(journal.read_text())] == [
        unknown
    ]
    next_authorization = gate.authorize(
        role="moving_head_planner", kind="planning", maximum_cost_usd=0.01
    )
    gate.settle(next_authorization, valid)


def test_local_owner_run_cli_requires_explicit_opt_in() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "run",
                "--manifest",
                "manifest.json",
                "--backend-factory",
                "owner_backend:build",
                "--results",
                "results.json",
            ]
        )


def _result(
    song: int,
    arm: Arm,
    replicate: int,
    total: float,
    manifest: ComparisonManifest,
    sync: float = 1.0,
) -> ArmRunResult:
    each = total / 4
    song_entry = next(item for item in manifest.songs if item.song_id == f"s{song}")
    held = HeldConstantIdentity(
        audio_sha256=song_entry.audio_sha256,
        analysis_cache_key=f"k{song}",
        analysis_payload_sha256="a" * 64,
        beat_grid_sha256="b" * 64,
        stems_sha256="c" * 64,
        fixture_config_sha256=manifest.fixture_config_sha256,
        template_set_sha256="d" * 64,
        renderer_sha256="e" * 64,
        evaluation_config_sha256="f" * 64,
    )
    roles = {
        Arm.A: ("vision_judge",),
        Arm.B: ("macro_planner", "moving_head_planner", "vision_judge"),
        Arm.C: ("moving_head_planner", "vision_judge"),
    }[arm]
    calls = [_call(role) for role in roles]
    calibration_sha = manifest.calibration_record_sha256
    calibration_path = manifest.calibration_record
    assert calibration_sha is not None and calibration_path is not None
    plan = ChoreographyPlan.model_validate(
        {
            "sections": [
                {
                    "section_name": "verse_1",
                    "start_bar": 1,
                    "end_bar": 4,
                    "section_role": "verse",
                    "energy_level": 50,
                    "template_id": "fan_pulse",
                    "intensity": "SMOOTH",
                    "color_intent": {
                        "selection": {
                            "kind": "PALETTE_ROLE",
                            "palette_role": "PRIMARY",
                            "explicit_color": None,
                        }
                    },
                    "shutter_events": [],
                    "gobo_events": [],
                    "moment_cues": [],
                }
            ],
            "overall_strategy": "fixture",
        }
    )
    nonce = None if arm is Arm.A else _sha(f"s{song}-{arm}-{replicate}".encode())
    planning_input = (
        None
        if arm is Arm.A
        else _planning_input_identity(manifest=manifest, song=song_entry, arm=arm, held=held)
    )
    return ArmRunResult(
        run_id=f"s{song}-{arm}-{replicate}",
        song_id=f"s{song}",
        arm=arm,
        replicate=replicate,
        analysis_cache_key=f"k{song}",
        analysis_payload_sha256="a" * 64,
        held_constant=held,
        regeneration_nonce=nonce,
        planning_input_sha256=planning_input,
        planning_cache_key=(
            None
            if planning_input is None or nonce is None
            else _planning_cache_key(planning_input, nonce)
        ),
        plan=plan,
        plan_sha256=_identity_sha(plan.model_dump(mode="json")),
        call_records=calls,
        planning_spend_usd=sum(call.cost_usd for call in calls if call.role != "vision_judge"),
        judging_spend_usd=sum(call.cost_usd for call in calls if call.role == "vision_judge"),
        score=SequenceScore(
            rubric=RubricScores(
                musicality_by_proxy=each,
                coordination=each,
                color_palette_coherence=each,
                variety_and_pacing=each,
            ),
            sync=SyncScores(beat=sync, downbeat=sync, section_boundary=sync),
        ),
        vision_evaluation=_vision(
            calibration_path,
            calibration_sha,
            held.evaluation_config_sha256,
            plan=plan,
            preview_path=song_entry.audio_path,
            preview_sha256=song_entry.audio_sha256,
            rubric_score=each,
            sync_rate=sync,
        ),
        review_artifact_path=song_entry.audio_path,
        review_artifact_sha256=song_entry.audio_sha256,
    )


def test_blinding_is_seeded_hides_arms_and_requires_full_song_plus_five(tmp_path: Path) -> None:
    manifest = _calibrated_manifest(tmp_path)
    results = [
        _result(song, arm, replicate, 28, manifest)
        for song in range(8)
        for arm, replicates in ((Arm.A, (1,)), (Arm.B, (1, 2)), (Arm.C, (1, 2)))
        for replicate in replicates
    ]
    first = build_blind_review(results, seed=99)
    second = build_blind_review(results, seed=99)
    assert first == second
    assert len(first.packet.review_sequence_ids) >= 10
    assert all("arm" not in item.model_dump() for item in first.packet.items)
    full_song_counts = {
        track_id: sum(item.blind_track_id == track_id for item in first.packet.items)
        for track_id in {item.blind_track_id for item in first.packet.items}
    }
    assert 5 in full_song_counts.values()


def test_blind_ranking_is_persisted_before_reveal(tmp_path: Path) -> None:
    manifest = _calibrated_manifest(tmp_path)
    preview = tmp_path / "source-with-arm-name.mp4"
    preview.write_bytes(b"opaque preview")
    preview_sha = _sha(preview.read_bytes())
    results = [
        _result(song, arm, replicate, 28, manifest).model_copy(
            update={
                "review_artifact_path": preview,
                "review_artifact_sha256": preview_sha,
            }
        )
        for song in range(8)
        for arm, replicates in ((Arm.A, (1,)), (Arm.B, (1, 2)), (Arm.C, (1, 2)))
        for replicate in replicates
    ]
    staged = stage_blind_review_packet(
        bundle=build_blind_review(results, seed=99),
        results=results,
        output_dir=tmp_path / "owner-review",
    )
    packet_text = (tmp_path / "owner-review" / "blind-review.json").read_text(encoding="utf-8")
    assert "source-with-arm-name" not in packet_text
    assert '"arm"' not in packet_text
    assert not (tmp_path / "owner-review" / "reveal.json").exists()

    ranking = HumanRanking(
        review_id=staged.packet.review_id,
        packet_sha256=staged.packet.packet_sha256,
        ordered_blind_ids=staged.packet.review_sequence_ids,
    )
    ranking_path = tmp_path / "owner-review" / "ranking.json"
    write_human_ranking(packet=staged.packet, ranking=ranking, output_path=ranking_path)
    write_reveal_key_after_ranking(
        reveal=staged.reveal,
        ranking_path=ranking_path,
        output_path=tmp_path / "owner-review" / "reveal.json",
    )
    assert (
        ranking_path.stat().st_mtime_ns
        <= (tmp_path / "owner-review" / "reveal.json").stat().st_mtime_ns
    )


def test_fixed_parity_computation_reaches_precommitted_human_power(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _calibrated_manifest(tmp_path)
    monkeypatch.setattr(
        "twinklr.core.reporting.evaluation.three_arm.validate_calibration", lambda _: object()
    )
    results: list[ArmRunResult] = []
    for song in range(8):
        results.append(_result(song, Arm.A, 1, 30.0, manifest, 1.0))
        results.append(_result(song, Arm.B, 1, 29.6, manifest, 0.99))
        results.append(_result(song, Arm.B, 2, 30.4, manifest, 0.99))
        results.append(_result(song, Arm.C, 1, 29.5, manifest, 0.99))
        results.append(_result(song, Arm.C, 2, 30.5, manifest, 0.99))

    blind = stage_blind_review_packet(
        bundle=build_blind_review(results, seed=5),
        results=results,
        output_dir=tmp_path / "blind",
    )
    pending = compute_comparison_report(
        manifest=manifest, results=results, blind_review=blind, human_ranking=None
    )
    assert pending.d1_outcome == "PENDING-OWNER"
    assert pending.arm_a_vs_b.parity is None

    # Ranking order deliberately alternates identities rather than preferring an arm.
    ranking = HumanRanking(
        review_id=blind.packet.review_id,
        packet_sha256=blind.packet.packet_sha256,
        ordered_blind_ids=blind.packet.review_sequence_ids,
    )
    final = compute_comparison_report(
        manifest=manifest, results=results, blind_review=blind, human_ranking=ranking
    )
    assert final.criteria_text == final.FIXED_PARITY_CRITERIA
    assert final.arm_a_vs_b.score_band_passed
    assert final.arm_a_vs_b.within_b_variation_passed
    assert final.arm_a_vs_b.sync_passed
    assert final.arm_a_vs_b.parity is True
    assert final.arm_a_vs_b.human_power_sufficient
    assert final.arm_a_vs_b.human_independent_comparison_count >= 5
    assert final.d1_outcome == "DETERMINISTIC_DEFAULT"
    assert final.human_ranking == ranking
    assert final.arm_a_vs_b.human_harness_order_agreement_rate is not None
    output = tmp_path / "evaluation" / "comparison.json"
    write_comparison_report_json(pending, output)
    assert output.is_file()
    assert '"d1_outcome": "PENDING-OWNER"' in output.read_text(encoding="utf-8")
    assert ComparisonReport.model_validate_json(output.read_text(encoding="utf-8")) == pending


def test_parity_uses_inclusive_half_point_band_and_strict_within_b_delta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _calibrated_manifest(tmp_path)
    monkeypatch.setattr(
        "twinklr.core.reporting.evaluation.three_arm.validate_calibration", lambda _: object()
    )
    results: list[ArmRunResult] = []
    for song in range(8):
        results.append(_result(song, Arm.A, 1, 30.5, manifest))
        results.append(_result(song, Arm.B, 1, 29.5, manifest))
        results.append(_result(song, Arm.B, 2, 30.5, manifest))
        results.append(_result(song, Arm.C, 1, 30.0, manifest))
        results.append(_result(song, Arm.C, 2, 30.0, manifest))
    blind = stage_blind_review_packet(
        bundle=build_blind_review(results, seed=7), results=results, output_dir=tmp_path / "blind"
    )
    report = compute_comparison_report(
        manifest=manifest, results=results, blind_review=blind, human_ranking=None
    )
    assert report.arm_a_vs_b.mean_total_difference == pytest.approx(0.5)
    assert report.arm_a_vs_b.right_mean_within_song_abs_delta == pytest.approx(1.0)
    assert report.arm_a_vs_b.score_band_passed
    assert report.arm_a_vs_b.within_b_variation_passed

    equal_delta = [
        _result(
            int(run.song_id[1:]),
            Arm.B,
            run.replicate,
            29.75 if run.replicate == 1 else 30.25,
            manifest,
        )
        if run.arm is Arm.B
        else run
        for run in results
    ]
    equal_blind = stage_blind_review_packet(
        bundle=build_blind_review(equal_delta, seed=7),
        results=equal_delta,
        output_dir=tmp_path / "equal-blind",
    )
    equal_report = compute_comparison_report(
        manifest=manifest,
        results=equal_delta,
        blind_review=equal_blind,
        human_ranking=None,
    )
    assert equal_report.arm_a_vs_b.right_mean_within_song_abs_delta == pytest.approx(0.5)
    assert not equal_report.arm_a_vs_b.within_b_variation_passed


def test_mean_arm_delta_does_not_turn_opposing_song_deltas_into_a_difference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _calibrated_manifest(tmp_path)
    monkeypatch.setattr(
        "twinklr.core.reporting.evaluation.three_arm.validate_calibration", lambda _: object()
    )
    results: list[ArmRunResult] = []
    for song in range(8):
        a_total = 31.0 if song < 4 else 29.0
        results.append(_result(song, Arm.A, 1, a_total, manifest))
        results.append(_result(song, Arm.B, 1, 29.6, manifest))
        results.append(_result(song, Arm.B, 2, 30.4, manifest))
        results.append(_result(song, Arm.C, 1, 30.0, manifest))
        results.append(_result(song, Arm.C, 2, 30.0, manifest))
    blind = stage_blind_review_packet(
        bundle=build_blind_review(results, seed=8), results=results, output_dir=tmp_path / "blind"
    )
    report = compute_comparison_report(
        manifest=manifest,
        results=results,
        blind_review=blind,
        human_ranking=None,
    )
    assert report.arm_a_vs_b.mean_total_difference == pytest.approx(0.0)
    assert report.arm_a_vs_b.right_mean_within_song_abs_delta == pytest.approx(0.8)


@pytest.mark.parametrize(
    ("a_total", "b_total", "expected"),
    [(40.0, 20.5, "DETERMINISTIC_DEFAULT"), (20.0, 40.0, "LLM_DEFAULT")],
)
def test_d1_preserves_signed_winner_direction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    a_total: float,
    b_total: float,
    expected: str,
) -> None:
    manifest = _calibrated_manifest(tmp_path)
    monkeypatch.setattr(
        "twinklr.core.reporting.evaluation.three_arm.validate_calibration", lambda _: object()
    )
    results = [
        _result(song, arm, replicate, total, manifest)
        for song in range(8)
        for arm, replicates, total in (
            (Arm.A, (1,), a_total),
            (Arm.B, (1, 2), b_total),
            (Arm.C, (1, 2), 30.0),
        )
        for replicate in replicates
    ]
    blind = stage_blind_review_packet(
        bundle=build_blind_review(results, seed=12),
        results=results,
        output_dir=tmp_path / "blind",
    )
    ranking = HumanRanking(
        review_id=blind.packet.review_id,
        packet_sha256=blind.packet.packet_sha256,
        ordered_blind_ids=blind.packet.review_sequence_ids,
    )
    report = compute_comparison_report(
        manifest=manifest, results=results, blind_review=blind, human_ranking=ranking
    )
    assert report.d1_outcome == expected


def test_blind_preview_mutation_blocks_ranking(tmp_path: Path) -> None:
    manifest = _calibrated_manifest(tmp_path)
    results = [
        _result(song, arm, replicate, 28, manifest)
        for song in range(8)
        for arm, replicates in ((Arm.A, (1,)), (Arm.B, (1, 2)), (Arm.C, (1, 2)))
        for replicate in replicates
    ]
    blind = stage_blind_review_packet(
        bundle=build_blind_review(results, seed=21),
        results=results,
        output_dir=tmp_path / "blind",
    )
    blind.packet.items[0].review_artifact.write_bytes(b"mutated after commitment")
    ranking = HumanRanking(
        review_id=blind.packet.review_id,
        packet_sha256=blind.packet.packet_sha256,
        ordered_blind_ids=blind.packet.review_sequence_ids,
    )
    with pytest.raises(ExperimentBlockedError, match="SHA-256 changed"):
        write_human_ranking(
            packet=blind.packet, ranking=ranking, output_path=tmp_path / "rank.json"
        )


def test_blind_models_reject_leaky_ids_filenames_and_mixed_parents(tmp_path: Path) -> None:
    digest = "a" * 64
    with pytest.raises(ValueError, match="blind_id"):
        BlindReviewItem(
            blind_id="Arm-A-source-name",
            blind_track_id="Track-01",
            review_artifact=tmp_path / "Arm-A-source-name.mp4",
            preview_sha256=digest,
        )
    with pytest.raises(ValueError, match="opaque basename"):
        BlindReviewItem(
            blind_id="Sequence-01-abcdef12",
            blind_track_id="Track-01",
            review_artifact=tmp_path / "Arm-A-source-name.mp4",
            preview_sha256=digest,
        )
    items = [
        BlindReviewItem(
            blind_id=f"Sequence-{index:02d}-{index:08x}",
            blind_track_id="Track-01",
            review_artifact=(tmp_path if index < 10 else tmp_path / "other")
            / f"Sequence-{index:02d}-{index:08x}.mp4",
            preview_sha256=digest,
        )
        for index in range(1, 11)
    ]
    with pytest.raises(ValueError, match="staging parent"):
        BlindReviewPacket(review_id="opaque-review", seed=1, items=items)


def test_ranking_rejects_recommitted_leaky_blind_path(tmp_path: Path) -> None:
    manifest = _calibrated_manifest(tmp_path)
    results = _all_results(manifest)
    staged = stage_blind_review_packet(
        bundle=build_blind_review(results, seed=71),
        results=results,
        output_dir=tmp_path / "blind",
    )
    items = list(staged.packet.items)
    first = items[0]
    items[0] = first.model_copy(
        update={"review_artifact": first.review_artifact.parent / "Arm-A-source-name.mp4"}
    )
    tampered = staged.packet.model_copy(update={"items": items})
    ranking = HumanRanking(
        review_id=tampered.review_id,
        packet_sha256=tampered.packet_sha256,
        ordered_blind_ids=tampered.review_sequence_ids,
    )
    with pytest.raises(ValueError, match="opaque basename"):
        write_human_ranking(
            packet=tampered,
            ranking=ranking,
            output_path=tmp_path / "blind" / "ranking.json",
        )


def test_iteration_usage_adapter_prices_exact_tokens_and_binds_configuration() -> None:
    source = IterationCallRecord(
        role="moving_head_planner",
        iteration=1,
        success=True,
        logical_requests=1,
        prompt_tokens=1_000,
        reasoning_tokens=2_000,
        completion_tokens=3_000,
        total_tokens=6_000,
        call_usages=[
            IterationCallUsage(
                prompt_tokens=1_000,
                reasoning_tokens=2_000,
                completion_tokens=3_000,
                total_tokens=6_000,
            )
        ],
    )
    records = arm_call_records_from_iteration(
        [source],
        model="gpt-5.6-sol",
        reasoning_effort="medium",
        temperature=0.7,
        pricing=PricingIdentity(
            pricing_id="frozen-price-table",
            prompt_per_million_usd=1,
            reasoning_per_million_usd=2,
            completion_per_million_usd=3,
        ),
    )
    assert records[0].cost_usd == pytest.approx(0.014)
    assert records[0].total_tokens == 6_000
    assert records[0].pricing_id == "frozen-price-table"


@pytest.mark.asyncio
async def test_cli_validates_calibration_before_backend_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _manifest(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        manifest.model_dump_json(exclude_computed_fields=True), encoding="utf-8"
    )
    imported = False

    def forbidden_factory(_: str) -> object:
        nonlocal imported
        imported = True
        raise AssertionError("backend import must not happen")

    monkeypatch.setattr(
        "twinklr.core.reporting.evaluation.three_arm_cli._backend_factory", forbidden_factory
    )
    args = argparse.Namespace(
        owner_opt_in=True,
        manifest=manifest_path,
        backend_factory="owner_backend:build",
        results=tmp_path / "results.json",
    )
    with pytest.raises(ExperimentBlockedError, match="accepted P2P-T6 calibration"):
        await _run_owner(args)
    assert not imported


def test_report_rejects_tampered_derived_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _calibrated_manifest(tmp_path)
    monkeypatch.setattr(
        "twinklr.core.reporting.evaluation.three_arm.validate_calibration", lambda _: object()
    )
    results = [
        _result(song, arm, replicate, 30, manifest)
        for song in range(8)
        for arm, replicates in ((Arm.A, (1,)), (Arm.B, (1, 2)), (Arm.C, (1, 2)))
        for replicate in replicates
    ]
    blind = stage_blind_review_packet(
        bundle=build_blind_review(results, seed=31),
        results=results,
        output_dir=tmp_path / "blind",
    )
    report = compute_comparison_report(
        manifest=manifest, results=results, blind_review=blind, human_ranking=None
    )
    raw = report.model_dump(mode="json", exclude_computed_fields=True)
    raw["arm_summaries"][0]["mean_rubric_total"] = 1.0
    with pytest.raises(ValueError, match="arm summaries"):
        ComparisonReport.model_validate(raw)


def test_result_matrix_rejects_duplicate_llm_nonce(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _calibrated_manifest(tmp_path)
    monkeypatch.setattr(
        "twinklr.core.reporting.evaluation.three_arm.validate_calibration", lambda _: object()
    )
    results = [
        _result(song, arm, replicate, 30, manifest)
        for song in range(8)
        for arm, replicates in ((Arm.A, (1,)), (Arm.B, (1, 2)), (Arm.C, (1, 2)))
        for replicate in replicates
    ]
    first_nonce = next(run.regeneration_nonce for run in results if run.arm is Arm.B)
    duplicate = [
        run.model_copy(update={"regeneration_nonce": first_nonce})
        if run.arm is Arm.C and run.song_id == "s0" and run.replicate == 1
        else run
        for run in results
    ]
    with pytest.raises(ValueError, match="nonces must be distinct"):
        compute_comparison_report(
            manifest=manifest,
            results=duplicate,
            blind_review=build_blind_review(duplicate, seed=41),
            human_ranking=None,
        )


def test_report_rejects_constructed_two_song_fake_evidence(tmp_path: Path) -> None:
    full_manifest = _calibrated_manifest(tmp_path)
    undersized = full_manifest.model_copy(update={"songs": full_manifest.songs[:2]})
    full_results = [
        _result(song, arm, replicate, 30, full_manifest)
        for song in range(8)
        for arm, replicates in ((Arm.A, (1,)), (Arm.B, (1, 2)), (Arm.C, (1, 2)))
        for replicate in replicates
    ]
    results = [run for run in full_results if run.song_id in {"s0", "s1"}]
    with pytest.raises(ValueError, match="N >= 8"):
        compute_comparison_report(
            manifest=undersized,
            results=results,
            blind_review=build_blind_review(full_results, seed=51),
            human_ranking=None,
        )


def _all_results(manifest: ComparisonManifest, *, total: float = 30) -> list[ArmRunResult]:
    return [
        _result(song, arm, replicate, total, manifest)
        for song in range(8)
        for arm, replicates in ((Arm.A, (1,)), (Arm.B, (1, 2)), (Arm.C, (1, 2)))
        for replicate in replicates
    ]


def test_blind_expansion_reaches_five_independent_song_pairs_across_seeds(
    tmp_path: Path,
) -> None:
    results = _all_results(_calibrated_manifest(tmp_path))
    for seed in range(100):
        bundle = build_blind_review(results, seed=seed)
        reveal = {entry.blind_id: entry for entry in bundle.reveal.entries}
        by_song: dict[str, set[Arm]] = {}
        track_counts: dict[str, int] = {}
        for item in bundle.packet.items:
            entry = reveal[item.blind_id]
            by_song.setdefault(entry.song_id, set()).add(entry.arm)
            track_counts[item.blind_track_id] = track_counts.get(item.blind_track_id, 0) + 1
        assert sum(Arm.A in arms and Arm.B in arms for arms in by_song.values()) >= 5
        assert 5 in track_counts.values()
        assert len(bundle.packet.items) >= 10


@pytest.mark.parametrize(
    ("tamper", "message"),
    (
        ("score", "sequence score"),
        ("plan", "plan identities"),
        ("preview", "scored vision preview"),
    ),
)
def test_report_rejects_score_plan_or_preview_evidence_divergence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
    message: str,
) -> None:
    manifest = _calibrated_manifest(tmp_path)
    monkeypatch.setattr(
        "twinklr.core.reporting.evaluation.three_arm.validate_calibration", lambda _: object()
    )
    results = _all_results(manifest)
    target = results[0]
    if tamper == "score":
        changed = target.model_copy(
            update={
                "score": SequenceScore(
                    rubric=RubricScores(
                        musicality_by_proxy=1,
                        coordination=1,
                        color_palette_coherence=1,
                        variety_and_pacing=1,
                    ),
                    sync=target.score.sync,
                )
            }
        )
    elif tamper == "plan":
        changed_plan = target.plan.model_copy(update={"overall_strategy": "tampered"})
        changed = target.model_copy(
            update={
                "plan": changed_plan,
                "plan_sha256": _identity_sha(changed_plan.model_dump(mode="json")),
            }
        )
    else:
        other = manifest.songs[1]
        changed = target.model_copy(
            update={
                "review_artifact_path": other.audio_path,
                "review_artifact_sha256": other.audio_sha256,
            }
        )
    tampered = [changed, *results[1:]]
    with pytest.raises(ValueError, match=message):
        compute_comparison_report(
            manifest=manifest,
            results=tampered,
            blind_review=build_blind_review(tampered, seed=61),
            human_ranking=None,
        )


def test_result_matrix_recomputes_price_and_role_specific_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _calibrated_manifest(tmp_path)
    monkeypatch.setattr(
        "twinklr.core.reporting.evaluation.three_arm.validate_calibration", lambda _: object()
    )
    results = _all_results(manifest)
    target = next(run for run in results if run.arm is Arm.B)
    macro, moving, vision = target.call_records
    million_free = macro.model_copy(
        update={"prompt_tokens": 1_000_000, "total_tokens": 1_000_000, "cost_usd": 0.0}
    )
    zero_cost = target.model_copy(
        update={
            "call_records": [million_free, moving, vision],
            "planning_spend_usd": moving.cost_usd,
        }
    )
    tampered = [zero_cost if run.run_id == target.run_id else run for run in results]
    with pytest.raises(ValueError, match="frozen role/provider/pricing"):
        compute_comparison_report(
            manifest=manifest,
            results=tampered,
            blind_review=build_blind_review(tampered, seed=62),
            human_ranking=None,
        )

    wrong_role = moving.model_copy(
        update={
            "model": manifest.macro_planner.model,
            "reasoning_effort": manifest.macro_planner.reasoning_effort,
            "temperature": manifest.macro_planner.temperature,
            "pricing_id": manifest.macro_planner.pricing.pricing_id,
        }
    )
    role_mismatch = target.model_copy(update={"call_records": [macro, wrong_role, vision]})
    tampered = [role_mismatch if run.run_id == target.run_id else run for run in results]
    with pytest.raises(ValueError, match="frozen role/provider/pricing"):
        compute_comparison_report(
            manifest=manifest,
            results=tampered,
            blind_review=build_blind_review(tampered, seed=63),
            human_ranking=None,
        )

    vision_result = target.vision_evaluation.result
    wrong_visual = vision_result.visual.model_copy(update={"model": "moving-model"})
    wrong_vision_result = vision_result.model_copy(update={"visual": wrong_visual})
    wrong_vision_evidence = VisionEvaluationEvidence.from_vision(
        wrong_vision_result,
        calibration_record_sha256=target.vision_evaluation.calibration_record_sha256,
        evaluation_config_sha256=target.vision_evaluation.evaluation_config_sha256,
    )
    vision_mismatch = target.model_copy(update={"vision_evaluation": wrong_vision_evidence})
    tampered = [vision_mismatch if run.run_id == target.run_id else run for run in results]
    with pytest.raises(ValueError, match="vision role config"):
        compute_comparison_report(
            manifest=manifest,
            results=tampered,
            blind_review=build_blind_review(tampered, seed=631),
            human_ranking=None,
        )


def test_multi_request_iteration_adapter_emits_individually_priced_settlements() -> None:
    source = IterationCallRecord(
        role="moving_head_repair",
        iteration=2,
        success=False,
        logical_requests=2,
        prompt_tokens=30,
        reasoning_tokens=3,
        completion_tokens=7,
        total_tokens=40,
        call_usages=[
            IterationCallUsage(
                prompt_tokens=10, reasoning_tokens=1, completion_tokens=4, total_tokens=15
            ),
            IterationCallUsage(
                prompt_tokens=20, reasoning_tokens=2, completion_tokens=3, total_tokens=25
            ),
        ],
    )
    pricing = PricingIdentity(
        pricing_id="repair-price",
        prompt_per_million_usd=2,
        reasoning_per_million_usd=3,
        completion_per_million_usd=5,
    )
    records = arm_call_records_from_iteration(
        [source],
        model="repair-model",
        reasoning_effort="high",
        temperature=0.4,
        pricing=pricing,
    )
    assert len(records) == 2
    assert all(record.logical_requests == record.provider_attempts == 1 for record in records)
    assert [record.succeeded for record in records] == [True, False]
    assert sum(record.cost_usd for record in records) == pytest.approx(104 / 1_000_000)

    with pytest.raises(ValueError, match="logical-request count"):
        arm_call_records_from_iteration(
            [source.model_copy(update={"logical_requests": 1})],
            model="repair-model",
            reasoning_effort="high",
            temperature=0.4,
            pricing=pricing,
        )


@pytest.mark.asyncio
async def test_provider_bound_gate_journals_before_next_authorization(tmp_path: Path) -> None:
    journal = tmp_path / "provider-attempts.json"
    gate = PreCallSpendGate(
        policy=SpendPolicy(),
        planning_cap_usd=1,
        judging_cap_usd=1,
        whole_remaining_usd=2,
        journal_path=journal,
    )

    async def first() -> ArmCallRecord:
        assert not journal.exists()
        return _call("moving_head_planner")

    async def second() -> ArmCallRecord:
        assert len(json.loads(journal.read_text(encoding="utf-8"))) == 1
        return _call("moving_head_planner")

    unknown = _call("moving_head_planner", succeeded=False).model_copy(
        update={
            "prompt_tokens": 0,
            "reasoning_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0,
            "failure": "provider_exception_usage_unavailable",
        }
    )

    await gate.run_provider_call(
        role="moving_head_planner",
        kind="planning",
        maximum_cost_usd=0.01,
        operation=first,
        unknown_failure_record=unknown,
    )
    await gate.run_provider_call(
        role="moving_head_planner",
        kind="planning",
        maximum_cost_usd=0.01,
        operation=second,
        unknown_failure_record=unknown,
    )
    assert len(json.loads(journal.read_text(encoding="utf-8"))) == 2


def test_report_rejects_nonce_cache_key_and_blind_track_recommitment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _calibrated_manifest(tmp_path)
    monkeypatch.setattr(
        "twinklr.core.reporting.evaluation.three_arm.validate_calibration", lambda _: object()
    )
    results = _all_results(manifest)
    target = next(run for run in results if run.arm is Arm.C)
    wrong_cache = target.model_copy(update={"planning_cache_key": "9" * 64})
    tampered_results = [wrong_cache if run.run_id == target.run_id else run for run in results]
    with pytest.raises(ValueError, match="exact nonce/input"):
        compute_comparison_report(
            manifest=manifest,
            results=tampered_results,
            blind_review=build_blind_review(tampered_results, seed=64),
            human_ranking=None,
        )

    blind = stage_blind_review_packet(
        bundle=build_blind_review(results, seed=65),
        results=results,
        output_dir=tmp_path / "blind",
    )
    report = compute_comparison_report(
        manifest=manifest, results=results, blind_review=blind, human_ranking=None
    )
    items = list(report.blind_packet.items)
    items[0] = items[0].model_copy(update={"blind_track_id": "Track-99"})
    packet = report.blind_packet.model_copy(update={"items": items})
    reveal = report.blind_reveal.model_copy(update={"packet_sha256": packet.packet_sha256})
    raw = report.model_dump(mode="json", exclude_computed_fields=True)
    raw["blind_packet"] = packet.model_dump(mode="json", exclude_computed_fields=True)
    raw["blind_packet_sha256"] = packet.packet_sha256
    raw["blind_reveal"] = reveal.model_dump(mode="json", exclude_computed_fields=True)
    with pytest.raises(ValueError, match="track grouping"):
        ComparisonReport.model_validate(raw)
