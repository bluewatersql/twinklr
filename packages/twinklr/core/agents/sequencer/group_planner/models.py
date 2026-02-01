"""GroupPlanner agent models.

GroupPlanner implements MacroPlan for each display group, selecting templates and presets
for each section/layer.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.agents.audio.profile.models import Provenance, SongSectionRef
from twinklr.core.agents.issues import Issue
from twinklr.core.agents.taxonomy import BlendMode, QuantizeMode, SnapMode, TimeRefType

# Time reference models


class TimeRef(BaseModel):
    """Time reference for placement (marker-based or absolute ms)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref_type: TimeRefType
    value: int = Field(ge=0)  # bar number (1-indexed) or milliseconds
    marker_type: str | None = Field(default=None)  # "bar", "beat", "phrase", etc.


class SnapRule(BaseModel):
    """Snap behavior for time alignment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snap_mode: SnapMode = SnapMode.NONE
    quantize: QuantizeMode = QuantizeMode.NONE


# Spatial intent


class SpatialIntent(BaseModel):
    """Spatial choreography intent for placement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pattern: str | None = None  # "MIRROR", "SWEEP", "RIPPLE", etc.
    direction: str | None = None  # "L2R", "R2L", "C2O", etc.
    roles: list[str] = Field(default_factory=list)  # Zone roles
    phase_offset: float | None = Field(default=None, ge=0.0, le=1.0)


# Asset references


class AssetSlot(BaseModel):
    """Asset slot reference in placement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    purpose: str  # "texture", "mask", "sprite", "gobo"
    asset_request_id: str | None = None
    asset_ref_id: str | None = None


# Template placement


class TemplatePlacement(BaseModel):
    """Single template placement within a layer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    placement_id: str
    start: TimeRef
    end: TimeRef
    snap: SnapRule
    template_id: str
    preset_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    intensity: float = Field(default=1.0, ge=0.0, le=1.5)
    blend_mode: BlendMode = BlendMode.NORMAL
    spatial: SpatialIntent | None = None
    media: AssetSlot | None = None


# Layer plan


class LayerPlan(BaseModel):
    """Plan for a single layer in a section."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    layer_index: int = Field(ge=0)
    placements: list[TemplatePlacement]


# Section plan


class SectionGroupPlan(BaseModel):
    """Plan for a single section in a specific group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section: SongSectionRef
    layers: list[LayerPlan]

    @model_validator(mode="after")
    def _validate_unique_layer_indices(self) -> SectionGroupPlan:
        """Validate layer indices are unique."""
        indices = [layer.layer_index for layer in self.layers]
        if len(indices) != len(set(indices)):
            raise ValueError("Layer indices must be unique within a section")
        return self


# Asset request


class AssetRequest(BaseModel):
    """Asset request from GroupPlanner to Asset Creation Agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    kind: str  # "image_png", "image_gif", "texture"
    use_case: str  # "matrix_texture", "sprite", "gobo", etc.
    style_tags: list[str] = Field(default_factory=list)
    content_tags: list[str] = Field(default_factory=list)
    palette_hint: str | None = None
    tiling: bool = False
    constraints: dict[str, Any] = Field(default_factory=dict)
    fallback_strategy: str = "use_builtin_if_missing"


# Compilation hints


class CompilationHints(BaseModel):
    """Hints for SequenceAssembler compilation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    quantize_policy: QuantizeMode = QuantizeMode.BARS
    transition_policy: str = "crossfade"  # "crossfade", "cut", "beat_snap"
    layering_policy: str = "blend"  # "blend", "priority", "allow_overlap"
    overlap_resolution: str = "trim"  # "trim", "allow", "priority"


# Complete group plan


class GroupPlan(BaseModel):
    """Complete plan for a single display group."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "group-plan.v2"
    plan_id: str
    group_id: str
    section_plans: list[SectionGroupPlan] = Field(min_length=1)
    asset_requests: list[AssetRequest] = Field(default_factory=list)
    compilation_hints: CompilationHints = Field(default_factory=CompilationHints)
    provenance: Provenance | None = None
    warnings: list[Issue] = Field(default_factory=list)


# Group plan set (aggregated output)


class GroupPlanSet(BaseModel):
    """Aggregated plans for all display groups."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "group-plan-set.v2"
    set_id: str
    group_plans: list[GroupPlan] = Field(min_length=1)
    provenance: Provenance | None = None
    warnings: list[Issue] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_group_ids(self) -> GroupPlanSet:
        """Validate group IDs are unique."""
        group_ids = [plan.group_id for plan in self.group_plans]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("Group IDs must be unique within GroupPlanSet")
        return self
