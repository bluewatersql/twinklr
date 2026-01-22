"""Curve registry and preset resolution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.modifiers import (
    CurveModifier,
    bounce_curve,
    mirror_curve,
    ping_pong_curve,
    repeat_curve,
    reverse_curve,
)
from blinkb0t.core.curves.semantics import CurveKind


@dataclass(frozen=True)
class NativeCurveDefinition:
    """Registry entry for curve generation."""

    curve_id: str
    default_params: dict[str, Any] | None = None
    description: str | None = None


@dataclass(frozen=True)
class CurveDefinition:
    """Registry entry for curve generation."""

    curve_id: str
    generator: Callable[..., list[CurvePoint]]
    kind: CurveKind
    default_samples: int
    default_params: dict[str, Any] | None = None
    modifiers: list[CurveModifier] | None = None
    description: str | None = None


def _apply_modifiers(points: list[CurvePoint], modifiers: list[CurveModifier]) -> list[CurvePoint]:
    """Apply modifier transformations to curve points."""
    result = points
    for modifier in modifiers:
        if modifier == CurveModifier.REVERSE:
            result = reverse_curve(result)
        elif modifier == CurveModifier.MIRROR:
            result = mirror_curve(result)
        elif modifier == CurveModifier.BOUNCE:
            result = bounce_curve(result)
        elif modifier == CurveModifier.PINGPONG:
            result = ping_pong_curve(result)
        elif modifier == CurveModifier.REPEAT:
            result = repeat_curve(result)
    return result


class CurveRegistry:
    """Registry for curve generators and preset resolution."""

    def __init__(self) -> None:
        self._registry: dict[str, CurveDefinition] = {}

    def register(self, spec: CurveDefinition) -> None:
        if spec.curve_id in self._registry:
            raise ValueError(f"Curve '{spec.curve_id}' already registered")
        self._registry[spec.curve_id] = spec

    def get(self, curve_id: str) -> CurveDefinition:
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
        spec = self.get(definition.curve_id)

        params = dict(spec.default_params or {})
        sample_count = n_samples or spec.default_samples
        points = spec.generator(sample_count, **params)

        modifiers = definition.modifiers or []
        if modifiers:
            points = _apply_modifiers(points, modifiers)

        return points
