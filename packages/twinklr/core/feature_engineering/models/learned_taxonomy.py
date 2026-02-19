"""Learned taxonomy model contracts (V2.2 baseline)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LearnedTaxonomyModel(BaseModel):
    """Serialized lightweight learned taxonomy model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    model_version: str
    label_names: tuple[str, ...] = ()
    vocabulary: tuple[str, ...] = ()
    label_priors: dict[str, float] = Field(default_factory=dict)
    token_likelihoods: dict[str, dict[str, float]] = Field(default_factory=dict)


class LearnedTaxonomyEvalReport(BaseModel):
    """Evaluation summary for learned taxonomy training."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    model_version: str
    train_samples: int = Field(ge=0)
    eval_samples: int = Field(ge=0)
    precision_micro: float = Field(ge=0.0, le=1.0)
    recall_micro: float = Field(ge=0.0, le=1.0)
    f1_micro: float = Field(ge=0.0, le=1.0)
    prediction_coverage: float = Field(ge=0.0, le=1.0)
    min_recall_for_promotion: float = Field(ge=0.0, le=1.0)
    min_f1_for_promotion: float = Field(ge=0.0, le=1.0)
    promotion_passed: bool = False
    notes: tuple[str, ...] = ()
