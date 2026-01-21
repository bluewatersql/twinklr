"""Geometry classification for per-fixture curve optimization.

Classifies geometries as SYMMETRIC or ASYMMETRIC to determine whether fixtures
can share curves (symmetric) or need per-fixture curves (asymmetric).

SYMMETRIC geometries produce evenly distributed offsets where all fixtures can
share the same curve parameters with just static offsets applied.

ASYMMETRIC geometries produce per-fixture positions/roles that require
individual curve rendering for optimal quality.
"""

from __future__ import annotations

from enum import Enum


class GeometryClass(str, Enum):
    """Geometry classification for curve rendering optimization."""

    SYMMETRIC = "symmetric"
    ASYMMETRIC = "asymmetric"


# Geometry type classifications for smart fallback logic
# These determine whether to use per-fixture curves or shared curves

# SYMMETRIC: Fixtures get evenly distributed offsets, can share curves efficiently
# All fixtures move through the same curve with static pan/tilt offsets
SYMMETRIC_GEOMETRIES = frozenset(
    [
        "fan",  # Even distribution across arc
        "chevron_v",  # Symmetric V shape
        "audience_scan",  # Uniform coverage spread
        "wall_wash",  # Parallel beams
        "rainbow_arc",  # Even arc distribution
    ]
)

# ASYMMETRIC: Fixtures get per-fixture positions/roles, need individual curves
# Each fixture has different movement paths or parameters
ASYMMETRIC_GEOMETRIES = frozenset(
    [
        "mirror_lr",  # Different L/R positions
        "wave_lr",  # Phase-shifted wave across fixtures
        "spotlight_cluster",  # Converging to focal point
        "alternating_updown",  # Alternating tilt roles per fixture
        "tunnel_cone",  # Circular/cone positioning with depth
        "center_out",  # Expanding/collapsing formation
        "x_cross",  # Diagonal crossing groups
        "scattered_chaos",  # Random per-fixture positions
    ]
)

# Validate no overlap
_overlap = SYMMETRIC_GEOMETRIES & ASYMMETRIC_GEOMETRIES
if _overlap:
    raise ValueError(f"Geometries cannot be both SYMMETRIC and ASYMMETRIC: {_overlap}")


def get_geometry_class(geometry_type: str | None) -> GeometryClass:
    """Get the classification for a geometry type.

    Args:
        geometry_type: Geometry pattern name (e.g., "wave_lr", "mirror_lr")

    Returns:
        GeometryClass.SYMMETRIC or GeometryClass.ASYMMETRIC

    Raises:
        ValueError: If geometry_type is unknown
    """
    if not geometry_type:
        return GeometryClass.SYMMETRIC  # Default for no geometry

    if geometry_type in SYMMETRIC_GEOMETRIES:
        return GeometryClass.SYMMETRIC

    if geometry_type in ASYMMETRIC_GEOMETRIES:
        return GeometryClass.ASYMMETRIC

    raise ValueError(
        f"Unknown geometry type '{geometry_type}'. Must be classified as SYMMETRIC or ASYMMETRIC."
    )


def should_use_per_fixture_curves(
    geometry_type: str | None,
    num_fixtures: int,
) -> bool:
    """Determine if per-fixture curves should be used.

    Per-fixture curves are used when:
    - Geometry is ASYMMETRIC (fixtures have different positions/roles)
    - AND there are multiple fixtures (single fixture optimizes to shared)

    Args:
        geometry_type: Geometry pattern name
        num_fixtures: Number of fixtures in the target group

    Returns:
        True if per-fixture curves should be used, False otherwise
    """
    if num_fixtures <= 1:
        return False  # Single fixture always uses shared curves

    if not geometry_type:
        return False  # No geometry means no per-fixture variation

    try:
        geom_class = get_geometry_class(geometry_type)
        return geom_class == GeometryClass.ASYMMETRIC
    except ValueError:
        # Unknown geometry type - default to shared curves for safety
        return False


def is_symmetric(geometry_type: str | None) -> bool:
    """Check if a geometry type is symmetric.

    Args:
        geometry_type: Geometry pattern name

    Returns:
        True if symmetric, False if asymmetric or unknown
    """
    if not geometry_type:
        return True

    return geometry_type in SYMMETRIC_GEOMETRIES


def is_asymmetric(geometry_type: str | None) -> bool:
    """Check if a geometry type is asymmetric.

    Args:
        geometry_type: Geometry pattern name

    Returns:
        True if asymmetric, False if symmetric or unknown
    """
    if not geometry_type:
        return False

    return geometry_type in ASYMMETRIC_GEOMETRIES
