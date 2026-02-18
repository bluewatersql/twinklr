"""Layout profiling models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.profiling.models.enums import ModelCategory, SemanticSize, StartChannelFormat


class StartChannelInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    raw: str
    format: StartChannelFormat
    universe: int | None = None
    channel: int | None = None
    chained_to: str | None = None
    offset: int | None = None


class DmxMotorProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    channel_coarse: str | None = None
    channel_fine: str | None = None
    slew_limit: str | None = None
    range_of_motion: str | None = None
    orient_zero: str | None = None
    orient_home: str | None = None
    reverse: str | None = None


class DmxColorWheelEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dmx_value: str
    color: str


class DmxFixtureProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fixture_type: str
    channel_count: int
    color_type: str | None = None
    color_wheel: tuple[DmxColorWheelEntry, ...] = ()
    pan: DmxMotorProfile | None = None
    tilt: DmxMotorProfile | None = None
    node_names: tuple[str, ...] = ()
    fixture_name: str | None = None


class SubModelProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    type: str
    layout: str
    pixel_ranges: tuple[str, ...]


class ModelProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    display_as: str
    category: ModelCategory
    is_active: bool
    string_type: str
    semantic_tags: tuple[str, ...]
    semantic_size: SemanticSize | None = None
    position: dict[str, float]
    scale: dict[str, float]
    rotation: dict[str, float]
    pixel_count: int
    node_count: int
    string_count: int
    channels_per_node: int
    channel_count: int
    light_count: int
    layout_group: str
    default_buffer_wxh: str
    est_current_amps: float
    start_channel: StartChannelInfo | None = None
    start_channel_no: int | None = None
    end_channel_no: int | None = None
    controller_connection: dict[str, str | int] | None = None
    submodels: tuple[SubModelProfile, ...] = ()
    aliases: tuple[str, ...] = ()
    dmx_profile: DmxFixtureProfile | None = None
    chain_next: str | None = None


class GroupProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    members: tuple[str, ...]
    model_count: int
    semantic_tags: tuple[str, ...]
    layout: str
    layout_group: str
    is_homogeneous: bool
    total_pixels: int
    member_type_composition: dict[str, int] = Field(default_factory=dict)
    member_category_composition: dict[str, int] = Field(default_factory=dict)
    unresolved_members: tuple[str, ...] = ()


class PixelStats(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int
    min: int
    max: int
    mean: float
    median: float


class LayoutStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total_models: int
    display_models: int
    dmx_fixtures: int
    auxiliary_models: int
    inactive_models: int
    total_submodels: int
    model_chained_count: int
    address_chained_count: int
    chain_sequences: tuple[tuple[str, ...], ...]
    model_families: dict[str, int]
    model_type_distribution: dict[str, int]
    string_type_distribution: dict[str, int]
    semantic_tag_distribution: dict[str, int]
    pixel_stats: PixelStats | None = None
    channel_stats: dict[str, int | float] | None = None
    protocol_distribution: dict[str, int]
    layout_group_distribution: dict[str, int]


class SpatialStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    bounding_box: dict[str, list[float]]
    center_of_mass: dict[str, float]
    spread: dict[str, float]
    is_3d_layout: bool


class LayoutMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_file: str
    source_path: str
    file_sha256: str
    file_size_bytes: int


class LayoutProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: LayoutMetadata
    statistics: LayoutStatistics
    spatial: SpatialStatistics | None = None
    models: tuple[ModelProfile, ...]
    groups: tuple[GroupProfile, ...]
    settings: dict[str, str] = Field(default_factory=dict)
    viewpoints: tuple[dict[str, str | float | bool], ...] = ()
    dmx_fixture_summary: dict[str, int] | None = None
