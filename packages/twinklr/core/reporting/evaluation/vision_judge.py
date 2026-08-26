"""Provider-framework vision rubric, budget guard, and timestamped context."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Any

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, field_validator

from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.result import AgentResult
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.config.models import AgentConfig

RUBRIC_VERSION = "lighting-automv-v1"
MAX_REQUEST_IMAGES = 1500
MAX_REQUEST_BYTES = 512 * 1024 * 1024


class RubricCategoryScore(BaseModel):
    """A grounded 0-10 category score."""

    score: float = Field(ge=0, le=10)
    justification: str = Field(min_length=1, max_length=600)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("justification")
    @classmethod
    def require_grounding(cls, value: str) -> str:
        lowered = value.lower()
        if "frame" not in lowered and "section" not in lowered:
            raise ValueError("justification must cite a frame index or section name")
        return value


class VisionRubricResponse(BaseModel):
    """Exactly four visual categories; deterministic metrics live elsewhere."""

    musicality_by_proxy: RubricCategoryScore
    coordination: RubricCategoryScore
    color_palette_coherence: RubricCategoryScore
    variety_and_pacing: RubricCategoryScore

    model_config = ConfigDict(extra="forbid", frozen=True)


class FrameInput(BaseModel):
    """One labeled image presented to the visual judge."""

    index: int = Field(ge=1)
    timestamp_ms: int = Field(ge=0)
    path: Path
    label: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class VisionJudgeConfig(BaseModel):
    """Cost prices and hard caps; model identity belongs to AgentConfig."""

    per_song_cap_usd: float = Field(default=0.20, gt=0)
    per_run_cap_usd: float = Field(default=2.00, gt=0)
    image_input_usd_per_megapixel: float = Field(default=0.0004, ge=0)
    input_usd_per_million_tokens: float = Field(default=0.20, ge=0)
    output_usd_per_million_tokens: float = Field(default=1.20, ge=0)
    estimated_output_tokens: int = Field(default=1000, gt=0, le=3000)

    model_config = ConfigDict(extra="forbid", frozen=True)


class VisionCostEstimate(BaseModel):
    """Pre-call estimate used by both song and run guards."""

    image_count: int = Field(ge=1)
    image_megapixels: float = Field(gt=0)
    image_cost_usd: float = Field(ge=0)
    output_allowance_usd: float = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)


class VisionTokenUsage(BaseModel):
    """Exact per-call usage returned by the runner."""

    prompt_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)


class JudgedFrames(BaseModel):
    """The paid visual half of a combined evaluation record."""

    rubric: VisionRubricResponse
    rubric_version: str = RUBRIC_VERSION
    model: str
    estimate: VisionCostEstimate
    actual_cost_usd: float = Field(ge=0)
    usage: VisionTokenUsage
    logical_request_count: int = Field(default=1, ge=1, le=1)
    provider_attempt_cap: int = Field(default=1, ge=1, le=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class BudgetExceededError(RuntimeError):
    """Raised before a provider request would exceed an evaluation cap."""


class VisionAttemptSpend(BaseModel):
    """Exact usage and priced spend from one completed logical attempt."""

    success: bool
    usage: VisionTokenUsage
    actual_cost_usd: float = Field(ge=0)
    error_message: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class VisionReservation:
    """Opaque reservation reconciled after an AgentResult is received."""

    reservation_id: int
    estimated_cost_usd: float


class VisionBudgetLedger:
    """Run-scoped reservation ledger; estimates are retained even when a call fails."""

    def __init__(self, *, config: VisionJudgeConfig) -> None:
        self.config = config
        self.actual_usd = 0.0
        self.song_count = 0
        self.attempts: list[VisionAttemptSpend] = []
        self._outstanding: dict[int, float] = {}
        self._next_reservation_id = 1

    @property
    def outstanding_estimate_usd(self) -> float:
        return sum(self._outstanding.values())

    @property
    def reserved_usd(self) -> float:
        """Backward-compatible name for estimates that have not settled yet."""
        return self.outstanding_estimate_usd

    @property
    def projected_spend_usd(self) -> float:
        return self.actual_usd + self.outstanding_estimate_usd

    def reserve(self, estimate: VisionCostEstimate, *, override: bool = False) -> VisionReservation:
        if not override and estimate.estimated_cost_usd > self.config.per_song_cap_usd:
            raise BudgetExceededError(
                f"Vision estimate ${estimate.estimated_cost_usd:.4f} exceeds per-song "
                f"cap ${self.config.per_song_cap_usd:.4f}; reduce frames/resolution or use "
                "the explicit owner-controlled override."
            )
        projected = self.projected_spend_usd + estimate.estimated_cost_usd
        if not override and projected > self.config.per_run_cap_usd:
            raise BudgetExceededError(
                f"Vision estimate would exceed per-run cap ${self.config.per_run_cap_usd:.4f}"
            )
        reservation = VisionReservation(
            reservation_id=self._next_reservation_id,
            estimated_cost_usd=estimate.estimated_cost_usd,
        )
        self._next_reservation_id += 1
        self._outstanding[reservation.reservation_id] = reservation.estimated_cost_usd
        self.song_count += 1
        return reservation

    def settle(
        self,
        reservation: VisionReservation,
        *,
        spend: VisionAttemptSpend,
    ) -> None:
        if reservation.reservation_id not in self._outstanding:
            raise ValueError("Vision reservation is missing or already settled")
        del self._outstanding[reservation.reservation_id]
        cost_usd = spend.actual_cost_usd
        self.actual_usd += cost_usd
        self.attempts.append(spend)


def get_vision_judge_spec(config: AgentConfig) -> AgentSpec:
    """Build the mini-tier vision role entirely from central configuration."""
    return AgentSpec(
        name="vision_judge",
        prompt_pack="prompts/vision_judge",
        response_model=VisionRubricResponse,
        mode=AgentMode.ONESHOT,
        model=config.model,
        temperature=config.temperature,
        reasoning_effort=config.reasoning_effort,
        max_tokens=min(config.max_tokens, 3000),
        timeout_seconds=config.timeout_seconds,
        max_schema_repair_attempts=0,
        provider_max_attempts=1,
        allow_json_object_fallback=False,
    )


def estimate_vision_cost(frames: list[FrameInput], config: VisionJudgeConfig) -> VisionCostEstimate:
    """Estimate image-resolution and bounded-output cost before any call."""
    if not frames:
        raise ValueError("At least one labeled frame/contact sheet is required")
    megapixels = 0.0
    for frame in frames:
        with Image.open(frame.path) as image:
            width, height = image.size
        megapixels += width * height / 1_000_000
    image_cost = megapixels * config.image_input_usd_per_megapixel
    output_allowance = (
        config.estimated_output_tokens * config.output_usd_per_million_tokens / 1_000_000
    )
    return VisionCostEstimate(
        image_count=len(frames),
        image_megapixels=megapixels,
        image_cost_usd=image_cost,
        output_allowance_usd=output_allowance,
        estimated_cost_usd=image_cost + output_allowance,
    )


async def judge_frames(
    *,
    runner: AsyncAgentRunner,
    agent_config: AgentConfig,
    frames: list[FrameInput],
    structure_text: str,
    section_names: set[str],
    config: VisionJudgeConfig,
    ledger: VisionBudgetLedger,
    override_budget: bool = False,
) -> JudgedFrames:
    """Run the one-request visual rubric after both budget guards pass."""
    if not structure_text.strip():
        raise ValueError("Timestamped structure text must be non-empty")
    if not section_names or any(not name.strip() for name in section_names):
        raise ValueError("At least one real section name is required")
    _validate_request_payload(frames, structure_text=structure_text)
    estimate = estimate_vision_cost(frames, config)
    reservation = ledger.reserve(estimate, override=override_budget)
    result = await runner.run(
        get_vision_judge_spec(agent_config),
        variables={
            "structure_text": structure_text,
            "frame_manifest": "\n".join(
                frame.label or f"Frame {frame.index}: {_format_timestamp(frame.timestamp_ms)}"
                for frame in frames
            ),
        },
        input_image_urls=[_data_url(frame.path) for frame in frames],
    )
    usage = VisionTokenUsage(
        prompt_tokens=result.prompt_tokens,
        reasoning_tokens=result.reasoning_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.tokens_used,
    )
    actual_cost = _actual_cost(result, config)
    ledger.settle(
        reservation,
        spend=VisionAttemptSpend(
            success=result.success,
            usage=usage,
            actual_cost_usd=actual_cost,
            error_message=result.error_message,
        ),
    )
    if not result.success or not isinstance(result.data, VisionRubricResponse):
        raise RuntimeError(result.error_message or "Vision judge returned no rubric")
    _validate_grounding(result.data, frames=frames, section_names=section_names)
    return JudgedFrames(
        rubric=result.data,
        model=str(result.metadata.get("model") or agent_config.model),
        estimate=estimate,
        actual_cost_usd=actual_cost,
        usage=usage,
    )


def _actual_cost(result: AgentResult, config: VisionJudgeConfig) -> float:
    return (
        result.prompt_tokens * config.input_usd_per_million_tokens
        + (result.reasoning_tokens + result.completion_tokens)
        * config.output_usd_per_million_tokens
    ) / 1_000_000


def validate_vision_request_payload(frames: list[FrameInput], *, context_text: str) -> None:
    """Apply provider hard limits before reservation or provider execution."""
    if len(frames) > MAX_REQUEST_IMAGES:
        raise BudgetExceededError(
            f"Vision request has {len(frames)} images, exceeding the 1,500-image hard limit"
        )
    manifest_bytes = sum(
        len((frame.label or f"Frame {frame.index}").encode("utf-8")) for frame in frames
    )
    encoded_bytes = (
        sum(_encoded_image_bytes(frame.path) for frame in frames)
        + len(context_text.encode("utf-8"))
        + manifest_bytes
    )
    if encoded_bytes > MAX_REQUEST_BYTES:
        raise BudgetExceededError(
            f"Vision request is {encoded_bytes / 1024 / 1024:.2f} MiB encoded, exceeding "
            "the 512 MiB hard limit"
        )


def _validate_request_payload(frames: list[FrameInput], *, structure_text: str) -> None:
    """Preserved rubric-v1 compatibility wrapper."""
    validate_vision_request_payload(frames, context_text=structure_text)


def _encoded_image_bytes(path: Path) -> int:
    raw_bytes = path.stat().st_size
    header_bytes = len("data:image/png;base64,")
    return header_bytes + 4 * math.ceil(raw_bytes / 3)


def _validate_grounding(
    rubric: VisionRubricResponse,
    *,
    frames: list[FrameInput],
    section_names: set[str],
) -> None:
    allowed_frames = supplied_frame_indices(frames)
    normalized_sections = {name.casefold() for name in section_names}
    for field_name in VisionRubricResponse.model_fields:
        justification = getattr(rubric, field_name).justification
        cited_ranges = list(
            re.finditer(r"\bFrames?\s+(\d+)(?:\s*[–-]\s*(\d+))?", justification, re.I)
        )
        cited_frames: set[int] = set()
        for match in cited_ranges:
            start = int(match.group(1))
            end = int(match.group(2) or start)
            cited_frames.update(range(min(start, end), max(start, end) + 1))
        unknown = sorted(cited_frames - allowed_frames)
        if unknown:
            raise RuntimeError(f"{field_name} justification cites unknown frame {unknown[0]}")
        lowered = justification.casefold()
        cites_section = any(
            re.search(rf"(?<!\w){re.escape(name)}(?!\w)", lowered) for name in normalized_sections
        )
        if not cited_frames and not cites_section:
            raise RuntimeError(
                f"{field_name} justification must cite a supplied frame or real section name"
            )


def supplied_frame_indices(frames: list[FrameInput]) -> set[int]:
    """Expand direct and contact-sheet range labels to their supplied frame indices."""
    allowed_frames: set[int] = set()
    for frame in frames:
        label = frame.label or f"Frame {frame.index}"
        matches = list(re.finditer(r"\bFrames?\s+(\d+)(?:\s*[–-]\s*(\d+))?", label, re.I))
        if not matches:
            allowed_frames.add(frame.index)
        for match in matches:
            start = int(match.group(1))
            end = int(match.group(2) or start)
            allowed_frames.update(range(min(start, end), max(start, end) + 1))
    return allowed_frames


def build_structure_text(
    *,
    sections: list[dict[str, Any]],
    tempo_bpm: float,
    beats_per_bar: int,
    beat_count: int,
    downbeat_count: int,
) -> str:
    """Render the timestamped structure companion supplied with every image call."""
    if not sections:
        raise ValueError("At least one timestamped section is required")
    lines = [
        "TWINKLR TIMESTAMPED STRUCTURE",
        (
            f"Grid summary: {tempo_bpm:.2f} BPM; {beats_per_bar} beats/bar; "
            f"{beat_count} beat markers; {downbeat_count} downbeat markers."
        ),
        "Sections:",
    ]
    for section in sections:
        name = str(section["section_name"])
        start_ms = int(section["start_ms"])
        end_ms = int(section["end_ms"])
        intent = str(section["intent"])
        lines.append(
            f"- {name} [{_format_timestamp(start_ms)}–{_format_timestamp(end_ms)}]: {intent}"
        )
    return "\n".join(lines)


def _data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    return f"data:{mime};base64,{encoded}"


def _format_timestamp(timestamp_ms: int) -> str:
    minutes, remainder = divmod(timestamp_ms, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
