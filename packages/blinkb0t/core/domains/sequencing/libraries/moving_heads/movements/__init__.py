"""Movement pattern library - Python-based with type safety.

Migrated from movingheads/data/movements/v1/library.json with content preservation.
This provides type-safe movement pattern definitions with Pydantic models.

The library is organized into focused modules by movement category:
- models: Shared models (MovementID, CategoricalParams, MovementPattern)
- core: Fundamental patterns (sweeps, circles, figure-8, hold)
- shakes: Oscillations and rhythmic movements (shakes, rocks, bounces)
- accents: Sharp, percussive movements (snaps, hits, pops)
- waves: Wave patterns and complex sweeps (waves, spirals, diagonals)
"""

from __future__ import annotations

from blinkb0t.core.domains.sequencing.libraries.moving_heads.base import CategoricalIntensity
from blinkb0t.core.domains.sequencing.libraries.moving_heads.movements.accents import (
    ACCENT_MOVEMENTS,
)

# Import movement categories
from blinkb0t.core.domains.sequencing.libraries.moving_heads.movements.core import CORE_MOVEMENTS

# Import models
from blinkb0t.core.domains.sequencing.libraries.moving_heads.movements.models import (
    DEFAULT_CATEGORICAL_PARAMS,
    CategoricalParams,
    MovementID,
    MovementPattern,
)
from blinkb0t.core.domains.sequencing.libraries.moving_heads.movements.shakes import SHAKE_MOVEMENTS
from blinkb0t.core.domains.sequencing.libraries.moving_heads.movements.waves import WAVE_MOVEMENTS

# Aggregate all movements into single library
MOVEMENT_LIBRARY: dict[MovementID, MovementPattern] = {
    **CORE_MOVEMENTS,
    **SHAKE_MOVEMENTS,
    **ACCENT_MOVEMENTS,
    **WAVE_MOVEMENTS,
}


# ============================================================================
# Accessor Functions
# ============================================================================


def get_movement(movement_id: MovementID) -> MovementPattern:
    """Get movement pattern by ID (type-safe).

    Args:
        movement_id: Movement pattern enum value

    Returns:
        Complete movement pattern definition

    Raises:
        KeyError: If movement_id not found (should never happen with enum)

    Example:
        pattern = get_movement(MovementID.SWEEP_LR)
        print(pattern.name)  # "Left/Right Sweep"
    """
    return MOVEMENT_LIBRARY[movement_id]


def get_movement_params(
    movement_id: MovementID, intensity: CategoricalIntensity
) -> CategoricalParams:
    """Get categorical parameters for movement at intensity level.

    Args:
        movement_id: Movement pattern enum value
        intensity: Categorical intensity level

    Returns:
        Parameters for specified intensity level

    Example:
        params = get_movement_params(
            MovementID.SWEEP_LR,
            CategoricalIntensity.DRAMATIC
        )
        print(params.amplitude)  # 0.6
    """
    pattern = MOVEMENT_LIBRARY[movement_id]
    return pattern.categorical_params[intensity]


def list_movements() -> list[MovementID]:
    """Get list of all available movement IDs.

    Returns:
        List of movement enum values
    """
    return list(MOVEMENT_LIBRARY.keys())


def search_movements(tag: str | None = None) -> list[MovementPattern]:
    """Search movements by tag or criteria.

    Args:
        tag: Optional tag to filter by (future feature)

    Returns:
        List of matching movement patterns
    """
    # Basic implementation - can be enhanced with tagging system
    return list(MOVEMENT_LIBRARY.values())


__all__ = [
    # Models
    "CategoricalParams",
    "MovementID",
    "MovementPattern",
    "DEFAULT_CATEGORICAL_PARAMS",
    # Library
    "MOVEMENT_LIBRARY",
    "CORE_MOVEMENTS",
    "SHAKE_MOVEMENTS",
    "ACCENT_MOVEMENTS",
    "WAVE_MOVEMENTS",
    # Accessors
    "get_movement",
    "get_movement_params",
    "list_movements",
    "search_movements",
]
