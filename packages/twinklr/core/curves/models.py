"""Curve schema models for the moving head sequencer.

This module defines the core curve primitives used throughout the pipeline:
- CurvePoint: A single normalized point (t, v) in [0,1] x [0,1]
- PointsCurve: A curve defined by explicit points with monotonic time
- NativeCurve: A curve defined by a named curve ID (e.g., LINEAR, HOLD)
- BaseCurve: Union type for any curve specification

All models are immutable where possible and validate on construction.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CurvePoint(BaseModel):
    """A single point on a normalized curve.

    Both t and v are normalized to [0, 1].
    This model is immutable (frozen=True).

    Attributes:
        t: Normalized time in range [0, 1].
        v: Normalized value in range [0, 1].

    Example:
        >>> point = CurvePoint(t=0.5, v=0.7)
        >>> point.t
        0.5
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    t: float = Field(..., ge=0.0, le=1.0, description="Normalized time [0,1]")
    v: float = Field(..., ge=0.0, le=1.0, description="Normalized value [0,1]")


class PointsCurve(BaseModel):
    """Curve defined by explicit points.

    Points must have non-decreasing t values (monotonic time).
    A minimum of 2 points is required to define a valid curve.

    Attributes:
        kind: Discriminator field, always "POINTS".
        points: List of CurvePoint with non-decreasing t values.

    Example:
        >>> curve = PointsCurve(points=[
        ...     CurvePoint(t=0.0, v=0.0),
        ...     CurvePoint(t=1.0, v=1.0),
        ... ])
        >>> curve.kind
        'POINTS'
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["POINTS"] = "POINTS"
    points: list[CurvePoint] = Field(..., min_length=2)

    @model_validator(mode="after")
    def _validate_monotonic_t(self) -> "PointsCurve":
        """Validate that points have non-decreasing t values."""
        last_t = -1.0
        for p in self.points:
            if p.t < last_t:
                raise ValueError("PointsCurve.points must have non-decreasing t")
            last_t = p.t
        return self


class NativeCurve(BaseModel):
    """Curve defined by native curve ID.

    Native curves reference built-in curve types like LINEAR, HOLD, etc.
    Optional parameters can be provided to customize the curve behavior.

    Attributes:
        kind: Discriminator field, always "NATIVE".
        curve_id: The name of the native curve (e.g., "LINEAR", "HOLD", "SINE").
        params: Optional parameters for the curve (e.g., frequency, phase).

    Example:
        >>> curve = NativeCurve(curve_id="SINE", params={"frequency": 2.0})
        >>> curve.kind
        'NATIVE'
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["NATIVE"] = "NATIVE"
    curve_id: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class CurveIntensityParams(BaseModel):
    """Standard intensity parameters for curve generation.

    These parameters are derived from categorical params based on Intensity level.
    Not all parameters are relevant to all curve types - functions should
    ignore irrelevant parameters.

    NOTE: This model is for documentation/validation purposes. Curve functions
    receive these as **kwargs, not as a model instance.

    Period is NOT included here - it's a planning-level concept in bars that
    handlers convert to cycles before passing to curve functions.

    Attributes:
        amplitude: Amplitude scaling factor [0, 1] (default: 1.0).
        frequency: Frequency multiplier [0, 10] (default: 1.0).
        center_offset: Center offset for movement curves [0, 1] (default: 0.5).

    Example:
        >>> params = CurveIntensityParams(amplitude=0.5, frequency=2.0)
        >>> params.to_dict()
        {'amplitude': 0.5, 'frequency': 2.0, 'center_offset': 0.5}
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    amplitude: float = Field(default=1.0, ge=0.0, le=1.0)
    frequency: float = Field(default=1.0, ge=0.0, le=10.0)
    center_offset: float = Field(default=0.5, ge=0.0, le=1.0)

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary for **kwargs expansion."""
        return self.model_dump()


# Union type for curve specifications.
# Use this when accepting any curve type.
BaseCurve = PointsCurve | NativeCurve
