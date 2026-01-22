"""Native curve specification and tuning helpers."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NativeCurveType(str, Enum):
    """Native curve identifiers compatible with xLights value curves."""

    FLAT = "flat"
    RAMP = "ramp"
    SINE = "sine"
    ABS_SINE = "abs sine"
    PARABOLIC = "parabolic"
    LOGARITHMIC = "logarithmic"
    EXPONENTIAL = "exponential"
    SAW_TOOTH = "saw tooth"


class NativeCurveSpec(BaseModel):
    """Specification for native parametric curves."""

    model_config = ConfigDict(frozen=False)

    type: NativeCurveType
    p1: float = Field(default=0.0)
    p2: float = Field(default=0.0)
    p3: float = Field(default=0.0)
    p4: float = Field(default=0.0)
    reverse: bool = Field(default=False)
    min_val: int = Field(default=0)
    max_val: int = Field(default=255)

    @field_validator("max_val")
    @classmethod
    def validate_range(cls, max_val: int, info):
        min_val = info.data.get("min_val", 0)
        if min_val >= max_val:
            raise ValueError("min_val must be less than max_val")
        return max_val

    def to_xlights_string(self, channel: int) -> str:
        xlights_type = self.type.value.title()
        parts = [
            "Active=TRUE",
            f"Id=ID_VALUECURVE_DMX{channel}",
            f"Type={xlights_type}",
            f"Min={self.min_val}",
            f"Max={self.max_val}",
        ]
        if self.p1 != 0.0:
            parts.append(f"P1={self.p1:.2f}")
        if self.p2 != 0.0:
            parts.append(f"P2={self.p2:.2f}")
        if self.p3 != 0.0:
            parts.append(f"P3={self.p3:.2f}")
        if self.p4 != 0.0:
            parts.append(f"P4={self.p4:.2f}")
        parts.append(f"RV={'TRUE' if self.reverse else 'FALSE'}")
        return "|".join(parts) + "|"


def generate_native_spec(curve_type: NativeCurveType, params: dict[str, float] | None = None) -> NativeCurveSpec:
    """Map high-level parameters to a native curve spec."""
    params = params or {}
    if curve_type == NativeCurveType.SINE:
        return NativeCurveSpec(type=curve_type, p2=params.get("amplitude", 100.0), p4=params.get("center", 128.0))
    if curve_type == NativeCurveType.ABS_SINE:
        return NativeCurveSpec(type=curve_type, p2=params.get("amplitude", 100.0), p4=params.get("center", 128.0))
    if curve_type == NativeCurveType.PARABOLIC:
        return NativeCurveSpec(type=curve_type, p2=params.get("amplitude", 100.0), p4=params.get("center", 128.0))
    if curve_type == NativeCurveType.RAMP:
        return NativeCurveSpec(type=curve_type, p1=params.get("min", 0.0), p2=params.get("max", 255.0))
    if curve_type == NativeCurveType.SAW_TOOTH:
        return NativeCurveSpec(type=curve_type, p1=params.get("min", 0.0), p2=params.get("max", 255.0))
    if curve_type == NativeCurveType.LOGARITHMIC:
        return NativeCurveSpec(type=curve_type, p1=params.get("min", 0.0), p2=params.get("max", 255.0))
    if curve_type == NativeCurveType.EXPONENTIAL:
        return NativeCurveSpec(type=curve_type, p1=params.get("min", 0.0), p2=params.get("max", 255.0))
    if curve_type == NativeCurveType.FLAT:
        return NativeCurveSpec(type=curve_type, p1=params.get("value", 128.0))
    raise ValueError(f"Unsupported native curve type: {curve_type}")


def tune_native_spec(spec: NativeCurveSpec, min_limit: float, max_limit: float) -> NativeCurveSpec:
    """Tune native curve parameters to fit within boundaries."""
    if spec.type in {NativeCurveType.SINE, NativeCurveType.ABS_SINE, NativeCurveType.PARABOLIC}:
        current_min = spec.p4 - spec.p2
        current_max = spec.p4 + spec.p2
        if current_min >= min_limit and current_max <= max_limit:
            return spec
        center = (min_limit + max_limit) / 2
        amplitude = (max_limit - min_limit) / 2
        return spec.model_copy(update={"p2": amplitude, "p4": center})

    if spec.type in {NativeCurveType.RAMP, NativeCurveType.SAW_TOOTH, NativeCurveType.EXPONENTIAL, NativeCurveType.LOGARITHMIC}:
        new_p1 = max(spec.p1, min_limit)
        new_p2 = min(spec.p2, max_limit)
        if new_p1 == spec.p1 and new_p2 == spec.p2:
            return spec
        return spec.model_copy(update={"p1": new_p1, "p2": new_p2})

    if spec.type == NativeCurveType.FLAT:
        new_p1 = max(min_limit, min(spec.p1, max_limit))
        if new_p1 == spec.p1:
            return spec
        return spec.model_copy(update={"p1": new_p1})

    return spec
