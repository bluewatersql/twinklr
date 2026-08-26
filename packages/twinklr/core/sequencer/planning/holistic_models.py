"""Cycle-free public models for holistic group-plan evaluation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.agents.issues import IssueSeverity, TargetedAction
from twinklr.core.agents.shared.judge.models import VerdictStatus


class CrossSectionIssue(BaseModel):
    """One issue spanning multiple sections."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issue_id: str
    severity: IssueSeverity
    affected_sections: list[str] = Field(min_length=1)
    description: str
    recommendation: str
    targeted_actions: list[TargetedAction]

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized.setdefault("targeted_actions", [])
        return normalized


class HolisticEvaluation(BaseModel):
    """Quality assessment of a complete group plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: VerdictStatus
    score: float = Field(ge=0.0, le=10.0)
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    strengths: list[str]
    cross_section_issues: list[CrossSectionIssue]

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized.setdefault("strengths", [])
        normalized.setdefault("cross_section_issues", [])
        return normalized

    @property
    def is_approved(self) -> bool:
        return self.status == VerdictStatus.APPROVE


__all__ = ["CrossSectionIssue", "HolisticEvaluation"]
