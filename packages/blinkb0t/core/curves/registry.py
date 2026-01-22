"""Curve registry and preset resolution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.semantics import CurveKind


@dataclass(frozen=True)
class CurveDefinition:
    """Curve definition or preset."""

    curve_id: str
    base_curve_id: str | None = None
    params: dict[str, Any] | None = None
    modifiers: list[str] | None = None
    kind: CurveKind = CurveKind.DIMMER_ABSOLUTE
    description: str | None = None


@dataclass(frozen=True)
class CurveGeneratorSpec:
    """Registry entry for curve generation."""

    curve_id: str
    generator: Callable[..., list[CurvePoint]]
    kind: CurveKind
    default_samples: int
    default_params: dict[str, Any] | None = None


def _apply_modifiers(points: list[CurvePoint], modifiers: list[str]) -> list[CurvePoint]:
    """Apply modifier transformations to curve points."""
    result = points
    for modifier in modifiers:
        if modifier == "reverse":
            reversed_points = [CurvePoint(t=1.0 - p.t, v=p.v) for p in reversed(result)]
            result = reversed_points
        elif modifier == "mirror":
            result = [CurvePoint(t=p.t, v=1.0 - p.v) for p in result]
    return result


class CurveRegistry:
    """Registry for curve generators and preset resolution."""

    def __init__(self) -> None:
        self._registry: dict[str, CurveGeneratorSpec] = {}

    def register(self, spec: CurveGeneratorSpec) -> None:
        if spec.curve_id in self._registry:
            raise ValueError(f"Curve '{spec.curve_id}' already registered")
        self._registry[spec.curve_id] = spec

    def get(self, curve_id: str) -> CurveGeneratorSpec:
        try:
            return self._registry[curve_id]
        except KeyError as exc:
            raise ValueError(f"Curve '{curve_id}' is not registered") from exc

    def resolve(
        self, definition: CurveDefinition, *, n_samples: int | None = None
    ) -> list[CurvePoint]:
        """Resolve a curve definition into points.

        Args:
            definition: Curve definition or preset.
            n_samples: Optional override for sample count.
        """
        if definition.base_curve_id:
            spec = self.get(definition.base_curve_id)
        else:
            spec = self.get(definition.curve_id)

        params = dict(spec.default_params or {})
        params.update(definition.params or {})
        sample_count = n_samples or spec.default_samples
        points = spec.generator(sample_count, **params)

        modifiers = definition.modifiers or []
        if modifiers:
            points = _apply_modifiers(points, modifiers)

        return points


def resolve_curve(
    registry: CurveRegistry,
    definition: CurveDefinition,
    *,
    n_samples: int | None = None,
) -> list[CurvePoint]:
    """Convenience wrapper for resolving a curve definition."""
    return registry.resolve(definition, n_samples=n_samples)
