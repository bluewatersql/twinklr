"""Geometry Engine for spatial arrangement transformations.

This module provides geometry transformations that convert single movement
specifications into per-fixture variations based on spatial patterns.

Example:
    Single instruction with geometry:
    {
        "target": "ALL_MH",
        "movement": {"pattern": "sweep_lr", "amplitude_deg": 60},
        "geometry": {"type": "wave_lr"}
    }

    Expands to 4 per-fixture movements with phase offsets:
    MH1: {"pattern": "sweep_lr", "amplitude_deg": 60, "phase_deg": 0}
    MH2: {"pattern": "sweep_lr", "amplitude_deg": 60, "phase_deg": 90}
    MH3: {"pattern": "sweep_lr", "amplitude_deg": 60, "phase_deg": 180}
    MH4: {"pattern": "sweep_lr", "amplitude_deg": 60, "phase_deg": 270}
"""

from .base import GeometryTransform
from .classification import (
    ASYMMETRIC_GEOMETRIES,
    SYMMETRIC_GEOMETRIES,
    GeometryClass,
    get_geometry_class,
    is_asymmetric,
    is_symmetric,
    should_use_per_fixture_curves,
)
from .engine import GeometryEngine

__all__ = [
    "GeometryTransform",
    "GeometryEngine",
    "GeometryClass",
    "SYMMETRIC_GEOMETRIES",
    "ASYMMETRIC_GEOMETRIES",
    "get_geometry_class",
    "is_symmetric",
    "is_asymmetric",
    "should_use_per_fixture_curves",
]
