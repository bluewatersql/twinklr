"""Taxonomy and target-role model contracts (V1.3/V1.4)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TaxonomyLabel(str, Enum):
    """Deterministic effect-function taxonomy labels."""

    # V1 labels
    RHYTHM_DRIVER = "rhythm_driver"
    ACCENT_HIT = "accent_hit"
    SUSTAINER = "sustainer"
    TRANSITION = "transition"
    TEXTURE_BED = "texture_bed"
    MOTION_DRIVER = "motion_driver"
    # V2 additions
    FILL_WASH = "fill_wash"
    SPARKLE_OVERLAY = "sparkle_overlay"
    CHASE_PATTERN = "chase_pattern"
    BURST_IMPACT = "burst_impact"
    LAYER_BASE = "layer_base"
    LAYER_ACCENT = "layer_accent"


class TaxonomyLabelScore(BaseModel):
    """Per-label confidence and explainability details."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: TaxonomyLabel
    confidence: float = Field(ge=0.0, le=1.0)
    rule_hits: tuple[str, ...] = ()


class PhraseTaxonomyRecord(BaseModel):
    """Taxonomy output keyed per phrase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    classifier_version: str

    phrase_id: str
    package_id: str
    sequence_file_id: str
    effect_event_id: str

    labels: tuple[TaxonomyLabel, ...] = ()
    label_confidences: tuple[float, ...] = ()
    rule_hit_keys: tuple[str, ...] = ()
    label_scores: tuple[TaxonomyLabelScore, ...] = ()


class TargetRole(str, Enum):
    """Semantic target roles used by planners."""

    LEAD = "lead"
    SUPPORT = "support"
    ACCENT = "accent"
    BACKGROUND = "background"
    IMPACT = "impact"
    MOTION = "motion"
    FALLBACK = "fallback"


class TargetRoleAssignment(BaseModel):
    """Target-role abstraction keyed by target identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    role_engine_version: str

    package_id: str
    sequence_file_id: str
    target_id: str
    target_name: str
    target_kind: str

    role: TargetRole
    role_confidence: float = Field(ge=0.0, le=1.0)
    reason_keys: tuple[str, ...] = ()

    event_count: int = Field(ge=0)
    active_duration_ms: int = Field(ge=0)
    pixel_count: int | None = Field(default=None, ge=0)

    target_layout_group: str | None = None
    target_category: str | None = None
    target_semantic_tags: tuple[str, ...] = ()

    role_binding_key: str
