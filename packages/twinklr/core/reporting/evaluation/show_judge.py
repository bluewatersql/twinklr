"""Rubric-v2 and provider-ready claims for visual combined-show judging."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.config.models import AgentConfig
from twinklr.core.reporting.evaluation.show_manifest import (
    ShowCapability,
    ShowEvaluationManifest,
    ShowTraceV2,
    load_show_evaluation_manifest,
    load_show_trace,
)
from twinklr.core.reporting.evaluation.vision_judge import (
    FrameInput,
    RubricCategoryScore,
    VisionAttemptSpend,
    VisionBudgetLedger,
    VisionCostEstimate,
    VisionJudgeConfig,
    VisionTokenUsage,
    estimate_vision_cost,
    supplied_frame_indices,
    validate_vision_request_payload,
)

SHOW_RUBRIC_VERSION = "lighting-automv-v2"


class CoordinationCriterion(BaseModel):
    """Human-applicable visual criterion whose direction is always higher-is-better."""

    criterion_id: Literal[
        "focal_clarity",
        "call_response_legibility",
        "cross_part_palette_agreement",
        "section_transition_agreement",
        "mutual_complement",
    ]
    title: str
    scoring_definition: str
    higher_is_better: Literal[True] = True

    model_config = ConfigDict(extra="forbid", frozen=True)


COORDINATION_CRITERIA: tuple[CoordinationCriterion, ...] = (
    CoordinationCriterion(
        criterion_id="focal_clarity",
        title="Focal clarity",
        scoring_definition="10 means the intended lead reads clearly while supporting parts remain subordinate.",
    ),
    CoordinationCriterion(
        criterion_id="call_response_legibility",
        title="Call-and-response legibility",
        scoring_definition="10 means each declared exchange reads as a clear visual conversation.",
    ),
    CoordinationCriterion(
        criterion_id="cross_part_palette_agreement",
        title="Cross-part palette agreement",
        scoring_definition="10 means both parts inhabit the declared colour world in every sampled section.",
    ),
    CoordinationCriterion(
        criterion_id="section_transition_agreement",
        title="Section-transition agreement",
        scoring_definition="10 means both parts visibly support the same structural change between sections.",
    ),
    CoordinationCriterion(
        criterion_id="mutual_complement",
        title="Mutual complement",
        scoring_definition="10 means the parts reinforce rather than wash out or compete for attention.",
    ),
)


class VisualCriterionScore(BaseModel):
    """A score or a strict N/A with an explicit reason."""

    applicability: Literal["scored", "not_applicable"]
    score: float | None = Field(default=None, ge=0, le=10)
    justification: str = Field(min_length=1, max_length=600)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def score_matches_applicability(self) -> VisualCriterionScore:
        if self.applicability == "scored" and self.score is None:
            raise ValueError("applicable visual criteria require a score")
        if self.applicability == "not_applicable" and self.score is not None:
            raise ValueError("not-applicable visual criteria may not carry a score")
        return self


class CrossPartCoordinationScore(BaseModel):
    """The five visual cross-part criteria added by rubric-v2."""

    focal_clarity: VisualCriterionScore
    call_response_legibility: VisualCriterionScore
    cross_part_palette_agreement: VisualCriterionScore
    section_transition_agreement: VisualCriterionScore
    mutual_complement: VisualCriterionScore

    model_config = ConfigDict(extra="forbid", frozen=True)


class ShowVisionRubricResponse(BaseModel):
    """The four v1 categories plus cross-part readability criteria."""

    musicality_by_proxy: RubricCategoryScore
    coordination: RubricCategoryScore
    color_palette_coherence: RubricCategoryScore
    variety_and_pacing: RubricCategoryScore
    cross_part_coordination: CrossPartCoordinationScore

    model_config = ConfigDict(extra="forbid", frozen=True)


class ShowJudgePayload(BaseModel):
    """Complete deterministic claims supplied beside sampled visual evidence."""

    rubric_version: Literal["lighting-automv-v2"] = "lighting-automv-v2"
    capability: ShowCapability
    claims_json: str = Field(min_length=2)
    trace_summary_json: str = Field(min_length=2)

    model_config = ConfigDict(extra="forbid", frozen=True)


class ShowJudgedFrames(BaseModel):
    """One budgeted rubric-v2 visual response and its exact provider provenance."""

    rubric: ShowVisionRubricResponse
    rubric_version: Literal["lighting-automv-v2"] = "lighting-automv-v2"
    model: str
    provider_response_id: str
    estimate: VisionCostEstimate
    actual_cost_usd: float = Field(ge=0)
    usage: VisionTokenUsage
    logical_request_count: Literal[1] = 1
    provider_attempt_cap: Literal[1] = 1

    model_config = ConfigDict(extra="forbid", frozen=True)


def build_show_judge_payload(manifest_path: Path) -> ShowJudgePayload:
    """Build all current-plan claims before any provider boundary is reachable."""
    manifest = load_show_evaluation_manifest(manifest_path)
    trace = load_show_trace(manifest_path.parent / manifest.trace_path)
    return build_show_judge_payload_from_models(manifest, trace)


def build_show_judge_payload_from_models(
    manifest: ShowEvaluationManifest,
    trace: ShowTraceV2,
) -> ShowJudgePayload:
    """Serialize focal, exchange, palette, section, and emitted-trace claims."""
    macro = manifest.macro_plan
    if not macro.focal_arc or not macro.palette_arc or not macro.sections:
        raise ValueError("show judge claims require focal arc, palette stops, and sections")
    sections = []
    for section in macro.sections:
        if not section.focal_roles:
            raise ValueError(f"section {section.section.section_id!r} has no focal roles")
        sections.append(
            {
                "section": section.section.model_dump(mode="json"),
                "focal_roles": [item.model_dump(mode="json") for item in section.focal_roles],
                "call_response_pairs": [
                    item.model_dump(mode="json") for item in section.call_response_pairs
                ],
                "palette_stop_id": section.palette_role.stop_id,
            }
        )
    claims = {
        "focal_arc": [item.model_dump(mode="json") for item in macro.focal_arc],
        "palette_stops": [item.model_dump(mode="json") for item in macro.palette_arc],
        "sections": sections,
        "coordination_criteria": [item.model_dump(mode="json") for item in COORDINATION_CRITERIA],
    }
    by_backend: dict[str, dict[str, object]] = {}
    for backend in ("display", "moving_head"):
        rows = [entry for entry in trace.entries if entry.backend == backend]
        by_backend[backend] = {
            "entry_count": len(rows),
            "section_ids": sorted({entry.section_id for entry in rows}),
            "group_ids": sorted({entry.group_id for entry in rows}),
            "first_start_ms": min((entry.start_ms for entry in rows), default=None),
            "last_end_ms": max((entry.end_ms for entry in rows), default=None),
        }
    return ShowJudgePayload(
        capability=manifest.capability,
        claims_json=json.dumps(claims, sort_keys=True),
        trace_summary_json=json.dumps(by_backend, sort_keys=True),
    )


def not_applicable_cross_part(reason: str) -> CrossPartCoordinationScore:
    """Construct the only valid display-only cross-part result."""
    value = VisualCriterionScore(
        applicability="not_applicable",
        score=None,
        justification=reason,
    )
    return CrossPartCoordinationScore(
        focal_clarity=value,
        call_response_legibility=value,
        cross_part_palette_agreement=value,
        section_transition_agreement=value,
        mutual_complement=value,
    )


def validate_rubric_capability(
    response: ShowVisionRubricResponse,
    capability: ShowCapability,
) -> None:
    """Fail if display-only output is scored or a combined show is marked N/A."""
    values = list(response.cross_part_coordination.model_dump().values())
    applications = {value["applicability"] for value in values}
    expected = "scored" if capability.cross_part_applicable else "not_applicable"
    if applications != {expected}:
        raise ValueError(f"cross-part rubric applicability must be {expected!r}")


def get_show_vision_judge_spec(config: AgentConfig) -> AgentSpec:
    """Build the rubric-v2 role without changing the preserved rubric-v1 role."""
    return AgentSpec(
        name="show_vision_judge",
        prompt_pack="prompts/show_vision_judge",
        response_model=ShowVisionRubricResponse,
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


async def judge_show_frames(
    *,
    runner: AsyncAgentRunner,
    agent_config: AgentConfig,
    frames: list[FrameInput],
    payload: ShowJudgePayload,
    section_names: set[str],
    config: VisionJudgeConfig,
    ledger: VisionBudgetLedger,
    override_budget: bool = False,
) -> ShowJudgedFrames:
    """Run exactly one budgeted provider request after all deterministic claims exist."""
    if not frames:
        raise ValueError("at least one labeled frame is required")
    if not section_names or any(not name.strip() for name in section_names):
        raise ValueError("at least one real section name is required")
    validate_vision_request_payload(
        frames,
        context_text="\n".join(
            (payload.capability.model_dump_json(), payload.claims_json, payload.trace_summary_json)
        ),
    )
    estimate = estimate_vision_cost(frames, config)
    reservation = ledger.reserve(estimate, override=override_budget)
    result = await runner.run(
        get_show_vision_judge_spec(agent_config),
        variables={
            "capability": payload.capability.model_dump_json(),
            "claims_json": payload.claims_json,
            "trace_summary_json": payload.trace_summary_json,
            "frame_manifest": "\n".join(
                frame.label or f"Frame {frame.index}: {frame.timestamp_ms} ms" for frame in frames
            ),
        },
        input_image_urls=[_image_data_url(frame.path) for frame in frames],
    )
    usage = VisionTokenUsage(
        prompt_tokens=result.prompt_tokens,
        reasoning_tokens=result.reasoning_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.tokens_used,
    )
    actual_cost = (
        result.prompt_tokens * config.input_usd_per_million_tokens
        + (result.reasoning_tokens + result.completion_tokens)
        * config.output_usd_per_million_tokens
    ) / 1_000_000
    ledger.settle(
        reservation,
        spend=VisionAttemptSpend(
            success=result.success,
            usage=usage,
            actual_cost_usd=actual_cost,
            error_message=result.error_message,
        ),
    )
    if not result.success or not isinstance(result.data, ShowVisionRubricResponse):
        raise RuntimeError(result.error_message or "show vision judge returned no rubric-v2")
    validate_rubric_capability(result.data, payload.capability)
    validate_show_grounding(result.data, frames=frames, section_names=section_names)
    response_id = str(result.metadata.get("response_id") or "").strip()
    if not response_id:
        raise RuntimeError("show vision judge response is missing provider response identity")
    return ShowJudgedFrames(
        rubric=result.data,
        model=str(result.metadata.get("model") or agent_config.model),
        provider_response_id=response_id,
        estimate=estimate,
        actual_cost_usd=actual_cost,
        usage=usage,
    )


def _image_data_url(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def validate_show_grounding(
    rubric: ShowVisionRubricResponse,
    *,
    frames: list[FrameInput],
    section_names: set[str],
) -> None:
    allowed_frames = supplied_frame_indices(frames)
    normalized_sections = {name.casefold() for name in section_names}
    justifications = [
        getattr(rubric, name).justification
        for name in (
            "musicality_by_proxy",
            "coordination",
            "color_palette_coherence",
            "variety_and_pacing",
        )
    ]
    justifications.extend(
        value.justification
        for value in (
            rubric.cross_part_coordination.focal_clarity,
            rubric.cross_part_coordination.call_response_legibility,
            rubric.cross_part_coordination.cross_part_palette_agreement,
            rubric.cross_part_coordination.section_transition_agreement,
            rubric.cross_part_coordination.mutual_complement,
        )
        if value.applicability == "scored"
    )
    for justification in justifications:
        cited = {int(value) for value in re.findall(r"\bFrame\s+(\d+)\b", justification, re.I)}
        if cited - allowed_frames:
            raise RuntimeError("show rubric justification cites an unknown frame")
        lowered = justification.casefold()
        has_section = any(
            re.search(rf"(?<!\w){re.escape(name)}(?!\w)", lowered) for name in normalized_sections
        )
        if not cited and not has_section:
            raise RuntimeError("show rubric justification must cite a frame or real section")


__all__ = [
    "COORDINATION_CRITERIA",
    "SHOW_RUBRIC_VERSION",
    "CoordinationCriterion",
    "CrossPartCoordinationScore",
    "ShowJudgePayload",
    "ShowJudgedFrames",
    "ShowVisionRubricResponse",
    "VisualCriterionScore",
    "build_show_judge_payload",
    "build_show_judge_payload_from_models",
    "get_show_vision_judge_spec",
    "judge_show_frames",
    "not_applicable_cross_part",
    "validate_rubric_capability",
    "validate_show_grounding",
]
