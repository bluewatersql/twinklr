"""ANN retrieval index model contracts (V2.3 baseline)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.feature_engineering.models.templates import TemplateKind


class AnnIndexEntry(BaseModel):
    """Single template vector entry in ANN index."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str
    template_kind: TemplateKind
    effect_family: str
    role: str | None = None
    vector: tuple[float, ...] = ()


class AnnRetrievalIndex(BaseModel):
    """Serialized ANN retrieval index artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    index_version: str
    vector_dim: int = Field(ge=1)
    total_entries: int = Field(ge=0)
    entries: tuple[AnnIndexEntry, ...] = ()


class AnnRetrievalSliceMetric(BaseModel):
    """Per-slice retrieval quality metric."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slice_key: str
    query_count: int = Field(ge=0)
    same_group_recall_at_5: float = Field(ge=0.0, le=1.0)


class AnnRetrievalCheck(BaseModel):
    """Gate check result for retrieval evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    passed: bool
    value: float
    threshold: float


class AnnRetrievalEvalReport(BaseModel):
    """Evaluation summary for ANN retrieval index quality."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    index_version: str
    total_queries: int = Field(ge=0)
    avg_top1_similarity: float = Field(ge=0.0, le=1.0)
    same_effect_family_recall_at_5: float = Field(ge=0.0, le=1.0)
    avg_query_latency_ms: float = Field(ge=0.0)
    effect_family_slices: tuple[AnnRetrievalSliceMetric, ...] = ()
    role_slices: tuple[AnnRetrievalSliceMetric, ...] = ()
    min_same_effect_family_recall_at_5: float = Field(ge=0.0, le=1.0)
    max_avg_query_latency_ms: float = Field(ge=0.0)
    gates_passed: bool = False
    checks: tuple[AnnRetrievalCheck, ...] = ()
