"""Tests for effect metadata profile builder wiring in corpus_artifacts.

Validates that EffectMetadataProfileBuilder.build() is called when
enable_effect_metadata=True and results are written via the writer.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.corpus_artifacts import write_v1_tail_artifacts


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


class TestEffectMetadataWiring:
    """Verify EffectMetadataProfileBuilder is wired into the pipeline."""

    def test_builder_called_when_enabled(self) -> None:
        """build() is called when enable_effect_metadata=True and phrases exist."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_effect_metadata=True)
        phrases = (MagicMock(),)

        write_v1_tail_artifacts(
            output_root=Path("/tmp/out"),
            bundles=(),
            phrases=phrases,
            taxonomy_rows=(),
            target_roles=(),
            template_catalogs=None,
            options=opts,
            writer=writer,
            artifact_writer=artifact_writer,
            components=components,
            store=store,
        )

        components.effect_metadata_builder.build.assert_called_once()

    def test_metadata_written_when_enabled(self) -> None:
        """write_effect_metadata() is called when builder produces output."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_effect_metadata=True)
        phrases = (MagicMock(),)

        write_v1_tail_artifacts(
            output_root=Path("/tmp/out"),
            bundles=(),
            phrases=phrases,
            taxonomy_rows=(),
            target_roles=(),
            template_catalogs=None,
            options=opts,
            writer=writer,
            artifact_writer=artifact_writer,
            components=components,
            store=store,
        )

        writer.write_effect_metadata.assert_called_once()

    def test_builder_skipped_when_disabled(self) -> None:
        """build() is NOT called when enable_effect_metadata=False."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_effect_metadata=False)
        phrases = (MagicMock(),)

        write_v1_tail_artifacts(
            output_root=Path("/tmp/out"),
            bundles=(),
            phrases=phrases,
            taxonomy_rows=(),
            target_roles=(),
            template_catalogs=None,
            options=opts,
            writer=writer,
            artifact_writer=artifact_writer,
            components=components,
            store=store,
        )

        components.effect_metadata_builder.build.assert_not_called()

    def test_builder_skipped_with_no_phrases(self) -> None:
        """build() is NOT called when phrases are empty."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_effect_metadata=True)

        write_v1_tail_artifacts(
            output_root=Path("/tmp/out"),
            bundles=(),
            phrases=(),
            taxonomy_rows=(),
            target_roles=(),
            template_catalogs=None,
            options=opts,
            writer=writer,
            artifact_writer=artifact_writer,
            components=components,
            store=store,
        )

        components.effect_metadata_builder.build.assert_not_called()

    def test_builder_receives_stacks_and_propensity(self) -> None:
        """build() receives stack_catalog and propensity_index arguments."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_effect_metadata=True)
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

        call_kwargs = components.effect_metadata_builder.build.call_args
        assert "phrases" in call_kwargs.kwargs
        assert "stacks" in call_kwargs.kwargs
        assert "propensity" in call_kwargs.kwargs
