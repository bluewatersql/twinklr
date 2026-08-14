"""Combined visual-rubric and deterministic-grid evaluation producer."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.config.models import AgentConfig
from twinklr.core.reporting.evaluation.calibration import OwnerCalibrationArtifact
from twinklr.core.reporting.evaluation.render import write_vision_evaluation_json
from twinklr.core.reporting.evaluation.sync_metrics import (
    DeterministicSyncMetrics,
    StructureSection,
    beat_grid_from_xsq,
    effect_intervals_from_xsq,
    score_sync_metrics,
)
from twinklr.core.reporting.evaluation.vision_frames import (
    FrameSampler,
    FrameSamplerConfig,
    compose_contact_sheets,
)
from twinklr.core.reporting.evaluation.vision_judge import (
    RUBRIC_VERSION,
    FrameInput,
    JudgedFrames,
    VisionBudgetLedger,
    VisionJudgeConfig,
    build_structure_text,
    judge_frames,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


class VisionEvaluationResult(BaseModel):
    """One committable score record for one current-schema rendered artifact."""

    schema_version: str = "1.0.0"
    created_at: str
    artifact_path: Path
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preview_path: Path
    preview_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sampled_frame_count: int = Field(ge=1)
    judge_image_count: int = Field(ge=1)
    sampling: FrameSamplerConfig
    visual: JudgedFrames
    deterministic: DeterministicSyncMetrics
    calibration_status: Literal["uncalibrated", "calibrated"] = "uncalibrated"
    calibration_record: Path | None = None
    calibration_record_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def calibrated_results_require_owner_record(self) -> VisionEvaluationResult:
        if self.calibration_status != "calibrated":
            return self
        if self.calibration_record is None:
            raise ValueError("calibrated results require the owner's calibration record")
        if not self.calibration_record.is_file():
            raise ValueError(f"owner calibration record does not exist: {self.calibration_record}")
        if self.calibration_record_sha256 is None:
            raise ValueError("calibrated results require a frozen calibration record SHA-256")
        record_hash = _sha256(self.calibration_record)
        if record_hash != self.calibration_record_sha256:
            raise ValueError("owner calibration record SHA-256 does not match the frozen record")
        record = OwnerCalibrationArtifact.model_validate_json(
            self.calibration_record.read_text(encoding="utf-8")
        )
        if record.decision != "accepted":
            raise ValueError("owner calibration record decision is not accepted")
        if record.rubric_version != self.visual.rubric_version:
            raise ValueError("owner calibration record rubric version does not match")
        if record.sampling != self.sampling:
            raise ValueError("owner calibration record sampling configuration does not match")
        return self


async def evaluate_preview(
    *,
    runner: AsyncAgentRunner,
    agent_config: AgentConfig,
    preview_path: Path,
    artifact_path: Path,
    plan: ChoreographyPlan,
    beat_grid: BeatGrid,
    output_dir: Path,
    judge_config: VisionJudgeConfig | None = None,
    sampling_config: FrameSamplerConfig | None = None,
    ledger: VisionBudgetLedger | None = None,
    ffmpeg_path: Path | None = None,
    override_budget: bool = False,
) -> VisionEvaluationResult:
    """Produce one result; video/API work remains an explicit local invocation."""
    judge_config = judge_config or VisionJudgeConfig()
    sampling_config = sampling_config or FrameSamplerConfig()

    # Everything knowable without the paid request is validated and captured first.
    preview_sha256 = _sha256(preview_path)
    artifact_sha256 = _sha256(artifact_path)
    delivered_grid = beat_grid_from_xsq(artifact_path)
    _assert_same_grid(beat_grid, delivered_grid)
    timestamped, metric_sections = plan_structure(plan, delivered_grid)
    deterministic = score_sync_metrics(
        beat_grid=delivered_grid,
        effects=effect_intervals_from_xsq(artifact_path),
        sections=metric_sections,
    )
    plan_sha256 = _identity_sha256(plan.model_dump(mode="json"))
    evaluation_config_sha256 = _identity_sha256(
        {
            "agent": agent_config.model_dump(mode="json"),
            "judge": judge_config.model_dump(mode="json"),
            "sampling": sampling_config.model_dump(mode="json"),
            "rubric_version": RUBRIC_VERSION,
        }
    )

    sampled = FrameSampler(config=sampling_config, ffmpeg_path=ffmpeg_path).sample(
        preview_path, output_dir / "frames"
    )
    if sampling_config.use_contact_sheets:
        sheets = compose_contact_sheets(
            [frame.path for frame in sampled],
            output_dir=output_dir / "contact_sheets",
            config=sampling_config,
        )
        source_by_index = {frame.index: frame for frame in sampled}
        judge_inputs = []
        for sheet in sheets:
            first = source_by_index[sheet.frame_indices[0]]
            last = source_by_index[sheet.frame_indices[-1]]
            judge_inputs.append(
                FrameInput(
                    index=sheet.index,
                    timestamp_ms=first.timestamp_ms,
                    path=sheet.path,
                    label=(
                        f"Contact sheet {sheet.index}: Frames {first.index}–{last.index}; "
                        f"{_timestamp(first.timestamp_ms)}–{_timestamp(last.timestamp_ms)}"
                    ),
                )
            )
    else:
        judge_inputs = [
            FrameInput(
                index=frame.index,
                timestamp_ms=frame.timestamp_ms,
                path=frame.path,
                label=frame.label,
            )
            for frame in sampled
        ]

    structure_text = build_structure_text(
        sections=timestamped,
        tempo_bpm=delivered_grid.tempo_bpm,
        beats_per_bar=delivered_grid.beats_per_bar,
        beat_count=len(delivered_grid.beat_boundaries),
        downbeat_count=len(delivered_grid.bar_boundaries),
    )
    run_ledger = ledger or VisionBudgetLedger(config=judge_config)
    visual = await judge_frames(
        runner=runner,
        agent_config=agent_config,
        frames=judge_inputs,
        structure_text=structure_text,
        section_names={str(section["section_name"]) for section in timestamped},
        config=judge_config,
        ledger=run_ledger,
        override_budget=override_budget,
    )
    result = VisionEvaluationResult(
        created_at=datetime.now(UTC).isoformat(),
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha256,
        preview_path=preview_path,
        preview_sha256=preview_sha256,
        plan_sha256=plan_sha256,
        evaluation_config_sha256=evaluation_config_sha256,
        sampled_frame_count=len(sampled),
        judge_image_count=len(judge_inputs),
        sampling=sampling_config,
        visual=visual,
        deterministic=deterministic,
    )
    write_vision_evaluation_json(result, output_dir / "vision_evaluation.json")
    return result


def plan_structure(
    plan: ChoreographyPlan, beat_grid: BeatGrid
) -> tuple[list[dict[str, str | int]], list[StructureSection]]:
    """Adapt today's PlanSection shape into timestamped judge and metric inputs."""
    judge_sections: list[dict[str, str | int]] = []
    metric_sections: list[StructureSection] = []
    for section in plan.sections:
        start_ms = round(beat_grid.get_bar_start_ms(section.start_bar - 1))
        end_ms = round(beat_grid.get_bar_start_ms(section.end_bar))
        judge_sections.append(
            {
                "section_name": section.section_name,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "intent": _section_intent(section),
            }
        )
        metric_sections.append(
            StructureSection(
                name=section.section_name,
                start_ms=start_ms,
                end_ms=end_ms,
                bars=section.end_bar - section.start_bar + 1,
            )
        )
    return judge_sections, metric_sections


def _section_intent(section: PlanSection) -> str:
    template = section.template_id or ", ".join(
        segment.template_id for segment in section.segments or []
    )
    color = section.color_intent.model_dump(mode="json")
    return (
        f"role={section.section_role or 'unspecified'}; energy={section.energy_level}; "
        f"intensity={section.intensity.value}; color={color}; templates={template}; "
        f"shutter_events={len(section.shutter_events)}; gobo_events={len(section.gobo_events)}; "
        f"moment_cues={','.join(cue.cue_id for cue in section.moment_cues) or 'none'}"
    )


def _sha256(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Evaluation input file not found: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identity_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _assert_same_grid(expected: BeatGrid, delivered: BeatGrid) -> None:
    if expected.beats_per_bar != delivered.beats_per_bar:
        raise ValueError("Supplied BeatGrid does not match the rendered XSQ beats-per-bar")
    for name, left, right in (
        ("beat", expected.beat_boundaries, delivered.beat_boundaries),
        ("bar", expected.bar_boundaries, delivered.bar_boundaries),
    ):
        if len(left) != len(right) or any(
            abs(expected_ms - delivered_ms) > 1.0
            for expected_ms, delivered_ms in zip(left, right, strict=True)
        ):
            raise ValueError(f"Supplied BeatGrid does not match rendered XSQ {name} markers")


def _timestamp(timestamp_ms: int) -> str:
    minutes, remainder = divmod(timestamp_ms, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
