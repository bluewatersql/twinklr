"""Motif mining model contracts (V2.0)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MotifOccurrence(BaseModel):
    """Single motif occurrence instance in one sequence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    package_id: str
    sequence_file_id: str
    start_bar_index: int = Field(ge=0)
    end_bar_index: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    phrase_count: int = Field(ge=1)


class MinedMotif(BaseModel):
    """Canonical mined motif with support and linkage metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    motif_id: str
    motif_signature: str
    bar_span: int = Field(ge=1, le=8)

    support_count: int = Field(ge=0)
    distinct_pack_count: int = Field(ge=0)
    distinct_sequence_count: int = Field(ge=0)

    template_ids: tuple[str, ...] = ()
    taxonomy_labels: tuple[str, ...] = ()
    occurrences: tuple[MotifOccurrence, ...] = ()


class MotifCatalog(BaseModel):
    """Serialized motif catalog artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    miner_version: str
    total_sequences: int = Field(ge=0)
    total_motifs: int = Field(ge=0)
    min_support_count: int = Field(ge=1)
    min_distinct_pack_count: int = Field(ge=1)
    min_distinct_sequence_count: int = Field(ge=1)

    motifs: tuple[MinedMotif, ...] = ()
