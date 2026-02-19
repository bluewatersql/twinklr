"""Corpus unification output models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CorpusQualityReport(BaseModel):
    """Quality summary for a unified corpus build."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_parse_success_ratio: float
    parse_success_ratio: float
    parse_total: int
    parse_success: int
    meets_minimum: bool


class CorpusRowCounts(BaseModel):
    """Row counts per output table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence_index: int
    events_base: int
    events_enriched: int
    effectdb_params: int
    lineage_index: int


class CorpusManifest(BaseModel):
    """Top-level corpus manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    corpus_id: str
    created_at: str
    schema_version: str
    manifest_schema_version: str
    write_extent_mb: int
    format: str
    source_profile_count: int
    row_counts: CorpusRowCounts
    quality: CorpusQualityReport
    source_profile_paths: tuple[str, ...]
