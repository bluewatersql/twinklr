"""Sequencer adapter contracts (V2.4 contract phase)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.feature_engineering.models.bundle import AudioStatus
from twinklr.core.feature_engineering.models.templates import TemplateKind
from twinklr.core.feature_engineering.models.transitions import TransitionType


class SequencerAdapterScope(str, Enum):
    """Supported sequencer adapter scopes for V2.4."""

    MACRO = "macro"
    GROUP = "group"


class PlannerChangeMode(str, Enum):
    """Planner behavior change mode for adapter payload consumption."""

    CONTRACT_ONLY = "contract_only"


class SequenceAdapterContext(BaseModel):
    """High-level sequence context shared by sequencer adapters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    package_id: str
    sequence_file_id: str
    sequence_name: str
    artist: str | None = None
    sequence_sha256: str
    audio_status: AudioStatus


class TemplateConstraint(BaseModel):
    """Template retrieval candidate projected into adapter contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str
    template_kind: TemplateKind
    retrieval_score: float = Field(ge=0.0, le=1.0)
    support_count: int = Field(ge=0)
    support_ratio: float = Field(ge=0.0, le=1.0)
    transition_flow_norm: float = Field(ge=0.0, le=1.0)

    effect_family: str
    role: str | None = None
    motion_class: str
    energy_class: str


class TransitionConstraint(BaseModel):
    """Transition graph edge constraint for sequencing decisions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_template_id: str
    target_template_id: str
    transition_type: TransitionType
    edge_count: int = Field(ge=0)


class RoleBindingContext(BaseModel):
    """Target-role binding context included for sequencer consumption."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_id: str
    target_name: str
    role: str
    role_confidence: float = Field(ge=0.0, le=1.0)


class MacroPlannerAdapterPayload(BaseModel):
    """Contract-only payload for macro sequencer integration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    adapter_version: str
    scope: SequencerAdapterScope = SequencerAdapterScope.MACRO
    planner_change_mode: PlannerChangeMode = PlannerChangeMode.CONTRACT_ONLY

    sequence: SequenceAdapterContext
    template_constraints: tuple[TemplateConstraint, ...] = ()
    transition_constraints: tuple[TransitionConstraint, ...] = ()
    role_bindings: tuple[RoleBindingContext, ...] = ()


class GroupPlannerAdapterPayload(BaseModel):
    """Contract-only payload for group sequencer integration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    adapter_version: str
    scope: SequencerAdapterScope = SequencerAdapterScope.GROUP
    planner_change_mode: PlannerChangeMode = PlannerChangeMode.CONTRACT_ONLY

    sequence: SequenceAdapterContext
    template_constraints: tuple[TemplateConstraint, ...] = ()
    transition_constraints: tuple[TransitionConstraint, ...] = ()
    role_bindings: tuple[RoleBindingContext, ...] = ()


class SequencerAdapterBundle(BaseModel):
    """Versioned bundle of sequencer adapter payloads."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    adapter_version: str
    macro: MacroPlannerAdapterPayload
    group: GroupPlannerAdapterPayload
