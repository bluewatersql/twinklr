"""Value curve bridge for the display rendering pipeline.

Converts ``CurveLibrary`` curves into xLights ``E_VALUECURVE_*``
format strings for animating effect parameters over time.

The moving-head path already has ``_curve_points_to_xlights_string``
for DMX channels; this module provides the equivalent for named
effect parameters (e.g., ``Twinkle_Count``, ``ColorWash_Speed``).

xLights ValueCurve format (custom points):
    ``Active=TRUE|Id=ID_VALUECURVE_{id}|Type=Custom|Min={min}|Max={max}|RV=FALSE|Values=t:v;t:v;...|``

xLights ValueCurve format (native curve):
    ``Active=TRUE|Id=ID_VALUECURVE_{id}|Type={type}|Min={min}|Max={max}|P1=...|RV=FALSE|``
"""

from __future__ import annotations

from twinklr.core.curves.generator import CurveGenerator
from twinklr.core.curves.library import CurveLibrary
from twinklr.core.curves.models import CurvePoint

# Module-level generator instance (stateless, safe to share).
_generator = CurveGenerator()


def build_value_curve_string(
    curve_id: CurveLibrary,
    param_id: str,
    min_val: float = 0.0,
    max_val: float = 100.0,
    num_points: int = 20,
    *,
    amplitude: float = 1.0,
    frequency: float = 1.0,
) -> str:
    """Generate an xLights ValueCurve string for a named effect parameter.

    Uses ``CurveGenerator`` to produce normalized curve points, then
    formats them into the xLights ``Active=TRUE|...|Values=t:v;...|``
    format expected by ``E_VALUECURVE_*`` keys.

    Args:
        curve_id: Curve type from the ``CurveLibrary`` enum.
        param_id: xLights parameter identifier (e.g.,
            ``"Twinkle_Count"``, ``"ColorWash_Speed"``).  Used in the
            ``Id=ID_VALUECURVE_{param_id}`` field.
        min_val: Minimum parameter value in xLights units.
        max_val: Maximum parameter value in xLights units.
        num_points: Number of sample points for custom curves.
        amplitude: Curve amplitude scaling (0.0-1.0).
        frequency: Curve frequency multiplier.

    Returns:
        Complete xLights ValueCurve string with trailing pipe.

    Raises:
        ValueError: If the curve_id is not found in the library.

    Example:
        >>> s = build_value_curve_string(
        ...     CurveLibrary.SINE, "Twinkle_Count",
        ...     min_val=0.0, max_val=25.0,
        ...     amplitude=0.5, frequency=2.0,
        ... )
        >>> s.startswith("Active=TRUE|")
        True
    """
    points = _generator.generate_custom_points(
        curve_id.value,
        num_points=num_points,
        amplitude=amplitude,
        frequency=frequency,
    )
    return curve_points_to_xlights_string(
        points, param_id=param_id, min_val=min_val, max_val=max_val
    )


def curve_points_to_xlights_string(
    points: list[CurvePoint],
    *,
    param_id: str,
    min_val: float = 0.0,
    max_val: float = 100.0,
) -> str:
    """Convert normalized curve points to an xLights ValueCurve string.

    This is the display-path equivalent of the moving-head path's
    ``_curve_points_to_xlights_string``, generalised for named
    parameters instead of DMX channel numbers.

    Args:
        points: Normalized curve points (t and v both in [0,1]).
        param_id: Parameter identifier for the ``Id`` field.
        min_val: Parameter minimum in xLights units.
        max_val: Parameter maximum in xLights units.

    Returns:
        xLights ValueCurve string with trailing pipe, or empty
        string if ``points`` is empty.
    """
    if not points:
        return ""

    # Build time:value pairs (both normalised 0-1, 2 decimal places).
    pairs: list[str] = []
    for pt in points:
        t_r = round(pt.t, 2)
        v_r = round(pt.v, 2)
        pairs.append(f"{t_r:.2f}:{v_r:.2f}")

    # Ensure anchors at t=0.0 and t=1.0
    if points[0].t > 0.01:
        v_start = round(points[0].v, 2)
        pairs.insert(0, f"0.00:{v_start:.2f}")
    if points[-1].t < 0.99:
        v_end = round(points[-1].v, 2)
        pairs.append(f"1.00:{v_end:.2f}")

    values_str = ";".join(pairs)

    parts = [
        "Active=TRUE",
        f"Id=ID_VALUECURVE_{param_id}",
        "Type=Custom",
        f"Min={min_val:.2f}",
        f"Max={max_val:.2f}",
        "RV=FALSE",
        f"Values={values_str}",
    ]
    return "|".join(parts) + "|"


__all__ = [
    "build_value_curve_string",
    "curve_points_to_xlights_string",
]
