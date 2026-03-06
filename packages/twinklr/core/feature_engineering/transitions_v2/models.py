"""Pydantic models for probabilistic transition modeling."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TransitionPrediction(BaseModel):
    """A predicted next-template with probability and confidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str
    probability: float = Field(ge=0.0, le=1.0)
    confidence_interval: tuple[float, float]
    duration_bucket: str | None = None
    rank: int = Field(ge=1)


class TransitionSuggestion(BaseModel):
    """Planner-friendly transition suggestion with source attribution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str
    probability: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    source: str  # "markov" or "fallback_graph"
    rank: int = Field(ge=1)


class TransitionEvalReport(BaseModel):
    """Quality metrics comparing Markov model against transition graph."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1.0.0"
    top_k_recall: float = Field(ge=0.0, le=1.0)
    hit_rate: float = Field(ge=0.0, le=1.0)
    coverage: float = Field(ge=0.0, le=1.0)
    total_templates: int = Field(ge=0)
    templates_with_predictions: int = Field(ge=0)
    held_out_count: int = Field(ge=0)
