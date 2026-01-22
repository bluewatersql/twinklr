"""Tests for curve registry and presets."""

import pytest

from blinkb0t.core.curves.generators import generate_sine
from blinkb0t.core.curves.registry import (
    CurveDefinition,
    CurveGeneratorSpec,
    CurveRegistry,
    resolve_curve,
)
from blinkb0t.core.curves.semantics import CurveKind


def test_registry_register_and_get() -> None:
    registry = CurveRegistry()
    spec = CurveGeneratorSpec(
        curve_id="SINE",
        generator=generate_sine,
        kind=CurveKind.DIMMER_ABSOLUTE,
        default_samples=8,
    )
    registry.register(spec)
    fetched = registry.get("SINE")
    assert fetched.curve_id == "SINE"
    assert fetched.default_samples == 8


def test_registry_duplicate_register_raises() -> None:
    registry = CurveRegistry()
    spec = CurveGeneratorSpec(
        curve_id="SINE",
        generator=generate_sine,
        kind=CurveKind.DIMMER_ABSOLUTE,
        default_samples=8,
    )
    registry.register(spec)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(spec)


def test_registry_resolve_base_definition() -> None:
    registry = CurveRegistry()
    registry.register(
        CurveGeneratorSpec(
            curve_id="SINE",
            generator=generate_sine,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=4,
        )
    )
    definition = CurveDefinition(curve_id="SINE")
    points = resolve_curve(registry, definition)
    assert len(points) == 4
    assert abs(points[0].v - 0.5) < 1e-10


def test_registry_resolve_preset_with_modifiers() -> None:
    registry = CurveRegistry()
    registry.register(
        CurveGeneratorSpec(
            curve_id="SINE",
            generator=generate_sine,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=4,
        )
    )
    definition = CurveDefinition(
        curve_id="SINE_REVERSED",
        base_curve_id="SINE",
        modifiers=["reverse"],
    )
    points = resolve_curve(registry, definition)
    assert len(points) == 4
    original = registry.resolve(CurveDefinition(curve_id="SINE"))
    assert abs(points[0].v - original[-1].v) < 1e-10
    assert abs(points[-1].v - original[0].v) < 1e-10


def test_registry_mirror_modifier() -> None:
    registry = CurveRegistry()
    registry.register(
        CurveGeneratorSpec(
            curve_id="SINE",
            generator=generate_sine,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=4,
        )
    )
    definition = CurveDefinition(
        curve_id="SINE_MIRROR",
        base_curve_id="SINE",
        modifiers=["mirror"],
    )
    points = resolve_curve(registry, definition)
    original = registry.resolve(CurveDefinition(curve_id="SINE"))
    assert abs(points[1].v - (1.0 - original[1].v)) < 1e-10


def test_registry_default_params_merge() -> None:
    registry = CurveRegistry()
    registry.register(
        CurveGeneratorSpec(
            curve_id="SINE",
            generator=generate_sine,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=8,
            default_params={"cycles": 2.0},
        )
    )
    definition = CurveDefinition(curve_id="SINE", params={"cycles": 1.0})
    points = resolve_curve(registry, definition, n_samples=8)
    assert len(points) == 8


def test_registry_sample_override() -> None:
    registry = CurveRegistry()
    registry.register(
        CurveGeneratorSpec(
            curve_id="SINE",
            generator=generate_sine,
            kind=CurveKind.DIMMER_ABSOLUTE,
            default_samples=4,
        )
    )
    definition = CurveDefinition(curve_id="SINE")
    points = resolve_curve(registry, definition, n_samples=6)
    assert len(points) == 6


def test_registry_missing_curve_raises() -> None:
    registry = CurveRegistry()
    with pytest.raises(ValueError, match="not registered"):
        registry.get("MISSING")
