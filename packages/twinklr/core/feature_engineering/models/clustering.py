"""Template clustering model contracts (V2.1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.feature_engineering.models.templates import TemplateKind


class ClusterMember(BaseModel):
    """A member template inside a cluster candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str
    template_kind: TemplateKind
    effect_family: str
    role: str | None = None


class TemplateClusterCandidate(BaseModel):
    """Reusable cluster candidate for human review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cluster_id: str
    cluster_size: int = Field(ge=2)
    mean_similarity: float = Field(ge=0.0, le=1.0)
    dominant_effect_family: str
    member_template_ids: tuple[str, ...] = ()
    members: tuple[ClusterMember, ...] = ()


class ClusterReviewQueueRow(BaseModel):
    """Review action item for one candidate cluster."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cluster_id: str
    priority: int = Field(ge=1, le=3)
    reason_keys: tuple[str, ...] = ()
    suggestion: str


class TemplateClusterCatalog(BaseModel):
    """Serialized template-clustering output and review queue."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    clusterer_version: str
    min_cluster_size: int = Field(ge=2)
    similarity_threshold: float = Field(ge=0.0, le=1.0)

    total_templates: int = Field(ge=0)
    total_clusters: int = Field(ge=0)
    clusters: tuple[TemplateClusterCandidate, ...] = ()
    review_queue: tuple[ClusterReviewQueueRow, ...] = ()
