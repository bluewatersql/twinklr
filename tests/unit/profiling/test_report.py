"""Unit tests for markdown report generation."""

from __future__ import annotations

from twinklr.core.profiling.models.effects import EffectStatistics
from twinklr.core.profiling.models.events import BaseEffectEventsFile
from twinklr.core.profiling.models.layout import (
    GroupProfile,
    LayoutMetadata,
    LayoutProfile,
    LayoutStatistics,
    ModelProfile,
)
from twinklr.core.profiling.models.pack import PackageManifest
from twinklr.core.profiling.models.palette import ColorPaletteProfile, PaletteClassifications
from twinklr.core.profiling.models.profile import (
    AssetInventory,
    LineageIndex,
    SequenceMetadata,
    SequencePackProfile,
)
from twinklr.core.profiling.report import generate_layout_report_md, generate_profile_summary_md


def _layout_profile() -> LayoutProfile:
    return LayoutProfile(
        metadata=LayoutMetadata(
            source_file="xlights_rgbeffects.xml",
            source_path="/tmp/xlights_rgbeffects.xml",
            file_sha256="sha",
            file_size_bytes=10,
        ),
        statistics=LayoutStatistics(
            total_models=1,
            display_models=1,
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
        models=(
            ModelProfile(
                name="Arch 1",
                display_as="Arches",
                category="display",
                is_active=True,
                string_type="RGB",
                semantic_tags=("arch",),
                position={"world_x": 0.0, "world_y": 0.0, "world_z": 0.0},
                scale={"x": 1.0, "y": 1.0, "z": 1.0},
                rotation={"x": 0.0, "y": 0.0, "z": 0.0},
                pixel_count=10,
                node_count=10,
                string_count=1,
                channels_per_node=3,
                channel_count=30,
                light_count=10,
                layout_group="Default",
                default_buffer_wxh="10x1",
                est_current_amps=0.6,
            ),
        ),
        groups=(
            GroupProfile(
                name="Group 1",
                members=("Arch 1",),
                model_count=1,
                semantic_tags=("arch",),
                layout="",
                layout_group="Default",
                is_homogeneous=True,
                total_pixels=10,
            ),
        ),
    )


def _profile() -> SequencePackProfile:
    layout = _layout_profile()
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
            song="Carol of the Bells",
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


def test_generate_layout_report_md() -> None:
    md = generate_layout_report_md(_layout_profile())
    assert "# RGB Effects Layout Profile" in md


def test_generate_profile_summary_md_contains_song() -> None:
    md = generate_profile_summary_md(_profile())
    assert "Carol of the Bells" in md


def test_report_generation_idempotent() -> None:
    profile = _profile()
    assert generate_profile_summary_md(profile) == generate_profile_summary_md(profile)
    layout = _layout_profile()
    assert generate_layout_report_md(layout) == generate_layout_report_md(layout)
