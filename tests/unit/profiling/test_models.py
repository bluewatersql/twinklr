"""Unit tests for profiling model contracts."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from twinklr.core.profiling.models.effects import (
    CategoricalValueProfile,
    DurationStats,
    EffectStatistics,
    EffectTypeProfile,
    NumericValueProfile,
    ParameterProfile,
)
from twinklr.core.profiling.models.enums import (
    FileKind,
    ModelCategory,
    ParameterValueType,
    SemanticSize,
    StartChannelFormat,
    TargetKind,
)
from twinklr.core.profiling.models.events import BaseEffectEventsFile, EffectEventRecord
from twinklr.core.profiling.models.layout import (
    GroupProfile,
    LayoutMetadata,
    LayoutProfile,
    LayoutStatistics,
    ModelProfile,
    PixelStats,
    SpatialStatistics,
    StartChannelInfo,
)
from twinklr.core.profiling.models.pack import FileEntry, PackageManifest
from twinklr.core.profiling.models.palette import (
    ColorPaletteProfile,
    PaletteClassifications,
    PaletteEntry,
)
from twinklr.core.profiling.models.profile import (
    AssetInventory,
    EnrichedEventRecord,
    LineageIndex,
    SequenceMetadata,
    SequencePackProfile,
)


def _make_event() -> EffectEventRecord:
    return EffectEventRecord(
        effect_event_id="evt-1",
        target_name="Arch 1",
        layer_index=0,
        layer_name="Normal",
        effect_type="Bars",
        start_ms=100,
        end_ms=300,
        config_fingerprint="abc123",
        effectdb_ref=0,
        effectdb_settings="speed=10",
        palette="#FF0000",
        protected=False,
        label="intro",
    )


def _make_model() -> ModelProfile:
    return ModelProfile(
        name="Arch 1",
        display_as="Arches",
        category=ModelCategory.DISPLAY,
        is_active=True,
        string_type="RGB Nodes",
        semantic_tags=("arch",),
        semantic_size=SemanticSize.MINI,
        position={"world_x": 0.0, "world_y": 1.0, "world_z": 2.0},
        scale={"x": 1.0, "y": 1.0, "z": 1.0},
        rotation={"x": 0.0, "y": 0.0, "z": 0.0},
        pixel_count=50,
        node_count=50,
        string_count=1,
        channels_per_node=3,
        channel_count=150,
        light_count=50,
        layout_group="HOUSE",
        default_buffer_wxh="50x1",
        est_current_amps=1.2,
        start_channel=StartChannelInfo(raw="1:1", format=StartChannelFormat.UNIVERSE_CHANNEL),
        start_channel_no=1,
        end_channel_no=150,
        controller_connection={"protocol": "E131", "universe": 1},
        chain_next=None,
    )


def test_models_construct_with_valid_data() -> None:
    file_entry = FileEntry(
        file_id="file-1",
        filename="sequence.xsq",
        ext=".xsq",
        size=123,
        sha256="deadbeef",
        kind=FileKind.SEQUENCE,
    )
    manifest = PackageManifest(
        package_id="pkg-1",
        zip_sha256="z123",
        source_extensions=frozenset({".zip"}),
        files=(file_entry,),
        sequence_file_id="file-1",
        rgb_effects_file_id=None,
    )

    event = _make_event()
    base_events = BaseEffectEventsFile(
        package_id="pkg-1",
        sequence_file_id="file-1",
        sequence_sha256="s123",
        events=(event,),
    )

    model = _make_model()
    group = GroupProfile(
        name="Arches",
        members=("Arch 1",),
        model_count=1,
        semantic_tags=("arch",),
        layout="Default",
        layout_group="HOUSE",
        is_homogeneous=True,
        total_pixels=50,
    )
    layout = LayoutProfile(
        metadata=LayoutMetadata(
            source_file="xlights_rgbeffects.xml",
            source_path="/tmp/xlights_rgbeffects.xml",
            file_sha256="rgb123",
            file_size_bytes=100,
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
            model_families={"Arch": 1},
            model_type_distribution={"Arches": 1},
            string_type_distribution={"RGB Nodes": 1},
            semantic_tag_distribution={"arch": 1},
            pixel_stats=PixelStats(total=50, min=50, max=50, mean=50.0, median=50.0),
            protocol_distribution={"E131": 1},
            layout_group_distribution={"HOUSE": 1},
        ),
        spatial=SpatialStatistics(
            bounding_box={"x_range": [0.0, 1.0], "y_range": [0.0, 1.0], "z_range": [0.0, 0.0]},
            center_of_mass={"x": 0.5, "y": 0.5, "z": 0.0},
            spread={"x_std": 0.1, "y_std": 0.1, "z_std": 0.0},
            is_3d_layout=False,
        ),
        models=(model,),
        groups=(group,),
    )

    param_profile = ParameterProfile(
        type=ParameterValueType.INT,
        count=1,
        numeric_profile=NumericValueProfile(min=1.0, max=1.0, avg=1.0, median=1.0),
    )
    effect_stats = EffectStatistics(
        total_events=1,
        distinct_effect_types=1,
        total_effect_duration_ms=200,
        avg_effect_duration_ms=200.0,
        total_targets_with_effects=1,
        effect_type_counts={"Bars": 1},
        effect_type_durations_ms={"Bars": 200},
        effect_type_profiles={
            "Bars": EffectTypeProfile(
                instance_count=1,
                duration_stats=DurationStats(
                    count=1, min_ms=200, max_ms=200, avg_ms=200.0, median_ms=200.0
                ),
                buffer_styles=("Default",),
                parameter_names=("Speed",),
                parameters={"Speed": param_profile},
            )
        },
        effects_per_target={"Arch 1": 1},
        layers_per_target={"Arch 1": 1},
    )

    palette = ColorPaletteProfile(
        unique_colors=("#FF0000",),
        single_colors=(PaletteEntry(colors=("#FF0000",), palette_entry_indices=(0,)),),
        color_palettes=(),
        classifications=PaletteClassifications(
            monochrome=(),
            warm=(),
            cool=(),
            primary_only=(),
            by_color_family={"red": ()},
        ),
    )

    enriched = EnrichedEventRecord(
        effect_event_id=event.effect_event_id,
        target_name=event.target_name,
        layer_index=event.layer_index,
        layer_name=event.layer_name,
        effect_type=event.effect_type,
        start_ms=event.start_ms,
        end_ms=event.end_ms,
        config_fingerprint=event.config_fingerprint,
        effectdb_ref=event.effectdb_ref,
        effectdb_settings=event.effectdb_settings,
        palette=event.palette,
        protected=event.protected,
        label=event.label,
        feat_duration_ms=200,
        target_kind=TargetKind.MODEL,
        target_semantic_tags=("arch",),
        target_category=ModelCategory.DISPLAY.value,
        target_pixel_count=50,
        target_string_type="RGB Nodes",
        target_layout_group="HOUSE",
        target_is_homogeneous=None,
        target_x0=0.0,
        target_y0=0.0,
        target_x1=1.0,
        target_y1=1.0,
    )

    profile = SequencePackProfile(
        manifest=manifest,
        sequence_metadata=SequenceMetadata(
            package_id="pkg-1",
            sequence_file_id="file-1",
            sequence_sha256="s123",
            xlights_version="2025.1",
            sequence_duration_ms=180000,
            media_file="song.mp3",
            image_dir="_lost",
            song="Song",
            artist="Artist",
            album="Album",
            author="Author",
        ),
        layout_profile=layout,
        effect_statistics=effect_stats,
        palette_profile=palette,
        asset_inventory=AssetInventory(
            assets=({"filename": "song.mp3", "asset_type": "audio"},),
            shaders=(),
        ),
        base_events=base_events,
        enriched_events=(enriched,),
        lineage=LineageIndex(
            package_id="pkg-1",
            zip_sha256="z123",
            sequence_file={"file_id": "file-1", "filename": "sequence.xsq"},
            rgb_effects_file={"file_id": "rgb-1", "filename": "xlights_rgbeffects.xml"},
            layout_id="layout-1",
            rgb_sha256="rgb123",
        ),
    )

    assert profile.sequence_metadata.song == "Song"


def test_frozen_models_reject_mutation() -> None:
    event = _make_event()
    with pytest.raises(ValidationError):
        event.start_ms = 999


def test_extra_forbid_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        FileEntry(
            file_id="file-1",
            filename="sequence.xsq",
            ext=".xsq",
            size=123,
            sha256="deadbeef",
            kind=FileKind.SEQUENCE,
            unexpected="nope",
        )


def test_event_validator_enforces_end_ms_after_start_ms() -> None:
    with pytest.raises(ValidationError):
        EffectEventRecord(
            effect_event_id="evt-1",
            target_name="Arch 1",
            layer_index=0,
            layer_name="Normal",
            effect_type="Bars",
            start_ms=300,
            end_ms=100,
            config_fingerprint="abc123",
            palette="#FF0000",
            protected=False,
            label=None,
        )


def test_enriched_event_duration_validator() -> None:
    with pytest.raises(ValidationError):
        EnrichedEventRecord(
            effect_event_id="evt-1",
            target_name="Arch 1",
            layer_index=0,
            layer_name="Normal",
            effect_type="Bars",
            start_ms=100,
            end_ms=200,
            config_fingerprint="abc123",
            palette="#FF0000",
            protected=False,
            label=None,
            feat_duration_ms=999,
            target_kind=TargetKind.UNKNOWN,
        )


def test_categorical_profile_distinct_count_validator() -> None:
    with pytest.raises(ValidationError):
        CategoricalValueProfile(distinct_values=("a", "b"), distinct_count=1)
