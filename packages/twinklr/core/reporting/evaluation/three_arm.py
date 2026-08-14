"""Offline-safe P2P-T13 three-arm experiment orchestration.

This module owns immutable manifests, held-constant identity checks, strict spend and
request gates, arm orchestration, blinding, and the fixed parity calculation.  Actual
provider/xLights work is supplied by an owner-local backend; importing or testing this
module cannot perform a live call.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
from typing import ClassVar, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from twinklr.core.agents.sequencer.moving_heads.deterministic_selector import (
    DeterministicSelector,
    SelectorSection,
)
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.reporting.evaluation.calibration import OwnerCalibrationArtifact
from twinklr.core.reporting.evaluation.vision_evaluation import VisionEvaluationResult

SHA256_PATTERN = r"^[0-9a-f]{64}$"
BLIND_ID_PATTERN = r"^Sequence-[0-9]{2}-[0-9a-f]{8}$"
UNKNOWN_PROVIDER_USAGE_FAILURE = "provider_exception_usage_unavailable"
MIN_INDEPENDENT_HUMAN_COMPARISONS = 5
D1_STANDING_DEFAULT = (
    "**D1 — LLM's role in section planning** *(unchanged)*: widen the channel, with the "
    "deterministic selector built as baseline/fallback/regression arm; standing default "
    "if blind evaluation shows parity."
)
FIXED_PARITY_CRITERIA = (
    "Parity is declared when **all** of the following hold on the song set:\n\n"
    "- The difference in **mean total rubric score** (the four categories summed) between "
    "arm A and arm B is **within 0.5 points on the 0–40 scale**, and\n"
    "- the difference is **smaller than the within-arm variance of arm B** across its two "
    "runs per song (i.e. the arms differ by less than the LLM differs from itself), and\n"
    "- the **blind human ranking shows no consistent preference** — the owner does not "
    "correctly identify the LLM arm as better at a rate meaningfully above chance on "
    "the spot-check subset, and\n"
    "- **deterministic sync metrics** are equal or better for arm A (these are objective; "
    "if arm A is worse on sync, it is not parity)."
)


class Arm(StrEnum):
    """The three fixed experiment arms."""

    A = "A"
    B = "B"
    C = "C"


class ExperimentBlockedError(RuntimeError):
    """A pre-call or evidence-integrity gate blocked the experiment."""


class ExperimentRunFailedError(ExperimentBlockedError):
    """A stopped owner run retaining exact spend from calls completed before failure."""

    def __init__(self, message: str, call_records: Sequence[ArmCallRecord]) -> None:
        super().__init__(message)
        self.call_records = tuple(call_records)
        self.actual_spend_usd = sum(record.cost_usd for record in call_records)


class SpendPolicy(BaseModel):
    """Pre-committed P2P-T13 cost and request ceilings."""

    planning_cap_usd: float = Field(default=25.0, gt=0, le=25.0)
    judging_per_sequence_cap_usd: float = Field(default=0.20, gt=0, le=0.20)
    whole_experiment_cap_usd: float = Field(default=40.0, gt=0, le=40.0)
    planning_logical_requests_per_run: int = Field(default=12, ge=1, le=12)
    provider_attempts_per_logical_request: int = Field(default=3, ge=1, le=3)
    judging_logical_requests_per_sequence: int = Field(default=1, ge=1, le=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class ExperimentPreconditions(BaseModel):
    """Recorded outcome of the six source-level experiment preconditions."""

    render_bottlenecks_fixed: Literal[True] = True
    llm_arm_channel_fixes_merged: Literal[True] = True
    per_call_usage_threaded: Literal[True] = True
    judge_threshold_behavioral: Literal[True] = True
    zero_iterations_supported: Literal[True] = True
    threshold_cache_identity_honest: Literal[True] = True
    evidence_baseline: Literal["8aeda12"] = "8aeda12"

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def all_six_pass(self) -> ExperimentPreconditions:
        results = (
            self.render_bottlenecks_fixed,
            self.llm_arm_channel_fixes_merged,
            self.per_call_usage_threaded,
            self.judge_threshold_behavioral,
            self.zero_iterations_supported,
            self.threshold_cache_identity_honest,
        )
        if not all(results):
            raise ValueError("all six P2P-T13 code preconditions must be verified")
        return self


class PricingIdentity(BaseModel):
    """Frozen token rates and formula used to price exact provider usage."""

    pricing_id: str = Field(min_length=1)
    prompt_per_million_usd: float = Field(gt=0)
    reasoning_per_million_usd: float = Field(gt=0)
    completion_per_million_usd: float = Field(gt=0)
    formula: Literal["token-components-v1"] = "token-components-v1"

    model_config = ConfigDict(extra="forbid", frozen=True)


class RoleExecutionConfig(BaseModel):
    """Frozen provider and pricing identity for one experiment role."""

    model: str = Field(min_length=1)
    reasoning_effort: str | None
    temperature: float = Field(ge=0, le=2)
    pricing: PricingIdentity

    model_config = ConfigDict(extra="forbid", frozen=True)


class SongManifestEntry(BaseModel):
    """One owner-local, non-redistributed song frozen before execution."""

    song_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    audio_path: Path
    audio_sha256: str = Field(pattern=SHA256_PATTERN)
    genres: list[str] = Field(min_length=1)
    prominent_lyrics: bool = False
    instrumental: bool = False
    non_four_four_or_tempo_varying: bool = False
    owner_familiar: bool = False

    model_config = ConfigDict(extra="forbid", frozen=True)


class ComparisonManifest(BaseModel):
    """The immutable experiment definition, frozen before the first run."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    experiment_id: str = Field(min_length=1)
    frozen_at: datetime
    songs: list[SongManifestEntry] = Field(min_length=8)
    seed: int
    arms: tuple[Arm, Arm, Arm] = (Arm.A, Arm.B, Arm.C)
    macro_planner: RoleExecutionConfig
    moving_head_planner: RoleExecutionConfig
    vision_judge: RoleExecutionConfig
    llm_runs_per_song: Literal[2] = 2
    grid_source: str = Field(min_length=1)
    stems_setting: str = Field(min_length=1)
    fixture_config_path: Path
    fixture_config_sha256: str = Field(pattern=SHA256_PATTERN)
    evaluation_harness_version: str = Field(min_length=1)
    calibration_record: Path | None = None
    calibration_record_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    spend: SpendPolicy = Field(default_factory=SpendPolicy)
    preconditions: ExperimentPreconditions = Field(default_factory=ExperimentPreconditions)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def fixed_protocol(self) -> ComparisonManifest:
        if self.arms != (Arm.A, Arm.B, Arm.C):
            raise ValueError("the comparison must contain exactly arms A, B, and C")
        song_ids = [song.song_id for song in self.songs]
        if len(song_ids) != len(set(song_ids)):
            raise ValueError("song_id values must be unique")
        genres = {genre.casefold() for song in self.songs for genre in song.genres}
        if len(genres) < 2:
            raise ValueError("the song set must contain at least two genres")
        required = {
            "prominent lyrics": any(song.prominent_lyrics for song in self.songs),
            "instrumental": any(song.instrumental for song in self.songs),
            "non-4/4 or tempo-varying": any(
                song.non_four_four_or_tempo_varying for song in self.songs
            ),
            "owner-familiar": any(song.owner_familiar for song in self.songs),
        }
        missing = [name for name, present in required.items() if not present]
        if missing:
            raise ValueError(f"song-set composition is missing: {', '.join(missing)}")
        if (self.calibration_record is None) != (self.calibration_record_sha256 is None):
            raise ValueError("calibration record path and SHA-256 must be supplied together")
        judging_ceiling = self.sequence_count * self.spend.judging_per_sequence_cap_usd
        if self.spend.planning_cap_usd + judging_ceiling > self.spend.whole_experiment_cap_usd:
            raise ValueError("planning plus judging reservations exceed the $40 hard cap")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sequence_count(self) -> int:
        return len(self.songs) * 5

    def validate_frozen_files(self) -> None:
        """Hash every owner input before any backend/provider work."""
        _assert_file_hash(self.fixture_config_path, self.fixture_config_sha256, "fixture config")
        for song in self.songs:
            _assert_file_hash(song.audio_path, song.audio_sha256, f"song {song.song_id}")


class HeldConstantIdentity(BaseModel):
    """Exact per-song identities that every arm result must echo."""

    audio_sha256: str = Field(pattern=SHA256_PATTERN)
    analysis_cache_key: str = Field(min_length=1)
    analysis_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    beat_grid_sha256: str = Field(pattern=SHA256_PATTERN)
    stems_sha256: str = Field(pattern=SHA256_PATTERN)
    fixture_config_sha256: str = Field(pattern=SHA256_PATTERN)
    template_set_sha256: str = Field(pattern=SHA256_PATTERN)
    renderer_sha256: str = Field(pattern=SHA256_PATTERN)
    evaluation_config_sha256: str = Field(pattern=SHA256_PATTERN)

    model_config = ConfigDict(extra="forbid", frozen=True)


class AnalysisSnapshot(BaseModel):
    """One shared analysis payload reused across all five runs for a song."""

    song_id: str
    cache_key: str = Field(min_length=1)
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    selector_sections: list[SelectorSection] = Field(min_length=1)
    beat_grid_sha256: str = Field(pattern=SHA256_PATTERN)
    stems_sha256: str = Field(pattern=SHA256_PATTERN)
    template_set_sha256: str = Field(pattern=SHA256_PATTERN)
    renderer_sha256: str = Field(pattern=SHA256_PATTERN)
    evaluation_config_sha256: str = Field(pattern=SHA256_PATTERN)

    model_config = ConfigDict(extra="forbid", frozen=True)

    def identity(
        self, manifest: ComparisonManifest, song: SongManifestEntry
    ) -> HeldConstantIdentity:
        return HeldConstantIdentity(
            audio_sha256=song.audio_sha256,
            analysis_cache_key=self.cache_key,
            analysis_payload_sha256=self.payload_sha256,
            beat_grid_sha256=self.beat_grid_sha256,
            stems_sha256=self.stems_sha256,
            fixture_config_sha256=manifest.fixture_config_sha256,
            template_set_sha256=self.template_set_sha256,
            renderer_sha256=self.renderer_sha256,
            evaluation_config_sha256=self.evaluation_config_sha256,
        )


class ArmCallRecord(BaseModel):
    """Exact priced usage for one planning/evaluation role invocation."""

    role: str = Field(min_length=1)
    model: str = Field(min_length=1)
    reasoning_effort: str | None
    temperature: float = Field(ge=0, le=2)
    pricing_id: str = Field(min_length=1)
    logical_requests: int = Field(ge=1)
    provider_attempts: int = Field(ge=1)
    prompt_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0, ge=0)
    succeeded: bool = True
    failure: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def exact_token_total(self) -> ArmCallRecord:
        expected = self.prompt_tokens + self.reasoning_tokens + self.completion_tokens
        if self.total_tokens != expected:
            raise ValueError("total_tokens must equal prompt + reasoning + completion")
        if (self.succeeded and self.failure is not None) or (
            not self.succeeded and self.failure is None
        ):
            raise ValueError("failed calls require a failure label; successful calls forbid one")
        return self


class ProviderOperationError(RuntimeError):
    """Provider failure carrying the exact priced usage available at failure time."""

    def __init__(self, message: str, *, call_record: ArmCallRecord) -> None:
        if call_record.succeeded:
            raise ValueError("provider operation errors require a failed call record")
        super().__init__(message)
        self.call_record = call_record


def arm_call_records_from_iteration(
    records: Sequence[object],
    *,
    model: str,
    reasoning_effort: str | None,
    temperature: float,
    pricing: PricingIdentity,
) -> list[ArmCallRecord]:
    """Convert shipped ``IterationCallRecord`` values into exact priced evidence."""
    from twinklr.core.agents.shared.judge.controller import (
        IterationCallRecord,
        IterationCallUsage,
    )

    converted: list[ArmCallRecord] = []
    for raw in records:
        record = IterationCallRecord.model_validate(raw)
        usages = list(record.call_usages)
        if usages:
            if record.logical_requests != len(usages):
                raise ValueError("iteration logical-request count does not match per-call usage")
            aggregate = (
                sum(item.prompt_tokens for item in usages),
                sum(item.reasoning_tokens for item in usages),
                sum(item.completion_tokens for item in usages),
                sum(item.total_tokens for item in usages),
            )
            if aggregate != (
                record.prompt_tokens,
                record.reasoning_tokens,
                record.completion_tokens,
                record.total_tokens,
            ):
                raise ValueError("iteration per-request usage does not equal its aggregate")
        else:
            if record.logical_requests != 1:
                raise ValueError("aggregate-only iteration evidence must describe exactly one call")
            usages = [
                IterationCallUsage(
                    prompt_tokens=record.prompt_tokens,
                    reasoning_tokens=record.reasoning_tokens,
                    completion_tokens=record.completion_tokens,
                    total_tokens=record.total_tokens,
                )
            ]
        for index, usage in enumerate(usages):
            succeeded = record.success if index == len(usages) - 1 else True
            converted.append(
                ArmCallRecord(
                    role=record.role,
                    model=model,
                    reasoning_effort=reasoning_effort,
                    temperature=temperature,
                    pricing_id=pricing.pricing_id,
                    logical_requests=1,
                    provider_attempts=1,
                    prompt_tokens=usage.prompt_tokens,
                    reasoning_tokens=usage.reasoning_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    cost_usd=_price_tokens(
                        prompt_tokens=usage.prompt_tokens,
                        reasoning_tokens=usage.reasoning_tokens,
                        completion_tokens=usage.completion_tokens,
                        pricing=pricing,
                    ),
                    succeeded=succeeded,
                    failure=None if succeeded else "iteration_call_failed",
                )
            )
    return converted


class VisionEvaluationEvidence(BaseModel):
    """Full serialized P2P-T6 output plus the identities required to trust it."""

    result: VisionEvaluationResult
    result_sha256: str = Field(pattern=SHA256_PATTERN)
    calibration_record_sha256: str = Field(pattern=SHA256_PATTERN)
    evaluation_config_sha256: str = Field(pattern=SHA256_PATTERN)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def exact_result_hash(self) -> VisionEvaluationEvidence:
        payload = self.result.model_dump(mode="json", exclude_computed_fields=True)
        if _identity_hash(payload) != self.result_sha256:
            raise ValueError("vision evaluation payload SHA-256 mismatch")
        result = self.result
        if result.calibration_status != "calibrated":
            raise ValueError("comparison requires a calibrated VisionEvaluationResult")
        if result.calibration_record_sha256 != self.calibration_record_sha256:
            raise ValueError("vision result calibration identity does not match its evidence")
        if result.evaluation_config_sha256 != self.evaluation_config_sha256:
            raise ValueError("vision result evaluation config does not match its evidence")
        return self

    @classmethod
    def from_vision(
        cls,
        result: VisionEvaluationResult,
        *,
        calibration_record_sha256: str,
        evaluation_config_sha256: str,
    ) -> VisionEvaluationEvidence:
        payload = result.model_dump(mode="json", exclude_computed_fields=True)
        return cls(
            result=result,
            result_sha256=_identity_hash(payload),
            calibration_record_sha256=calibration_record_sha256,
            evaluation_config_sha256=evaluation_config_sha256,
        )


class CallAuthorization(BaseModel):
    """One pre-call reservation consumed by exactly one usage record."""

    authorization_id: str
    role: str
    kind: Literal["planning", "judging"]
    maximum_cost_usd: float = Field(ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)


class PreCallSpendGate:
    """Mutable owner-backend gate covering success, failure, retry, and repair calls.

    The backend must call :meth:`authorize` immediately before every logical provider
    request and :meth:`settle` in ``finally`` with that request's exact usage record.
    Failed requests and schema repairs therefore consume the same caps as successes.
    """

    def __init__(
        self,
        *,
        policy: SpendPolicy,
        planning_cap_usd: float,
        judging_cap_usd: float,
        whole_remaining_usd: float,
        journal_path: Path | None = None,
    ) -> None:
        self._policy = policy
        self._planning_cap = planning_cap_usd
        self._judging_cap = judging_cap_usd
        self._whole_remaining = whole_remaining_usd
        self._outstanding: dict[str, CallAuthorization] = {}
        self._records: list[ArmCallRecord] = []
        self._journal_path = journal_path
        self._journaled_count = 0

    @property
    def records(self) -> tuple[ArmCallRecord, ...]:
        return tuple(self._records)

    def authorize(
        self, *, role: str, kind: Literal["planning", "judging"], maximum_cost_usd: float
    ) -> CallAuthorization:
        if self._outstanding:
            raise ExperimentBlockedError(
                "a provider authorization is already outstanding; parallel calls are forbidden"
            )
        if self._journal_path is not None and self._journaled_count != len(self._records):
            raise ExperimentBlockedError(
                "prior provider usage was not durably journaled before the next authorization"
            )
        expected_kind = _call_kind_for_role(role)
        if kind != expected_kind:
            raise ExperimentBlockedError(f"{role} must use the {expected_kind} spend gate")
        if maximum_cost_usd < 0:
            raise ValueError("maximum call cost cannot be negative")
        planning_logical = sum(
            record.logical_requests for record in self._records if record.role != "vision_judge"
        ) + sum(item.kind == "planning" for item in self._outstanding.values())
        judging_logical = sum(
            record.logical_requests for record in self._records if record.role == "vision_judge"
        ) + sum(item.kind == "judging" for item in self._outstanding.values())
        if kind == "planning" and planning_logical >= (
            self._policy.planning_logical_requests_per_run
        ):
            raise ExperimentBlockedError("planning logical-request ceiling reached before call")
        if kind == "judging" and judging_logical >= (
            self._policy.judging_logical_requests_per_sequence
        ):
            raise ExperimentBlockedError("judging logical-request ceiling reached before call")

        settled_planning = sum(
            record.cost_usd for record in self._records if record.role != "vision_judge"
        )
        settled_judging = sum(
            record.cost_usd for record in self._records if record.role == "vision_judge"
        )
        reserved_planning = sum(
            item.maximum_cost_usd for item in self._outstanding.values() if item.kind == "planning"
        )
        reserved_judging = sum(
            item.maximum_cost_usd for item in self._outstanding.values() if item.kind == "judging"
        )
        next_planning = settled_planning + reserved_planning
        next_judging = settled_judging + reserved_judging
        if kind == "planning":
            next_planning += maximum_cost_usd
        else:
            next_judging += maximum_cost_usd
        if next_planning > self._planning_cap:
            raise ExperimentBlockedError("next planning call could exceed its hard reservation")
        if next_judging > self._judging_cap:
            raise ExperimentBlockedError("next judging call could exceed its hard reservation")
        if next_planning + next_judging > self._whole_remaining:
            raise ExperimentBlockedError("next provider call could exceed the $40 hard cap")

        authorization = CallAuthorization(
            authorization_id=_identity_hash(
                {
                    "role": role,
                    "kind": kind,
                    "ordinal": len(self._records) + len(self._outstanding),
                }
            ),
            role=role,
            kind=kind,
            maximum_cost_usd=maximum_cost_usd,
        )
        self._outstanding[authorization.authorization_id] = authorization
        return authorization

    def settle(self, authorization: CallAuthorization, record: ArmCallRecord) -> None:
        reserved = self._outstanding.get(authorization.authorization_id)
        if reserved != authorization:
            raise ExperimentBlockedError("unknown or already-settled call authorization")
        if record.role != authorization.role:
            raise ExperimentBlockedError("usage record role does not match call authorization")
        if record.logical_requests != 1:
            raise ExperimentBlockedError("each authorization covers one logical request")
        del self._outstanding[authorization.authorization_id]
        self._records.append(record)
        self._persist_records()
        if record.cost_usd > authorization.maximum_cost_usd:
            raise ExperimentBlockedError("actual call spend exceeded its pre-call reservation")
        if record.provider_attempts > self._policy.provider_attempts_per_logical_request:
            raise ExperimentBlockedError("provider-attempt ceiling exceeded")

    def assert_closed(self) -> None:
        if self._outstanding:
            raise ExperimentBlockedError(
                "backend returned with unsettled provider-call reservations"
            )

    def _persist_records(self) -> None:
        """Durably replace the partial-attempt journal before another call may start."""
        if self._journal_path is None:
            return
        self._journal_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._journal_path.with_suffix(self._journal_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                [
                    record.model_dump(mode="json", exclude_computed_fields=True)
                    for record in self._records
                ],
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self._journal_path)
        self._journaled_count = len(self._records)

    async def run_provider_call(
        self,
        *,
        role: str,
        kind: Literal["planning", "judging"],
        maximum_cost_usd: float,
        operation: Callable[[], Awaitable[ArmCallRecord]],
        unknown_failure_record: ArmCallRecord,
    ) -> ArmCallRecord:
        """Run one provider operation; every success or exception closes and journals once."""
        _validate_unknown_failure_record(role, unknown_failure_record)
        authorization = self.authorize(role=role, kind=kind, maximum_cost_usd=maximum_cost_usd)
        try:
            record = await operation()
        except BaseException as error:
            record = (
                error.call_record
                if isinstance(error, ProviderOperationError)
                and error.call_record.role == authorization.role
                else unknown_failure_record
            )
            try:
                self.settle(authorization, record)
            except BaseException as settlement_error:
                if authorization.authorization_id in self._outstanding:
                    self.settle(authorization, unknown_failure_record)
                error.add_note(
                    f"provider failure usage was journaled; gate also failed: {settlement_error}"
                )
            raise
        try:
            if not isinstance(record, ArmCallRecord):
                raise TypeError(
                    f"provider operation returned {type(record).__name__}, expected ArmCallRecord"
                )
            record = ArmCallRecord.model_validate(
                record.model_dump(mode="python", exclude_computed_fields=True)
            )
        except Exception as invalid_error:
            if authorization.authorization_id in self._outstanding:
                self.settle(authorization, unknown_failure_record)
            raise ExperimentBlockedError(
                "provider operation returned invalid call evidence; unknown usage was journaled"
            ) from invalid_error
        try:
            self.settle(authorization, record)
        except BaseException as error:
            if authorization.authorization_id in self._outstanding:
                self.settle(authorization, unknown_failure_record)
            if isinstance(error, ExperimentBlockedError):
                raise
            raise ExperimentBlockedError(
                "provider call settlement failed after closing its authorization"
            ) from error
        return record


class RubricScores(BaseModel):
    """The four P2P-T6 visual scores, never including sync."""

    musicality_by_proxy: float = Field(ge=0, le=10)
    coordination: float = Field(ge=0, le=10)
    color_palette_coherence: float = Field(ge=0, le=10)
    variety_and_pacing: float = Field(ge=0, le=10)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> float:
        return (
            self.musicality_by_proxy
            + self.coordination
            + self.color_palette_coherence
            + self.variety_and_pacing
        )

    @classmethod
    def from_vision(cls, result: VisionEvaluationResult) -> RubricScores:
        rubric = result.visual.rubric
        return cls(
            musicality_by_proxy=rubric.musicality_by_proxy.score,
            coordination=rubric.coordination.score,
            color_palette_coherence=rubric.color_palette_coherence.score,
            variety_and_pacing=rubric.variety_and_pacing.score,
        )


class SyncScores(BaseModel):
    """Comparable objective rates extracted from deterministic sync metrics."""

    beat: float = Field(ge=0, le=1)
    downbeat: float = Field(ge=0, le=1)
    section_boundary: float = Field(ge=0, le=1)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def from_vision(cls, result: VisionEvaluationResult) -> SyncScores:
        metrics = result.deterministic
        beat = metrics.beat_starts.on_grid_rate
        downbeat = metrics.downbeat_starts.on_grid_rate
        section_boundary = metrics.section_boundaries.alignment_rate
        if beat is None or downbeat is None or section_boundary is None:
            raise ValueError("sync parity requires non-empty beat and downbeat metrics")
        return cls(
            beat=float(beat),
            downbeat=float(downbeat),
            section_boundary=float(section_boundary),
        )


class SequenceScore(BaseModel):
    rubric: RubricScores
    sync: SyncScores

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def from_vision(cls, result: VisionEvaluationResult) -> SequenceScore:
        return cls(rubric=RubricScores.from_vision(result), sync=SyncScores.from_vision(result))


class ArmExecutionRequest(BaseModel):
    """One backend request with the graph switch and cache-busting nonce explicit."""

    experiment_id: str
    song: SongManifestEntry
    arm: Arm
    replicate: int = Field(ge=1, le=2)
    analysis: AnalysisSnapshot
    held_constant: HeldConstantIdentity
    calibration_record: Path
    calibration_record_sha256: str = Field(pattern=SHA256_PATTERN)
    plan: ChoreographyPlan | None
    include_macro: bool
    regeneration_nonce: str | None = Field(default=None, pattern=SHA256_PATTERN)
    planning_input_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    planning_cache_key: str | None = Field(default=None, pattern=SHA256_PATTERN)
    planning_reservation_usd: float = Field(ge=0)
    judging_reservation_usd: float = Field(gt=0)
    spend_gate: PreCallSpendGate = Field(exclude=True, repr=False)

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def arm_shape(self) -> ArmExecutionRequest:
        if self.arm is Arm.A and (self.plan is None or self.include_macro):
            raise ValueError("Arm A requires a deterministic plan and no macro stage")
        if self.arm is Arm.B and (self.plan is not None or not self.include_macro):
            raise ValueError("Arm B requires the full LLM graph including macro")
        if self.arm is Arm.C and (self.plan is not None or self.include_macro):
            raise ValueError("Arm C requires the LLM planner with macro removed")
        cache_fields = (
            self.regeneration_nonce,
            self.planning_input_sha256,
            self.planning_cache_key,
        )
        if self.arm is Arm.A and any(value is not None for value in cache_fields):
            raise ValueError("Arm A cannot have LLM planning-cache identity")
        if self.arm in (Arm.B, Arm.C) and any(value is None for value in cache_fields):
            raise ValueError("LLM arms require nonce, planning input, and cache-key identity")
        return self


class ArmRunResult(BaseModel):
    """One scored run with exact provenance and spend."""

    run_id: str
    song_id: str
    arm: Arm
    replicate: int = Field(ge=1, le=2)
    analysis_cache_key: str
    analysis_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    held_constant: HeldConstantIdentity
    regeneration_nonce: str | None = Field(default=None, pattern=SHA256_PATTERN)
    planning_input_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    planning_cache_key: str | None = Field(default=None, pattern=SHA256_PATTERN)
    plan: ChoreographyPlan
    plan_sha256: str = Field(pattern=SHA256_PATTERN)
    call_records: list[ArmCallRecord]
    planning_spend_usd: float = Field(ge=0)
    judging_spend_usd: float = Field(ge=0)
    score: SequenceScore
    vision_evaluation: VisionEvaluationEvidence
    review_artifact_path: Path
    review_artifact_sha256: str = Field(pattern=SHA256_PATTERN)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def review_artifact_pair(self) -> ArmRunResult:
        if self.arm is Arm.A and self.regeneration_nonce is not None:
            raise ValueError("Arm A must not persist an LLM regeneration nonce")
        if self.arm in (Arm.B, Arm.C) and self.regeneration_nonce is None:
            raise ValueError("LLM arms must persist their regeneration nonce")
        cache_fields = (self.planning_input_sha256, self.planning_cache_key)
        if self.arm is Arm.A and any(value is not None for value in cache_fields):
            raise ValueError("Arm A cannot persist an LLM planning-cache identity")
        if self.arm in (Arm.B, Arm.C) and any(value is None for value in cache_fields):
            raise ValueError("LLM arms must persist input-bound planning cache identity")
        expected_plan_sha = _identity_hash(self.plan.model_dump(mode="json"))
        if self.plan_sha256 != expected_plan_sha:
            raise ValueError("run plan SHA-256 does not match its ChoreographyPlan")
        if any(section.legacy_intent_omitted for section in self.plan.sections):
            raise ValueError(
                "experiment plans must explicitly populate every schema-v2 intent field"
            )
        vision = self.vision_evaluation.result
        if vision.plan_sha256 != self.plan_sha256:
            raise ValueError("vision plan identity does not match the scored run plan")
        if (
            vision.preview_path != self.review_artifact_path
            or vision.preview_sha256 != self.review_artifact_sha256
        ):
            raise ValueError("blind review artifact does not match the scored vision preview")
        if self.score != SequenceScore.from_vision(vision):
            raise ValueError("SequenceScore does not match embedded VisionEvaluationResult")
        return self


class ExperimentBackend(Protocol):
    """Owner-local bridge to analysis, planning/rendering, and P2P-T6 evaluation."""

    async def analyze(self, song: SongManifestEntry) -> AnalysisSnapshot: ...

    async def execute(self, request: ArmExecutionRequest) -> ArmRunResult: ...


class ComparisonExperimentRunner:
    """Drive exactly 5N runs while enforcing every gate around a local backend."""

    def __init__(
        self,
        *,
        manifest: ComparisonManifest,
        backend: ExperimentBackend,
        attempt_journal_dir: Path | None = None,
    ) -> None:
        self.manifest = manifest
        self.backend = backend
        self.attempt_journal_dir = attempt_journal_dir

    async def run(self, *, owner_opt_in: bool = False) -> list[ArmRunResult]:
        if not owner_opt_in:
            raise ExperimentBlockedError(
                "LOCAL-ONLY comparison requires explicit owner opt-in before any work"
            )
        self.manifest.validate_frozen_files()
        self._assert_calibrated()
        calibration_hash = self.manifest.calibration_record_sha256
        calibration_path = self.manifest.calibration_record
        if calibration_hash is None or calibration_path is None:
            raise AssertionError("accepted calibration must have a frozen SHA-256")

        results: list[ArmRunResult] = []
        planning_spend = 0.0
        judging_spend = 0.0
        planning_runs = len(self.manifest.songs) * 4
        planning_reservation = self.manifest.spend.planning_cap_usd / planning_runs

        for song in self.manifest.songs:
            analysis = await self.backend.analyze(song)
            if analysis.song_id != song.song_id:
                raise ExperimentBlockedError("analysis snapshot song identity mismatch")
            expected_identity = analysis.identity(self.manifest, song)
            if any(
                value == "0" * 64
                for value in (
                    expected_identity.analysis_payload_sha256,
                    expected_identity.beat_grid_sha256,
                    expected_identity.stems_sha256,
                    expected_identity.template_set_sha256,
                    expected_identity.renderer_sha256,
                    expected_identity.evaluation_config_sha256,
                )
            ):
                raise ExperimentBlockedError(
                    "analysis returned placeholder held-constant identities before paid work"
                )
            seen_nonces: set[str] = set()

            for arm, replicates in ((Arm.A, (1,)), (Arm.B, (1, 2)), (Arm.C, (1, 2))):
                for replicate in replicates:
                    reservation = 0.0 if arm is Arm.A else planning_reservation
                    projected = (
                        planning_spend
                        + judging_spend
                        + reservation
                        + self.manifest.spend.judging_per_sequence_cap_usd
                    )
                    if projected > self.manifest.spend.whole_experiment_cap_usd:
                        raise ExperimentBlockedError(
                            "next run reservation exceeds the $40 hard cap"
                        )
                    nonce = (
                        None
                        if arm is Arm.A
                        else _identity_hash(
                            {
                                "experiment": self.manifest.experiment_id,
                                "song": song.song_id,
                                "arm": arm.value,
                                "replicate": replicate,
                            }
                        )
                    )
                    if nonce is not None:
                        if nonce in seen_nonces:
                            raise AssertionError("regeneration nonces must be unique per song/run")
                        seen_nonces.add(nonce)
                    plan = (
                        DeterministicSelector(seed=self.manifest.seed)
                        .select(analysis.selector_sections)
                        .plan
                        if arm is Arm.A
                        else None
                    )
                    planning_input = (
                        None
                        if arm is Arm.A
                        else _planning_input_identity(
                            manifest=self.manifest,
                            song=song,
                            arm=arm,
                            held=expected_identity,
                        )
                    )
                    planning_cache_key = (
                        None
                        if planning_input is None or nonce is None
                        else _planning_cache_key(planning_input, nonce)
                    )
                    request = ArmExecutionRequest(
                        experiment_id=self.manifest.experiment_id,
                        song=song,
                        arm=arm,
                        replicate=replicate,
                        analysis=analysis,
                        held_constant=expected_identity,
                        calibration_record=calibration_path,
                        calibration_record_sha256=calibration_hash,
                        plan=plan,
                        include_macro=arm is Arm.B,
                        regeneration_nonce=nonce,
                        planning_input_sha256=planning_input,
                        planning_cache_key=planning_cache_key,
                        planning_reservation_usd=reservation,
                        judging_reservation_usd=(self.manifest.spend.judging_per_sequence_cap_usd),
                        spend_gate=PreCallSpendGate(
                            policy=self.manifest.spend,
                            planning_cap_usd=reservation,
                            judging_cap_usd=self.manifest.spend.judging_per_sequence_cap_usd,
                            whole_remaining_usd=(
                                self.manifest.spend.whole_experiment_cap_usd
                                - planning_spend
                                - judging_spend
                            ),
                            journal_path=(
                                None
                                if self.attempt_journal_dir is None
                                else self.attempt_journal_dir
                                / f"{song.song_id}-{arm.value}-{replicate}.json"
                            ),
                        ),
                    )
                    try:
                        result = await self.backend.execute(request)
                    except Exception as error:
                        request.spend_gate.assert_closed()
                        raise ExperimentRunFailedError(
                            "owner backend failed; paid/failed/repair usage is retained "
                            f"for {song.song_id}/{arm.value}/{replicate}",
                            request.spend_gate.records,
                        ) from error
                    request.spend_gate.assert_closed()
                    if tuple(result.call_records) != request.spend_gate.records:
                        raise ExperimentBlockedError(
                            "backend result does not match pre-call-gated usage records"
                        )
                    self._validate_result(result, request, expected_identity)
                    planning_spend += result.planning_spend_usd
                    judging_spend += result.judging_spend_usd
                    if planning_spend > self.manifest.spend.planning_cap_usd:
                        raise ExperimentBlockedError("actual planning spend exceeded $25")
                    if result.judging_spend_usd > self.manifest.spend.judging_per_sequence_cap_usd:
                        raise ExperimentBlockedError("sequence judging spend exceeded $0.20")
                    if (
                        planning_spend + judging_spend
                        > self.manifest.spend.whole_experiment_cap_usd
                    ):
                        raise ExperimentBlockedError("actual experiment spend exceeded $40")
                    results.append(result)

        if len(results) != self.manifest.sequence_count:
            raise AssertionError("runner did not produce the required 5N sequences")
        return results

    def _assert_calibrated(self) -> None:
        validate_calibration(self.manifest)

    def _validate_result(
        self,
        result: ArmRunResult,
        request: ArmExecutionRequest,
        expected_identity: HeldConstantIdentity,
    ) -> None:
        if (result.song_id, result.arm, result.replicate) != (
            request.song.song_id,
            request.arm,
            request.replicate,
        ):
            raise ExperimentBlockedError("backend returned the wrong song/arm/replicate")
        if result.analysis_cache_key != expected_identity.analysis_cache_key or (
            result.analysis_payload_sha256 != expected_identity.analysis_payload_sha256
        ):
            raise ExperimentBlockedError("analysis cache identity changed across arms")
        if result.held_constant != expected_identity:
            raise ExperimentBlockedError("held-constant hashes changed across arms")
        if result.regeneration_nonce != (
            None if request.arm is Arm.A else request.regeneration_nonce
        ):
            raise ExperimentBlockedError("result regeneration nonce does not match its run")
        if (
            result.planning_input_sha256 != request.planning_input_sha256
            or result.planning_cache_key != request.planning_cache_key
        ):
            raise ExperimentBlockedError(
                "result planning cache key does not match its exact requested nonce/input"
            )
        if result.vision_evaluation.calibration_record_sha256 != (
            self.manifest.calibration_record_sha256
        ):
            raise ExperimentBlockedError("vision result is not pinned to manifest calibration")
        if result.vision_evaluation.evaluation_config_sha256 != (
            expected_identity.evaluation_config_sha256
        ):
            raise ExperimentBlockedError("vision result evaluation config changed across arms")

        roles = {record.role for record in result.call_records}
        if result.arm is Arm.B and "macro_planner" not in roles:
            raise ExperimentBlockedError("Arm B call record is missing the macro planner")
        if result.arm is Arm.C and any("macro" in role.casefold() for role in roles):
            raise ExperimentBlockedError("Arm C call record contains macro planner activity")

        planning_records = [
            record for record in result.call_records if record.role != "vision_judge"
        ]
        for record in result.call_records:
            if not _call_matches_role_config(record, _role_config(self.manifest, record.role)):
                raise ExperimentBlockedError(
                    "call-record provider/pricing identity differs from its frozen role config"
                )
        judging_records = [
            record for record in result.call_records if record.role == "vision_judge"
        ]
        logical = sum(record.logical_requests for record in planning_records)
        attempts = sum(record.provider_attempts for record in planning_records)
        if logical > self.manifest.spend.planning_logical_requests_per_run:
            raise ExperimentBlockedError("planning logical-request ceiling exceeded")
        if attempts > logical * self.manifest.spend.provider_attempts_per_logical_request:
            raise ExperimentBlockedError("planning provider-attempt ceiling exceeded")
        recorded_planning_spend = sum(record.cost_usd for record in planning_records)
        if not math.isclose(recorded_planning_spend, result.planning_spend_usd, abs_tol=1e-9):
            raise ExperimentBlockedError("planning spend does not equal per-call usage records")
        if result.planning_spend_usd > request.planning_reservation_usd:
            raise ExperimentBlockedError("run planning spend exceeded its pre-call reservation")

        judging_logical = sum(record.logical_requests for record in judging_records)
        judging_attempts = sum(record.provider_attempts for record in judging_records)
        if judging_logical != self.manifest.spend.judging_logical_requests_per_sequence:
            raise ExperimentBlockedError("every sequence requires exactly one judging request")
        if judging_attempts > (
            judging_logical * self.manifest.spend.provider_attempts_per_logical_request
        ):
            raise ExperimentBlockedError("judging provider-attempt ceiling exceeded")
        recorded_judging_spend = sum(record.cost_usd for record in judging_records)
        if not math.isclose(recorded_judging_spend, result.judging_spend_usd, abs_tol=1e-9):
            raise ExperimentBlockedError("judging spend does not equal per-call usage records")
        if result.judging_spend_usd > request.judging_reservation_usd:
            raise ExperimentBlockedError("run judging spend exceeded its pre-call reservation")

        if result.arm is Arm.A and planning_records:
            raise ExperimentBlockedError("Arm A made an LLM call on the planning path")


class BlindReviewItem(BaseModel):
    """Owner-visible item; intentionally contains no arm, filename, score, or reasoning."""

    blind_id: str = Field(pattern=BLIND_ID_PATTERN)
    blind_track_id: str
    review_artifact: Path
    preview_sha256: str = Field(pattern=SHA256_PATTERN)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def opaque_artifact_name(self) -> BlindReviewItem:
        if self.review_artifact.name != f"{self.blind_id}.mp4":
            raise ValueError("blind review artifact must use the exact opaque basename")
        return self


class BlindReviewPacket(BaseModel):
    """The only artifact shown to the owner before ranking is persisted."""

    review_id: str
    seed: int
    items: list[BlindReviewItem] = Field(min_length=10)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def neutral_staging_layout(self) -> BlindReviewPacket:
        if len({item.blind_id for item in self.items}) != len(self.items):
            raise ValueError("blind packet IDs must be unique")
        if len({item.review_artifact.parent for item in self.items}) != 1:
            raise ValueError("all blind artifacts must share one expected staging parent")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def packet_sha256(self) -> str:
        return _identity_hash(
            {
                "review_id": self.review_id,
                "seed": self.seed,
                "items": [item.model_dump(mode="json") for item in self.items],
            }
        )

    @property
    def review_sequence_ids(self) -> list[str]:
        return [item.blind_id for item in self.items]


class BlindRevealEntry(BaseModel):
    blind_id: str
    run_id: str
    song_id: str
    arm: Arm
    replicate: int

    model_config = ConfigDict(extra="forbid", frozen=True)


class BlindRevealKey(BaseModel):
    review_id: str
    packet_sha256: str = Field(pattern=SHA256_PATTERN)
    entries: list[BlindRevealEntry]

    model_config = ConfigDict(extra="forbid", frozen=True)


class BlindReviewBundle(BaseModel):
    """Packet and separately persisted reveal key returned to the owner tooling."""

    packet: BlindReviewPacket
    reveal: BlindRevealKey

    model_config = ConfigDict(extra="forbid", frozen=True)


class HumanRanking(BaseModel):
    """Frozen blind ranking which must exist before the reveal key is consumed."""

    review_id: str
    packet_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ordered_blind_ids: list[str] = Field(min_length=10)
    notes: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def unique_ids(self) -> HumanRanking:
        if len(self.ordered_blind_ids) != len(set(self.ordered_blind_ids)):
            raise ValueError("ordered_blind_ids must be unique")
        return self


class ArmSummary(BaseModel):
    arm: Arm
    run_count: int
    mean_rubric_total: float
    mean_beat_sync: float
    mean_downbeat_sync: float
    mean_section_boundary_sync: float
    planning_spend_usd: float
    judging_spend_usd: float

    model_config = ConfigDict(extra="forbid", frozen=True)


class PairwiseParity(BaseModel):
    """Frozen comparison values, all expressed on the rubric's 0--40 scale.

    ``right_mean_within_song_abs_delta`` is the pre-data operational definition of
    the spec's "within-arm variance": for each song, take ``abs(B1 - B2)``, then
    average those deltas.  It deliberately stays in score units so the fixed strict
    comparison to ``mean_total_difference`` is dimensionally meaningful.
    """

    left_arm: Arm
    right_arm: Arm
    mean_total_difference: float
    right_mean_within_song_abs_delta: float
    score_band_passed: bool
    within_b_variation_passed: bool
    human_no_preference_passed: bool | None
    human_right_preference_rate: float | None
    human_one_sided_p_value: float | None
    human_harness_order_agreement_rate: float | None
    human_independent_comparison_count: int
    human_power_sufficient: bool
    sync_passed: bool
    parity: bool | None

    model_config = ConfigDict(extra="forbid", frozen=True)


class ComparisonRunRecord(BaseModel):
    """Per-song/arm/run evidence retained without exposing plan prose to reviewers."""

    run_id: str
    song_id: str
    arm: Arm
    replicate: int
    analysis_cache_key: str
    analysis_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    held_constant: HeldConstantIdentity
    regeneration_nonce: str | None
    planning_input_sha256: str | None
    planning_cache_key: str | None
    plan: ChoreographyPlan
    plan_sha256: str = Field(pattern=SHA256_PATTERN)
    call_records: list[ArmCallRecord]
    planning_spend_usd: float
    judging_spend_usd: float
    score: SequenceScore
    vision_evaluation: VisionEvaluationEvidence
    review_artifact_path: Path
    review_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    blind_id: str | None

    model_config = ConfigDict(extra="forbid", frozen=True)


class ComparisonReport(BaseModel):
    """First typed producer for the repository's comparative evaluation report."""

    FIXED_PARITY_CRITERIA: ClassVar[str] = FIXED_PARITY_CRITERIA
    schema_version: Literal["2.0.0"] = "2.0.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    manifest: ComparisonManifest
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    criteria_text: str = FIXED_PARITY_CRITERIA
    d1_standing_default_text: str = D1_STANDING_DEFAULT
    calibration_accepted: Literal[True]
    arm_summaries: list[ArmSummary]
    run_records: list[ComparisonRunRecord]
    arm_a_vs_b: PairwiseParity
    arm_c_vs_b: PairwiseParity
    blind_review_id: str
    blind_packet_sha256: str = Field(pattern=SHA256_PATTERN)
    blind_packet: BlindReviewPacket
    blind_reveal: BlindRevealKey
    human_ranking_recorded: bool
    human_ranking: HumanRanking | None
    calibration_record_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    d1_outcome: Literal["PENDING-OWNER", "DETERMINISTIC_DEFAULT", "LLM_DEFAULT", "INCONCLUSIVE"]
    actual_planning_spend_usd: float
    actual_judging_spend_usd: float
    actual_total_spend_usd: float

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def criteria_are_fixed(self) -> ComparisonReport:
        if self.criteria_text != FIXED_PARITY_CRITERIA:
            raise ValueError("fixed parity criteria may not be edited")
        if self.d1_standing_default_text != D1_STANDING_DEFAULT:
            raise ValueError("D1 standing-default wording may not be edited")
        if not self.calibration_accepted and self.d1_outcome != "PENDING-OWNER":
            raise ValueError("uncalibrated evidence cannot decide D1")
        if self.calibration_accepted and self.calibration_record_sha256 is None:
            raise ValueError("calibrated evidence requires the accepted artifact SHA-256")
        if (
            _identity_hash(self.manifest.model_dump(mode="json", exclude_computed_fields=True))
            != self.manifest_sha256
        ):
            raise ValueError("comparison manifest SHA-256 mismatch")
        _validate_report_integrity(self)
        return self


def build_blind_review(results: Sequence[ArmRunResult], *, seed: int) -> BlindReviewBundle:
    """Choose the fixed minimum, then expand to five independent A-v-B songs."""
    by_song: dict[str, list[ArmRunResult]] = defaultdict(list)
    for result in results:
        by_song[result.song_id].append(result)
    complete = sorted(song for song, runs in by_song.items() if len(runs) == 5)
    if not complete:
        raise ValueError("blind review requires at least one song with all five runs")
    generator = random.Random(seed)
    full_song = generator.choice(complete)
    selected = list(by_song[full_song])
    remaining = [result for result in results if result.song_id != full_song]
    if len(remaining) < 5:
        raise ValueError("blind review requires five additional sequences")
    selected.extend(generator.sample(remaining, 5))
    selected_run_ids = {result.run_id for result in selected}

    def has_pair(song_id: str) -> bool:
        arms = {
            result.arm
            for result in selected
            if result.song_id == song_id and result.run_id in selected_run_ids
        }
        return Arm.A in arms and Arm.B in arms

    candidate_songs = complete.copy()
    generator.shuffle(candidate_songs)
    for song_id in candidate_songs:
        if sum(has_pair(candidate) for candidate in complete) >= (
            MIN_INDEPENDENT_HUMAN_COMPARISONS
        ):
            break
        if has_pair(song_id):
            continue
        song_runs = by_song[song_id]
        selected_arms = {result.arm for result in selected if result.song_id == song_id}
        if Arm.A not in selected_arms:
            arm_a = next(result for result in song_runs if result.arm is Arm.A)
            selected.append(arm_a)
            selected_run_ids.add(arm_a.run_id)
        if Arm.B not in selected_arms:
            arm_b = generator.choice([result for result in song_runs if result.arm is Arm.B])
            selected.append(arm_b)
            selected_run_ids.add(arm_b.run_id)
    if sum(has_pair(candidate) for candidate in complete) < MIN_INDEPENDENT_HUMAN_COMPARISONS:
        raise ValueError("blind review cannot reach five independent A-v-B song comparisons")
    generator.shuffle(selected)

    review_id = _identity_hash({"seed": seed, "runs": sorted(r.run_id for r in selected)})[:20]
    track_ids: dict[str, str] = {}
    items: list[BlindReviewItem] = []
    reveal_entries: list[BlindRevealEntry] = []
    for index, result in enumerate(selected, start=1):
        track_ids.setdefault(result.song_id, f"Track-{len(track_ids) + 1:02d}")
        blind_id = f"Sequence-{index:02d}-{_identity_hash({'review': review_id, 'run': result.run_id})[:8]}"
        items.append(
            BlindReviewItem(
                blind_id=blind_id,
                blind_track_id=track_ids[result.song_id],
                review_artifact=Path("blind") / f"{blind_id}.mp4",
                preview_sha256=result.review_artifact_sha256,
            )
        )
        reveal_entries.append(
            BlindRevealEntry(
                blind_id=blind_id,
                run_id=result.run_id,
                song_id=result.song_id,
                arm=result.arm,
                replicate=result.replicate,
            )
        )
    packet = BlindReviewPacket(review_id=review_id, seed=seed, items=items)
    return BlindReviewBundle(
        packet=packet,
        reveal=BlindRevealKey(
            review_id=review_id,
            packet_sha256=packet.packet_sha256,
            entries=reveal_entries,
        ),
    )


def validate_calibration(manifest: ComparisonManifest) -> OwnerCalibrationArtifact:
    """Validate the real owner-accepted P2P-T6 artifact before paid work or verdicts."""
    path = manifest.calibration_record
    expected_hash = manifest.calibration_record_sha256
    if path is None or expected_hash is None:
        raise ExperimentBlockedError(
            "paid comparison requires an accepted P2P-T6 calibration record; "
            "the calibrated gate is PENDING-OWNER"
        )
    _assert_file_hash(path, expected_hash, "P2P-T6 calibration record")
    artifact = OwnerCalibrationArtifact.model_validate_json(path.read_text(encoding="utf-8"))
    if artifact.decision != "accepted":
        raise ExperimentBlockedError("P2P-T6 calibration record is not owner-accepted")
    if artifact.rubric_version != manifest.evaluation_harness_version:
        raise ExperimentBlockedError("calibration rubric version does not match the manifest")
    return artifact


def compute_comparison_report(
    *,
    manifest: ComparisonManifest,
    results: Sequence[ArmRunResult],
    blind_review: BlindReviewBundle,
    human_ranking: HumanRanking | None,
) -> ComparisonReport:
    """Apply the frozen A/B and C/B criteria without changing their thresholds."""
    _validate_result_matrix(results, manifest)
    validate_calibration(manifest)
    verify_blind_packet_bytes(blind_review.packet)
    human = None
    if human_ranking is not None:
        if human_ranking.review_id != blind_review.packet.review_id:
            raise ValueError("human ranking review_id does not match the blind packet")
        if human_ranking.packet_sha256 not in (None, blind_review.packet.packet_sha256):
            raise ValueError("human ranking was not recorded against this blind packet")
        if set(human_ranking.ordered_blind_ids) != set(blind_review.packet.review_sequence_ids):
            raise ValueError("human ranking must contain every blind item exactly once")
        human = _human_preference(human_ranking, blind_review.reveal, results)

    summaries = [_summarize_arm(results, arm) for arm in Arm]
    a_vs_b = _pairwise(results, Arm.A, Arm.B, human)
    c_vs_b = _pairwise(results, Arm.C, Arm.B, human)
    outcome = _derive_outcome(summaries, a_vs_b, human_ranking)
    planning = sum(result.planning_spend_usd for result in results)
    judging = sum(result.judging_spend_usd for result in results)
    blind_by_run = {entry.run_id: entry.blind_id for entry in blind_review.reveal.entries}
    return ComparisonReport(
        manifest=manifest,
        manifest_sha256=_identity_hash(
            manifest.model_dump(mode="json", exclude_computed_fields=True)
        ),
        calibration_accepted=True,
        arm_summaries=summaries,
        run_records=[
            ComparisonRunRecord(
                run_id=result.run_id,
                song_id=result.song_id,
                arm=result.arm,
                replicate=result.replicate,
                analysis_cache_key=result.analysis_cache_key,
                analysis_payload_sha256=result.analysis_payload_sha256,
                held_constant=result.held_constant,
                regeneration_nonce=result.regeneration_nonce,
                planning_input_sha256=result.planning_input_sha256,
                planning_cache_key=result.planning_cache_key,
                plan=result.plan,
                plan_sha256=result.plan_sha256,
                call_records=result.call_records,
                planning_spend_usd=result.planning_spend_usd,
                judging_spend_usd=result.judging_spend_usd,
                score=result.score,
                vision_evaluation=result.vision_evaluation,
                review_artifact_path=result.review_artifact_path,
                review_artifact_sha256=result.review_artifact_sha256,
                blind_id=blind_by_run.get(result.run_id),
            )
            for result in results
        ],
        arm_a_vs_b=a_vs_b,
        arm_c_vs_b=c_vs_b,
        blind_review_id=blind_review.packet.review_id,
        blind_packet_sha256=blind_review.packet.packet_sha256,
        blind_packet=blind_review.packet,
        blind_reveal=blind_review.reveal,
        human_ranking_recorded=human_ranking is not None,
        human_ranking=human_ranking,
        calibration_record_sha256=manifest.calibration_record_sha256,
        d1_outcome=outcome,
        actual_planning_spend_usd=planning,
        actual_judging_spend_usd=judging,
        actual_total_spend_usd=planning + judging,
    )


def stage_blind_review_packet(
    *,
    bundle: BlindReviewBundle,
    results: Sequence[ArmRunResult],
    output_dir: Path,
) -> BlindReviewBundle:
    """Copy previews to opaque names and persist only the owner-visible packet.

    The reveal key is returned to the orchestration process but is intentionally not
    written here.  ``write_reveal_key_after_ranking`` is the only persistence seam.
    """
    by_run = {result.run_id: result for result in results}
    output_dir.mkdir(parents=True, exist_ok=True)
    staged_items: list[BlindReviewItem] = []
    reveal_by_blind = {entry.blind_id: entry for entry in bundle.reveal.entries}
    for item in bundle.packet.items:
        entry = reveal_by_blind[item.blind_id]
        result = by_run[entry.run_id]
        if item.preview_sha256 != result.review_artifact_sha256:
            raise ValueError("blind packet preview commitment changed before staging")
        _assert_file_hash(
            result.review_artifact_path,
            result.review_artifact_sha256,
            f"review artifact {result.run_id}",
        )
        destination = output_dir / f"{item.blind_id}.mp4"
        shutil.copyfile(result.review_artifact_path, destination)
        if _file_sha256(destination) != result.review_artifact_sha256:
            raise RuntimeError("staged blind artifact hash changed during copy")
        staged_items.append(item.model_copy(update={"review_artifact": destination}))
    packet = BlindReviewPacket.model_validate(
        bundle.packet.model_copy(update={"items": staged_items}).model_dump(
            mode="json", exclude_computed_fields=True
        )
    )
    reveal = bundle.reveal.model_copy(update={"packet_sha256": packet.packet_sha256})
    (output_dir / "blind-review.json").write_text(
        json.dumps(packet.model_dump(mode="json", exclude_computed_fields=True), indent=2),
        encoding="utf-8",
    )
    return BlindReviewBundle(packet=packet, reveal=reveal)


def write_human_ranking(
    *, packet: BlindReviewPacket, ranking: HumanRanking, output_path: Path
) -> None:
    """Persist the blind ranking before any reveal key can be written."""
    verify_blind_packet_bytes(packet)
    if ranking.review_id != packet.review_id:
        raise ValueError("ranking review_id does not match packet")
    if ranking.packet_sha256 != packet.packet_sha256:
        raise ValueError("ranking must pin the exact blind packet SHA-256")
    if set(ranking.ordered_blind_ids) != set(packet.review_sequence_ids):
        raise ValueError("ranking must include every blind item exactly once")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(ranking.model_dump(mode="json"), indent=2), encoding="utf-8")


def verify_blind_packet_bytes(
    packet: BlindReviewPacket, *, expected_staging_parent: Path | None = None
) -> None:
    """Revalidate neutral names/layout and re-hash every opaque preview."""
    validated = BlindReviewPacket.model_validate(
        packet.model_dump(mode="json", exclude_computed_fields=True)
    )
    if expected_staging_parent is not None and any(
        item.review_artifact.parent != expected_staging_parent for item in validated.items
    ):
        raise ValueError("blind artifacts do not use the expected staging parent")
    for item in validated.items:
        _assert_file_hash(item.review_artifact, item.preview_sha256, item.blind_id)


def write_reveal_key_after_ranking(
    *, reveal: BlindRevealKey, ranking_path: Path, output_path: Path
) -> None:
    """Persist arm identities only after a valid frozen ranking exists."""
    if not ranking_path.is_file():
        raise ValueError("human ranking must be persisted before the reveal key")
    ranking = HumanRanking.model_validate_json(ranking_path.read_text(encoding="utf-8"))
    if ranking.review_id != reveal.review_id or ranking.packet_sha256 != reveal.packet_sha256:
        raise ValueError("persisted ranking does not match the reveal key commitment")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(reveal.model_dump(mode="json"), indent=2), encoding="utf-8")


def _summarize_arm(
    results: Sequence[ArmRunResult] | Sequence[ComparisonRunRecord], arm: Arm
) -> ArmSummary:
    selected = [result for result in results if result.arm is arm]
    return ArmSummary(
        arm=arm,
        run_count=len(selected),
        mean_rubric_total=_mean([result.score.rubric.total for result in selected]),
        mean_beat_sync=_mean([result.score.sync.beat for result in selected]),
        mean_downbeat_sync=_mean([result.score.sync.downbeat for result in selected]),
        mean_section_boundary_sync=_mean(
            [result.score.sync.section_boundary for result in selected]
        ),
        planning_spend_usd=sum(result.planning_spend_usd for result in selected),
        judging_spend_usd=sum(result.judging_spend_usd for result in selected),
    )


def _pairwise(
    results: Sequence[ArmRunResult] | Sequence[ComparisonRunRecord],
    left: Arm,
    right: Arm,
    human: dict[tuple[Arm, Arm], tuple[float, float, bool | None, float | None, int]] | None,
) -> PairwiseParity:
    left_runs = [result for result in results if result.arm is left]
    right_runs = [result for result in results if result.arm is right]
    difference = abs(
        _mean([run.score.rubric.total for run in left_runs])
        - _mean([run.score.rubric.total for run in right_runs])
    )
    right_by_song: dict[str, list[float]] = defaultdict(list)
    for run in right_runs:
        right_by_song[run.song_id].append(run.score.rubric.total)
    pair_differences = [
        abs(values[0] - values[1]) for values in right_by_song.values() if len(values) == 2
    ]
    within = _mean(pair_differences)
    score_band = difference <= 0.5
    within_passed = difference < within
    sync_passed = all(
        _mean([getattr(run.score.sync, field) for run in left_runs])
        >= _mean([getattr(run.score.sync, field) for run in right_runs])
        for field in ("beat", "downbeat", "section_boundary")
    )
    human_values = human.get((left, right)) if human is not None else None
    human_rate, human_p, human_pass, human_harness_agreement, human_count = (
        human_values if human_values is not None else (None, None, None, None, 0)
    )
    parity = (
        None if human_pass is None else score_band and within_passed and human_pass and sync_passed
    )
    return PairwiseParity(
        left_arm=left,
        right_arm=right,
        mean_total_difference=difference,
        right_mean_within_song_abs_delta=within,
        score_band_passed=score_band,
        within_b_variation_passed=within_passed,
        human_no_preference_passed=human_pass,
        human_right_preference_rate=human_rate,
        human_one_sided_p_value=human_p,
        human_harness_order_agreement_rate=human_harness_agreement,
        human_independent_comparison_count=human_count,
        human_power_sufficient=human_count >= MIN_INDEPENDENT_HUMAN_COMPARISONS,
        sync_passed=sync_passed,
        parity=parity,
    )


def _human_preference(
    ranking: HumanRanking,
    reveal: BlindRevealKey,
    results: Sequence[ArmRunResult] | Sequence[ComparisonRunRecord],
) -> dict[tuple[Arm, Arm], tuple[float, float, bool | None, float | None, int]]:
    position = {blind_id: index for index, blind_id in enumerate(ranking.ordered_blind_ids)}
    entries_by_song: dict[str, list[BlindRevealEntry]] = defaultdict(list)
    for entry in reveal.entries:
        entries_by_song[entry.song_id].append(entry)
    score_by_run = {result.run_id: result.score.rubric.total for result in results}
    output: dict[tuple[Arm, Arm], tuple[float, float, bool | None, float | None, int]] = {}
    for left, right in ((Arm.A, Arm.B), (Arm.C, Arm.B)):
        comparisons: list[bool] = []
        harness_agreement: list[bool] = []
        for entries in entries_by_song.values():
            left_entries = [entry for entry in entries if entry.arm is left]
            right_entries = [entry for entry in entries if entry.arm is right]
            if not left_entries or not right_entries:
                continue
            left_rank = _mean([float(position[entry.blind_id]) for entry in left_entries])
            right_rank = _mean([float(position[entry.blind_id]) for entry in right_entries])
            human_prefers_right = right_rank < left_rank
            comparisons.append(human_prefers_right)
            left_score = _mean([score_by_run[entry.run_id] for entry in left_entries])
            right_score = _mean([score_by_run[entry.run_id] for entry in right_entries])
            if not math.isclose(left_score, right_score, abs_tol=1e-9):
                harness_agreement.append(human_prefers_right == (right_score > left_score))
        if not comparisons:
            continue
        wins = sum(comparisons)
        rate = wins / len(comparisons)
        p_value = _one_sided_binomial_p_value(wins, len(comparisons))
        agreement = sum(harness_agreement) / len(harness_agreement) if harness_agreement else None
        sufficient = len(comparisons) >= MIN_INDEPENDENT_HUMAN_COMPARISONS
        output[(left, right)] = (
            rate,
            p_value,
            p_value > 0.05 if sufficient else None,
            agreement,
            len(comparisons),
        )
    return output


def _one_sided_binomial_p_value(successes: int, trials: int) -> float:
    return float(
        sum(math.comb(trials, value) for value in range(successes, trials + 1)) / (2**trials)
    )


def _validate_result_matrix(
    results: Sequence[ArmRunResult] | Sequence[ComparisonRunRecord],
    manifest: ComparisonManifest,
) -> None:
    if len(manifest.songs) < 8:
        raise ValueError("comparison manifest requires N >= 8 songs")
    if len(results) != manifest.sequence_count:
        raise ValueError("comparison requires the manifest's exact 5N run count")
    if len({result.run_id for result in results}) != len(results):
        raise ValueError("comparison run_id values must be unique")
    by_song: dict[str, list[ArmRunResult | ComparisonRunRecord]] = defaultdict(list)
    for result in results:
        by_song[result.song_id].append(result)
    expected_song_ids = {song.song_id for song in manifest.songs}
    if set(by_song) != expected_song_ids:
        raise ValueError("result song set does not match the frozen manifest")
    nonces: set[str] = set()
    planning_cache_keys: set[str] = set()
    total_planning_spend = 0.0
    total_judging_spend = 0.0
    song_by_id = {song.song_id: song for song in manifest.songs}
    for song_id, runs in by_song.items():
        shape = sorted((run.arm.value, run.replicate) for run in runs)
        expected = [("A", 1), ("B", 1), ("B", 2), ("C", 1), ("C", 2)]
        if shape != expected:
            raise ValueError(f"song {song_id} does not contain the required five-run matrix")
        identities = {(run.analysis_cache_key, run.analysis_payload_sha256) for run in runs}
        if len(identities) != 1:
            raise ValueError(f"song {song_id} did not hold analysis constant")
        held = {run.held_constant for run in runs}
        if len(held) != 1:
            raise ValueError(f"song {song_id} held-constant hashes differ across arms")
        identity = next(iter(held))
        if any(
            run.analysis_cache_key != identity.analysis_cache_key
            or run.analysis_payload_sha256 != identity.analysis_payload_sha256
            for run in runs
        ):
            raise ValueError("run analysis identity does not match held-constant evidence")
        if identity.audio_sha256 != song_by_id[song_id].audio_sha256:
            raise ValueError("held audio SHA-256 does not match the manifest")
        if identity.fixture_config_sha256 != manifest.fixture_config_sha256:
            raise ValueError("held fixture SHA-256 does not match the manifest")
        if any(
            value == "0" * 64
            for value in (
                identity.analysis_payload_sha256,
                identity.beat_grid_sha256,
                identity.stems_sha256,
                identity.template_set_sha256,
                identity.renderer_sha256,
                identity.evaluation_config_sha256,
            )
        ):
            raise ValueError("held-constant identities cannot use placeholder hashes")
        for run in runs:
            roles = {record.role for record in run.call_records}
            if "vision_judge" not in roles:
                raise ValueError("every run requires preserved vision-judge usage")
            if run.arm is Arm.A and roles != {"vision_judge"}:
                raise ValueError("Arm A cannot contain planning call records")
            if run.arm is Arm.B and (
                "macro_planner" not in roles or not any("moving_head" in role for role in roles)
            ):
                raise ValueError("Arm B requires macro and moving-head call records")
            if run.arm is Arm.C and (
                any("macro" in role for role in roles)
                or not any("moving_head" in role for role in roles)
            ):
                raise ValueError("Arm C must contain moving-head but no macro calls")
            if run.arm in (Arm.B, Arm.C):
                assert run.regeneration_nonce is not None
                if run.regeneration_nonce in nonces:
                    raise ValueError("B/C regeneration nonces must be distinct")
                nonces.add(run.regeneration_nonce)
                expected_input = _planning_input_identity(
                    manifest=manifest,
                    song=song_by_id[song_id],
                    arm=run.arm,
                    held=run.held_constant,
                )
                if run.planning_input_sha256 != expected_input or (
                    run.planning_cache_key
                    != _planning_cache_key(expected_input, run.regeneration_nonce)
                ):
                    raise ValueError(
                        "planning cache key is not bound to its exact nonce/input identity"
                    )
                assert run.planning_cache_key is not None
                if run.planning_cache_key in planning_cache_keys:
                    raise ValueError("B/C planning cache keys must be distinct")
                planning_cache_keys.add(run.planning_cache_key)
            elif any(
                value is not None
                for value in (
                    run.regeneration_nonce,
                    run.planning_input_sha256,
                    run.planning_cache_key,
                )
            ):
                raise ValueError("Arm A cannot contain LLM planning-cache identity")
            if run.vision_evaluation.calibration_record_sha256 != (
                manifest.calibration_record_sha256
            ):
                raise ValueError("vision evidence calibration hash does not match manifest")
            if run.vision_evaluation.evaluation_config_sha256 != (
                identity.evaluation_config_sha256
            ):
                raise ValueError("vision evidence config hash does not match held identity")
            planning_records = [r for r in run.call_records if r.role != "vision_judge"]
            judging_records = [r for r in run.call_records if r.role == "vision_judge"]
            vision = run.vision_evaluation.result
            plan_sha = _identity_hash(run.plan.model_dump(mode="json"))
            if run.plan_sha256 != plan_sha or vision.plan_sha256 != plan_sha:
                raise ValueError("run, plan, and vision plan identities do not match")
            if (
                run.review_artifact_path != vision.preview_path
                or run.review_artifact_sha256 != vision.preview_sha256
            ):
                raise ValueError("blind review artifact is not the scored vision preview")
            if run.score != SequenceScore.from_vision(vision):
                raise ValueError("sequence score does not match embedded vision evidence")
            vision_usage = vision.visual.usage
            if (
                sum(record.prompt_tokens for record in judging_records)
                != vision_usage.prompt_tokens
                or sum(record.reasoning_tokens for record in judging_records)
                != vision_usage.reasoning_tokens
                or sum(record.completion_tokens for record in judging_records)
                != vision_usage.completion_tokens
                or sum(record.total_tokens for record in judging_records)
                != vision_usage.total_tokens
                or not math.isclose(
                    sum(record.cost_usd for record in judging_records),
                    vision.visual.actual_cost_usd,
                    abs_tol=1e-9,
                )
            ):
                raise ValueError(
                    "vision call ledger does not match preserved VisionEvaluationResult usage"
                )
            for record in run.call_records:
                config = _role_config(manifest, record.role)
                if not _call_matches_role_config(record, config):
                    raise ValueError(
                        "call record does not match its frozen role/provider/pricing config"
                    )
            vision_config = manifest.vision_judge
            if vision.visual.model != vision_config.model:
                raise ValueError("VisionEvaluationResult model differs from vision role config")
            planning_logical = sum(record.logical_requests for record in planning_records)
            if planning_logical > manifest.spend.planning_logical_requests_per_run:
                raise ValueError("planning logical-request ceiling exceeded")
            if any(
                record.provider_attempts
                > record.logical_requests * manifest.spend.provider_attempts_per_logical_request
                for record in run.call_records
            ):
                raise ValueError("provider-attempt ceiling exceeded")
            if sum(record.logical_requests for record in judging_records) != (
                manifest.spend.judging_logical_requests_per_sequence
            ):
                raise ValueError("every sequence requires exactly one judging request")
            if not math.isclose(
                sum(record.cost_usd for record in planning_records),
                run.planning_spend_usd,
                abs_tol=1e-9,
            ):
                raise ValueError("run planning spend does not match exact call records")
            if not math.isclose(
                sum(record.cost_usd for record in judging_records),
                run.judging_spend_usd,
                abs_tol=1e-9,
            ):
                raise ValueError("run judging spend does not match exact call records")
            if run.judging_spend_usd > manifest.spend.judging_per_sequence_cap_usd:
                raise ValueError("sequence judging spend exceeded the manifest cap")
            total_planning_spend += run.planning_spend_usd
            total_judging_spend += run.judging_spend_usd
    if total_planning_spend > manifest.spend.planning_cap_usd:
        raise ValueError("comparison planning spend exceeded the manifest cap")
    if total_planning_spend + total_judging_spend > manifest.spend.whole_experiment_cap_usd:
        raise ValueError("comparison spend exceeded the $40 manifest cap")


def _derive_outcome(
    summaries: Sequence[ArmSummary],
    a_vs_b: PairwiseParity,
    human_ranking: HumanRanking | None,
) -> Literal["PENDING-OWNER", "DETERMINISTIC_DEFAULT", "LLM_DEFAULT", "INCONCLUSIVE"]:
    if human_ranking is None:
        return "PENDING-OWNER"
    a_mean = next(item.mean_rubric_total for item in summaries if item.arm is Arm.A)
    b_mean = next(item.mean_rubric_total for item in summaries if item.arm is Arm.B)
    if a_mean - b_mean > 0.5:
        return "DETERMINISTIC_DEFAULT"
    if b_mean - a_mean > 0.5:
        return "LLM_DEFAULT"
    if a_vs_b.parity is True:
        return "DETERMINISTIC_DEFAULT"
    return "INCONCLUSIVE"


def _role_config(manifest: ComparisonManifest, role: str) -> RoleExecutionConfig:
    normalized = role.casefold()
    if normalized == "vision_judge":
        return manifest.vision_judge
    if "macro" in normalized:
        return manifest.macro_planner
    if "moving_head" in normalized:
        return manifest.moving_head_planner
    raise ValueError(f"unrecognized experiment call role: {role}")


def _call_kind_for_role(role: str) -> Literal["planning", "judging"]:
    normalized = role.casefold()
    if normalized == "vision_judge":
        return "judging"
    if "macro" in normalized or "moving_head" in normalized:
        return "planning"
    raise ExperimentBlockedError(f"unrecognized experiment call role: {role}")


def _validate_unknown_failure_record(role: str, record: ArmCallRecord) -> None:
    if (
        record.role != role
        or record.succeeded
        or record.failure != UNKNOWN_PROVIDER_USAGE_FAILURE
        or record.prompt_tokens != 0
        or record.reasoning_tokens != 0
        or record.completion_tokens != 0
        or record.total_tokens != 0
        or record.cost_usd != 0
        or record.logical_requests != 1
        or record.provider_attempts != 1
    ):
        raise ValueError(
            "unknown provider failure fallback must be a role-bound zero-usage failed record"
        )


def _price_tokens(
    *,
    prompt_tokens: int,
    reasoning_tokens: int,
    completion_tokens: int,
    pricing: PricingIdentity,
) -> float:
    return (
        prompt_tokens * pricing.prompt_per_million_usd
        + reasoning_tokens * pricing.reasoning_per_million_usd
        + completion_tokens * pricing.completion_per_million_usd
    ) / 1_000_000


def _call_matches_role_config(record: ArmCallRecord, config: RoleExecutionConfig) -> bool:
    expected_cost = _price_tokens(
        prompt_tokens=record.prompt_tokens,
        reasoning_tokens=record.reasoning_tokens,
        completion_tokens=record.completion_tokens,
        pricing=config.pricing,
    )
    return (
        record.model == config.model
        and record.reasoning_effort == config.reasoning_effort
        and math.isclose(record.temperature, config.temperature, abs_tol=1e-12)
        and record.pricing_id == config.pricing.pricing_id
        and math.isclose(record.cost_usd, expected_cost, rel_tol=1e-12, abs_tol=0.0)
    )


def _planning_input_identity(
    *,
    manifest: ComparisonManifest,
    song: SongManifestEntry,
    arm: Arm,
    held: HeldConstantIdentity,
) -> str:
    if arm not in (Arm.B, Arm.C):
        raise ValueError("planning input identity exists only for LLM arms")
    return _identity_hash(
        {
            "experiment_id": manifest.experiment_id,
            "song_id": song.song_id,
            "held_constant": held.model_dump(mode="json"),
            "arm": arm.value,
            "include_macro": arm is Arm.B,
            "macro_planner": manifest.macro_planner.model_dump(mode="json"),
            "moving_head_planner": manifest.moving_head_planner.model_dump(mode="json"),
        }
    )


def _planning_cache_key(planning_input_sha256: str, regeneration_nonce: str) -> str:
    return _identity_hash(
        {
            "planning_input_sha256": planning_input_sha256,
            "regeneration_nonce": regeneration_nonce,
        }
    )


def _validate_report_integrity(report: ComparisonReport) -> None:
    """Recompute every derived report claim from its manifest-bound raw evidence."""
    validate_calibration(report.manifest)
    verify_blind_packet_bytes(report.blind_packet)
    _validate_result_matrix(report.run_records, report.manifest)
    if report.calibration_record_sha256 != report.manifest.calibration_record_sha256:
        raise ValueError("report calibration hash does not match the manifest")
    if report.blind_review_id != report.blind_packet.review_id:
        raise ValueError("report blind review id does not match its packet")
    if report.blind_packet_sha256 != report.blind_packet.packet_sha256:
        raise ValueError("report blind packet SHA-256 mismatch")
    if report.blind_reveal.review_id != report.blind_packet.review_id or (
        report.blind_reveal.packet_sha256 != report.blind_packet.packet_sha256
    ):
        raise ValueError("report reveal does not match its blind packet commitment")
    record_by_run = {record.run_id: record for record in report.run_records}
    item_by_blind = {item.blind_id: item for item in report.blind_packet.items}
    reveal_by_blind = {entry.blind_id: entry for entry in report.blind_reveal.entries}
    expected_tracks: dict[str, str] = {}
    for item in report.blind_packet.items:
        entry = reveal_by_blind.get(item.blind_id)
        if entry is None:
            raise ValueError("blind packet item is absent from the reveal mapping")
        expected_tracks.setdefault(entry.song_id, f"Track-{len(expected_tracks) + 1:02d}")
        if item.blind_track_id != expected_tracks[entry.song_id]:
            raise ValueError("blind track grouping does not match revealed song identities")
    for entry in report.blind_reveal.entries:
        record = record_by_run.get(entry.run_id)
        blind_item = item_by_blind.get(entry.blind_id)
        if record is None or blind_item is None:
            raise ValueError("blind evidence references an unknown run or packet item")
        if (record.song_id, record.arm, record.replicate, record.blind_id) != (
            entry.song_id,
            entry.arm,
            entry.replicate,
            entry.blind_id,
        ):
            raise ValueError("blind reveal mapping does not match its run record")
        if blind_item.preview_sha256 != record.review_artifact_sha256:
            raise ValueError("blind preview commitment does not match run evidence")
    expected_blind_ids = {entry.blind_id for entry in report.blind_reveal.entries}
    if {record.blind_id for record in report.run_records if record.blind_id is not None} != (
        expected_blind_ids
    ):
        raise ValueError("run-record blind mapping is incomplete")
    human = None
    if report.human_ranking is not None:
        if report.human_ranking.review_id != report.blind_packet.review_id or (
            report.human_ranking.packet_sha256 != report.blind_packet.packet_sha256
        ):
            raise ValueError("report human ranking does not match the blind packet")
        if set(report.human_ranking.ordered_blind_ids) != set(
            report.blind_packet.review_sequence_ids
        ):
            raise ValueError("report human ranking is not the committed blind subset")
        human = _human_preference(
            report.human_ranking,
            report.blind_reveal,
            report.run_records,
        )
    if report.human_ranking_recorded != (report.human_ranking is not None):
        raise ValueError("human-ranking recorded flag is inconsistent")
    summaries = [_summarize_arm(report.run_records, arm) for arm in Arm]
    a_vs_b = _pairwise(report.run_records, Arm.A, Arm.B, human)
    c_vs_b = _pairwise(report.run_records, Arm.C, Arm.B, human)
    if report.arm_summaries != summaries:
        raise ValueError("arm summaries do not match run evidence")
    if report.arm_a_vs_b != a_vs_b or report.arm_c_vs_b != c_vs_b:
        raise ValueError("pairwise claims do not match run and human evidence")
    if report.d1_outcome != _derive_outcome(summaries, a_vs_b, report.human_ranking):
        raise ValueError("D1 outcome does not match the signed score direction and parity")
    planning = sum(record.planning_spend_usd for record in report.run_records)
    judging = sum(record.judging_spend_usd for record in report.run_records)
    if not math.isclose(report.actual_planning_spend_usd, planning, abs_tol=1e-9):
        raise ValueError("report planning spend does not match run evidence")
    if not math.isclose(report.actual_judging_spend_usd, judging, abs_tol=1e-9):
        raise ValueError("report judging spend does not match run evidence")
    if not math.isclose(report.actual_total_spend_usd, planning + judging, abs_tol=1e-9):
        raise ValueError("report total spend does not match run evidence")


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("cannot calculate a mean from no values")
    return sum(values) / len(values)


def _identity_hash(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_file_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise ExperimentBlockedError(f"{label} does not exist: {path}")
    if _file_sha256(path) != expected:
        raise ExperimentBlockedError(f"{label} SHA-256 changed after the manifest was frozen")
