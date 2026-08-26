"""Native xLights curve specification."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NativeCurveType(StrEnum):
    """Native curve identifiers compatible with xLights value curves."""

    FLAT = "flat"
    RAMP = "ramp"
    SINE = "sine"
    ABS_SINE = "abs sine"
    PARABOLIC = "parabolic"
    LOGARITHMIC = "logarithmic"
    EXPONENTIAL = "exponential"
    SAW_TOOTH = "saw tooth"


class xLightsNativeCurve(BaseModel):  # noqa: N801 — intentional xLights-branded name, used widely
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
