"""Transition modeling contracts (V1.6)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TransitionType(str, Enum):
    """Deterministic transition class labels."""

    HARD_CUT = "hard_cut"
    CROSSFADE = "crossfade"
    TIMED_GAP = "timed_gap"
    OVERLAP_BLEND = "overlap_blend"


class TransitionRecord(BaseModel):
    """A transition edge observed between adjacent templates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence_file_id: str
    package_id: str
    from_phrase_id: str
    to_phrase_id: str
    from_template_id: str
    to_template_id: str
    from_end_ms: int = Field(ge=0)
    to_start_ms: int = Field(ge=0)
    gap_ms: int
    transition_type: TransitionType


class TransitionEdge(BaseModel):
    """Aggregated directed edge between template nodes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_template_id: str
    target_template_id: str
    edge_count: int = Field(ge=1)
    confidence: float = Field(ge=0.0, le=1.0)
    mean_gap_ms: float
    transition_type_distribution: dict[TransitionType, int]


class TransitionAnomaly(BaseModel):
    """Anomaly emitted during transition graph checks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    severity: str
    message: str


class TransitionGraph(BaseModel):
    """Serialized transition graph artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    graph_version: str

    total_transitions: int = Field(ge=0)
    total_nodes: int = Field(ge=0)
    total_edges: int = Field(ge=0)

    edges: tuple[TransitionEdge, ...] = ()
    transitions: tuple[TransitionRecord, ...] = ()
    anomalies: tuple[TransitionAnomaly, ...] = ()
