"""Layering feature contracts (V1.7)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LayeringFeatureRow(BaseModel):
    """Sequence-level layering feature summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    package_id: str
    sequence_file_id: str

    phrase_count: int = Field(ge=0)
    max_concurrent_layers: int = Field(ge=0)
    mean_concurrent_layers: float = Field(ge=0.0)
    hierarchy_transitions: int = Field(ge=0)

    overlap_pairs: int = Field(ge=0)
    same_target_overlap_pairs: int = Field(ge=0)
    collision_score: float = Field(ge=0.0, le=1.0)

