"""Effect stack model contracts.

An EffectStack represents the complete set of effects active on a single
display target at a given point in time — the fundamental visual unit
in xLights sequences.  A 1-layer stack is simply a stack with one layer.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.sequencer.vocabulary import BlendMode, LayerRole


class EffectStackLayer(BaseModel):
    """One layer within a multi-layer effect stack.

    Captures the effect phrase, its visual role, blend/mix parameters,
    and the preserved effect parameters from the source sequence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    phrase: EffectPhrase = Field(description="Source phrase for this layer")
    layer_role: LayerRole = Field(description="Visual role (BASE, RHYTHM, ACCENT, etc.)")
    blend_mode: BlendMode = Field(
        default=BlendMode.NORMAL,
        description="Blend mode from source sequence",
    )
    mix: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Mix level from source sequence",
    )
    preserved_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured effect parameters from effectdb",
    )


class EffectStack(BaseModel):
    """Complete set of co-occurring effects on a target — the visual unit.

    Groups all layers active on the same target within overlapping time
    ranges into a single composite.  This is the atomic unit of template
    discovery: a 1-layer stack is a simple effect, a 3-layer stack is a
    rich composite like ColorWash + Bars + Sparkle.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    stack_id: str = Field(description="Unique identifier for this stack instance")
    package_id: str = Field(description="Source package identifier")
    sequence_file_id: str = Field(description="Source sequence identifier")
    target_name: str = Field(description="Display model target (e.g. MegaTree, Arch)")
    model_type: str | None = Field(
        default=None,
        description="Inferred display model type",
    )
    start_ms: int = Field(ge=0, description="Stack start time (ms)")
    end_ms: int = Field(ge=0, description="Stack end time (ms)")
    duration_ms: int = Field(ge=0, description="Stack duration (ms)")
    section_label: str | None = Field(
        default=None,
        description="Audio section label at stack onset",
    )
    layers: tuple[EffectStackLayer, ...] = Field(
        description="Ordered layers (index 0 = background)",
    )
    layer_count: int = Field(ge=1, description="Number of layers in the stack")
    stack_signature: str = Field(
        description="Canonical stack signature for template mining",
    )


class EffectStackCatalog(BaseModel):
    """Collection of detected stacks for a corpus."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="v1.0.0")
    total_phrase_count: int = Field(ge=0)
    total_stack_count: int = Field(ge=0)
    single_layer_count: int = Field(ge=0)
    multi_layer_count: int = Field(ge=0)
    max_layer_count: int = Field(ge=0)
    stacks: tuple[EffectStack, ...] = ()
