"""Phrase encoding model contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MotionClass(StrEnum):
    STATIC = "static"
    SWEEP = "sweep"
    PULSE = "pulse"
    SPARKLE = "sparkle"
    DMX_PROGRAM = "dmx_program"
    UNKNOWN = "unknown"


class ColorClass(StrEnum):
    MONO = "mono"
    PALETTE = "palette"
    MULTI = "multi"
    UNKNOWN = "unknown"


class EnergyClass(StrEnum):
    LOW = "low"
    MID = "mid"
    HIGH = "high"
    BURST = "burst"
    UNKNOWN = "unknown"


class ContinuityClass(StrEnum):
    SUSTAINED = "sustained"
    RHYTHMIC = "rhythmic"
    TRANSITIONAL = "transitional"
    UNKNOWN = "unknown"


class SpatialClass(StrEnum):
    SINGLE_TARGET = "single_target"
    MULTI_TARGET = "multi_target"
    GROUP = "group"
    UNKNOWN = "unknown"


class PhraseSource(StrEnum):
    EFFECT_TYPE_MAP = "effect_type_map"
    FALLBACK = "fallback"


class EffectPhrase(BaseModel):
    """Canonical vendor-agnostic phrase record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    phrase_id: str
    package_id: str
    sequence_file_id: str
    effect_event_id: str

    effect_type: str
    effect_family: str
    motion_class: MotionClass
    color_class: ColorClass
    energy_class: EnergyClass
    continuity_class: ContinuityClass
    spatial_class: SpatialClass
    source: PhraseSource
    map_confidence: float = Field(ge=0.0, le=1.0)

    target_name: str
    layer_index: int
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    duration_ms: int = Field(ge=0)

    start_beat_index: int | None = None
    end_beat_index: int | None = None
    section_label: str | None = None
    onset_sync_score: float | None = Field(default=None, ge=0.0, le=1.0)

    param_signature: str

    # Structured parameters preserved from effectdb for stack construction.
    # Optional for backward compatibility — populated by PhraseEncoder V1.3+.
    preserved_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured effect parameters from effectdb",
    )
    blend_mode: str | None = Field(
        default=None,
        description="Blend mode from source XSQ layer",
    )
    mix: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Mix level from source XSQ layer",
    )
