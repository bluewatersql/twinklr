"""Temporal (ordered) motif mining model contracts — Spec 03."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.feature_engineering.models.motifs import MotifOccurrence


class TemporalMotifStep(BaseModel):
    """One step in a temporal motif sequence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    position: int = Field(ge=0)
    effect_family: str
    energy_class: str
    motion_class: str
    gap_from_previous_ms: int | None = None


class TemporalMotif(BaseModel):
    """Ordered template sequence pattern."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    motif_id: str
    temporal_signature: str
    pattern_name: str
    sequence_length: int = Field(ge=2, le=5)
    steps: tuple[TemporalMotifStep, ...]
    support_count: int = Field(ge=0)
    distinct_pack_count: int = Field(ge=0)
    distinct_sequence_count: int = Field(ge=0)
    occurrences: tuple[MotifOccurrence, ...] = ()


class TemporalMotifCatalog(BaseModel):
    """Catalog of discovered temporal motifs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "v1.0.0"
    miner_version: str = "temporal_motif_v1"
    total_sequences: int = Field(ge=0)
    total_temporal_motifs: int = Field(ge=0)
    motifs: tuple[TemporalMotif, ...] = ()
