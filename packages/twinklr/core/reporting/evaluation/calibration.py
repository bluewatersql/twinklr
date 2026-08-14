"""Owner-blind calibration calculations for the visual rubric."""

from __future__ import annotations

from datetime import datetime
from itertools import permutations
import math
import random
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.reporting.evaluation.vision_frames import FrameSamplerConfig
from twinklr.core.reporting.evaluation.vision_judge import VisionRubricResponse

CATEGORY_FIELDS = (
    "musicality_by_proxy",
    "coordination",
    "color_palette_coherence",
    "variety_and_pacing",
)


class HumanCategoryScores(BaseModel):
    """Owner scores recorded before the harness result is revealed."""

    musicality_by_proxy: float = Field(ge=0, le=10)
    coordination: float = Field(ge=0, le=10)
    color_palette_coherence: float = Field(ge=0, le=10)
    variety_and_pacing: float = Field(ge=0, le=10)

    model_config = ConfigDict(extra="forbid", frozen=True)


class CalibrationSample(BaseModel):
    """One blinded owner observation joined to one harness output."""

    sequence_id: str = Field(min_length=1)
    owner_rank: int = Field(ge=1)
    owner_scores: HumanCategoryScores
    vision_scores: VisionRubricResponse

    model_config = ConfigDict(extra="forbid", frozen=True)


class CalibrationReport(BaseModel):
    """Agreement evidence awaiting the owner's explicit acceptance decision."""

    sample_count: int = Field(ge=5)
    spearman_rank_correlation: float = Field(ge=-1, le=1)
    permutation_p_value: float = Field(ge=0, le=1)
    permutation_count: int = Field(gt=0)
    permutation_method: Literal["exact", "monte_carlo"]
    category_mean_absolute_error: dict[str, float]
    owner_decision: Literal["pending"] = "pending"

    model_config = ConfigDict(extra="forbid", frozen=True)


class CalibrationBatch(BaseModel):
    """At least five uniquely ranked samples, as required by the owner protocol."""

    samples: list[CalibrationSample] = Field(min_length=5)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def unique_samples_and_ranks(self) -> CalibrationBatch:
        identifiers = [sample.sequence_id for sample in self.samples]
        ranks = [sample.owner_rank for sample in self.samples]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Calibration sequence_id values must be unique")
        if sorted(ranks) != list(range(1, len(self.samples) + 1)):
            raise ValueError("owner_rank must contain each rank from 1 through N exactly once")
        return self


def calculate_calibration(batch: CalibrationBatch) -> CalibrationReport:
    """Calculate agreement without changing any stored human observation."""
    vision_averages = [
        sum(getattr(sample.vision_scores, field).score for field in CATEGORY_FIELDS)
        / len(CATEGORY_FIELDS)
        for sample in batch.samples
    ]
    vision_ranks = _descending_average_ranks(vision_averages)
    owner_ranks = [float(sample.owner_rank) for sample in batch.samples]
    spearman = _spearman(owner_ranks, vision_ranks)
    p_value, permutation_count, method = _permutation_test(owner_ranks, vision_ranks, spearman)
    errors = {
        field: sum(
            abs(getattr(sample.owner_scores, field) - getattr(sample.vision_scores, field).score)
            for sample in batch.samples
        )
        / len(batch.samples)
        for field in CATEGORY_FIELDS
    }
    return CalibrationReport(
        sample_count=len(batch.samples),
        spearman_rank_correlation=spearman,
        permutation_p_value=p_value,
        permutation_count=permutation_count,
        permutation_method=method,
        category_mean_absolute_error=errors,
    )


def _descending_average_ranks(values: list[float]) -> list[float]:
    """Rank high scores first, assigning tied observations their average rank."""
    order = sorted(range(len(values)), key=lambda index: -values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average_rank = ((start + 1) + end) / 2
        for index in order[start:end]:
            ranks[index] = average_rank
        start = end
    return ranks


def _spearman(first: list[float], second: list[float]) -> float:
    """Pearson correlation of ranks, which remains valid when ranks contain ties."""
    first_mean = sum(first) / len(first)
    second_mean = sum(second) / len(second)
    numerator = sum(
        (left - first_mean) * (right - second_mean)
        for left, right in zip(first, second, strict=True)
    )
    first_scale = math.sqrt(sum((value - first_mean) ** 2 for value in first))
    second_scale = math.sqrt(sum((value - second_mean) ** 2 for value in second))
    if first_scale == 0 or second_scale == 0:
        return 0.0
    return numerator / (first_scale * second_scale)


def _permutation_test(
    owner_ranks: list[float], vision_ranks: list[float], observed: float
) -> tuple[float, int, Literal["exact", "monte_carlo"]]:
    """Two-sided deterministic permutation test for the observed rank agreement."""
    threshold = abs(observed) - 1e-12
    if len(owner_ranks) <= 8:
        total = math.factorial(len(owner_ranks))
        extreme = sum(
            abs(_spearman(list(permutation), vision_ranks)) >= threshold
            for permutation in permutations(owner_ranks)
        )
        return extreme / total, total, "exact"

    sample_count = 10_000
    generator = random.Random(0)
    extreme = 0
    for _ in range(sample_count):
        permutation = owner_ranks.copy()
        generator.shuffle(permutation)
        extreme += abs(_spearman(permutation, vision_ranks)) >= threshold
    return (extreme + 1) / (sample_count + 1), sample_count, "monte_carlo"


class CalibrationEvidenceSample(CalibrationSample):
    """One calibration sample with immutable artifact and spend identities."""

    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preview_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_cost_usd: float = Field(ge=0)


class OwnerCalibrationArtifact(BaseModel):
    """Frozen owner decision that can authorize calibrated result status."""

    schema_version: str = "1.0.0"
    recorded_at: datetime
    owner_identity: str = Field(min_length=1)
    decision: Literal["accepted", "rejected"]
    rubric_version: str = Field(min_length=1)
    sampling: FrameSamplerConfig
    samples: list[CalibrationEvidenceSample] = Field(min_length=5)
    report: CalibrationReport

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_frozen_evidence(self) -> OwnerCalibrationArtifact:
        artifact_hashes = [sample.artifact_sha256 for sample in self.samples]
        if len(set(artifact_hashes)) != len(artifact_hashes):
            raise ValueError("calibration artifact_sha256 values must be unique")
        preview_hashes = [sample.preview_sha256 for sample in self.samples]
        if len(set(preview_hashes)) != len(preview_hashes):
            raise ValueError("calibration preview_sha256 values must be unique")
        batch = CalibrationBatch(samples=list(self.samples))
        expected = calculate_calibration(batch)
        if self.report != expected:
            raise ValueError("calibration report does not match the frozen N>=5 evidence")
        return self
