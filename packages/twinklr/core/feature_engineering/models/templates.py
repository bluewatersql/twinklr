"""Template mining model contracts (V1.5)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TemplateKind(str, Enum):
    """Template catalog split by semantic scope."""

    CONTENT = "content"
    ORCHESTRATION = "orchestration"


class TemplateAssignment(BaseModel):
    """Per-phrase template assignment record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    package_id: str
    sequence_file_id: str
    phrase_id: str
    effect_event_id: str
    template_id: str


class TemplateProvenance(BaseModel):
    """Template source lineage reference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    package_id: str
    sequence_file_id: str
    phrase_id: str
    effect_event_id: str


class MinedTemplate(BaseModel):
    """A mined reusable template with quality metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str
    template_kind: TemplateKind
    template_signature: str

    support_count: int = Field(ge=0)
    distinct_pack_count: int = Field(ge=0)
    support_ratio: float = Field(ge=0.0, le=1.0)
    cross_pack_stability: float = Field(ge=0.0, le=1.0)
    onset_sync_mean: float | None = Field(default=None, ge=0.0, le=1.0)

    role: str | None = None
    taxonomy_labels: tuple[str, ...] = ()
    effect_family: str
    motion_class: str
    color_class: str
    energy_class: str
    continuity_class: str
    spatial_class: str

    provenance: tuple[TemplateProvenance, ...] = ()

    # Stack-level metadata (populated by stack-aware miner V2+).
    layer_count: int = Field(default=1, ge=1, description="Layers in the stack unit")
    stack_composition: tuple[str, ...] = Field(
        default=(),
        description="Ordered effect families in the stack (e.g. ('color_wash', 'bars', 'sparkle'))",
    )
    layer_blend_modes: tuple[str, ...] = Field(
        default=(),
        description="Blend modes per layer in order",
    )
    layer_mixes: tuple[float, ...] = Field(
        default=(),
        description="Mix levels per layer in order",
    )


class TemplateCatalog(BaseModel):
    """Serialized template catalog artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    miner_version: str
    template_kind: TemplateKind

    total_phrase_count: int = Field(ge=0)
    assigned_phrase_count: int = Field(ge=0)
    assignment_coverage: float = Field(ge=0.0, le=1.0)
    min_instance_count: int = Field(ge=1)
    min_distinct_pack_count: int = Field(ge=1)

    templates: tuple[MinedTemplate, ...] = ()
    assignments: tuple[TemplateAssignment, ...] = ()
