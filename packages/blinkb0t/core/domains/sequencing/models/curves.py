"""Pydantic models for curve engine.

Data models for curve definitions, specifications, and metadata.
All models are validated with Pydantic for type safety and serialization.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
    CurveSource,
    NativeCurveType,
)


class CurvePoint(BaseModel):
    """A point on a curve in normalized time-value space.

    Represents a single point on a curve, where time is normalized to [0, 1]
    and value can be any numeric value (typically DMX 0-255 or 0-65535).

    Used for custom curves that are generated as point arrays.

    Attributes:
        time: Normalized time position [0, 1]
        value: Curve value at this time (typically DMX value)
    """

    model_config = ConfigDict(frozen=True)  # Immutable for safety

    time: float = Field(..., ge=0.0, le=1.0, description="Normalized time [0, 1]")
    value: float = Field(..., description="Curve value at this time")


class ValueCurveSpec(BaseModel):
    """Specification for xLights native curve.

    Represents a native xLights curve using parametric formulas.
    More efficient than point arrays since xLights renders them directly.

    Parameters p1-p4 have different meanings depending on curve type:
    - Sine: p2=amplitude, p4=center
    - Ramp: p1=start, p2=end
    - Parabolic: p2=amplitude, p4=center
    - Saw Tooth: p1=min, p2=max

    Attributes:
        type: Native curve type (sine, ramp, parabolic, etc.)
        p1-p4: Curve parameters (meaning depends on type)
        reverse: Flip curve horizontally
        min_val: Minimum output value (typically 0)
        max_val: Maximum output value (typically 255 or 65535)
    """

    model_config = ConfigDict(frozen=False)  # Allow modification for tuning

    type: NativeCurveType = Field(..., description="Native curve type")
    p1: float = Field(default=0.0, description="Parameter 1 (curve-specific)")
    p2: float = Field(default=0.0, description="Parameter 2 (curve-specific)")
    p3: float = Field(default=0.0, description="Parameter 3 (curve-specific)")
    p4: float = Field(default=0.0, description="Parameter 4 (curve-specific)")
    reverse: bool = Field(default=False, description="Reverse curve direction")
    min_val: int = Field(default=0, description="Minimum output value")
    max_val: int = Field(default=255, description="Maximum output value")

    @field_validator("max_val")
    @classmethod
    def validate_range(cls, max_val: int, info: Any) -> int:
        """Validate that min_val < max_val."""
        min_val = info.data.get("min_val", 0)
        if min_val >= max_val:
            raise ValueError(f"min_val ({min_val}) must be less than max_val ({max_val})")
        return max_val

    def to_xlights_string(self, channel: int) -> str:
        """Generate xLights value curve parameter string.

        Args:
            channel: DMX channel number (1-512)

        Returns:
            xLights value curve parameter string in the format:
            "Active=TRUE|Id=ID_VALUECURVE_DMX{channel}|Type={type}|Min={min}|Max={max}|P1={p1}|...|RV={rv}|"

        Examples:
            >>> spec = ValueCurveSpec(type=NativeCurveType.RAMP, p2=150.0)
            >>> spec.to_xlights_string(11)
            'Active=TRUE|Id=ID_VALUECURVE_DMX11|Type=Ramp|Min=0|Max=255|P2=150.00|RV=FALSE|'
        """
        # Convert curve type to title case for xLights (case-sensitive)
        # Internal: "ramp", "sine", "abs sine" -> xLights: "Ramp", "Sine", "Abs Sine"
        xlights_type = self.type.value.title()

        parts = [
            "Active=TRUE",
            f"Id=ID_VALUECURVE_DMX{channel}",
            f"Type={xlights_type}",
            "Min=0",
            "Max=255",
        ]

        # Add parameter values if non-zero
        if self.p1 != 0.0:
            parts.append(f"P1={self.p1:.2f}")
        if self.p2 != 0.0:
            parts.append(f"P2={self.p2:.2f}")
        if self.p3 != 0.0:
            parts.append(f"P3={self.p3:.2f}")
        if self.p4 != 0.0:
            parts.append(f"P4={self.p4:.2f}")

        # Reverse flag (must be TRUE or FALSE in caps)
        parts.append(f"RV={'TRUE' if self.reverse else 'FALSE'}")

        # xLights format requires trailing pipe
        return "|".join(parts) + "|"


class CurveMetadata(BaseModel):
    """Metadata about a curve definition.

    Optional metadata for documentation, categorization, and optimization hints.

    Attributes:
        use_cases: List of typical use cases for this curve
        priority: Implementation priority (1=high, 2=normal, 3=low)
        performance_notes: Performance characteristics or optimization hints
        tags: Searchable tags for categorization
    """

    model_config = ConfigDict(frozen=False)

    use_cases: list[str] = Field(default_factory=list, description="Typical use cases")
    priority: int = Field(default=2, ge=1, le=3, description="Priority (1=high, 3=low)")
    performance_notes: str | None = Field(default=None, description="Performance characteristics")
    tags: list[str] = Field(default_factory=list, description="Searchable tags")


class CurveDefinition(BaseModel):
    """Complete definition of a curve.

    Defines a curve's identity, source, base shape, modifiers, and parameters.
    Used by CurveLibrary to register and look up curves.

    Attributes:
        id: Unique identifier for this curve
        source: Where curve originates (native, custom, preset)
        base_curve: Name of base curve type (for native/custom)
        base_curve_id: ID of base curve to reference (for presets only)
        modifiers: List of modifiers to apply (reverse, wrap, etc.)
        default_params: Default parameter values (for native/custom)
        preset_params: Preset-specific parameters (for presets only)
        metadata: Optional metadata about the curve
        description: Human-readable description
    """

    model_config = ConfigDict(frozen=False)

    id: str = Field(..., description="Unique curve identifier")
    source: CurveSource = Field(..., description="Curve source type")
    base_curve: str | None = Field(None, description="Base curve name (native/custom only)")
    base_curve_id: str | None = Field(None, description="Referenced curve ID (presets only)")
    modifiers: list[str] = Field(default_factory=list, description="Applied modifiers")
    default_params: dict[str, Any] = Field(default_factory=dict, description="Default parameters")
    preset_params: dict[str, Any] = Field(default_factory=dict, description="Preset parameters")
    metadata: CurveMetadata | None = Field(default=None, description="Curve metadata")
    description: str | None = Field(default=None, description="Human-readable description")

    @model_validator(mode="after")
    def validate_curve_fields(self) -> CurveDefinition:
        """Validate curve definition fields based on source type."""
        if self.source == CurveSource.NATIVE or self.source == CurveSource.CUSTOM:
            if not self.base_curve:
                raise ValueError(f"{self.source.value} curves must have 'base_curve'")
            if self.base_curve_id:
                raise ValueError(f"{self.source.value} curves cannot have 'base_curve_id'")
        elif self.source == CurveSource.PRESET:
            if not self.base_curve_id:
                raise ValueError("Preset curves must have 'base_curve_id'")
            if self.base_curve:
                raise ValueError("Preset curves cannot have 'base_curve'")
        return self


# Type aliases for convenience
CurveSpec = ValueCurveSpec
CurveDef = CurveDefinition
