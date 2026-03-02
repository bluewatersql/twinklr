"""Tests for color palette discovery wiring in corpus_artifacts.

Validates that ColorFamilyDiscoverer.discover() is called when
enable_color_discovery=True and the palette path flows to ColorArcExtractor.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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


class TestColorDiscoveryWiring:
    """Verify ColorFamilyDiscoverer is wired into the pipeline."""

    def test_discovery_called_when_enabled(self) -> None:
        """discover() is called with phrase data when enabled."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_color_discovery=True)
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

        components.color_family_discoverer.discover.assert_called_once()

    def test_palette_library_written_when_palettes_found(self) -> None:
        """write_color_palette_library() is called when discover returns palettes."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_color_discovery=True)
        phrases = (MagicMock(),)
        components.color_family_discoverer.discover.return_value = [MagicMock()]

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

        writer.write_color_palette_library.assert_called_once()

    def test_discovery_skipped_when_disabled(self) -> None:
        """discover() is NOT called when enable_color_discovery=False."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_color_discovery=False)
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

        components.color_family_discoverer.discover.assert_not_called()

    def test_discovery_skipped_with_no_phrases(self) -> None:
        """discover() is NOT called when phrases are empty."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_color_discovery=True)

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

        components.color_family_discoverer.discover.assert_not_called()

    def test_palette_path_flows_to_color_arc(self) -> None:
        """Discovered palette path is passed to write_color_arc."""
        writer, artifact_writer, components, store = _make_mocks()
        opts = _disabled_options(enable_color_discovery=True, enable_color_arc=True)
        phrases = (MagicMock(),)
        fake_palette_path = Path("/tmp/out/color_palette_library.json")
        writer.write_color_palette_library.return_value = fake_palette_path
        components.color_family_discoverer.discover.return_value = [MagicMock()]

        with patch(
            "twinklr.core.feature_engineering.corpus_artifacts.write_color_arc"
        ) as mock_write_arc:
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

            mock_write_arc.assert_called_once()
            call_kwargs = mock_write_arc.call_args
            assert call_kwargs.kwargs.get("palette_library_path") == fake_palette_path
