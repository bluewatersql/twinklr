"""Tests for temporal motif mining wiring in corpus_artifacts.

Validates that MotifMiner.mine_temporal() is called when
enable_v2_temporal_motif_mining=True and template catalogs are available.
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


def _make_template_catalogs() -> tuple[MagicMock, MagicMock]:
    """Create a mock (content_catalog, orchestration_catalog) tuple."""
    content = MagicMock()
    orchestration = MagicMock()
    content.templates = ()
    orchestration.templates = ()
    return content, orchestration


class TestTemporalMotifWiring:
    """Verify MotifMiner.mine_temporal() is wired into the pipeline."""

    def test_mine_temporal_called_when_enabled(self) -> None:
        """mine_temporal() is called when enabled and template_catalogs present."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_v2_temporal_motif_mining=True)
        phrases = (MagicMock(),)
        catalogs = _make_template_catalogs()

        write_v1_tail_artifacts(
            output_root=Path("/tmp/out"),
            bundles=(),
            phrases=phrases,
            taxonomy_rows=(),
            target_roles=(),
            template_catalogs=catalogs,
            options=opts,
            writer=writer,
            artifact_writer=artifact_writer,
            components=components,
            store=store,
        )

        components.motif_miner.mine_temporal.assert_called_once()

    def test_temporal_catalog_written(self) -> None:
        """write_temporal_motif_catalog() is called after mining."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_v2_temporal_motif_mining=True)
        phrases = (MagicMock(),)
        catalogs = _make_template_catalogs()

        write_v1_tail_artifacts(
            output_root=Path("/tmp/out"),
            bundles=(),
            phrases=phrases,
            taxonomy_rows=(),
            target_roles=(),
            template_catalogs=catalogs,
            options=opts,
            writer=writer,
            artifact_writer=artifact_writer,
            components=components,
            store=store,
        )

        writer.write_temporal_motif_catalog.assert_called_once()

    def test_mine_temporal_skipped_when_disabled(self) -> None:
        """mine_temporal() is NOT called when enable_v2_temporal_motif_mining=False."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_v2_temporal_motif_mining=False)
        phrases = (MagicMock(),)
        catalogs = _make_template_catalogs()

        write_v1_tail_artifacts(
            output_root=Path("/tmp/out"),
            bundles=(),
            phrases=phrases,
            taxonomy_rows=(),
            target_roles=(),
            template_catalogs=catalogs,
            options=opts,
            writer=writer,
            artifact_writer=artifact_writer,
            components=components,
            store=store,
        )

        components.motif_miner.mine_temporal.assert_not_called()

    def test_mine_temporal_skipped_without_catalogs(self) -> None:
        """mine_temporal() is NOT called when template_catalogs is None."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_v2_temporal_motif_mining=True)
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

        components.motif_miner.mine_temporal.assert_not_called()
