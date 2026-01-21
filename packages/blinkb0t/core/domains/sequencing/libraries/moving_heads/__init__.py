"""Moving head pattern libraries (movements, geometry, dimmers)."""

from blinkb0t.core.domains.sequencing.libraries.moving_heads.base import (
    CategoricalIntensity,
    CurveCategory,
    CurveMapping,
    CurveType,
)
from blinkb0t.core.domains.sequencing.libraries.moving_heads.dimmers import (
    DIMMER_LIBRARY,
    DimmerID,
    DimmerPattern,
    get_dimmer,
    get_dimmer_params,
    list_dimmers,
)
from blinkb0t.core.domains.sequencing.libraries.moving_heads.geometry import (
    GEOMETRY_LIBRARY,
    GeometryDefinition,
    GeometryID,
    get_geometry,
    list_geometries,
)
from blinkb0t.core.domains.sequencing.libraries.moving_heads.movements import (
    MOVEMENT_LIBRARY,
    MovementID,
    MovementPattern,
    get_movement,
    get_movement_params,
    list_movements,
)

__all__ = [
    # Base types
    "CategoricalIntensity",
    "CurveCategory",
    "CurveMapping",
    "CurveType",
    # Dimmers
    "DIMMER_LIBRARY",
    "DimmerID",
    "DimmerPattern",
    "get_dimmer",
    "list_dimmers",
    # Geometry
    "GEOMETRY_LIBRARY",
    "GeometryDefinition",
    "GeometryID",
    "get_geometry",
    "list_geometries",
    # Movements
    "MOVEMENT_LIBRARY",
    "MovementID",
    "MovementPattern",
    "get_movement",
    "get_dimmer_params",
    "get_movement_params",
    "list_movements",
]
