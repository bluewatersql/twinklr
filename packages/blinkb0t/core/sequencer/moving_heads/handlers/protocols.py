"""Handler Protocols for the moving head sequencer.

This module defines the protocol interfaces for geometry, movement,
and dimmer handlers. Each handler type has a specific contract:

- GeometryHandler: Resolves static base poses (no animation)
- MovementHandler: Generates offset-centered motion curves
- DimmerHandler: Generates absolute brightness curves

All handlers are pure functions that produce deterministic outputs.
"""

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.curves.library import CurveLibrary
from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.sequencer.models.enum import Intensity

# =============================================================================
# Result Models (immutable data containers)
# =============================================================================


class GeometryResult(BaseModel):
    """Result from a geometry handler.

    Contains the static base pose for a fixture in normalized coordinates.
    These values represent the "home" position before any movement is applied.

    Attributes:
        pan_norm: Normalized pan position [0, 1].
        tilt_norm: Normalized tilt position [0, 1].

    Example:
        >>> result = GeometryResult(pan_norm=0.5, tilt_norm=0.3)
        >>> result.pan_norm
        0.5
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    pan_norm: float = Field(..., ge=0.0, le=1.0)
    tilt_norm: float = Field(..., ge=0.0, le=1.0)


class MovementResult(BaseModel):
    """Result from a movement handler.

    Contains offset-centered motion curves where v=0.5 means "no offset".
    The curves are applied as deltas around the geometry base pose.

    Attributes:
        pan_curve: Pan motion curve (offset-centered, v=0.5 = no motion).
        tilt_curve: Tilt motion curve (offset-centered, v=0.5 = no motion).

    Example:
        >>> points = [CurvePoint(t=0.0, v=0.5), CurvePoint(t=1.0, v=0.5)]
        >>> result = MovementResult(pan_curve=points, tilt_curve=points)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    pan_curve_type: CurveLibrary
    tilt_curve_type: CurveLibrary
    pan_curve: list[CurvePoint] = Field(..., min_length=2)
    tilt_curve: list[CurvePoint] = Field(..., min_length=2)


class DimmerResult(BaseModel):
    """Result from a dimmer handler.

    Contains an absolute brightness curve where v=0 is off and v=1 is full.
    Values are typically within [min_norm, max_norm] as specified.

    Attributes:
        dimmer_curve: Dimmer curve (absolute, v=0 to v=1).

    Example:
        >>> points = [CurvePoint(t=0.0, v=0.0), CurvePoint(t=1.0, v=1.0)]
        >>> result = DimmerResult(dimmer_curve=points)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    dimmer_curve: list[CurvePoint] = Field(..., min_length=2)


# =============================================================================
# Handler Protocols
# =============================================================================


class GeometryHandler(Protocol):
    """Protocol for geometry handlers.

    Geometry handlers resolve static base poses for fixtures.
    They determine WHERE the rig is positioned in space (formation),
    but do NOT animate or change over time.

    Attributes:
        handler_id: Unique identifier for this handler (e.g., "ROLE_POSE").
    """

    handler_id: str

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve the base pose for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "FRONT_LEFT").
            params: Handler-specific parameters from the template.
            calibration: Fixture calibration data from rig profile.

        Returns:
            GeometryResult with normalized pan/tilt base positions.
        """
        ...


class MovementHandler(Protocol):
    """Protocol for movement handlers.

    Movement handlers generate motion curves that are applied as offsets
    around the geometry base pose. Curves are offset-centered where
    v=0.5 means "no offset from base pose".

    Attributes:
        handler_id: Unique identifier for this handler (e.g., "SWEEP_LR").
    """

    handler_id: str

    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: Intensity,
    ) -> MovementResult:
        """Generate movement curves.

        Args:
            params: Handler-specific parameters from the template.
            n_samples: Number of samples to generate.
            cycles: Number of motion cycles.
            intensity: Intensity level (e.g., "SMOOTH", "DRAMATIC").

        Returns:
            MovementResult with offset-centered pan/tilt curves.
        """
        ...


class DimmerHandler(Protocol):
    """Protocol for dimmer handlers.

    Dimmer handlers generate absolute brightness curves where
    v=0 is off and v=1 is full brightness.

    Attributes:
        handler_id: Unique identifier for this handler (e.g., "PULSE").
    """

    handler_id: str

    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: Intensity,
        min_norm: float,
        max_norm: float,
    ) -> DimmerResult:
        """Generate dimmer curve.

        Args:
            params: Handler-specific parameters from the template.
            n_samples: Number of samples to generate.
            cycles: Number of dimmer cycles.
            intensity: Intensity level (e.g., "SMOOTH", "DRAMATIC").
            min_norm: Minimum brightness (normalized [0, 1]).
            max_norm: Maximum brightness (normalized [0, 1]).

        Returns:
            DimmerResult with absolute dimmer curve.
        """
        ...
