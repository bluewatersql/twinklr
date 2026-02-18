"""Unit tests for event enrichment joins."""

from __future__ import annotations

from twinklr.core.profiling.enrich import enrich_events
from twinklr.core.profiling.models.enums import ModelCategory, TargetKind
from twinklr.core.profiling.models.events import EffectEventRecord
from twinklr.core.profiling.models.layout import (
    GroupProfile,
    LayoutMetadata,
    LayoutProfile,
    LayoutStatistics,
    ModelProfile,
)


def _layout() -> LayoutProfile:
    model = ModelProfile(
        name="Arch 1",
        display_as="Arches",
        category=ModelCategory.DISPLAY,
        is_active=True,
        string_type="RGB",
        semantic_tags=("arch",),
        position={"world_x": 1.0, "world_y": 2.0, "world_z": 0.0},
        scale={"x": 1.0, "y": 1.0, "z": 1.0},
        rotation={"x": 0.0, "y": 0.0, "z": 0.0},
        pixel_count=10,
        node_count=10,
        string_count=1,
        channels_per_node=3,
        channel_count=30,
        light_count=10,
        layout_group="HOUSE",
        default_buffer_wxh="10x1",
        est_current_amps=0.6,
    )
    group = GroupProfile(
        name="Arches",
        members=("Arch 1",),
        model_count=1,
        semantic_tags=("arch",),
        layout="",
        layout_group="HOUSE",
        is_homogeneous=True,
        total_pixels=10,
        member_type_composition={"Arches": 1},
        member_category_composition={"display": 1},
    )
    return LayoutProfile(
        metadata=LayoutMetadata(
            source_file="xlights_rgbeffects.xml",
            source_path="/tmp/xlights_rgbeffects.xml",
            file_sha256="sha",
            file_size_bytes=1,
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
        models=(model,),
        groups=(group,),
    )


def _event(target_name: str) -> EffectEventRecord:
    return EffectEventRecord(
        effect_event_id="evt",
        target_name=target_name,
        layer_index=0,
        layer_name="Main",
        effect_type="Bars",
        start_ms=100,
        end_ms=200,
        config_fingerprint="fp",
        palette="#FF0000",
        protected=False,
        label=None,
    )


def test_enrich_model_target() -> None:
    enriched = enrich_events((_event("Arch 1"),), _layout())
    event = enriched[0]
    assert event.target_kind is TargetKind.MODEL
    assert event.target_category == "display"
    assert event.target_semantic_tags == ("arch",)
    assert event.target_x0 == 1.0


def test_enrich_group_target() -> None:
    enriched = enrich_events((_event("Arches"),), _layout())
    event = enriched[0]
    assert event.target_kind is TargetKind.GROUP
    assert event.target_is_homogeneous is True
    assert event.target_semantic_tags == ("arch",)


def test_enrich_unknown_target() -> None:
    enriched = enrich_events((_event("Missing"),), _layout())
    event = enriched[0]
    assert event.target_kind is TargetKind.UNKNOWN
    assert event.target_category is None
    assert event.target_x0 is None
