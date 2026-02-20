"""Phase 2 end-to-end integration test.

Verifies the full recipe pipeline:
  MinedTemplate → PromotionPipeline → RecipeCatalog → RecipeRenderer

Confirms that mined templates flow through promotion, quality gates,
recipe synthesis, catalog assembly, and multi-layer rendering with
dynamic parameter evaluation and color source resolution.
"""

from __future__ import annotations

from twinklr.core.feature_engineering.models.templates import MinedTemplate, TemplateKind
from twinklr.core.feature_engineering.promotion import PromotionPipeline
from twinklr.core.feature_engineering.style_transfer import (
    StyleBlendEvaluator,
    StyleWeightedRetrieval,
)
from twinklr.core.sequencer.display.recipe_renderer import (
    RecipeRenderer,
    RenderEnvironment,
)
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    MotifCompatibility,
    PaletteSpec,
    ParamValue,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    LaneKind,
    MotionVerb,
    VisualDepth,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mined_template(
    template_id: str,
    effect_family: str = "shimmer",
    motion_class: str = "sweep",
    energy_class: str = "mid",
    support_count: int = 20,
    cross_pack_stability: float = 0.7,
) -> MinedTemplate:
    return MinedTemplate(
        template_id=template_id,
        template_kind=TemplateKind.CONTENT,
        template_signature=f"{effect_family}|{motion_class}|palette|{energy_class}|rhythmic|single_target|rhythm_driver",
        support_count=support_count,
        distinct_pack_count=3,
        support_ratio=0.4,
        cross_pack_stability=cross_pack_stability,
        effect_family=effect_family,
        motion_class=motion_class,
        color_class="palette",
        energy_class=energy_class,
        continuity_class="sustained",
        spatial_class="single_target",
    )


def _make_builtin_recipe() -> EffectRecipe:
    """A hand-crafted builtin recipe for catalog merging."""
    from twinklr.core.sequencer.templates.group.models.template import TimingHints

    return EffectRecipe(
        recipe_id="builtin_wash_soft_v1",
        name="Soft Wash",
        description="Gentle color wash for ambient base layers",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["wash", "ambient", "base"],
        timing=TimingHints(bars_min=4, bars_max=64),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Wash",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="ColorWash",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={"Speed": ParamValue(value=0)},
                motion=[MotionVerb.FADE],
                density=0.9,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_mined_template_to_rendered_output() -> None:
    """Full pipeline: MinedTemplate → promotion → catalog → render.

    Verifies that a mined template with sufficient quality passes
    through promotion, gets synthesized into an EffectRecipe, lands
    in the RecipeCatalog, and renders to concrete layers with resolved
    parameters and colors.
    """
    # Stage 1: Promotion pipeline
    mined_good = _make_mined_template("tpl_shimmer_001", support_count=20)
    mined_bad = _make_mined_template(
        "tpl_weak_002", support_count=2, cross_pack_stability=0.1
    )

    result = PromotionPipeline().run(
        candidates=[mined_good, mined_bad],
        min_support=5,
        min_stability=0.3,
    )

    assert len(result.promoted_recipes) == 1
    promoted_recipe = result.promoted_recipes[0]
    assert isinstance(promoted_recipe, EffectRecipe)
    assert promoted_recipe.provenance.source == "mined"
    assert "tpl_shimmer_001" in promoted_recipe.provenance.mined_template_ids

    # Stage 2: Catalog assembly (merge builtins + promoted)
    builtin = _make_builtin_recipe()
    catalog = RecipeCatalog.merge(
        builtins=[builtin],
        promoted=[promoted_recipe],
    )

    assert len(catalog.recipes) == 2
    assert catalog.has_recipe(builtin.recipe_id)
    assert catalog.has_recipe(promoted_recipe.recipe_id)

    # Verify lane-based lookup works
    base_recipes = catalog.list_by_lane(LaneKind.BASE)
    assert builtin in base_recipes

    # Stage 3: Render the promoted recipe
    env = RenderEnvironment(
        energy=0.8,
        density=0.6,
        palette_colors={"primary": "#FF0000", "accent": "#00FF00"},
    )
    renderer = RecipeRenderer()
    render_result = renderer.render(promoted_recipe, env)

    assert render_result.recipe_id == promoted_recipe.recipe_id
    assert len(render_result.layers) == len(promoted_recipe.layers)
    assert len(render_result.warnings) == 0

    # Verify each rendered layer has resolved values
    for rendered_layer in render_result.layers:
        assert rendered_layer.resolved_color is not None
        assert rendered_layer.effect_type != ""


def test_multi_layer_recipe_renders_all_layers() -> None:
    """Multi-layer recipe produces correct number of rendered layers."""
    from twinklr.core.sequencer.templates.group.models.template import TimingHints

    recipe = EffectRecipe(
        recipe_id="multi_layer_test",
        name="Multi-Layer Test",
        description="Three-layer test recipe",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["test"],
        timing=TimingHints(bars_min=4, bars_max=16),
        palette_spec=PaletteSpec(
            mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]
        ),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Background",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="ColorWash",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={},
                motion=[MotionVerb.FADE],
                density=0.9,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
            RecipeLayer(
                layer_index=1,
                layer_name="Pattern",
                layer_depth=VisualDepth.MIDGROUND,
                effect_type="Bars",
                blend_mode=BlendMode.ADD,
                mix=0.7,
                params={
                    "BarCount": ParamValue(expr="energy * 12", min_val=4, max_val=16)
                },
                motion=[MotionVerb.SWEEP],
                density=0.6,
                color_source=ColorSource.PALETTE_ACCENT,
            ),
            RecipeLayer(
                layer_index=2,
                layer_name="Sparkle",
                layer_depth=VisualDepth.FOREGROUND,
                effect_type="Sparkle",
                blend_mode=BlendMode.SCREEN,
                mix=0.4,
                params={"Density": ParamValue(value=30)},
                motion=[MotionVerb.SPARKLE],
                density=0.3,
                color_source=ColorSource.WHITE_ONLY,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
    )

    env = RenderEnvironment(
        energy=0.75,
        density=0.5,
        palette_colors={"primary": "#E53935", "accent": "#43A047"},
    )
    result = RecipeRenderer().render(recipe, env)

    assert len(result.layers) == 3
    assert result.layers[0].resolved_color == "#E53935"  # primary
    assert result.layers[1].resolved_color == "#43A047"  # accent
    assert result.layers[2].resolved_color == "#FFFFFF"  # white_only

    # Dynamic param: energy * 12 = 0.75 * 12 = 9.0
    bar_count = result.layers[1].resolved_params["BarCount"]
    assert bar_count == 9.0

    # Static param passthrough
    sparkle_density = result.layers[2].resolved_params["Density"]
    assert sparkle_density == 30


def test_promotion_cluster_dedup_merges_provenance() -> None:
    """Cluster dedup merges provenance from multiple mined templates."""
    tpl_a = _make_mined_template("tpl_a")
    tpl_b = _make_mined_template("tpl_b")

    clusters = [{"cluster_id": "c1", "member_ids": ["tpl_a", "tpl_b"], "keep_id": "tpl_a"}]

    result = PromotionPipeline().run(
        candidates=[tpl_a, tpl_b],
        clusters=clusters,
    )

    # Only one recipe produced (tpl_b merged into tpl_a)
    assert len(result.promoted_recipes) == 1
    recipe = result.promoted_recipes[0]
    # Provenance should include both template IDs
    assert "tpl_a" in recipe.provenance.mined_template_ids
    assert "tpl_b" in recipe.provenance.mined_template_ids


def test_catalog_lane_filtering() -> None:
    """RecipeCatalog filters recipes by lane correctly."""
    from twinklr.core.sequencer.templates.group.models.template import TimingHints

    base_recipe = _make_builtin_recipe()  # GroupTemplateType.BASE
    rhythm_recipe = EffectRecipe(
        recipe_id="rhythm_pulse_v1",
        name="Rhythm Pulse",
        description="Beat-synced pulse",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["rhythm"],
        timing=TimingHints(bars_min=2, bars_max=16),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Pulse",
                layer_depth=VisualDepth.MIDGROUND,
                effect_type="On",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={},
                motion=[MotionVerb.PULSE],
                density=0.7,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
    )

    catalog = RecipeCatalog(recipes=[base_recipe, rhythm_recipe])

    base_results = catalog.list_by_lane(LaneKind.BASE)
    rhythm_results = catalog.list_by_lane(LaneKind.RHYTHM)
    accent_results = catalog.list_by_lane(LaneKind.ACCENT)

    assert len(base_results) == 1
    assert base_results[0].recipe_id == "builtin_wash_soft_v1"
    assert len(rhythm_results) == 1
    assert rhythm_results[0].recipe_id == "rhythm_pulse_v1"
    assert len(accent_results) == 0


def test_motif_compatibility_on_recipe() -> None:
    """MotifCompatibility scores are preserved through catalog operations."""
    from twinklr.core.sequencer.templates.group.models.template import TimingHints

    recipe = EffectRecipe(
        recipe_id="motif_test",
        name="Motif Test",
        description="Recipe with motif compatibility",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["test"],
        timing=TimingHints(bars_min=4, bars_max=16),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Base",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="ColorWash",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={},
                motion=[MotionVerb.FADE],
                density=0.8,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
        motif_compatibility=[
            MotifCompatibility(motif_id="grid", score=0.9, reason="Grid pattern match"),
            MotifCompatibility(motif_id="wave", score=0.4, reason="Weak wave match"),
        ],
    )

    catalog = RecipeCatalog(recipes=[recipe])
    retrieved = catalog.get_recipe("motif_test")
    assert retrieved is not None
    assert len(retrieved.motif_compatibility) == 2
    best = max(retrieved.motif_compatibility, key=lambda m: m.score)
    assert best.motif_id == "grid"
    assert best.score == 0.9


def test_style_weighted_retrieval_with_catalog() -> None:
    """StyleWeightedRetrieval ranks catalog recipes by style affinity."""
    from twinklr.core.feature_engineering.models.style import (
        ColorStyleProfile,
        LayeringStyleProfile,
        StyleFingerprint,
        TimingStyleProfile,
        TransitionStyleProfile,
    )

    builtin = _make_builtin_recipe()

    # Create a recipe with style markers for better scoring
    from twinklr.core.sequencer.templates.group.models.template import TimingHints

    styled_recipe = EffectRecipe(
        recipe_id="styled_shimmer_v1",
        name="Styled Shimmer",
        description="Shimmer with style markers",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["shimmer"],
        timing=TimingHints(bars_min=4, bars_max=32),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Shimmer",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="Shimmer",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={},
                motion=[MotionVerb.SHIMMER],
                density=0.7,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=0.5, energy_affinity=EnergyTarget.MED),
    )

    catalog = RecipeCatalog(recipes=[builtin, styled_recipe])

    style = StyleFingerprint(
        creator_id="test_creator",
        recipe_preferences={"shimmer": 0.9},
        transition_style=TransitionStyleProfile(
            preferred_gap_ms=50.0, overlap_tendency=0.3, variety_score=0.5
        ),
        color_tendencies=ColorStyleProfile(
            palette_complexity=0.5, contrast_preference=0.5, temperature_preference=0.5
        ),
        timing_style=TimingStyleProfile(
            beat_alignment_strictness=0.5, density_preference=0.65, section_change_aggression=0.5
        ),
        layering_style=LayeringStyleProfile(
            mean_layers=1.0, max_layers=2, blend_mode_preference="normal"
        ),
        corpus_sequence_count=10,
    )

    retrieval = StyleWeightedRetrieval()
    scored = retrieval.rank(catalog, style)

    assert len(scored) == 2
    # Shimmer recipe should rank higher due to effect_family match
    assert scored[0].recipe.recipe_id == "styled_shimmer_v1"
    assert scored[0].score > scored[1].score
