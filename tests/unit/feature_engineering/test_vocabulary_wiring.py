"""Tests for vocabulary expansion wiring in corpus_artifacts.

Validates that VocabularyExpander.expand() is called when
enable_vocabulary_expansion=True and stack data is available.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.corpus_artifacts import write_v1_tail_artifacts
from twinklr.core.feature_engineering.models.stacks import EffectStackCatalog


def _disabled_options(**overrides: object) -> FeatureEngineeringPipelineOptions:
    """Create options with all stages disabled except explicit overrides."""
    defaults: dict[str, object] = {
        "enable_transition_modeling": False,
        "enable_layering_features": False,
        "enable_color_narrative": False,
        "enable_color_arc": False,
        "enable_propensity": False,
        "enable_style_fingerprint": False,
        "enable_quality_gates": False,
        "enable_recipe_promotion": False,
        "enable_color_discovery": False,
        "enable_effect_metadata": False,
        "enable_vocabulary_expansion": False,
        "enable_v2_motif_mining": False,
        "enable_v2_temporal_motif_mining": False,
        "enable_v2_clustering": False,
        "enable_v2_learned_taxonomy": False,
        "enable_v2_ann_retrieval": False,
        "enable_v2_adapter_contracts": False,
        "enable_template_retrieval_ranking": False,
        "enable_template_diagnostics": False,
    }
    defaults.update(overrides)
    return FeatureEngineeringPipelineOptions(**defaults)  # type: ignore[arg-type]


def _make_mocks() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """Create mock writer, artifact_writer, components, store."""
    writer = MagicMock()
    artifact_writer = MagicMock()
    components = MagicMock()
    store = MagicMock()
    return writer, artifact_writer, components, store


def _make_stack_catalog() -> EffectStackCatalog:
    """Create a minimal EffectStackCatalog for testing."""
    return EffectStackCatalog(
        total_phrase_count=2,
        total_stack_count=1,
        single_layer_count=0,
        multi_layer_count=1,
        max_layer_count=2,
        stacks=(),
    )


class TestVocabularyExpansionWiring:
    """Verify VocabularyExpander is wired into the pipeline."""

    def test_expand_called_when_enabled_with_stacks(self) -> None:
        """expand() is called when enabled and stacks are available."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_vocabulary_expansion=True)
        phrases = (MagicMock(),)
        mock_stacks = (MagicMock(layer_count=2),)

        with patch(
            "twinklr.core.feature_engineering.corpus_artifacts._build_stack_catalog",
            return_value=_make_stack_catalog(),
        ):
            write_v1_tail_artifacts(
                output_root=Path("/tmp/out"),
                bundles=(),
                phrases=phrases,
                taxonomy_rows=(),
                target_roles=(),
                template_catalogs=None,
                stacks=mock_stacks,
                options=opts,
                writer=writer,
                artifact_writer=artifact_writer,
                components=components,
                store=store,
            )

        components.vocabulary_expander.expand.assert_called_once()

    def test_extensions_written_when_expanded(self) -> None:
        """write_vocabulary_extensions() is called after expansion."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_vocabulary_expansion=True)
        phrases = (MagicMock(),)
        mock_stacks = (MagicMock(layer_count=2),)

        with patch(
            "twinklr.core.feature_engineering.corpus_artifacts._build_stack_catalog",
            return_value=_make_stack_catalog(),
        ):
            write_v1_tail_artifacts(
                output_root=Path("/tmp/out"),
                bundles=(),
                phrases=phrases,
                taxonomy_rows=(),
                target_roles=(),
                template_catalogs=None,
                stacks=mock_stacks,
                options=opts,
                writer=writer,
                artifact_writer=artifact_writer,
                components=components,
                store=store,
            )

        writer.write_vocabulary_extensions.assert_called_once()

    def test_expand_skipped_when_disabled(self) -> None:
        """expand() is NOT called when enable_vocabulary_expansion=False."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_vocabulary_expansion=False)
        phrases = (MagicMock(),)
        mock_stacks = (MagicMock(layer_count=2),)

        with patch(
            "twinklr.core.feature_engineering.corpus_artifacts._build_stack_catalog",
            return_value=_make_stack_catalog(),
        ):
            write_v1_tail_artifacts(
                output_root=Path("/tmp/out"),
                bundles=(),
                phrases=phrases,
                taxonomy_rows=(),
                target_roles=(),
                template_catalogs=None,
                stacks=mock_stacks,
                options=opts,
                writer=writer,
                artifact_writer=artifact_writer,
                components=components,
                store=store,
            )

        components.vocabulary_expander.expand.assert_not_called()

    def test_expand_skipped_without_stacks(self) -> None:
        """expand() is NOT called when no stacks are provided."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_vocabulary_expansion=True)
        phrases = (MagicMock(),)

        write_v1_tail_artifacts(
            output_root=Path("/tmp/out"),
            bundles=(),
            phrases=phrases,
            taxonomy_rows=(),
            target_roles=(),
            template_catalogs=None,
            stacks=None,
            options=opts,
            writer=writer,
            artifact_writer=artifact_writer,
            components=components,
            store=store,
        )

        components.vocabulary_expander.expand.assert_not_called()

    def test_expand_receives_stack_catalog(self) -> None:
        """expand() receives stack_catalog kwarg."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_vocabulary_expansion=True)
        phrases = (MagicMock(),)
        mock_stacks = (MagicMock(layer_count=2),)
        mock_catalog = _make_stack_catalog()

        with patch(
            "twinklr.core.feature_engineering.corpus_artifacts._build_stack_catalog",
            return_value=mock_catalog,
        ):
            write_v1_tail_artifacts(
                output_root=Path("/tmp/out"),
                bundles=(),
                phrases=phrases,
                taxonomy_rows=(),
                target_roles=(),
                template_catalogs=None,
                stacks=mock_stacks,
                options=opts,
                writer=writer,
                artifact_writer=artifact_writer,
                components=components,
                store=store,
            )

        call_kwargs = components.vocabulary_expander.expand.call_args
        assert call_kwargs.kwargs.get("stack_catalog") == mock_catalog
