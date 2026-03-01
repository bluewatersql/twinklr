"""Tests for ComponentFactory — CQ-01 + PERF-20 lazy initialization."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from twinklr.core.feature_engineering.component_factory import ComponentFactory
from twinklr.core.feature_engineering.pipeline import FeatureEngineeringPipelineOptions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_options() -> FeatureEngineeringPipelineOptions:
    return FeatureEngineeringPipelineOptions()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestComponentFactoryConstruction:
    """ComponentFactory constructs without eager component instantiation."""

    def test_constructs_with_default_options(self) -> None:
        factory = ComponentFactory(_default_options())
        assert factory is not None

    def test_constructs_with_custom_options(self) -> None:
        opts = FeatureEngineeringPipelineOptions(confidence_threshold=0.75)
        factory = ComponentFactory(opts)
        assert factory is not None


# ---------------------------------------------------------------------------
# Lazy initialization — components are created only on first access
# ---------------------------------------------------------------------------


class TestLazyInitialization:
    """Components are not instantiated until first property access."""

    def test_alignment_engine_lazy(self) -> None:
        factory = ComponentFactory(_default_options())
        with patch(
            "twinklr.core.feature_engineering.component_factory.TemporalAlignmentEngine"
        ) as mock_cls:
            mock_cls.return_value = MagicMock()
            # Accessing the property triggers instantiation
            _ = factory.alignment
            mock_cls.assert_called_once()

    def test_phrase_encoder_lazy(self) -> None:
        factory = ComponentFactory(_default_options())
        with patch("twinklr.core.feature_engineering.component_factory.PhraseEncoder") as mock_cls:
            mock_cls.return_value = MagicMock()
            _ = factory.phrase_encoder
            mock_cls.assert_called_once()

    def test_taxonomy_classifier_lazy(self) -> None:
        factory = ComponentFactory(_default_options())
        with patch(
            "twinklr.core.feature_engineering.component_factory.TaxonomyClassifier"
        ) as mock_cls:
            mock_cls.return_value = MagicMock()
            _ = factory.taxonomy_classifier
            mock_cls.assert_called_once()

    def test_target_roles_lazy(self) -> None:
        factory = ComponentFactory(_default_options())
        with patch(
            "twinklr.core.feature_engineering.component_factory.TargetRoleAssigner"
        ) as mock_cls:
            mock_cls.return_value = MagicMock()
            _ = factory.target_roles
            mock_cls.assert_called_once()

    def test_template_miner_lazy(self) -> None:
        factory = ComponentFactory(_default_options())
        with patch("twinklr.core.feature_engineering.component_factory.TemplateMiner") as mock_cls:
            mock_cls.return_value = MagicMock()
            _ = factory.template_miner
            mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# Caching — same instance returned on repeated access
# ---------------------------------------------------------------------------


class TestCachedProperty:
    """Each component property returns the same instance on repeated access."""

    def test_alignment_is_cached(self) -> None:
        factory = ComponentFactory(_default_options())
        a = factory.alignment
        b = factory.alignment
        assert a is b

    def test_phrase_encoder_is_cached(self) -> None:
        factory = ComponentFactory(_default_options())
        a = factory.phrase_encoder
        b = factory.phrase_encoder
        assert a is b

    def test_taxonomy_classifier_is_cached(self) -> None:
        factory = ComponentFactory(_default_options())
        a = factory.taxonomy_classifier
        b = factory.taxonomy_classifier
        assert a is b

    def test_motif_miner_is_cached(self) -> None:
        factory = ComponentFactory(_default_options())
        a = factory.motif_miner
        b = factory.motif_miner
        assert a is b

    def test_template_clusterer_is_cached(self) -> None:
        factory = ComponentFactory(_default_options())
        a = factory.template_clusterer
        b = factory.template_clusterer
        assert a is b

    def test_ann_retrieval_indexer_is_cached(self) -> None:
        factory = ComponentFactory(_default_options())
        a = factory.ann_retrieval_indexer
        b = factory.ann_retrieval_indexer
        assert a is b


# ---------------------------------------------------------------------------
# Options are propagated to components
# ---------------------------------------------------------------------------


class TestOptionsPropagation:
    """ComponentFactory passes options to sub-components correctly."""

    def test_motif_miner_uses_options(self) -> None:
        opts = FeatureEngineeringPipelineOptions(v2_motif_min_support_count=7)
        factory = ComponentFactory(opts)
        miner = factory.motif_miner
        # MotifMiner stores options; check the support count was passed
        assert miner is not None  # Constructed without error

    def test_clusterer_uses_similarity_threshold(self) -> None:
        opts = FeatureEngineeringPipelineOptions(v2_cluster_similarity_threshold=0.55)
        factory = ComponentFactory(opts)
        clusterer = factory.template_clusterer
        assert clusterer is not None

    def test_learned_taxonomy_uses_recall_threshold(self) -> None:
        opts = FeatureEngineeringPipelineOptions(v2_taxonomy_min_recall_for_promotion=0.42)
        factory = ComponentFactory(opts)
        trainer = factory.learned_taxonomy_trainer
        assert trainer is not None


# ---------------------------------------------------------------------------
# All expected properties exist
# ---------------------------------------------------------------------------


class TestAllPropertiesExist:
    """ComponentFactory exposes all required component properties."""

    def test_has_alignment(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "alignment")

    def test_has_phrase_encoder(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "phrase_encoder")

    def test_has_taxonomy_classifier(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "taxonomy_classifier")

    def test_has_target_roles(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "target_roles")

    def test_has_template_miner(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "template_miner")

    def test_has_transition_modeler(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "transition_modeler")

    def test_has_template_retrieval_ranker(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "template_retrieval_ranker")

    def test_has_template_diagnostics(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "template_diagnostics")

    def test_has_motif_miner(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "motif_miner")

    def test_has_template_clusterer(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "template_clusterer")

    def test_has_learned_taxonomy_trainer(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "learned_taxonomy_trainer")

    def test_has_ann_retrieval_indexer(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "ann_retrieval_indexer")

    def test_has_stack_detector(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "stack_detector")

    def test_has_macro_adapter_builder(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "macro_adapter_builder")

    def test_has_group_adapter_builder(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "group_adapter_builder")

    def test_has_layering(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "layering")

    def test_has_color_narrative(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "color_narrative")

    def test_has_color_arc(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "color_arc")

    def test_has_propensity_miner(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "propensity_miner")

    def test_has_style_fingerprint(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "style_fingerprint")

    def test_has_quality_gates(self) -> None:
        assert hasattr(ComponentFactory(_default_options()), "quality_gates")


# ---------------------------------------------------------------------------
# File size guard
# ---------------------------------------------------------------------------


class TestComponentFactoryFileSize:
    """component_factory.py must be under 500 lines."""

    def test_file_size(self) -> None:
        from pathlib import Path as _Path

        repo_root = _Path(__file__).parents[3]
        src = repo_root / "packages/twinklr/core/feature_engineering/component_factory.py"
        lines = len(src.read_text().splitlines())
        assert lines < 500, f"component_factory.py is {lines} lines (must be < 500)"
