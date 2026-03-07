"""Tests for scripts/build/backfill_template_metadata.py.

TDD: tests written before implementation.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from twinklr.core.feature_engineering.models.motifs import (
    MinedMotif,
    MotifCatalog,
)
from twinklr.core.feature_engineering.models.propensity import (
    EffectModelAffinity,
    PropensityIndex,
)
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    EffectRecipe,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    VisualDepth,
)


def _load_module():
    """Load the backfill_template_metadata script module."""
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "scripts" / "build" / "backfill_template_metadata.py"
    spec = importlib.util.spec_from_file_location("backfill_template_metadata", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_propensity_index() -> PropensityIndex:
    """Build a minimal PropensityIndex fixture with known entries."""
    return PropensityIndex(
        schema_version="v1.0.0",
        affinities=(
            EffectModelAffinity(
                effect_family="spirals",
                model_type="megatree",
                frequency=0.8,
                exclusivity=0.6,
                corpus_support=50,
            ),
            EffectModelAffinity(
                effect_family="spirals",
                model_type="arch",
                frequency=0.4,
                exclusivity=0.3,
                corpus_support=20,
            ),
            EffectModelAffinity(
                effect_family="spirals",
                model_type="matrix",
                frequency=0.9,
                exclusivity=0.9,
                corpus_support=100,
            ),
            EffectModelAffinity(
                effect_family="on",
                model_type="pixel_prop",
                frequency=0.7,
                exclusivity=0.5,
                corpus_support=30,
            ),
        ),
        anti_affinities=(),
    )


def _make_motif_catalog() -> MotifCatalog:
    """Build a minimal MotifCatalog fixture."""
    return MotifCatalog(
        schema_version="v2.0.0",
        miner_version="1.0.0",
        total_sequences=100,
        total_motifs=5,
        min_support_count=3,
        min_distinct_pack_count=2,
        min_distinct_sequence_count=2,
        motifs=(
            MinedMotif(
                motif_id="motif_spirals_001",
                motif_signature="spirals|WIPE|HIGH",
                bar_span=2,
                support_count=15,
                distinct_pack_count=5,
                distinct_sequence_count=8,
                template_ids=(),
                taxonomy_labels=("spirals", "wipe"),
                occurrences=(),
            ),
            MinedMotif(
                motif_id="motif_bars_001",
                motif_signature="bars|PULSE|MEDIUM",
                bar_span=1,
                support_count=8,
                distinct_pack_count=3,
                distinct_sequence_count=4,
                template_ids=(),
                taxonomy_labels=("bars", "pulse"),
                occurrences=(),
            ),
        ),
    )


def _make_layer(layer_index: int = 0, effect_type: str = "Spirals") -> RecipeLayer:
    """Build a minimal RecipeLayer."""
    return RecipeLayer(
        layer_index=layer_index,
        layer_name=f"Layer{layer_index}",
        layer_depth=VisualDepth.FOREGROUND,
        effect_type=effect_type,
        blend_mode=BlendMode.NORMAL,
        mix=1.0,
        density=0.5,
        color_source="palette_primary",
    )


def _make_recipe(
    recipe_id: str = "test_recipe_001",
    effect_type: str = "Spirals",
    tags: list[str] | None = None,
    curator_notes: str | None = None,
) -> EffectRecipe:
    """Build a minimal EffectRecipe."""
    return EffectRecipe(
        recipe_id=recipe_id,
        name="Test Recipe",
        description="Test",
        recipe_version="1.0.0",
        effect_family="spirals",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=tags or ["test"],
        timing=TimingHints(
            bars_min=1,
            bars_max=4,
            beats_per_bar=None,
            loop_len_ms=None,
            emphasize_downbeats=False,
        ),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(_make_layer(0, effect_type=effect_type),),
        provenance=RecipeProvenance(source="builtin", curator_notes=curator_notes),
        style_markers=StyleMarkers(
            complexity=0.3,
            energy_affinity=EnergyTarget.MED,
        ),
    )


# ---------------------------------------------------------------------------
# Test 1: lookup_affinities with known effect type → list of results
# ---------------------------------------------------------------------------


def test_lookup_affinities_known_effect_type() -> None:
    """lookup_affinities for a known effect family returns at least one result."""
    module = _load_module()
    propensity = _make_propensity_index()
    results = module.lookup_affinities("Spirals", propensity)
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# Test 2: lookup_affinities with unknown effect type → empty list
# ---------------------------------------------------------------------------


def test_lookup_affinities_unknown_effect_type() -> None:
    """lookup_affinities for an unknown effect family returns empty list."""
    module = _load_module()
    propensity = _make_propensity_index()
    results = module.lookup_affinities("UnknownEffect", propensity)
    assert results == []


# ---------------------------------------------------------------------------
# Test 3: lookup_affinities returns top-N sorted by score descending
# ---------------------------------------------------------------------------


def test_lookup_affinities_sorted_by_score_desc() -> None:
    """lookup_affinities results are sorted by score descending."""
    module = _load_module()
    propensity = _make_propensity_index()
    results = module.lookup_affinities("Spirals", propensity, top_n=10)
    scores = [r.affinity_score for r in results]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Test 4: lookup_motif_compatibility matching effect_type → returns motif
# ---------------------------------------------------------------------------


def test_lookup_motif_compatibility_matching_effect_type() -> None:
    """lookup_motif_compatibility finds motifs that overlap with recipe effect_type."""
    module = _load_module()
    recipe = _make_recipe(effect_type="Spirals", tags=["wipe"])
    catalog = _make_motif_catalog()
    results = module.lookup_motif_compatibility(recipe, catalog)
    assert len(results) > 0


# ---------------------------------------------------------------------------
# Test 5: lookup_motif_compatibility no overlap → empty list
# ---------------------------------------------------------------------------


def test_lookup_motif_compatibility_no_overlap() -> None:
    """lookup_motif_compatibility returns empty list when no motifs overlap."""
    module = _load_module()
    recipe = _make_recipe(effect_type="Kaleidoscope", tags=["kaleidoscope"])
    catalog = _make_motif_catalog()
    results = module.lookup_motif_compatibility(recipe, catalog)
    assert results == []


# ---------------------------------------------------------------------------
# Test 6: lookup_motif_compatibility confidence capped at 1.0
# ---------------------------------------------------------------------------


def test_lookup_motif_compatibility_confidence_capped() -> None:
    """lookup_motif_compatibility scores are all <= 1.0."""
    module = _load_module()
    recipe = _make_recipe(effect_type="Spirals", tags=["spirals", "wipe"])
    catalog = _make_motif_catalog()
    results = module.lookup_motif_compatibility(recipe, catalog)
    for r in results:
        assert r.score <= 1.0


# ---------------------------------------------------------------------------
# Test 7: backfill_recipe produces non-empty model_affinities
# ---------------------------------------------------------------------------


def test_backfill_recipe_produces_model_affinities() -> None:
    """backfill_recipe returns a recipe with non-empty model_affinities for known effect."""
    module = _load_module()
    recipe = _make_recipe(effect_type="Spirals")
    propensity = _make_propensity_index()
    catalog = _make_motif_catalog()
    updated = module.backfill_recipe(recipe, propensity, catalog, posture="FLAT")
    assert len(updated.model_affinities) > 0


# ---------------------------------------------------------------------------
# Test 8: backfill_recipe produces non-empty motif_compatibility
# ---------------------------------------------------------------------------


def test_backfill_recipe_produces_motif_compatibility() -> None:
    """backfill_recipe returns a recipe with non-empty motif_compatibility for matching recipe."""
    module = _load_module()
    recipe = _make_recipe(effect_type="Spirals", tags=["spirals", "wipe"])
    propensity = _make_propensity_index()
    catalog = _make_motif_catalog()
    updated = module.backfill_recipe(recipe, propensity, catalog, posture="FLAT")
    assert len(updated.motif_compatibility) > 0


# ---------------------------------------------------------------------------
# Test 9: backfill_recipe preserves original recipe_id
# ---------------------------------------------------------------------------


def test_backfill_recipe_preserves_recipe_id() -> None:
    """backfill_recipe must not alter the recipe_id."""
    module = _load_module()
    recipe = _make_recipe(recipe_id="my_unique_recipe_id", effect_type="Spirals")
    propensity = _make_propensity_index()
    catalog = _make_motif_catalog()
    updated = module.backfill_recipe(recipe, propensity, catalog, posture="RICH")
    assert updated.recipe_id == "my_unique_recipe_id"


# ---------------------------------------------------------------------------
# Test 10: backfill_recipe appends posture to curator_notes (AUD-03)
# ---------------------------------------------------------------------------


def test_backfill_recipe_appends_curator_notes() -> None:
    """backfill_recipe appends posture classification to provenance.curator_notes."""
    module = _load_module()
    recipe = _make_recipe(effect_type="Spirals", curator_notes=None)
    propensity = _make_propensity_index()
    catalog = _make_motif_catalog()
    updated = module.backfill_recipe(recipe, propensity, catalog, posture="RICH")
    notes = updated.provenance.curator_notes
    assert notes is not None
    assert "RICH" in notes
    assert "Audit Phase 06" in notes
