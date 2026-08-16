"""P3-T2 admission tests for recipe effect types."""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.display.composition.models import TemplateCompileError
from twinklr.core.sequencer.display.composition.recipe_compiler import RecipeCompiler
from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers
from twinklr.core.sequencer.display.effects.handlers.on import OnHandler
from twinklr.core.sequencer.display.effects.registry import HandlerRegistry
from twinklr.core.sequencer.display.renderer import DisplayRenderer
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

from .composition.test_recipe_compiler import _make_context, _make_placement, _make_recipe


def test_unknown_effect_type_rejected_at_admission() -> None:
    registry = load_builtin_handlers()
    recipe = _make_recipe(recipe_id="recipe_bad_type")
    bad_layer = recipe.layers[0].model_copy(update={"effect_type": "Twinkler"})
    recipe = recipe.model_copy(update={"layers": (bad_layer,)})
    compiler = RecipeCompiler(
        catalog=RecipeCatalog(recipes=[recipe]),
        handler_registry=registry,
    )

    with pytest.raises(TemplateCompileError) as caught:
        compiler.compile(_make_placement("recipe_bad_type"), _make_context())

    message = str(caught.value)
    assert "Twinkler" in message
    assert "recipe_bad_type" in message
    assert "Twinkle" in message


def test_known_effect_types_admitted() -> None:
    registry = load_builtin_handlers()
    for effect_type in registry.registered_types:
        recipe_id = f"recipe_{effect_type.lower().replace(' ', '_')}"
        recipe = _make_recipe(recipe_id=recipe_id)
        layer = recipe.layers[0].model_copy(update={"effect_type": effect_type})
        recipe = recipe.model_copy(update={"layers": (layer,)})
        compiler = RecipeCompiler(
            catalog=RecipeCatalog(recipes=[recipe]),
            handler_registry=registry,
        )

        effects = compiler.compile(_make_placement(recipe_id), _make_context())

        assert effects[0].event.effect_type == effect_type


def test_placeholder_resolution_keeps_structured_substitution_provenance() -> None:
    recipe = _make_recipe(recipe_id="recipe_without_mapping")
    layer = recipe.layers[0].model_copy(update={"effect_type": "PLACEHOLDER"})
    recipe = recipe.model_copy(update={"layers": (layer,)})
    compiler = RecipeCompiler(catalog=RecipeCatalog(recipes=[recipe]))

    effect = compiler.compile(_make_placement("recipe_without_mapping"), _make_context())[0].event

    assert effect.effect_type == "On"
    assert effect.effect_substitution is not None
    assert effect.effect_substitution.model_dump() == {
        "requested_effect_type": "PLACEHOLDER",
        "substituted_effect_type": "On",
        "reason": "placeholder effect type resolved from template id",
    }


def test_recipe_compiler_can_bind_the_exact_runtime_registry() -> None:
    recipe = _make_recipe()
    compiler = RecipeCompiler(catalog=RecipeCatalog(recipes=[recipe]))
    runtime_registry = HandlerRegistry()
    runtime_registry.register(OnHandler())
    compiler.use_handler_registry(runtime_registry)

    assert compiler.handler_registry is runtime_registry
    with pytest.raises(TemplateCompileError, match="Color Wash"):
        compiler.compile(_make_placement(), _make_context())


def test_display_renderer_shares_runtime_registry_with_recipe_admission() -> None:
    recipe = _make_recipe()
    compiler = RecipeCompiler(catalog=RecipeCatalog(recipes=[recipe]))
    runtime_registry = HandlerRegistry()
    grid = BeatGrid(
        bar_boundaries=[0.0, 2000.0],
        beat_boundaries=[0.0, 500.0, 1000.0, 1500.0, 2000.0],
        eighth_boundaries=[],
        sixteenth_boundaries=[],
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=2000.0,
    )

    DisplayRenderer(
        beat_grid=grid,
        choreo_graph=ChoreographyGraph(
            graph_id="registry-test",
            groups=[ChoreoGroup(id="G0", role="ARCHES")],
        ),
        handler_registry=runtime_registry,
        template_compiler=compiler,
    )

    assert compiler.handler_registry is runtime_registry


def test_recipe_compiler_preserves_an_empty_custom_registry() -> None:
    registry = HandlerRegistry()

    compiler = RecipeCompiler(
        catalog=RecipeCatalog(recipes=[_make_recipe()]),
        handler_registry=registry,
    )

    assert compiler.handler_registry is registry
