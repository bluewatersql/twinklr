"""Tests for the DefaultTemplateCompiler."""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.display.composition.models import (
    TemplateCompileError,
)
from twinklr.core.sequencer.display.composition.template_compiler import (
    DefaultTemplateCompiler,
    TemplateCompileContext,
)
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.templates.group.library import (
    GroupTemplateRegistry,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    GroupPlacement,
    PlanTarget,
)
from twinklr.core.sequencer.templates.group.models.template import (
    GroupConstraints,
    GroupPlanTemplate,
    LayerRecipe,
    ProjectionSpec,
)
from twinklr.core.sequencer.vocabulary import (
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    LaneKind,
    MotionVerb,
    PlanningTimeRef,
    ProjectionIntent,
    VisualDepth,
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType

# ------------------------------------------------------------------
# Test helpers
# ------------------------------------------------------------------


def _make_registry(templates: list[GroupPlanTemplate] | None = None) -> GroupTemplateRegistry:
    """Build a registry from a list of templates."""
    reg = GroupTemplateRegistry()
    for tpl in templates or []:
        # Need to capture tpl in closure for factory
        def factory(t: GroupPlanTemplate = tpl) -> GroupPlanTemplate:
            return t

        reg.register(factory)
    return reg


def _make_template(
    template_id: str = "gtpl_test_wash",
    layer_recipes: list[LayerRecipe] | None = None,
) -> GroupPlanTemplate:
    """Build a minimal GroupPlanTemplate for testing."""
    if layer_recipes is None:
        layer_recipes = [
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash", "gradient"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.NONE],
                density=0.5,
                contrast=0.5,
                color_mode=ColorMode.ANALOGOUS,
            ),
        ]
    return GroupPlanTemplate(
        template_id=template_id,
        name=f"Test {template_id}",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        constraints=GroupConstraints(max_layers=max(len(layer_recipes), 1)),
        layer_recipe=layer_recipes,
    )


def _make_placement(template_id: str = "gtpl_test_wash") -> GroupPlacement:
    """Build a minimal GroupPlacement for testing."""
    return GroupPlacement(
        placement_id="p-1",
        target=PlanTarget(type=TargetType.GROUP, id="ARCHES"),
        template_id=template_id,
        start=PlanningTimeRef(bar=1, beat=1),
    )


def _make_context() -> TemplateCompileContext:
    """Build a minimal TemplateCompileContext."""
    return TemplateCompileContext(
        section_id="verse_1",
        lane=LaneKind.BASE,
        palette=ResolvedPalette(colors=["#FF0000", "#00FF00"], active_slots=[1, 2]),
        start_ms=0,
        end_ms=4000,
        intensity=0.8,
        placement_index=0,
    )


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestDefaultTemplateCompiler:
    """Tests for DefaultTemplateCompiler."""

    def test_single_layer_template(self) -> None:
        """Single layer recipe produces one CompiledEffect."""
        tpl = _make_template()
        registry = _make_registry([tpl])
        compiler = DefaultTemplateCompiler(registry)

        results = compiler.compile(_make_placement(), _make_context())

        assert len(results) == 1
        assert results[0].event.effect_type == "Color Wash"
        assert results[0].visual_depth == VisualDepth.BACKGROUND

    def test_multi_layer_template(self) -> None:
        """Multi-layer template produces multiple CompiledEffects."""
        recipes = [
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.3,
                contrast=0.3,
                color_mode=ColorMode.ANALOGOUS,
            ),
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["sparkles", "confetti"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SHIMMER],
                density=0.8,
                contrast=0.7,
                color_mode=ColorMode.FULL_SPECTRUM,
            ),
        ]
        tpl = _make_template("gtpl_test_multi", recipes)
        registry = _make_registry([tpl])
        compiler = DefaultTemplateCompiler(registry)

        results = compiler.compile(_make_placement("gtpl_test_multi"), _make_context())

        assert len(results) == 2
        # First is background wash
        assert results[0].visual_depth == VisualDepth.BACKGROUND
        assert results[0].event.effect_type == "Color Wash"
        assert "Brightness" in results[0].event.value_curves  # PULSE curve
        # Second is foreground sparkles
        assert results[1].visual_depth == VisualDepth.FOREGROUND
        assert results[1].event.effect_type == "Twinkle"
        assert "Speed" in results[1].event.value_curves  # SHIMMER curve

    def test_template_not_found_raises(self) -> None:
        """Missing template raises TemplateCompileError."""
        registry = _make_registry([])
        compiler = DefaultTemplateCompiler(registry)

        with pytest.raises(TemplateCompileError, match="not found in registry"):
            compiler.compile(_make_placement("gtpl_nonexistent"), _make_context())

    def test_empty_layer_recipe_raises(self) -> None:
        """Empty layer_recipe raises TemplateCompileError."""
        tpl = _make_template("gtpl_empty", layer_recipes=[])
        registry = _make_registry([tpl])
        compiler = DefaultTemplateCompiler(registry)

        with pytest.raises(TemplateCompileError, match="empty layer_recipe"):
            compiler.compile(_make_placement("gtpl_empty"), _make_context())

    def test_unrecognised_motif_raises(self) -> None:
        """Unrecognised motifs in LayerRecipe raise TemplateCompileError."""
        bad_recipe = LayerRecipe(
            layer=VisualDepth.MIDGROUND,
            motifs=["disco_ball", "laser_beam"],
            visual_intent=GroupVisualIntent.ABSTRACT,
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            color_mode=ColorMode.MONOCHROME,
        )
        tpl = _make_template("gtpl_bad_motif", [bad_recipe])
        registry = _make_registry([tpl])
        compiler = DefaultTemplateCompiler(registry)

        with pytest.raises(TemplateCompileError, match="No recognised motif"):
            compiler.compile(_make_placement("gtpl_bad_motif"), _make_context())

    def test_event_ids_include_layer_index(self) -> None:
        """Each CompiledEffect has a unique event_id with layer index."""
        recipes = [
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.NONE],
                density=0.5,
                contrast=0.5,
                color_mode=ColorMode.ANALOGOUS,
            ),
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["sparkles"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.NONE],
                density=0.5,
                contrast=0.5,
                color_mode=ColorMode.FULL_SPECTRUM,
            ),
        ]
        tpl = _make_template("gtpl_ids", recipes)
        registry = _make_registry([tpl])
        compiler = DefaultTemplateCompiler(registry)

        results = compiler.compile(_make_placement("gtpl_ids"), _make_context())

        assert results[0].event.event_id.endswith("_L0")
        assert results[1].event.event_id.endswith("_L1")

    def test_timing_from_context(self) -> None:
        """Compiled effects inherit timing from context."""
        tpl = _make_template()
        registry = _make_registry([tpl])
        compiler = DefaultTemplateCompiler(registry)
        ctx = _make_context()

        results = compiler.compile(_make_placement(), ctx)

        assert results[0].event.start_ms == 0
        assert results[0].event.end_ms == 4000

    def test_traceability_source(self) -> None:
        """Source field preserves section/lane/group/template traceability."""
        tpl = _make_template()
        registry = _make_registry([tpl])
        compiler = DefaultTemplateCompiler(registry)

        results = compiler.compile(_make_placement(), _make_context())
        src = results[0].event.source

        assert src.section_id == "verse_1"
        assert src.lane == LaneKind.BASE
        assert src.group_id == "ARCHES"
        assert src.template_id == "gtpl_test_wash"

    def test_param_overrides_merged(self) -> None:
        """Valid param_overrides from placement are merged into parameters."""
        tpl = _make_template()
        registry = _make_registry([tpl])
        compiler = DefaultTemplateCompiler(registry)
        placement = GroupPlacement(
            placement_id="p-ovr",
            target=PlanTarget(type=TargetType.GROUP, id="ARCHES"),
            template_id="gtpl_test_wash",
            start=PlanningTimeRef(bar=1, beat=1),
            param_overrides={"speed": 80},  # Valid for Color Wash
        )

        results = compiler.compile(placement, _make_context())
        assert results[0].event.parameters["speed"] == 80

    def test_invalid_param_overrides_filtered(self) -> None:
        """Invalid param_overrides from placement are silently filtered."""
        tpl = _make_template()
        registry = _make_registry([tpl])
        compiler = DefaultTemplateCompiler(registry)
        placement = GroupPlacement(
            placement_id="p-bad",
            target=PlanTarget(type=TargetType.GROUP, id="ARCHES"),
            template_id="gtpl_test_wash",
            start=PlanningTimeRef(bar=1, beat=1),
            param_overrides={"motif_bias": "sparkly"},  # Not a handler param
        )

        results = compiler.compile(placement, _make_context())
        assert "motif_bias" not in results[0].event.parameters

    def test_compiler_satisfies_protocol(self) -> None:
        """DefaultTemplateCompiler satisfies TemplateCompiler protocol."""
        from twinklr.core.sequencer.display.composition.template_compiler import (
            TemplateCompiler,
        )

        registry = _make_registry([])
        compiler = DefaultTemplateCompiler(registry)
        assert isinstance(compiler, TemplateCompiler)


class TestDiverseEffectTypes:
    """Verify that different motifs produce diverse xLights effects."""

    @pytest.fixture
    def compiler(self) -> DefaultTemplateCompiler:
        """Compiler with templates spanning multiple effect types."""
        templates = [
            _make_template(
                "gtpl_fan",
                [
                    LayerRecipe(
                        layer=VisualDepth.FOREGROUND,
                        motifs=["radial_rays"],
                        visual_intent=GroupVisualIntent.ABSTRACT,
                        motion=[MotionVerb.PULSE],
                        density=0.6,
                        contrast=0.7,
                        color_mode=ColorMode.FULL_SPECTRUM,
                    ),
                ],
            ),
            _make_template(
                "gtpl_snow",
                [
                    LayerRecipe(
                        layer=VisualDepth.BACKGROUND,
                        motifs=["snowflakes"],
                        visual_intent=GroupVisualIntent.ORGANIC,
                        motion=[MotionVerb.NONE],
                        density=0.4,
                        contrast=0.3,
                        color_mode=ColorMode.MONOCHROME,
                    ),
                ],
            ),
            _make_template(
                "gtpl_meteor",
                [
                    LayerRecipe(
                        layer=VisualDepth.MIDGROUND,
                        motifs=["light_trails"],
                        visual_intent=GroupVisualIntent.ABSTRACT,
                        motion=[MotionVerb.CHASE],
                        density=0.5,
                        contrast=0.6,
                        color_mode=ColorMode.ANALOGOUS,
                    ),
                ],
            ),
        ]
        return DefaultTemplateCompiler(_make_registry(templates))

    def test_fan_template(self, compiler: DefaultTemplateCompiler) -> None:
        r = compiler.compile(_make_placement("gtpl_fan"), _make_context())
        assert r[0].event.effect_type == "Fan"

    def test_snow_template(self, compiler: DefaultTemplateCompiler) -> None:
        r = compiler.compile(_make_placement("gtpl_snow"), _make_context())
        assert r[0].event.effect_type == "Snowflakes"

    def test_meteor_template(self, compiler: DefaultTemplateCompiler) -> None:
        r = compiler.compile(_make_placement("gtpl_meteor"), _make_context())
        assert r[0].event.effect_type == "Meteors"
        # CHASE motion should produce a Speed curve
        assert "Speed" in r[0].event.value_curves
