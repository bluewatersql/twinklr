"""Pydantic models for sequence embeddings and similarity artifacts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SequenceFeatureVector(BaseModel):
    """Fixed-dimensional feature vector extracted from per-sequence FE output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1.0.0"
    package_id: str
    sequence_file_id: str
    feature_names: tuple[str, ...]
    values: tuple[float, ...]
    dimensionality: int


class SequenceEmbedding(BaseModel):
    """Dense embedding produced from a sequence feature vector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    package_id: str
    sequence_file_id: str
    embedding: tuple[float, ...]
    dimensionality: int
    strategy: str


class SimilarityLink(BaseModel):
    """A similarity relationship between two sequences."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_package_id: str
    source_sequence_id: str
    target_package_id: str
    target_sequence_id: str
    similarity: float = Field(ge=0.0, le=1.0)
    rank: int = Field(ge=1)


class RetrievalQualityReport(BaseModel):
    """Comparative quality metrics for embedding-based retrieval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1.0.0"
    precision_at_5: float = Field(ge=0.0, le=1.0)
    recall_at_5: float = Field(ge=0.0, le=1.0)
    ndcg_at_5: float = Field(ge=0.0, le=1.0)
    mean_query_latency_ms: float = Field(ge=0.0)
    total_queries: int = Field(ge=0)
    passes_quality_gate: bool = False
