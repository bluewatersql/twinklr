"""Template retrieval/ranking model contracts (V1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.feature_engineering.models.templates import TemplateKind


class TemplateRecommendation(BaseModel):
    """A ranked template candidate for retrieval and reuse."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str
    template_kind: TemplateKind
    retrieval_score: float = Field(ge=0.0, le=1.0)
    rank: int = Field(ge=1)

    support_count: int = Field(ge=0)
    support_ratio: float = Field(ge=0.0, le=1.0)
    cross_pack_stability: float = Field(ge=0.0, le=1.0)
    onset_sync_mean: float | None = Field(default=None, ge=0.0, le=1.0)

    transition_in_count: int = Field(ge=0)
    transition_out_count: int = Field(ge=0)
    transition_flow_count: int = Field(ge=0)
    transition_flow_norm: float = Field(ge=0.0, le=1.0)

    taxonomy_label_count: int = Field(ge=0)
    taxonomy_labels: tuple[str, ...] = ()
    role: str | None = None

    effect_family: str
    motion_class: str
    color_class: str
    energy_class: str
    continuity_class: str
    spatial_class: str


class TemplateRetrievalIndex(BaseModel):
    """Serialized ranked template index for baseline retrieval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    ranker_version: str
    total_templates: int = Field(ge=0)
    recommendations: tuple[TemplateRecommendation, ...] = ()
