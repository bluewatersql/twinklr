"""Unit tests for spatial and chain topology utilities."""

from __future__ import annotations

from twinklr.core.profiling.layout.spatial import (
    compute_spatial_statistics,
    detect_model_families,
    reconstruct_chain_sequences,
)
from twinklr.core.profiling.models.enums import ModelCategory, StartChannelFormat
from twinklr.core.profiling.models.layout import ModelProfile, StartChannelInfo


def _model(
    name: str,
    world_x: float,
    world_y: float,
    world_z: float,
    *,
    chain_next: str | None = None,
    chained_to: str | None = None,
) -> ModelProfile:
    start_channel = (
        StartChannelInfo(
            raw=f">{chained_to}:1", format=StartChannelFormat.CHAINED, chained_to=chained_to
        )
        if chained_to
        else None
    )
    return ModelProfile(
        name=name,
        display_as="Arches",
        category=ModelCategory.DISPLAY,
        is_active=True,
        string_type="RGB Nodes",
        semantic_tags=("arch",),
        position={"world_x": world_x, "world_y": world_y, "world_z": world_z},
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
        start_channel=start_channel,
        chain_next=chain_next,
    )


def test_reconstruct_chain_sequences() -> None:
    models = [
        _model("Arch 1", 0, 0, 0, chain_next="Arch 2"),
        _model("Arch 2", 1, 0, 0, chain_next="Arch 3"),
        _model("Arch 3", 2, 0, 0),
    ]
    sequences = reconstruct_chain_sequences(models)
    assert ("Arch 1", "Arch 2", "Arch 3") in sequences


def test_detect_model_families() -> None:
    families = detect_model_families(
        [
            _model("Arch 1", 0, 0, 0),
            _model("Arch 2", 1, 0, 0),
            _model("Arch 3", 2, 0, 0),
            _model("Tree", 3, 0, 0),
        ]
    )
    assert families == {"Arch": 3}


def test_compute_spatial_statistics() -> None:
    stats = compute_spatial_statistics(
        [
            _model("Arch 1", 0, 0, 0),
            _model("Arch 2", 2, 2, 0),
            _model("Arch 3", 4, 0, 1),
        ]
    )
    assert stats is not None
    assert stats.bounding_box["x_range"] == [0.0, 4.0]
    assert stats.is_3d_layout is True
