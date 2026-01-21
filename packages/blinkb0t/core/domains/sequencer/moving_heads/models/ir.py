"""Sequencing v2 core models (Step 1 – MVP).

This module defines the foundational Pydantic models for a clean,
compiler-based moving-head sequencing architecture.

Guiding principles implemented here:
- Fixtures, groups, and orders are *rig config* (not templates)
- Pydantic for all models
- Validation ensures config correctness early
- Models are data-only (no rendering); helpers are minimal and side-effect free

You can drop this into your repo and wire it up via DI.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from blinkb0t.core.domains.sequencer.moving_heads.models.base import BlendMode, ChannelName


class CurvePoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    t: float = Field(..., ge=0.0, le=1.0, description="Normalized time")
    v: float = Field(..., ge=0.0, le=1.0, description="Normalized value")


class PointsCurveSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["POINTS"] = "POINTS"
    points: list[CurvePoint] = Field(..., min_length=2)

    @model_validator(mode="after")
    def _validate_monotonic_t(self) -> PointsCurveSpec:
        # xLights-style point arrays typically assume non-decreasing t.
        last_t = -1.0
        for p in self.points:
            if p.t < last_t:
                raise ValueError("PointsCurveSpec.points must have non-decreasing t")
            last_t = p.t
        # Encourage 0 and 1 endpoints (not strictly required, but helpful).
        return self


class NativeCurveSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["NATIVE"] = "NATIVE"
    curve_id: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


CurveSpec = PointsCurveSpec | NativeCurveSpec


class ChannelSegment(BaseModel):
    """IR segment for a single fixture + channel over a time range.

    Either `static_dmx` is set OR `curve` is set.

    For PAN/TILT movement curves, you can optionally encode them as
    *offset-centered* curves (v centered at 0.5) with `base_dmx` and
    `amplitude_dmx`, or you can export absolute DMX points downstream.

    MVP-friendly fields included to support both approaches.
    """

    model_config = ConfigDict(extra="forbid")

    fixture_id: str = Field(..., min_length=1)
    channel: ChannelName

    t0_ms: int = Field(..., ge=0)
    t1_ms: int = Field(..., ge=0)

    # Option A: static
    static_dmx: int | None = Field(default=None, ge=0, le=255)

    # Option B: curve
    curve: CurveSpec | None = Field(default=None)

    # Composition hints (primarily for movement offset curves)
    base_dmx: int | None = Field(default=None, ge=0, le=255)
    amplitude_dmx: int | None = Field(default=None, ge=0, le=255)
    offset_centered: bool = Field(
        default=False,
        description="If true, interpret curve values as offset around 0.5",
    )

    blend_mode: BlendMode = Field(default=BlendMode.OVERRIDE)

    clamp_min: int = Field(default=0, ge=0, le=255)
    clamp_max: int = Field(default=255, ge=0, le=255)

    @model_validator(mode="after")
    def _validate_static_vs_curve(self) -> ChannelSegment:
        if self.t1_ms < self.t0_ms:
            raise ValueError("t1_ms must be >= t0_ms")

        if self.static_dmx is None and self.curve is None:
            raise ValueError("ChannelSegment must set either static_dmx or curve")
        if self.static_dmx is not None and self.curve is not None:
            raise ValueError("ChannelSegment cannot set both static_dmx and curve")

        if self.clamp_max < self.clamp_min:
            raise ValueError("clamp_max must be >= clamp_min")

        # For offset-centered curves, base/amplitude must exist
        if self.curve is not None and self.offset_centered:
            if self.base_dmx is None or self.amplitude_dmx is None:
                raise ValueError("offset_centered curves require base_dmx and amplitude_dmx")

        return self
