"""Curve library for managing curve definitions.

Provides a centralized registry for all curve definitions (native, custom, presets).
Supports loading from JSON, filtering, and querying curves.
"""

from __future__ import annotations

from typing import Any

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveSource
from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition


class CurveLibrary:
    """Registry of curve definitions.

    Manages a collection of curve definitions, providing methods to:
    - Register new curves
    - Retrieve curves by ID
    - Filter curves by source type
    - Load/export curves from/to JSON

    Example:
        >>> library = CurveLibrary()
        >>> library.register(CurveDefinition(
        ...     id="sine_smooth",
        ...     source=CurveSource.NATIVE,
        ...     base_curve="sine"
        ... ))
        >>> curve = library.get("sine_smooth")
    """

    def __init__(self) -> None:
        """Initialize empty curve library."""
        self._curves: dict[str, CurveDefinition] = {}

    def register(self, curve: CurveDefinition) -> None:
        """Register a curve definition.

        Args:
            curve: Curve definition to register

        Raises:
            ValueError: If curve ID is already registered
        """
        if curve.id in self._curves:
            raise ValueError(f"Curve '{curve.id}' is already registered")

        self._curves[curve.id] = curve

    def get(self, curve_id: str) -> CurveDefinition | None:
        """Get curve definition by ID.

        Args:
            curve_id: Unique curve identifier

        Returns:
            Curve definition if found, None otherwise
        """
        return self._curves.get(curve_id)

    def has(self, curve_id: str) -> bool:
        """Check if curve exists in library.

        Args:
            curve_id: Unique curve identifier

        Returns:
            True if curve exists, False otherwise
        """
        return curve_id in self._curves

    def list_all(self) -> list[CurveDefinition]:
        """List all curves in library.

        Returns:
            List of all curve definitions
        """
        return list(self._curves.values())

    def list_by_source(self, source: CurveSource) -> list[CurveDefinition]:
        """List curves filtered by source type.

        Args:
            source: Curve source type to filter by

        Returns:
            List of curve definitions matching source type
        """
        return [curve for curve in self._curves.values() if curve.source == source]

    def count(self) -> int:
        """Get total number of curves in library.

        Returns:
            Number of registered curves
        """
        return len(self._curves)

    def clear(self) -> None:
        """Remove all curves from library."""
        self._curves.clear()

    def load_from_dict(self, curves_data: list[dict[str, Any]]) -> None:
        """Load curves from JSON dictionary list.

        Args:
            curves_data: List of curve definition dictionaries

        Example:
            >>> library.load_from_dict([
            ...     {
            ...         "id": "sine_smooth",
            ...         "source": "native",
            ...         "base_curve": "sine",
            ...         "description": "Smooth sine wave"
            ...     }
            ... ])
        """
        for curve_dict in curves_data:
            curve = CurveDefinition(**curve_dict)
            self.register(curve)

    def export_to_dict(self) -> list[dict[str, Any]]:
        """Export all curves to JSON dictionary list.

        Returns:
            List of curve definition dictionaries

        Example:
            >>> curves_json = library.export_to_dict()
            >>> # Can be serialized to JSON file
        """
        return [curve.model_dump() for curve in self._curves.values()]
