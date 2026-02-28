"""Tests for the SQLite feature store backend (Phase 2B).

All tests use tmp_path for DB isolation and follow the TDD pattern:
upsert data → query it back → assert round-trip fidelity.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.propensity import EffectModelAffinity
from twinklr.core.feature_engineering.models.stacks import (
    EffectStack,
    EffectStackLayer,
)
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TaxonomyLabel,
    TaxonomyLabelScore,
)
from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateAssignment,
    TemplateKind,
)
from twinklr.core.feature_engineering.models.transitions import (
    TransitionEdge,
    TransitionType,
)
from twinklr.core.feature_store.backends.sqlite import SQLiteFeatureStore
from twinklr.core.feature_store.models import FeatureStoreConfig
from twinklr.core.feature_store.protocols import FeatureStoreProviderSync
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
    LayerRole,
    VisualDepth,
)

# ---------------------------------------------------------------------------
# Fixtures — minimal valid model instances
# ---------------------------------------------------------------------------


def _make_phrase(
    phrase_id: str = "p1",
    package_id: str = "pkg1",
    sequence_file_id: str = "seq1",
    effect_family: str = "color_wash",
    target_name: str = "MegaTree",
) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.0",
        phrase_id=phrase_id,
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        effect_event_id=f"ev_{phrase_id}",
        effect_type="Color Wash",
        effect_family=effect_family,
        motion_class=MotionClass.STATIC,
        color_class=ColorClass.PALETTE,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=0.9,
        target_name=target_name,
        layer_index=0,
        start_ms=0,
        end_ms=5000,
        duration_ms=5000,
        param_signature="color_wash|static|palette",
    )


def _make_template(
    template_id: str = "t1",
    effect_family: str = "color_wash",
    support_count: int = 5,
    cross_pack_stability: float = 0.8,
) -> MinedTemplate:
    return MinedTemplate(
        template_id=template_id,
        template_kind=TemplateKind.CONTENT,
        template_signature=f"sig_{template_id}",
        support_count=support_count,
        distinct_pack_count=2,
        support_ratio=0.5,
        cross_pack_stability=cross_pack_stability,
        effect_family=effect_family,
        motion_class="static",
        color_class="palette",
        energy_class="mid",
        continuity_class="sustained",
        spatial_class="single_target",
    )


def _make_stack(
    stack_id: str = "s1",
    package_id: str = "pkg1",
    sequence_file_id: str = "seq1",
    target_name: str = "MegaTree",
    stack_signature: str = "color_wash",
) -> EffectStack:
    phrase = _make_phrase(phrase_id=f"ph_{stack_id}", target_name=target_name)
    layer = EffectStackLayer(
        phrase=phrase,
        layer_role=LayerRole.BASE,
        blend_mode=BlendMode.NORMAL,
        mix=1.0,
    )
    return EffectStack(
        stack_id=stack_id,
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        target_name=target_name,
        start_ms=0,
        end_ms=5000,
        duration_ms=5000,
        layers=(layer,),
        layer_count=1,
        stack_signature=stack_signature,
    )


def _make_transition(
    source: str = "t1",
    target: str = "t2",
) -> TransitionEdge:
    return TransitionEdge(
        source_template_id=source,
        target_template_id=target,
        edge_count=5,
        confidence=0.8,
        mean_gap_ms=100.0,
        transition_type_distribution={
            TransitionType.HARD_CUT: 3,
            TransitionType.CROSSFADE: 2,
        },
    )


def _make_recipe(recipe_id: str = "r1") -> EffectRecipe:
    layer = RecipeLayer(
        layer_index=0,
        layer_name="base",
        layer_depth=VisualDepth.BACKGROUND,
        effect_type="Color Wash",
        blend_mode=BlendMode.NORMAL,
        mix=1.0,
        density=0.5,
    )
    return EffectRecipe(
        recipe_id=recipe_id,
        name="Test Recipe",
        description="A test recipe",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        timing=TimingHints(bars_min=2, bars_max=8),
        palette_spec=PaletteSpec(
            mode=ColorMode.MONOCHROME,
            palette_roles=["primary"],
        ),
        layers=(layer,),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(
            complexity=0.3,
            energy_affinity=EnergyTarget.MED,
        ),
    )


def _make_taxonomy(phrase_id: str = "p1") -> PhraseTaxonomyRecord:
    return PhraseTaxonomyRecord(
        schema_version="v1.0",
        classifier_version="v1.0",
        phrase_id=phrase_id,
        package_id="pkg1",
        sequence_file_id="seq1",
        effect_event_id=f"ev_{phrase_id}",
        labels=(TaxonomyLabel.SUSTAINER,),
        label_confidences=(0.9,),
        label_scores=(TaxonomyLabelScore(label=TaxonomyLabel.SUSTAINER, confidence=0.9),),
    )


def _make_propensity(
    effect_family: str = "color_wash",
    model_type: str = "megatree",
) -> EffectModelAffinity:
    return EffectModelAffinity(
        effect_family=effect_family,
        model_type=model_type,
        frequency=0.7,
        exclusivity=0.4,
        corpus_support=10,
    )


def _make_assignment(
    package_id: str = "pkg1",
    sequence_file_id: str = "seq1",
    phrase_id: str = "p1",
    template_id: str = "t1",
) -> TemplateAssignment:
    return TemplateAssignment(
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        phrase_id=phrase_id,
        effect_event_id=f"ev_{phrase_id}",
        template_id=template_id,
    )


# ---------------------------------------------------------------------------
# Fixture — initialized store
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteFeatureStore:
    """Return an initialized SQLiteFeatureStore backed by a temp DB."""
    cfg = FeatureStoreConfig(
        backend="sqlite",
        db_path=tmp_path / "test.db",
        auto_bootstrap=True,
        enable_wal=True,
    )
    s = SQLiteFeatureStore(cfg)
    s.initialize()
    return s


# ---------------------------------------------------------------------------
# Lifecycle tests
# ---------------------------------------------------------------------------


def test_initialize_creates_db(tmp_path: Path) -> None:
    """initialize() creates the DB file on disk."""
    db_path = tmp_path / "test.db"
    cfg = FeatureStoreConfig(backend="sqlite", db_path=db_path)
    s = SQLiteFeatureStore(cfg)
    s.initialize()
    assert db_path.exists()
    s.close()


def test_initialize_opens_existing(tmp_path: Path) -> None:
    """Calling initialize() twice on the same path does not raise."""
    db_path = tmp_path / "test.db"
    cfg = FeatureStoreConfig(backend="sqlite", db_path=db_path)
    s1 = SQLiteFeatureStore(cfg)
    s1.initialize()
    s1.close()

    s2 = SQLiteFeatureStore(cfg)
    s2.initialize()
    s2.close()


def test_close_is_idempotent(store: SQLiteFeatureStore) -> None:
    """Calling close() twice does not raise."""
    store.close()
    store.close()


def test_wal_mode_enabled(tmp_path: Path) -> None:
    """WAL journal mode is enabled when enable_wal=True."""
    cfg = FeatureStoreConfig(
        backend="sqlite",
        db_path=tmp_path / "wal.db",
        enable_wal=True,
    )
    s = SQLiteFeatureStore(cfg)
    s.initialize()
    # Access internal connection to check pragma
    row = s._conn.execute("PRAGMA journal_mode").fetchone()  # type: ignore[attr-defined]
    assert row[0] == "wal"
    s.close()


def test_satisfies_protocol(store: SQLiteFeatureStore) -> None:
    """SQLiteFeatureStore satisfies FeatureStoreProviderSync protocol."""
    assert isinstance(store, FeatureStoreProviderSync)


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------


def test_get_schema_version(store: SQLiteFeatureStore) -> None:
    """get_schema_version returns '1.0.0' after bootstrap."""
    assert store.get_schema_version() == "1.0.0"


# ---------------------------------------------------------------------------
# Phrases round-trip
# ---------------------------------------------------------------------------


def test_upsert_query_phrases_by_target(store: SQLiteFeatureStore) -> None:
    """Upserted phrases are retrievable by target."""
    p1 = _make_phrase(phrase_id="p1", target_name="MegaTree")
    p2 = _make_phrase(phrase_id="p2", target_name="Arch")
    store.upsert_phrases((p1, p2))

    results = store.query_phrases_by_target("pkg1", "seq1", "MegaTree")
    assert len(results) == 1
    assert results[0].phrase_id == "p1"
    assert results[0].target_name == "MegaTree"


def test_upsert_query_phrases_by_family(store: SQLiteFeatureStore) -> None:
    """Upserted phrases are retrievable by effect family."""
    p1 = _make_phrase(phrase_id="p1", effect_family="color_wash")
    p2 = _make_phrase(phrase_id="p2", effect_family="bars")
    store.upsert_phrases((p1, p2))

    results = store.query_phrases_by_family("color_wash")
    assert len(results) == 1
    assert results[0].effect_family == "color_wash"


def test_upsert_is_idempotent(store: SQLiteFeatureStore) -> None:
    """Upserting the same phrase twice keeps count at 1."""
    p = _make_phrase(phrase_id="p1")
    store.upsert_phrases((p,))
    store.upsert_phrases((p,))

    results = store.query_phrases_by_family("color_wash")
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Templates round-trip
# ---------------------------------------------------------------------------


def test_upsert_query_templates(store: SQLiteFeatureStore) -> None:
    """Upserted templates are retrievable with filters."""
    t1 = _make_template(
        "t1", effect_family="color_wash", support_count=10, cross_pack_stability=0.9
    )
    t2 = _make_template("t2", effect_family="bars", support_count=2, cross_pack_stability=0.5)
    store.upsert_templates((t1, t2))

    # No filter — both returned
    all_templates = store.query_templates()
    assert len(all_templates) == 2

    # Filter by family
    cw = store.query_templates(effect_family="color_wash")
    assert len(cw) == 1
    assert cw[0].template_id == "t1"

    # Filter by min_support
    high_support = store.query_templates(min_support=5)
    assert len(high_support) == 1
    assert high_support[0].template_id == "t1"

    # Filter by min_stability
    stable = store.query_templates(min_stability=0.8)
    assert len(stable) == 1
    assert stable[0].template_id == "t1"


# ---------------------------------------------------------------------------
# Stacks round-trip
# ---------------------------------------------------------------------------


def test_upsert_query_stacks_by_target(store: SQLiteFeatureStore) -> None:
    """Upserted stacks are retrievable by target."""
    s1 = _make_stack("s1", target_name="MegaTree")
    s2 = _make_stack("s2", target_name="Arch")
    store.upsert_stacks((s1, s2))

    results = store.query_stacks_by_target("pkg1", "seq1", "MegaTree")
    assert len(results) == 1
    assert results[0].stack_id == "s1"


def test_upsert_query_stacks_by_signature(store: SQLiteFeatureStore) -> None:
    """Upserted stacks are retrievable by signature."""
    s1 = _make_stack("s1", stack_signature="color_wash|bars")
    s2 = _make_stack("s2", stack_signature="sparkle")
    store.upsert_stacks((s1, s2))

    results = store.query_stacks_by_signature("color_wash|bars")
    assert len(results) == 1
    assert results[0].stack_id == "s1"


# ---------------------------------------------------------------------------
# Transitions round-trip
# ---------------------------------------------------------------------------


def test_upsert_query_transitions(store: SQLiteFeatureStore) -> None:
    """Upserted transitions are retrievable."""
    e1 = _make_transition("t1", "t2")
    e2 = _make_transition("t1", "t3")
    store.upsert_transitions((e1, e2))

    all_edges = store.query_transitions()
    assert len(all_edges) == 2

    filtered = store.query_transitions(source_template_id="t1")
    assert len(filtered) == 2
    assert all(e.source_template_id == "t1" for e in filtered)


# ---------------------------------------------------------------------------
# Recipes round-trip
# ---------------------------------------------------------------------------


def test_upsert_query_recipes(store: SQLiteFeatureStore) -> None:
    """Upserted recipes are retrievable."""
    r1 = _make_recipe("r1")
    store.upsert_recipes((r1,))

    all_recipes = store.query_recipes()
    assert len(all_recipes) == 1
    assert all_recipes[0].recipe_id == "r1"

    filtered = store.query_recipes(template_type="BASE")
    assert len(filtered) == 1


# ---------------------------------------------------------------------------
# Taxonomy round-trip
# ---------------------------------------------------------------------------


def test_upsert_taxonomy_round_trip(store: SQLiteFeatureStore) -> None:
    """Upserted taxonomy records survive round-trip."""
    r1 = _make_taxonomy("p1")
    r2 = _make_taxonomy("p2")
    store.upsert_taxonomy((r1, r2))

    stats = store.get_corpus_stats()
    assert stats.taxonomy_count == 2


# ---------------------------------------------------------------------------
# Propensity round-trip
# ---------------------------------------------------------------------------


def test_upsert_propensity_round_trip(store: SQLiteFeatureStore) -> None:
    """Upserted propensity entries survive round-trip."""
    a1 = _make_propensity("color_wash", "megatree")
    a2 = _make_propensity("bars", "arch")
    store.upsert_propensity((a1, a2))

    stats = store.get_corpus_stats()
    assert stats.propensity_count == 2


# ---------------------------------------------------------------------------
# Corpus metadata round-trip
# ---------------------------------------------------------------------------


def test_corpus_metadata_round_trip(store: SQLiteFeatureStore) -> None:
    """upsert_corpus_metadata persists metadata JSON."""
    count = store.upsert_corpus_metadata("corpus-001", '{"total": 42}')
    assert count == 1


# ---------------------------------------------------------------------------
# CorpusStats
# ---------------------------------------------------------------------------


def test_get_corpus_stats(store: SQLiteFeatureStore) -> None:
    """get_corpus_stats returns accurate counts after upserts."""
    store.upsert_phrases((_make_phrase("p1"), _make_phrase("p2")))
    store.upsert_templates((_make_template("t1"),))
    store.upsert_stacks((_make_stack("s1"),))
    store.upsert_transitions((_make_transition(),))
    store.upsert_recipes((_make_recipe("r1"),))
    store.upsert_taxonomy((_make_taxonomy("p1"),))
    store.upsert_propensity((_make_propensity(),))

    stats = store.get_corpus_stats()
    assert stats.phrase_count == 2
    assert stats.template_count == 1
    assert stats.stack_count == 1
    assert stats.transition_count == 1
    assert stats.recipe_count == 1
    assert stats.taxonomy_count == 1
    assert stats.propensity_count == 1


# ---------------------------------------------------------------------------
# Reference data round-trip
# ---------------------------------------------------------------------------


def test_reference_data_round_trip(store: SQLiteFeatureStore) -> None:
    """store_reference_data and load_reference_data form a round-trip."""
    store.store_reference_data("palette_map", '{"primary": "red"}', "1.0")
    result = store.load_reference_data("palette_map")
    assert result == '{"primary": "red"}'


def test_load_reference_data_missing_key(store: SQLiteFeatureStore) -> None:
    """load_reference_data returns None for a missing key."""
    result = store.load_reference_data("nonexistent_key")
    assert result is None


# ---------------------------------------------------------------------------
# Template assignments round-trip
# ---------------------------------------------------------------------------


def test_upsert_template_assignments(store: SQLiteFeatureStore) -> None:
    """Upserted template assignments are counted in stats (via template_assignments table)."""
    a1 = _make_assignment("pkg1", "seq1", "p1", "t1")
    a2 = _make_assignment("pkg1", "seq1", "p2", "t1")
    count = store.upsert_template_assignments((a1, a2))
    assert count == 2
