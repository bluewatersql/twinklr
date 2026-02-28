"""Tests for builtin template enrichment.

Validates that the enrichment script properly resolves placeholder
effect_type values and populates params for all 221 builtin templates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from twinklr.core.sequencer.display.templates.effect_map import resolve_effect_type
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe

# Placeholder effect_type values that must be replaced
PLACEHOLDERS = frozenset(
    {"ABSTRACT", "GEOMETRIC", "IMAGERY", "TEXTURE", "HYBRID", "ORGANIC", "PLACEHOLDER"}
)

_BUILTINS_DIR = Path(__file__).resolve().parents[3] / "data" / "templates" / "builtins"


def _load_all_builtins() -> list[tuple[str, dict[str, Any]]]:
    """Load all builtin template JSON files."""
    results: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(_BUILTINS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        results.append((path.stem, data))
    return results


def _all_builtin_ids() -> list[str]:
    """Return sorted list of all builtin recipe IDs."""
    return [stem for stem, _ in _load_all_builtins()]


class TestBuiltinEnrichmentPlaceholders:
    """All builtin templates must have real xLights effect types."""

    def test_no_placeholder_effect_types(self) -> None:
        """No layer in any builtin should use a placeholder effect_type."""
        violations: list[str] = []
        for stem, data in _load_all_builtins():
            for layer in data.get("layers", []):
                if layer.get("effect_type") in PLACEHOLDERS:
                    violations.append(
                        f"{stem}: layer {layer.get('layer_index')} has {layer['effect_type']}"
                    )
        assert not violations, f"Found {len(violations)} placeholder effect types:\n" + "\n".join(
            violations[:20]
        )

    def test_effect_types_are_known_xlights_effects(self) -> None:
        """All resolved effect types should be recognized xLights effect names."""
        known_effects = {
            "Color Wash",
            "Spirals",
            "Twinkle",
            "Meteors",
            "Fan",
            "Shockwave",
            "Strobe",
            "On",
            "Snowflakes",
            "Marquee",
            "SingleStrand",
            "Pictures",
            "Ripple",
            "Fire",
        }
        unknown: list[str] = []
        for stem, data in _load_all_builtins():
            for layer in data.get("layers", []):
                et = layer.get("effect_type", "")
                if et not in known_effects:
                    unknown.append(f"{stem}: {et}")
        assert not unknown, f"Found {len(unknown)} unknown effect types:\n" + "\n".join(
            unknown[:20]
        )


class TestBuiltinEnrichmentParams:
    """All builtin templates must have populated params."""

    def test_at_least_one_param_per_template(self) -> None:
        """Every builtin must have at least one layer with non-empty params."""
        empty: list[str] = []
        for stem, data in _load_all_builtins():
            has_params = False
            for layer in data.get("layers", []):
                if layer.get("params") and len(layer["params"]) > 0:
                    has_params = True
                    break
            if not has_params:
                empty.append(stem)
        assert not empty, f"Found {len(empty)} templates with all-empty params:\n" + "\n".join(
            empty[:20]
        )

    def test_params_use_param_value_format(self) -> None:
        """All param values must be in ParamValue format: {\"value\": X}."""
        bad: list[str] = []
        for stem, data in _load_all_builtins():
            for layer in data.get("layers", []):
                for key, val in layer.get("params", {}).items():
                    if not isinstance(val, dict) or "value" not in val:
                        bad.append(
                            f"{stem}: layer {layer.get('layer_index')} param '{key}' = {val!r}"
                        )
        assert not bad, f"Found {len(bad)} non-ParamValue params:\n" + "\n".join(bad[:20])


class TestBuiltinEnrichmentValidation:
    """All enriched templates must validate against the EffectRecipe schema."""

    def test_all_templates_validate(self) -> None:
        """Every builtin JSON must pass EffectRecipe.model_validate."""
        failures: list[str] = []
        for stem, data in _load_all_builtins():
            try:
                EffectRecipe.model_validate(data)
            except Exception as exc:
                failures.append(f"{stem}: {exc}")
        assert not failures, f"Found {len(failures)} validation failures:\n" + "\n".join(
            failures[:20]
        )


class TestBuiltinEnrichmentIdempotency:
    """Enrichment must be idempotent."""

    def test_enrichment_is_idempotent(self) -> None:
        """Running enrichment on an already-enriched template produces the same result.

        We verify by checking that resolved effect types and params match
        what resolve_effect_type would produce.
        """
        for stem, data in _load_all_builtins():
            recipe_id = data["recipe_id"]
            resolved = resolve_effect_type(recipe_id)
            # The first layer should have the resolved effect type
            layers = data.get("layers", [])
            if not layers:
                continue
            first_layer = layers[0]
            effect_type = first_layer.get("effect_type", "")
            # After enrichment, the effect_type should NOT be a placeholder
            assert effect_type not in PLACEHOLDERS, (
                f"{stem}: effect_type is still placeholder {effect_type}"
            )
            # Re-resolving should give the same effect type
            # (idempotency: the enriched type should match what resolve would give)
            assert effect_type == resolved.effect_type, (
                f"{stem}: effect_type {effect_type} != resolved {resolved.effect_type}"
            )
