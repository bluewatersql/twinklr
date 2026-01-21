from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.domains.sequencer.moving_heads.models.base import IntensityLevel


class DefaultsPatch(BaseModel):
    """Patch for TemplateDefaults."""

    model_config = ConfigDict(extra="forbid")

    dimmer_floor_dmx: int | None = Field(default=None, ge=0, le=255)
    dimmer_ceiling_dmx: int | None = Field(default=None, ge=0, le=255)


class MovementPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intensity: IntensityLevel | None = None
    cycles: float | None = Field(default=None, gt=0.0)
    movement_params: dict[str, Any] | None = None


class DimmerPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intensity: IntensityLevel | None = None
    min_norm: float | None = Field(default=None, ge=0.0, le=1.0)
    max_norm: float | None = Field(default=None, ge=0.0, le=1.0)
    cycles: float | None = Field(default=None, gt=0.0)
    dimmer_params: dict[str, Any] | None = None


class StepPatch(BaseModel):
    """Patch applied to a template step by step_id."""

    model_config = ConfigDict(extra="forbid")

    movement: MovementPatch | None = None
    dimmer: DimmerPatch | None = None
    # Geometry patches intentionally omitted in MVP; add later if needed.


class TemplatePreset(BaseModel):
    """Preset patch doc."""

    model_config = ConfigDict(extra="forbid")

    preset_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)

    defaults: DefaultsPatch | None = None

    # step_id -> patch
    step_patches: dict[str, StepPatch] = Field(default_factory=dict)
