"""Quality gate contracts (V1.9)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class QualityCheckResult(BaseModel):
    """Single quality check output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    passed: bool
    value: float | int | str | None = None
    threshold: float | int | str | None = None
    message: str


class QualityReport(BaseModel):
    """Aggregated deterministic quality report."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    report_version: str
    passed: bool

    checks: tuple[QualityCheckResult, ...] = ()
    metadata: dict[str, str] = Field(default_factory=dict)

