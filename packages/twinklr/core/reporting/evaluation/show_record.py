"""Strict offline and completed record contracts for show-level evaluation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.reporting.evaluation.show_judge import (
    ShowVisionRubricResponse,
    validate_rubric_capability,
)
from twinklr.core.reporting.evaluation.show_manifest import (
    SHA256_PATTERN,
    ShowCapability,
    file_sha256,
    load_show_evaluation_manifest,
    load_show_trace,
)
from twinklr.core.reporting.evaluation.show_metrics import ShowMetrics, score_show_metrics
from twinklr.core.reporting.evaluation.vision_frames import FrameSamplerConfig


class ShowDeterministicReport(BaseModel):
    """Commit-safe output of the zero-external deterministic tier."""

    schema_version: Literal["twinklr-show-deterministic-report.v1"] = (
        "twinklr-show-deterministic-report.v1"
    )
    manifest_path: Path
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    trace_sha256: str = Field(pattern=SHA256_PATTERN)
    capability: ShowCapability
    metrics: ShowMetrics
    recipe_ids: list[str]
    moving_head_template_ids: list[str]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def identifiers_are_canonical(self) -> ShowDeterministicReport:
        if self.recipe_ids != sorted(set(self.recipe_ids)):
            raise ValueError("recipe_ids must be sorted and unique")
        if self.moving_head_template_ids != sorted(set(self.moving_head_template_ids)):
            raise ValueError("moving_head_template_ids must be sorted and unique")
        return self


class SampledFrameProvenance(BaseModel):
    """One exact image supplied to the visual evaluator."""

    index: int = Field(ge=1)
    timestamp_ms: int = Field(ge=0)
    path: Path
    sha256: str = Field(pattern=SHA256_PATTERN)

    model_config = ConfigDict(extra="forbid", frozen=True)


class ShowVisualEvidence(BaseModel):
    """Provider and sampling evidence from an explicitly completed local run."""

    rubric_version: Literal["lighting-automv-v2"] = "lighting-automv-v2"
    rubric: ShowVisionRubricResponse
    model: str = Field(min_length=1)
    provider_response_id: str = Field(min_length=1)
    preview_path: Path
    preview_sha256: str = Field(pattern=SHA256_PATTERN)
    sampling: FrameSamplerConfig
    sampled_frames: list[SampledFrameProvenance] = Field(min_length=1)
    rendered_prompt_path: Path
    prompt_sha256: str = Field(pattern=SHA256_PATTERN)
    actual_cost_usd: float = Field(ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)


class HumanCategoryScores(BaseModel):
    """The same five top-level categories a human can apply to the same frames."""

    musicality_by_proxy: float = Field(ge=0, le=10)
    coordination: float = Field(ge=0, le=10)
    color_palette_coherence: float = Field(ge=0, le=10)
    variety_and_pacing: float = Field(ge=0, le=10)
    cross_part_coordination: float | None = Field(default=None, ge=0, le=10)

    model_config = ConfigDict(extra="forbid", frozen=True)


class HumanShowJudgment(BaseModel):
    """Human-authored judgment captured beside the exact visual evidence."""

    reviewer: str = Field(min_length=1)
    recorded_at: datetime
    scores: HumanCategoryScores
    free_text: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class CategoryAgreement(BaseModel):
    """Human minus visual-evaluator score, preserving direction and magnitude."""

    musicality_by_proxy: float
    coordination: float
    color_palette_coherence: float
    variety_and_pacing: float
    cross_part_coordination: float | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class ShowEvaluationRecord(BaseModel):
    """A completed record; offline reports alone cannot validate as this type."""

    schema_version: Literal["twinklr-show-evaluation-record.v2"] = (
        "twinklr-show-evaluation-record.v2"
    )
    status: Literal["completed"] = "completed"
    deterministic: ShowDeterministicReport
    visual: ShowVisualEvidence
    human: HumanShowJudgment
    agreement: CategoryAgreement

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def agreement_is_derived_not_authored(self) -> ShowEvaluationRecord:
        validate_rubric_capability(self.visual.rubric, self.deterministic.capability)
        expected = compute_agreement(self.visual.rubric, self.human.scores)
        for name, expected_value in expected.model_dump().items():
            actual = getattr(self.agreement, name)
            if expected_value is None or actual is None:
                if expected_value != actual:
                    raise ValueError("agreement N/A state does not match visual and human scores")
            elif abs(expected_value - actual) > 1e-9:
                raise ValueError(f"agreement field {name!r} was tampered or miscomputed")
        if self.deterministic.capability.cross_part_applicable:
            if self.human.scores.cross_part_coordination is None:
                raise ValueError("combined completed records require a human cross-part score")
        elif self.human.scores.cross_part_coordination is not None:
            raise ValueError("single-part completed records require cross-part N/A")
        return self


def build_deterministic_report(manifest_path: Path) -> ShowDeterministicReport:
    """Compute and package one deterministic report without external processes."""
    manifest, metrics = score_show_metrics(manifest_path)
    trace = load_show_trace(manifest_path.parent / manifest.trace_path)
    return ShowDeterministicReport(
        manifest_path=manifest_path,
        manifest_sha256=file_sha256(manifest_path),
        artifact_sha256=manifest.xsq_sha256,
        trace_sha256=manifest.trace_sha256,
        capability=manifest.capability,
        metrics=metrics,
        recipe_ids=sorted(
            {entry.template_id for entry in trace.entries if entry.backend == "display"}
        ),
        moving_head_template_ids=sorted(
            {entry.template_id for entry in trace.entries if entry.backend == "moving_head"}
        ),
    )


def write_deterministic_report(report: ShowDeterministicReport, path: Path) -> Path:
    """Atomically persist the offline report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def load_show_evaluation_record(path: Path) -> ShowEvaluationRecord:
    """Load a completed record only after rebuilding every file-backed claim."""
    record = cast(
        "ShowEvaluationRecord",
        ShowEvaluationRecord.model_validate_json(path.read_text(encoding="utf-8")),
    )
    manifest_path = _resolve_provenance_path(path, record.deterministic.manifest_path)
    preview_path = _resolve_provenance_path(path, record.visual.preview_path)
    prompt_path = _resolve_provenance_path(path, record.visual.rendered_prompt_path)
    frame_paths = [
        _resolve_provenance_path(path, frame.path) for frame in record.visual.sampled_frames
    ]
    _require_sha256(preview_path, record.visual.preview_sha256, "preview")
    _require_sha256(prompt_path, record.visual.prompt_sha256, "rendered prompt")
    for provenance, frame_path in zip(record.visual.sampled_frames, frame_paths, strict=True):
        _require_sha256(frame_path, provenance.sha256, f"sampled frame {provenance.index}")
    _require_sha256(
        manifest_path,
        record.deterministic.manifest_sha256,
        "show evaluation manifest",
    )
    load_show_evaluation_manifest(manifest_path)
    rebuilt = build_deterministic_report(manifest_path).model_copy(
        update={"manifest_path": record.deterministic.manifest_path}
    )
    if rebuilt != record.deterministic:
        raise ValueError("stored deterministic claims do not match rebuilt manifest evidence")
    return record


def _resolve_provenance_path(record_path: Path, provenance_path: Path) -> Path:
    if provenance_path.is_absolute():
        raise ValueError("completed-record provenance paths must be relative")
    record_path = record_path.resolve()
    allowed_root = _repository_or_record_root(record_path)
    candidates = {
        (record_path.parent / provenance_path).resolve(),
        (allowed_root / provenance_path).resolve(),
    }
    if any(not candidate.is_relative_to(allowed_root) for candidate in candidates):
        raise ValueError("completed-record provenance path escapes its repository")
    existing = sorted(candidate for candidate in candidates if candidate.is_file())
    if len(existing) > 1:
        raise ValueError("completed-record provenance path is ambiguous")
    if not existing:
        raise FileNotFoundError(sorted(candidates)[0])
    return existing[0]


def _repository_or_record_root(record_path: Path) -> Path:
    for candidate in (record_path.parent, *record_path.parents):
        if (candidate / ".git").exists():
            return candidate
    return record_path.parent


def _require_sha256(path: Path, expected: str, label: str) -> None:
    if file_sha256(path) != expected:
        raise ValueError(f"{label} SHA-256 does not match completed record")


def compute_agreement(
    rubric: ShowVisionRubricResponse,
    human: HumanCategoryScores,
) -> CategoryAgreement:
    """Compute the accumulable one-record calibration line."""
    cross_values = [
        value.score
        for value in (
            rubric.cross_part_coordination.focal_clarity,
            rubric.cross_part_coordination.call_response_legibility,
            rubric.cross_part_coordination.cross_part_palette_agreement,
            rubric.cross_part_coordination.section_transition_agreement,
            rubric.cross_part_coordination.mutual_complement,
        )
        if value.score is not None
    ]
    visual_cross = sum(cross_values) / len(cross_values) if cross_values else None
    return CategoryAgreement(
        musicality_by_proxy=human.musicality_by_proxy - rubric.musicality_by_proxy.score,
        coordination=human.coordination - rubric.coordination.score,
        color_palette_coherence=human.color_palette_coherence
        - rubric.color_palette_coherence.score,
        variety_and_pacing=human.variety_and_pacing - rubric.variety_and_pacing.score,
        cross_part_coordination=(
            human.cross_part_coordination - visual_cross
            if human.cross_part_coordination is not None and visual_cross is not None
            else None
        ),
    )


__all__ = [
    "CategoryAgreement",
    "HumanCategoryScores",
    "HumanShowJudgment",
    "SampledFrameProvenance",
    "ShowDeterministicReport",
    "ShowEvaluationRecord",
    "ShowVisualEvidence",
    "build_deterministic_report",
    "compute_agreement",
    "load_show_evaluation_record",
    "write_deterministic_report",
]
