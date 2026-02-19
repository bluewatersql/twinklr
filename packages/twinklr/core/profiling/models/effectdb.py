"""Structured EffectDB profiling models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from twinklr.core.profiling.models.enums import (
    EffectDbControlType,
    EffectDbNamespace,
    ParameterValueType,
)


class EffectDbParam(BaseModel):
    """Single structured parameter parsed from EffectDB settings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: EffectDbNamespace
    control_type: EffectDbControlType
    param_name_raw: str
    param_name_normalized: str
    value_raw: str
    value_type: ParameterValueType
    value_int: int | None = None
    value_float: float | None = None
    value_bool: bool | None = None
    value_string: str | None = None
