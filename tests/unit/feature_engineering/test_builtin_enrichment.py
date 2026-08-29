"""Tests for builtin group-template effect resolution.

These validate the **tracked** seed catalog (`catalog/templates/builtins/`), which
is what production loads after P1K-T3 repointed every call site away from the legacy,
gitignored `data/templates/`. Tracked recipes intentionally store the sentinel
``effect_type: "PLACEHOLDER"`` and are resolved to a concrete xLights effect at compile
time via ``effect_map.resolve_effect_type``; these tests therefore assert on the
**resolved** effect, not on a pre-baked stored value.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from twinklr.core.sequencer.display.templates.effect_map import resolve_effect_type
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe

# Placeholder effect_type sentinels that must resolve to a concrete effect at runtime.
PLACEHOLDERS = frozenset(
    {"ABSTRACT", "GEOMETRIC", "IMAGERY", "TEXTURE", "HYBRID", "ORGANIC", "PLACEHOLDER"}
)

# Known xLights effect names the resolver is allowed to produce.
KNOWN_EFFECTS = frozenset(
    {
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
        "Pinwheel",
    }
)

# Tracked seed catalog (committed), not the gitignored `data/templates/` overlay.
_BUILTINS_DIR = Path(__file__).resolve().parents[3] / "catalog" / "templates" / "builtins"


def _load_all_builtins() -> list[tuple[str, dict[str, Any]]]:
    """Load every tracked builtin recipe JSON file."""
    results: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(_BUILTINS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        results.append((path.stem, data))
    return results


class TestBuiltinEffectResolution:
    """Every tracked recipe id must resolve to a concrete, known xLights effect."""

    def test_every_recipe_resolves_to_non_placeholder(self) -> None:
        violations: list[str] = []
        for stem, data in _load_all_builtins():
            resolved = resolve_effect_type(data["recipe_id"]).effect_type
            if resolved in PLACEHOLDERS:
                violations.append(f"{stem}: resolved to placeholder {resolved}")
        assert not violations, "Recipes resolving to a placeholder:\n" + "\n".join(violations[:20])

    def test_resolved_effect_types_are_known(self) -> None:
        unknown: list[str] = []
        for stem, data in _load_all_builtins():
            resolved = resolve_effect_type(data["recipe_id"]).effect_type
            if resolved not in KNOWN_EFFECTS:
                unknown.append(f"{stem}: {resolved}")
        assert not unknown, "Recipes resolving to unknown effects:\n" + "\n".join(unknown[:20])


class TestBuiltinRecipeStructure:
    """Tracked recipe files must be well-formed and load as EffectRecipe."""

    def test_all_recipes_validate(self) -> None:
        failures: list[str] = []
        for stem, data in _load_all_builtins():
            try:
                EffectRecipe.model_validate(data)
            except Exception as exc:
                failures.append(f"{stem}: {exc}")
        assert not failures, "EffectRecipe validation failures:\n" + "\n".join(failures[:20])

    def test_params_use_param_value_format(self) -> None:
        bad: list[str] = []
        for stem, data in _load_all_builtins():
            for layer in data.get("layers", []):
                for key, val in layer.get("params", {}).items():
                    if not isinstance(val, dict) or "value" not in val:
                        bad.append(
                            f"{stem}: layer {layer.get('layer_index')} param '{key}' = {val!r}"
                        )
        assert not bad, "Non-ParamValue params:\n" + "\n".join(bad[:20])


class TestBuiltinResolutionIdempotency:
    """Effect resolution is deterministic (idempotent) for tracked recipes."""

    def test_resolution_is_deterministic(self) -> None:
        for _stem, data in _load_all_builtins():
            recipe_id = data["recipe_id"]
            first = resolve_effect_type(recipe_id)
            second = resolve_effect_type(recipe_id)
            assert first.effect_type == second.effect_type
            assert first.defaults == second.defaults
