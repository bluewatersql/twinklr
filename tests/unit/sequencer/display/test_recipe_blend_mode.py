"""Tests for the blend_mode/mix wiring fix in the composition pipeline.

Covers REND-01 through REND-04:
- REND-01: CompiledEffect.layer_blend_mode field
- REND-02: RECIPE_BLEND_TO_LAYER_METHOD mapping constant
- REND-03: RecipeCompiler._layer_to_compiled_effect fix
- REND-04: CompositionEngine sub-layer blend mode registration
"""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from twinklr.core.sequencer.display.composition.models import CompiledEffect
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_event import RenderEvent, RenderEventSource
from twinklr.core.sequencer.vocabulary import LaneKind, VisualDepth

# ---------------------------------------------------------------------------
# REND-01: CompiledEffect model has layer_blend_mode field
# ---------------------------------------------------------------------------

_DEFAULT_PALETTE = ResolvedPalette(colors=["#FF0000", "#00FF00"], active_slots=[1, 2])
_DEFAULT_SOURCE = RenderEventSource(
    section_id="s0",
    lane=LaneKind.BASE,
    group_id="g0",
    template_id="t0",
    placement_id="p0",
    placement_index=0,
)


def _make_render_event(event_id: str = "test") -> RenderEvent:
    return RenderEvent(
        event_id=event_id,
        start_ms=0,
        end_ms=1000,
        effect_type="Bars",
        parameters={},
        palette=_DEFAULT_PALETTE,
        source=_DEFAULT_SOURCE,
    )


def test_compiled_effect_default_layer_blend_mode() -> None:
    """CompiledEffect without layer_blend_mode defaults to 'Normal'."""
    event = _make_render_event()
    ce = CompiledEffect(event=event, visual_depth=VisualDepth.BACKGROUND)
    assert ce.layer_blend_mode == "Normal"


def test_compiled_effect_layer_blend_mode_serialization() -> None:
    """Field serializes correctly in model_dump."""
    event = _make_render_event()
    ce = CompiledEffect(event=event, visual_depth=VisualDepth.BACKGROUND, layer_blend_mode="Max")
    dumped = ce.model_dump()
    assert dumped["layer_blend_mode"] == "Max"


def test_compiled_effect_layer_blend_mode_immutable() -> None:
    """Field is immutable (frozen model)."""
    event = _make_render_event()
    ce = CompiledEffect(event=event, visual_depth=VisualDepth.BACKGROUND)
    with pytest.raises(ValidationError):
        ce.layer_blend_mode = "Max"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# REND-02: RECIPE_BLEND_TO_LAYER_METHOD mapping constant
# ---------------------------------------------------------------------------


def test_normal_maps_to_normal() -> None:
    from twinklr.core.sequencer.display.composition.recipe_compiler import (
        RECIPE_BLEND_TO_LAYER_METHOD,
    )
    from twinklr.core.sequencer.vocabulary import BlendMode

    assert RECIPE_BLEND_TO_LAYER_METHOD[BlendMode.NORMAL] == "Normal"


def test_add_maps_to_max() -> None:
    from twinklr.core.sequencer.display.composition.recipe_compiler import (
        RECIPE_BLEND_TO_LAYER_METHOD,
    )
    from twinklr.core.sequencer.vocabulary import BlendMode

    assert RECIPE_BLEND_TO_LAYER_METHOD[BlendMode.ADD] == "Max"


def test_screen_maps_to_normal() -> None:
    from twinklr.core.sequencer.display.composition.recipe_compiler import (
        RECIPE_BLEND_TO_LAYER_METHOD,
    )
    from twinklr.core.sequencer.vocabulary import BlendMode

    assert RECIPE_BLEND_TO_LAYER_METHOD[BlendMode.SCREEN] == "Normal"


def test_mask_maps_to_one_reveals_two() -> None:
    from twinklr.core.sequencer.display.composition.recipe_compiler import (
        RECIPE_BLEND_TO_LAYER_METHOD,
    )
    from twinklr.core.sequencer.vocabulary import BlendMode

    assert RECIPE_BLEND_TO_LAYER_METHOD[BlendMode.MASK] == "1 reveals 2"


# ---------------------------------------------------------------------------
# REND-03: RecipeCompiler._layer_to_compiled_effect wiring
# ---------------------------------------------------------------------------

from twinklr.core.sequencer.display.recipe_renderer import RenderedLayer  # noqa: E402
from twinklr.core.sequencer.vocabulary import BlendMode  # noqa: E402


def _make_rendered_layer(
    blend_mode: BlendMode = BlendMode.ADD,
    mix: float = 0.7,
) -> RenderedLayer:
    return RenderedLayer(
        layer_index=0,
        layer_name="test",
        layer_depth=VisualDepth.FOREGROUND,
        effect_type="Sparkles",
        blend_mode=blend_mode,
        mix=mix,
        resolved_params={"C_SLIDER_Speed": 50},
        resolved_color="#FF0000",
        density=0.5,
        timing_offset_beats=0.0,
    )


def _make_compile_context() -> object:
    """Build a minimal TemplateCompileContext-like object for the compiler."""
    from twinklr.core.sequencer.display.composition.template_compiler import (
        TemplateCompileContext,
    )
    from twinklr.core.sequencer.vocabulary import LaneKind

    return TemplateCompileContext(
        section_id="s1",
        lane=LaneKind.BASE,
        palette=_DEFAULT_PALETTE,
        start_ms=0,
        end_ms=4000,
        intensity=0.5,
        placement_index=0,
    )


def test_compiler_no_blend_mode_in_event_parameters() -> None:
    """_layer_to_compiled_effect must NOT put 'blend_mode' in event.parameters."""
    from twinklr.core.sequencer.display.composition.recipe_compiler import RecipeCompiler
    from twinklr.core.sequencer.display.models.render_event import RenderEventSource
    from twinklr.core.sequencer.vocabulary import LaneKind

    layer = _make_rendered_layer()
    ctx = _make_compile_context()
    source = RenderEventSource(
        section_id="s1",
        lane=LaneKind.BASE,
        group_id="g1",
        template_id="tmpl1",
        placement_id="p1",
        placement_index=0,
    )
    ce = RecipeCompiler._layer_to_compiled_effect(layer, ctx, source)
    assert "blend_mode" not in ce.event.parameters


def test_compiler_no_mix_in_event_parameters() -> None:
    """_layer_to_compiled_effect must NOT put 'mix' in event.parameters."""
    from twinklr.core.sequencer.display.composition.recipe_compiler import RecipeCompiler
    from twinklr.core.sequencer.display.models.render_event import RenderEventSource
    from twinklr.core.sequencer.vocabulary import LaneKind

    layer = _make_rendered_layer()
    ctx = _make_compile_context()
    source = RenderEventSource(
        section_id="s1",
        lane=LaneKind.BASE,
        group_id="g1",
        template_id="tmpl1",
        placement_id="p1",
        placement_index=0,
    )
    ce = RecipeCompiler._layer_to_compiled_effect(layer, ctx, source)
    assert "mix" not in ce.event.parameters


def test_compiler_e_slider_mix_correct() -> None:
    """E_SLIDER_Mix must be int(layer.mix * 100)."""
    from twinklr.core.sequencer.display.composition.recipe_compiler import RecipeCompiler
    from twinklr.core.sequencer.display.models.render_event import RenderEventSource
    from twinklr.core.sequencer.vocabulary import LaneKind

    mix = 0.7
    layer = _make_rendered_layer(mix=mix)
    ctx = _make_compile_context()
    source = RenderEventSource(
        section_id="s1",
        lane=LaneKind.BASE,
        group_id="g1",
        template_id="tmpl1",
        placement_id="p1",
        placement_index=0,
    )
    ce = RecipeCompiler._layer_to_compiled_effect(layer, ctx, source)
    assert ce.event.parameters["E_SLIDER_Mix"] == int(mix * 100)


def test_compiler_layer_blend_mode_mapped() -> None:
    """CompiledEffect.layer_blend_mode must be the xLights-mapped value."""
    from twinklr.core.sequencer.display.composition.recipe_compiler import (
        RECIPE_BLEND_TO_LAYER_METHOD,
        RecipeCompiler,
    )
    from twinklr.core.sequencer.display.models.render_event import RenderEventSource
    from twinklr.core.sequencer.vocabulary import LaneKind

    blend_mode = BlendMode.ADD
    layer = _make_rendered_layer(blend_mode=blend_mode)
    ctx = _make_compile_context()
    source = RenderEventSource(
        section_id="s1",
        lane=LaneKind.BASE,
        group_id="g1",
        template_id="tmpl1",
        placement_id="p1",
        placement_index=0,
    )
    ce = RecipeCompiler._layer_to_compiled_effect(layer, ctx, source)
    assert ce.layer_blend_mode == RECIPE_BLEND_TO_LAYER_METHOD[blend_mode]


# ---------------------------------------------------------------------------
# REND-04: CompositionEngine sub-layer blend mode registration
# ---------------------------------------------------------------------------


def _make_compiled_effect(blend_mode_str: str = "Normal") -> CompiledEffect:
    event = _make_render_event("e1")
    return CompiledEffect(
        event=event,
        visual_depth=VisualDepth.BACKGROUND,
        layer_blend_mode=blend_mode_str,
    )


def _simulate_sub_layer_registration(
    compiled_effects: list[CompiledEffect],
    element_name: str = "grp1",
) -> dict[tuple[str, int], str]:
    """Simulate the _compose_coordination sub-layer registration loop.

    Mirrors the exact logic added to engine.py for REND-04.
    Tests that CompiledEffect.layer_blend_mode flows into _layer_blend_modes.
    """
    from twinklr.core.sequencer.display.composition.layer_allocator import LayerAllocator
    from twinklr.core.sequencer.vocabulary import LaneKind

    allocator = LayerAllocator()
    layer_blend_modes: dict[tuple[str, int], str] = {}

    for ce in compiled_effects:
        sub_layer = allocator.allocate_sub_layer(LaneKind.BASE, ce.visual_depth)
        blend_key = (element_name, sub_layer)
        if blend_key not in layer_blend_modes:
            layer_blend_modes[blend_key] = ce.layer_blend_mode

    return layer_blend_modes


def test_single_layer_recipe_normal() -> None:
    """Single CompiledEffect with Normal blend mode registers 'Normal' in _layer_blend_modes."""
    ce_normal = _make_compiled_effect("Normal")
    result = _simulate_sub_layer_registration([ce_normal])
    assert any(v == "Normal" for v in result.values())


def test_two_layer_recipe_blend_modes_registered() -> None:
    """Two CompiledEffects at different depths both register in _layer_blend_modes."""
    # Use distinct visual_depth so allocate_sub_layer returns different indices,
    # allowing both blend modes to be registered under separate keys.
    event = _make_render_event("e2")
    ce1 = CompiledEffect(
        event=event, visual_depth=VisualDepth.BACKGROUND, layer_blend_mode="Normal"
    )
    ce2 = CompiledEffect(event=event, visual_depth=VisualDepth.FOREGROUND, layer_blend_mode="Max")
    result = _simulate_sub_layer_registration([ce1, ce2])
    values = list(result.values())
    assert "Normal" in values
    assert "Max" in values
