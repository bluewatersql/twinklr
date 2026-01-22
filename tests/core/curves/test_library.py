"""Tests for curve library wiring."""

from blinkb0t.core.curves.library import CurveId, build_default_registry
from blinkb0t.core.curves.registry import CurveDefinition


def test_library_registers_all_curve_ids() -> None:
    registry = build_default_registry()
    for curve_id in CurveId:
        spec = registry.get(curve_id.value)
        assert spec.curve_id == curve_id.value


def test_library_resolves_movement_curve() -> None:
    registry = build_default_registry()
    definition = CurveDefinition(curve_id=CurveId.MOVEMENT_SINE.value)
    points = registry.resolve(definition, n_samples=8)
    assert len(points) == 8
    assert abs(points[0].v - points[-1].v) < 1e-10
