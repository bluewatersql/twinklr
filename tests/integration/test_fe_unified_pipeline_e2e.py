"""End-to-end integration test: FE enhancements + unified pipeline.

Verifies the complete feature-engineering lifecycle and its integration
with the unified DAG-based pipeline executor:

  1. FE pipeline runs corpus discovery, per-profile stages (alignment,
     phrase encoding, taxonomy, target roles, stack detection), and
     corpus-aggregate stages (template mining, transition modeling,
     motif mining, clustering, learned taxonomy, ANN retrieval,
     layering, color narrative, color arc, propensity, style fingerprint,
     quality gates, recipe promotion, adapter contracts).

  2. Feature store lifecycle (SQLite backend) — initialise, upsert
     phrases/taxonomy/corpus-metadata, query back, close.

  3. Recipe pipeline — MinedTemplate → PromotionPipeline → RecipeCatalog
     → RecipeRenderer → StyleWeightedRetrieval.

  4. Unified pipeline DAG — PipelineDefinition + PipelineExecutor with
     stub stages exercising SEQUENTIAL, PARALLEL, CONDITIONAL, and
     FAN_OUT patterns, verifying dependency resolution, state sharing,
     and result aggregation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from twinklr.core.feature_engineering.models.templates import MinedTemplate, TemplateKind
from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    FeatureEngineeringPipelineOptions,
)
from twinklr.core.feature_engineering.promotion import PromotionPipeline
from twinklr.core.feature_engineering.style_transfer import StyleWeightedRetrieval
from twinklr.core.feature_store.backends.null import NullFeatureStore
from twinklr.core.feature_store.factory import create_feature_store
from twinklr.core.feature_store.models import FeatureStoreConfig
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.definition import (
    ExecutionPattern,
    PipelineDefinition,
    StageDefinition,
)
from twinklr.core.pipeline.executor import PipelineExecutor
from twinklr.core.pipeline.result import success_result
from twinklr.core.sequencer.display.recipe_renderer import (
    RecipeRenderer,
    RenderEnvironment,
)
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
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

if TYPE_CHECKING:
    from twinklr.core.pipeline.result import StageResult

# ============================================================================
# Shared Helpers
# ============================================================================


class _FakeAnalyzer:
    """Minimal audio-analyzer stub returning enough features for all FE stages."""

    def analyze_sync(self, audio_path: str, *, force_reprocess: bool = False):
        return type(
            "_Bundle",
            (),
            {
                "features": {
                    "duration_s": 180.0,
                    "assumptions": {"beats_per_bar": 4},
                    "beats_s": [i * 0.5 for i in range(32)],
                    "bars_s": [i * 2.0 for i in range(8)],
                    "energy": {
                        "times_s": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
                        "rms_norm": [0.1, 0.3, 0.6, 0.9, 0.7, 0.5, 0.8, 0.4],
                    },
                    "tempo_analysis": {
                        "tempo_curve": [{"time_s": 0.0, "tempo_bpm": 128.0}],
                    },
                    "tension": {"tension_curve": [0.2, 0.4, 0.7, 0.8, 0.6, 0.3]},
                    "structure": {
                        "sections": [
                            {"start_s": 0.0, "end_s": 4.0, "label": "intro"},
                            {"start_s": 4.0, "end_s": 8.0, "label": "verse"},
                            {"start_s": 8.0, "end_s": 12.0, "label": "chorus"},
                        ],
                    },
                    "harmonic": {
                        "chords": {
                            "chords": [
                                {"time_s": 0.0, "chord": "C:maj"},
                                {"time_s": 4.0, "chord": "G:maj"},
                                {"time_s": 8.0, "chord": "A:min"},
                            ],
                        },
                    },
                },
            },
        )()


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_audio(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake-audio-bytes")


def _seed_profile(
    profile_dir: Path,
    *,
    pkg_id: str = "pkg-e2e",
    seq_id: str = "seq-e2e",
    song: str = "E2E Test Song",
) -> None:
    """Create a minimal profile directory with enriched events."""
    _write_json(
        profile_dir / "sequence_metadata.json",
        {
            "package_id": pkg_id,
            "sequence_file_id": seq_id,
            "sequence_sha256": f"sha-{seq_id}",
            "media_file": f"{song}.mp3",
            "song": song,
            "artist": "Test Artist",
        },
    )
    _write_json(
        profile_dir / "lineage_index.json",
        {"sequence_file": {"filename": f"{song}.xsq"}},
    )
    _write_json(
        profile_dir / "enriched_effect_events.json",
        [
            {
                "effect_event_id": f"evt-{i}",
                "target_name": target,
                "layer_index": 0,
                "effect_type": fx,
                "start_ms": i * 1000,
                "end_ms": (i + 1) * 1000,
            }
            for i, (target, fx) in enumerate(
                [
                    ("Megatree", "On"),
                    ("Megatree", "Shimmer"),
                    ("Arch", "Twinkle"),
                    ("Arch", "On"),
                    ("Fence", "ColorWash"),
                    ("Fence", "Sparkle"),
                ]
            )
        ],
    )


def _setup_corpus(
    tmp_path: Path,
    *,
    profile_count: int = 1,
) -> tuple[Path, Path, Path]:
    """Create corpus structure with N profile entries."""
    corpus_dir = tmp_path / "corpus"
    output_root = tmp_path / "features"
    extracted_root = tmp_path / "vendor"

    entries = []
    for i in range(profile_count):
        profile_dir = tmp_path / "profiles" / f"profile_{i}"
        pkg_id = f"pkg-{i}"
        seq_id = f"seq-{i}"
        _seed_profile(profile_dir, pkg_id=pkg_id, seq_id=seq_id, song=f"Song_{i}")
        _write_audio(extracted_root / f"extracted_{i}" / f"Song_{i}.mp3")
        entries.append(
            json.dumps(
                {
                    "profile_path": str(profile_dir),
                    "package_id": pkg_id,
                    "sequence_file_id": seq_id,
                }
            )
        )

    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "sequence_index.jsonl").write_text("\n".join(entries) + "\n", encoding="utf-8")

    return corpus_dir, output_root, extracted_root


def _make_mined_template(
    template_id: str,
    effect_family: str = "shimmer",
    motion_class: str = "sweep",
    energy_class: str = "mid",
    support_count: int = 25,
    cross_pack_stability: float = 0.75,
) -> MinedTemplate:
    return MinedTemplate(
        template_id=template_id,
        template_kind=TemplateKind.CONTENT,
        template_signature=(
            f"{effect_family}|{motion_class}|palette|{energy_class}"
            "|rhythmic|single_target|rhythm_driver"
        ),
        support_count=support_count,
        distinct_pack_count=4,
        support_ratio=0.45,
        cross_pack_stability=cross_pack_stability,
        effect_family=effect_family,
        motion_class=motion_class,
        color_class="palette",
        energy_class=energy_class,
        continuity_class="sustained",
        spatial_class="single_target",
    )


def _make_recipe(
    recipe_id: str,
    *,
    template_type: GroupTemplateType = GroupTemplateType.BASE,
    energy: EnergyTarget = EnergyTarget.LOW,
    source: str = "builtin",
) -> EffectRecipe:
    from twinklr.core.sequencer.templates.group.models.template import TimingHints

    return EffectRecipe(
        recipe_id=recipe_id,
        name=recipe_id.replace("_", " ").title(),
        description=f"Test recipe {recipe_id}",
        recipe_version="1.0.0",
        template_type=template_type,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["test"],
        timing=TimingHints(bars_min=4, bars_max=32),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Base",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="ColorWash",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={"Speed": ParamValue(value=0)},
                motion=[MotionVerb.FADE],
                density=0.8,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source=source),
        style_markers=StyleMarkers(complexity=0.33, energy_affinity=energy),
    )


# ============================================================================
# Part 1: FE Pipeline — Full Corpus Run (Phases 0 + 1)
# ============================================================================


class TestFEPipelineFullCorpus:
    """Verify the FE pipeline produces all Phase 0, Phase 1, and Phase 2 artifacts."""

    def test_corpus_run_produces_all_phase_artifacts(self, tmp_path: Path) -> None:
        """Full FE pipeline run: alignment, phrases, taxonomy, targets, stacks,
        templates, transitions, motifs, clusters, retrieval, layering,
        color narrative, color arc, propensity, style fingerprint,
        quality gates, recipe promotion, and adapter contracts.
        """
        corpus_dir, output_root, extracted_root = _setup_corpus(tmp_path)

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(
                extracted_search_roots=(extracted_root,),
                enable_color_arc=True,
                enable_propensity=True,
                enable_style_fingerprint=True,
                enable_template_mining=True,
                enable_transition_modeling=True,
                enable_layering_features=True,
                enable_color_narrative=True,
                enable_quality_gates=True,
                enable_recipe_promotion=True,
                enable_v2_motif_mining=True,
                enable_v2_clustering=True,
                enable_v2_learned_taxonomy=True,
                enable_v2_ann_retrieval=True,
                enable_v2_adapter_contracts=True,
                enable_stack_detection=True,
            ),
            analyzer=_FakeAnalyzer(),
        )
        bundles = pipeline.run_corpus(corpus_dir, output_root)

        assert len(bundles) >= 1, "Expected at least one FeatureBundle"

        bundle = bundles[0]
        assert bundle.package_id is not None
        assert bundle.sequence_file_id is not None
        assert bundle.audio is not None

        # Phase 1 corpus-level artifacts
        assert (output_root / "color_arc.json").exists(), "color_arc.json missing"
        assert (output_root / "propensity_index.json").exists(), "propensity.json missing"
        assert (output_root / "style_fingerprint.json").exists(), "style_fp.json missing"

        # Feature store manifest
        manifest_path = output_root / "feature_store_manifest.json"
        assert manifest_path.exists(), "manifest missing"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "color_arc" in manifest
        assert "propensity_index" in manifest
        assert "style_fingerprint" in manifest

    def test_corpus_run_color_arc_structure(self, tmp_path: Path) -> None:
        """Color arc artifact contains palette_library and section_assignments."""
        corpus_dir, output_root, extracted_root = _setup_corpus(tmp_path)

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(
                extracted_search_roots=(extracted_root,),
            ),
            analyzer=_FakeAnalyzer(),
        )
        pipeline.run_corpus(corpus_dir, output_root)

        arc = json.loads((output_root / "color_arc.json").read_text(encoding="utf-8"))
        assert "palette_library" in arc
        assert "section_assignments" in arc
        assert isinstance(arc["palette_library"], list)

    def test_corpus_run_propensity_affinities(self, tmp_path: Path) -> None:
        """Propensity index contains affinities with required fields."""
        corpus_dir, output_root, extracted_root = _setup_corpus(tmp_path)

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(
                extracted_search_roots=(extracted_root,),
            ),
            analyzer=_FakeAnalyzer(),
        )
        pipeline.run_corpus(corpus_dir, output_root)

        index = json.loads((output_root / "propensity_index.json").read_text(encoding="utf-8"))
        assert "affinities" in index
        for aff in index["affinities"]:
            assert "effect_family" in aff
            assert "model_type" in aff
            assert "frequency" in aff

    def test_corpus_run_style_fingerprint_fields(self, tmp_path: Path) -> None:
        """Style fingerprint includes all sub-profiles."""
        corpus_dir, output_root, extracted_root = _setup_corpus(tmp_path)

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(
                extracted_search_roots=(extracted_root,),
            ),
            analyzer=_FakeAnalyzer(),
        )
        pipeline.run_corpus(corpus_dir, output_root)

        fp = json.loads((output_root / "style_fingerprint.json").read_text(encoding="utf-8"))
        for key in (
            "creator_id",
            "recipe_preferences",
            "transition_style",
            "timing_style",
            "layering_style",
        ):
            assert key in fp, f"style fingerprint missing '{key}'"

    def test_disabled_stages_omit_artifacts(self, tmp_path: Path) -> None:
        """Disabling Phase 1 stages suppresses their output files and manifest entries."""
        corpus_dir, output_root, extracted_root = _setup_corpus(tmp_path)

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(
                extracted_search_roots=(extracted_root,),
                enable_color_arc=False,
                enable_propensity=False,
                enable_style_fingerprint=False,
            ),
            analyzer=_FakeAnalyzer(),
        )
        pipeline.run_corpus(corpus_dir, output_root)

        assert not (output_root / "color_arc.json").exists()
        assert not (output_root / "propensity_index.json").exists()
        assert not (output_root / "style_fingerprint.json").exists()

        manifest = json.loads(
            (output_root / "feature_store_manifest.json").read_text(encoding="utf-8")
        )
        assert "color_arc" not in manifest
        assert "propensity_index" not in manifest
        assert "style_fingerprint" not in manifest

    def test_multi_profile_corpus(self, tmp_path: Path) -> None:
        """FE pipeline handles multiple profiles in a single corpus run."""
        corpus_dir, output_root, extracted_root = _setup_corpus(tmp_path, profile_count=3)

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(
                extracted_search_roots=(extracted_root,),
            ),
            analyzer=_FakeAnalyzer(),
        )
        bundles = pipeline.run_corpus(corpus_dir, output_root)

        assert len(bundles) == 3
        pkg_ids = {b.package_id for b in bundles}
        assert pkg_ids == {"pkg-0", "pkg-1", "pkg-2"}


# ============================================================================
# Part 2: Feature Store Integration (Phase 2)
# ============================================================================


class TestFeatureStoreLifecycle:
    """Verify feature store integration across all lifecycle phases."""

    def test_null_store_default(self) -> None:
        """Default pipeline uses NullFeatureStore (no-op persistence)."""
        pipeline = FeatureEngineeringPipeline()
        assert isinstance(pipeline._store, NullFeatureStore)

    def test_sqlite_store_creation(self, tmp_path: Path) -> None:
        """SQLite config produces a real (non-null) store."""
        config = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "fe.db")
        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(feature_store_config=config)
        )
        assert not isinstance(pipeline._store, NullFeatureStore)

    def test_sqlite_phrase_persistence_e2e(self, tmp_path: Path) -> None:
        """Run profile → SQLite store → query back phrases by target."""
        profile_dir = tmp_path / "profile"
        output_dir = tmp_path / "out"
        _seed_profile(profile_dir, pkg_id="pkg-store", seq_id="seq-store")

        db_path = tmp_path / "feature_store.db"
        config = FeatureStoreConfig(backend="sqlite", db_path=db_path)
        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(feature_store_config=config)
        )
        pipeline.run_profile(profile_dir, output_dir)

        store = create_feature_store(config)
        store.initialize()
        try:
            phrases = store.query_phrases_by_target(
                package_id="pkg-store",
                sequence_file_id="seq-store",
                target_name="Megatree",
            )
            assert len(phrases) > 0
            assert all(p.target_name == "Megatree" for p in phrases)
        finally:
            store.close()

    def test_store_lifecycle_initialize_close(self, tmp_path: Path) -> None:
        """Store.initialize() and store.close() are called during run_profile."""
        profile_dir = tmp_path / "profile"
        output_dir = tmp_path / "out"
        _seed_profile(profile_dir)

        mock_store = MagicMock()
        pipeline = FeatureEngineeringPipeline()
        pipeline._store = mock_store

        pipeline.run_profile(profile_dir, output_dir)

        mock_store.initialize.assert_called_once()
        mock_store.close.assert_called_once()

    def test_store_close_on_exception(self, tmp_path: Path) -> None:
        """Store.close() is called even when the pipeline raises."""
        from unittest.mock import patch

        profile_dir = tmp_path / "profile"
        output_dir = tmp_path / "out"
        _seed_profile(profile_dir)

        mock_store = MagicMock()
        pipeline = FeatureEngineeringPipeline()
        pipeline._store = mock_store

        with (
            patch.object(pipeline, "_run_profile_internal", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError, match="boom"),
        ):
            pipeline.run_profile(profile_dir, output_dir)

        mock_store.close.assert_called_once()

    def test_corpus_run_with_sqlite_stores_metadata(self, tmp_path: Path) -> None:
        """Corpus run with SQLite calls upsert_corpus_metadata."""
        corpus_dir, output_root, extracted_root = _setup_corpus(tmp_path)

        mock_store = MagicMock()
        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(
                extracted_search_roots=(extracted_root,),
            ),
            analyzer=_FakeAnalyzer(),
        )
        pipeline._store = mock_store

        pipeline.run_corpus(corpus_dir, output_root)

        mock_store.upsert_corpus_metadata.assert_called_once()
        corpus_id, metadata_json = mock_store.upsert_corpus_metadata.call_args[0]
        assert isinstance(corpus_id, str) and len(corpus_id) > 0
        parsed = json.loads(metadata_json)
        assert "sequence_count" in parsed


# ============================================================================
# Part 3: Recipe Pipeline — Promotion → Catalog → Render → Style Retrieval
# ============================================================================


class TestRecipePipelineE2E:
    """Full recipe lifecycle: mine → promote → catalog → render → rank."""

    def test_mined_template_to_catalog_to_render(self) -> None:
        """MinedTemplate passes promotion, enters catalog, renders correctly."""
        good = _make_mined_template("tpl_shimmer_e2e", support_count=30)
        weak = _make_mined_template("tpl_weak_e2e", support_count=1, cross_pack_stability=0.05)

        result = PromotionPipeline().run(candidates=[good, weak], min_support=5, min_stability=0.3)
        assert len(result.promoted_recipes) == 1
        promoted = result.promoted_recipes[0]
        assert isinstance(promoted, EffectRecipe)
        assert promoted.provenance.source == "mined"

        builtin = _make_recipe("builtin_wash_e2e")
        catalog = RecipeCatalog.merge(builtins=[builtin], promoted=[promoted])
        assert len(catalog.recipes) == 2
        assert catalog.has_recipe(builtin.recipe_id)
        assert catalog.has_recipe(promoted.recipe_id)

        env = RenderEnvironment(
            energy=0.7,
            density=0.5,
            palette_colors={"primary": "#3F51B5"},
        )
        render_result = RecipeRenderer().render(promoted, env)
        assert render_result.recipe_id == promoted.recipe_id
        assert len(render_result.layers) == len(promoted.layers)
        assert len(render_result.warnings) == 0

    def test_multi_layer_dynamic_params(self) -> None:
        """Dynamic ParamValue expressions evaluate correctly in render."""
        from twinklr.core.sequencer.templates.group.models.template import TimingHints

        recipe = EffectRecipe(
            recipe_id="dynamic_e2e",
            name="Dynamic Param Test",
            description="Tests dynamic parameter evaluation",
            recipe_version="1.0.0",
            template_type=GroupTemplateType.RHYTHM,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=["test"],
            timing=TimingHints(bars_min=4, bars_max=16),
            palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
            layers=(
                RecipeLayer(
                    layer_index=0,
                    layer_name="BG",
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
                        "BarCount": ParamValue(expr="energy * 10", min_val=2, max_val=20),
                    },
                    motion=[MotionVerb.SWEEP],
                    density=0.6,
                    color_source=ColorSource.PALETTE_ACCENT,
                ),
            ),
            provenance=RecipeProvenance(source="builtin"),
            style_markers=StyleMarkers(complexity=0.66, energy_affinity=EnergyTarget.MED),
        )

        env = RenderEnvironment(
            energy=0.8,
            density=0.5,
            palette_colors={"primary": "#E53935", "accent": "#43A047"},
        )
        result = RecipeRenderer().render(recipe, env)

        assert len(result.layers) == 2
        assert result.layers[0].resolved_color == "#E53935"
        assert result.layers[1].resolved_color == "#43A047"
        assert result.layers[1].resolved_params["BarCount"] == 8.0  # 0.8 * 10

    def test_catalog_lane_filtering(self) -> None:
        """RecipeCatalog lane filtering separates BASE, RHYTHM, ACCENT correctly."""
        base = _make_recipe("base_r", template_type=GroupTemplateType.BASE)
        rhythm = _make_recipe("rhythm_r", template_type=GroupTemplateType.RHYTHM)

        catalog = RecipeCatalog(recipes=[base, rhythm])
        assert len(catalog.list_by_lane(LaneKind.BASE)) == 1
        assert len(catalog.list_by_lane(LaneKind.RHYTHM)) == 1
        assert len(catalog.list_by_lane(LaneKind.ACCENT)) == 0

    def test_style_weighted_retrieval_ranking(self) -> None:
        """StyleWeightedRetrieval ranks recipes by style fingerprint affinity."""
        from twinklr.core.feature_engineering.models.style import (
            ColorStyleProfile,
            LayeringStyleProfile,
            StyleFingerprint,
            TimingStyleProfile,
            TransitionStyleProfile,
        )

        generic = _make_recipe("generic_wash")
        shimmer = _make_recipe("styled_shimmer", energy=EnergyTarget.MED)

        catalog = RecipeCatalog(recipes=[generic, shimmer])

        style = StyleFingerprint(
            creator_id="test_creator",
            recipe_preferences={"shimmer": 0.95},
            transition_style=TransitionStyleProfile(
                preferred_gap_ms=40.0, overlap_tendency=0.2, variety_score=0.6
            ),
            color_tendencies=ColorStyleProfile(
                palette_complexity=0.4, contrast_preference=0.5, temperature_preference=0.5
            ),
            timing_style=TimingStyleProfile(
                beat_alignment_strictness=0.6, density_preference=0.7, section_change_aggression=0.4
            ),
            layering_style=LayeringStyleProfile(
                mean_layers=1.5, max_layers=3, blend_mode_preference="normal"
            ),
            corpus_sequence_count=15,
        )

        scored = StyleWeightedRetrieval().rank(catalog, style)
        assert len(scored) == 2
        assert scored[0].score >= scored[1].score


# ============================================================================
# Part 4: Unified Pipeline DAG — PipelineExecutor
# ============================================================================


class _StubStage:
    """Stub stage that records calls and returns a canned output."""

    def __init__(self, name: str, output: Any) -> None:
        self._name = name
        self._output = output
        self.calls: list[tuple[Any, PipelineContext]] = []

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, input: Any, context: PipelineContext) -> StageResult[Any]:
        self.calls.append((input, context))
        return success_result(self._output, stage_name=self._name)


class _StatefulStage:
    """Stub stage that reads/writes pipeline state."""

    def __init__(self, name: str, read_key: str, write_key: str, output: Any) -> None:
        self._name = name
        self._read_key = read_key
        self._write_key = write_key
        self._output = output

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, input: Any, context: PipelineContext) -> StageResult[Any]:
        context.set_state(self._write_key, context.get_state(self._read_key, "?"))
        return success_result(self._output, stage_name=self._name)


class _FanOutStage:
    """Stub stage for FAN_OUT pattern; returns per-item result."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, input: Any, context: PipelineContext) -> StageResult[Any]:
        return success_result(f"processed:{input}", stage_name=self._name)


def _make_mock_session() -> MagicMock:
    """Create a minimal mock TwinklrSession for PipelineContext."""
    session = MagicMock()
    session.app_config = MagicMock()
    session.job_config = MagicMock()
    session.llm_provider = MagicMock()
    session.agent_cache = MagicMock()
    session.agent_cache.get = AsyncMock(return_value=None)
    session.llm_logger = MagicMock()
    return session


class TestUnifiedPipelineDAG:
    """Verify PipelineDefinition + PipelineExecutor DAG behaviour."""

    @pytest.mark.asyncio
    async def test_sequential_two_stage_pipeline(self) -> None:
        """Two sequential stages: A → B. B receives A's output."""
        stage_a = _StubStage("a", output="result_a")
        stage_b = _StubStage("b", output="result_b")

        pipeline = PipelineDefinition(
            name="seq_test",
            stages=[
                StageDefinition(id="a", stage=stage_a),
                StageDefinition(id="b", stage=stage_b, inputs=["a"]),
            ],
        )

        ctx = PipelineContext(session=_make_mock_session())
        result = await PipelineExecutor().execute(pipeline, "input_0", ctx)

        assert result.success
        assert result.outputs["a"] == "result_a"
        assert result.outputs["b"] == "result_b"
        assert len(stage_a.calls) == 1
        assert len(stage_b.calls) == 1

    @pytest.mark.asyncio
    async def test_parallel_stages(self) -> None:
        """Two independent stages run in parallel from the same entry."""
        stage_x = _StubStage("x", output="rx")
        stage_y = _StubStage("y", output="ry")
        stage_join = _StubStage("join", output="final")

        pipeline = PipelineDefinition(
            name="par_test",
            stages=[
                StageDefinition(id="x", stage=stage_x),
                StageDefinition(id="y", stage=stage_y),
                StageDefinition(id="join", stage=stage_join, inputs=["x", "y"]),
            ],
        )

        ctx = PipelineContext(session=_make_mock_session())
        result = await PipelineExecutor().execute(pipeline, "in", ctx)

        assert result.success
        assert "x" in result.outputs
        assert "y" in result.outputs
        assert result.outputs["join"] == "final"

    @pytest.mark.asyncio
    async def test_conditional_stage_skipped(self) -> None:
        """Conditional stage is skipped when condition returns False."""
        stage_a = _StubStage("a", output="ra")
        stage_cond = _StubStage("cond", output="should_not_run")

        pipeline = PipelineDefinition(
            name="cond_test",
            stages=[
                StageDefinition(id="a", stage=stage_a),
                StageDefinition(
                    id="cond",
                    stage=stage_cond,
                    inputs=["a"],
                    pattern=ExecutionPattern.CONDITIONAL,
                    condition=lambda ctx: ctx.get_state("run_cond", False),
                ),
            ],
        )

        ctx = PipelineContext(session=_make_mock_session())
        result = await PipelineExecutor().execute(pipeline, "in", ctx)

        assert result.success
        assert len(stage_cond.calls) == 0

    @pytest.mark.asyncio
    async def test_conditional_stage_runs(self) -> None:
        """Conditional stage executes when condition returns True."""
        stage_a = _StubStage("a", output="ra")
        stage_cond = _StubStage("cond", output="cond_result")

        pipeline = PipelineDefinition(
            name="cond_run_test",
            stages=[
                StageDefinition(id="a", stage=stage_a),
                StageDefinition(
                    id="cond",
                    stage=stage_cond,
                    inputs=["a"],
                    pattern=ExecutionPattern.CONDITIONAL,
                    condition=lambda ctx: ctx.get_state("run_cond", False),
                ),
            ],
        )

        ctx = PipelineContext(session=_make_mock_session())
        ctx.set_state("run_cond", True)
        result = await PipelineExecutor().execute(pipeline, "in", ctx)

        assert result.success
        assert len(stage_cond.calls) == 1
        assert result.outputs["cond"] == "cond_result"

    @pytest.mark.asyncio
    async def test_pipeline_state_sharing(self) -> None:
        """State set by one stage is visible to subsequent stages."""
        stage_writer = _StatefulStage("w", read_key="_none_", write_key="shared_val", output="w")
        stage_reader = _StatefulStage("r", read_key="shared_val", write_key="echo", output="r")

        pipeline = PipelineDefinition(
            name="state_test",
            stages=[
                StageDefinition(id="w", stage=stage_writer),
                StageDefinition(id="r", stage=stage_reader, inputs=["w"]),
            ],
        )

        ctx = PipelineContext(session=_make_mock_session())
        ctx.set_state("_none_", "hello")
        result = await PipelineExecutor().execute(pipeline, "in", ctx)

        assert result.success
        assert ctx.get_state("shared_val") == "hello"
        assert ctx.get_state("echo") == "hello"

    @pytest.mark.asyncio
    async def test_pipeline_validation_rejects_cycles(self) -> None:
        """Pipeline with cyclic dependencies fails validation."""
        stage_a = _StubStage("a", output="a")
        stage_b = _StubStage("b", output="b")

        pipeline = PipelineDefinition(
            name="cycle_test",
            stages=[
                StageDefinition(id="a", stage=stage_a, inputs=["b"]),
                StageDefinition(id="b", stage=stage_b, inputs=["a"]),
            ],
        )

        errors = pipeline.validate_pipeline()
        assert len(errors) > 0, "Cyclic pipeline should fail validation"

    @pytest.mark.asyncio
    async def test_pipeline_result_metadata(self) -> None:
        """PipelineResult includes timing and per-stage metadata."""
        stage_a = _StubStage("a", output="ra")

        pipeline = PipelineDefinition(
            name="meta_test",
            stages=[StageDefinition(id="a", stage=stage_a)],
        )

        ctx = PipelineContext(session=_make_mock_session())
        result = await PipelineExecutor().execute(pipeline, "in", ctx)

        assert result.success
        assert result.total_duration_ms >= 0
        assert "a" in result.stage_results
        assert result.stage_results["a"].success

    @pytest.mark.asyncio
    async def test_moving_heads_dag_shape(self) -> None:
        """Verify build_moving_heads_pipeline produces correct DAG topology."""
        from twinklr.core.pipeline.definitions.moving_heads import (
            build_moving_heads_pipeline,
        )

        pipeline = build_moving_heads_pipeline(
            display_groups=[
                {"id": "MH", "role_key": "MH", "model_count": 4, "group_type": "mh"},
            ],
            fixture_count=4,
            available_templates=["sweep_slow", "bounce_fan_pulse"],
            xsq_output_path=Path("/tmp/test.xsq"),
        )

        stage_ids = {s.id for s in pipeline.stages}
        assert stage_ids == {"audio", "profile", "lyrics", "macro", "moving_heads", "render"}

        errors = pipeline.validate_pipeline()
        assert errors == [], f"Pipeline has validation errors: {errors}"

        # Verify dependency wiring
        stage_map = {s.id: s for s in pipeline.stages}
        assert stage_map["audio"].inputs == []
        assert "audio" in stage_map["profile"].inputs
        assert "audio" in stage_map["lyrics"].inputs
        assert "profile" in stage_map["macro"].inputs
        assert "audio" in stage_map["moving_heads"].inputs
        assert "moving_heads" in stage_map["render"].inputs

        # Lyrics is conditional
        assert stage_map["lyrics"].pattern == ExecutionPattern.CONDITIONAL
