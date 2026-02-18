"""Unit tests for profile artifact writer."""

from __future__ import annotations

from pathlib import Path

from twinklr.core.profiling.artifacts import ProfileArtifactWriter
from twinklr.core.profiling.models.effects import EffectStatistics
from twinklr.core.profiling.models.events import BaseEffectEventsFile
from twinklr.core.profiling.models.layout import LayoutMetadata, LayoutProfile, LayoutStatistics
from twinklr.core.profiling.models.pack import PackageManifest
from twinklr.core.profiling.models.palette import ColorPaletteProfile, PaletteClassifications
from twinklr.core.profiling.models.profile import (
    AssetInventory,
    LineageIndex,
    SequenceMetadata,
    SequencePackProfile,
)


def _profile() -> SequencePackProfile:
    layout = LayoutProfile(
        metadata=LayoutMetadata(
            source_file="xlights_rgbeffects.xml",
            source_path="/tmp/xlights_rgbeffects.xml",
            file_sha256="rgbsha",
            file_size_bytes=1,
        ),
        statistics=LayoutStatistics(
            total_models=0,
            display_models=0,
            dmx_fixtures=0,
            auxiliary_models=0,
            inactive_models=0,
            total_submodels=0,
            model_chained_count=0,
            address_chained_count=0,
            chain_sequences=(),
            model_families={},
            model_type_distribution={},
            string_type_distribution={},
            semantic_tag_distribution={},
            protocol_distribution={},
            layout_group_distribution={},
        ),
        models=(),
        groups=(),
    )
    return SequencePackProfile(
        manifest=PackageManifest(
            package_id="pkg",
            zip_sha256="zipsha",
            source_extensions=frozenset({".zip"}),
            files=(),
            sequence_file_id="seq",
            rgb_effects_file_id="rgb",
        ),
        sequence_metadata=SequenceMetadata(
            package_id="pkg",
            sequence_file_id="seq",
            sequence_sha256="seqsha",
            xlights_version="2025.1",
            sequence_duration_ms=1000,
            media_file="song.mp3",
            image_dir="_lost",
            song="Song",
            artist="Artist",
            album="Album",
            author="Author",
        ),
        layout_profile=layout,
        effect_statistics=EffectStatistics(
            total_events=0,
            distinct_effect_types=0,
            total_effect_duration_ms=0,
            avg_effect_duration_ms=0.0,
            total_targets_with_effects=0,
            effect_type_counts={},
            effect_type_durations_ms={},
            effect_type_profiles={},
            effects_per_target={},
            layers_per_target={},
        ),
        palette_profile=ColorPaletteProfile(
            unique_colors=(),
            single_colors=(),
            color_palettes=(),
            classifications=PaletteClassifications(
                monochrome=(),
                warm=(),
                cool=(),
                primary_only=(),
                by_color_family={},
            ),
        ),
        asset_inventory=AssetInventory(assets=(), shaders=()),
        base_events=BaseEffectEventsFile(
            package_id="pkg",
            sequence_file_id="seq",
            sequence_sha256="seqsha",
            events=(),
        ),
        enriched_events=(),
        lineage=LineageIndex(
            package_id="pkg",
            zip_sha256="zipsha",
            sequence_file={"file_id": "seq", "filename": "sequence.xsq"},
            rgb_effects_file=None,
            layout_id=None,
            rgb_sha256=None,
        ),
    )


def test_write_json_bundle_outputs_expected_files(tmp_path: Path) -> None:
    profile = _profile()
    writer = ProfileArtifactWriter()
    writer.write_json_bundle(tmp_path, profile)

    expected = {
        "package_manifest.json",
        "sequence_metadata.json",
        "base_effect_events.json",
        "enriched_effect_events.json",
        "effect_statistics.json",
        "color_palettes.json",
        "asset_inventory.json",
        "shader_inventory.json",
        "lineage_index.json",
        "rgbeffects_profile.json",
        "layout_semantics.json",
    }
    assert expected.issubset({p.name for p in tmp_path.iterdir()})


def test_write_markdown_bundle_outputs_reports(tmp_path: Path) -> None:
    profile = _profile()
    writer = ProfileArtifactWriter()
    writer.write_markdown_bundle(tmp_path, profile)

    assert (tmp_path / "profile_summary.md").exists()
    assert (tmp_path / "profile_rgbeffects.md").exists()
