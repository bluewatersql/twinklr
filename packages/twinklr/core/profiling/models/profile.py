"""Top-level profiling output models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from twinklr.core.profiling.models.effects import EffectStatistics
from twinklr.core.profiling.models.enums import TargetKind
from twinklr.core.profiling.models.events import BaseEffectEventsFile
from twinklr.core.profiling.models.layout import LayoutProfile
from twinklr.core.profiling.models.pack import PackageManifest
from twinklr.core.profiling.models.palette import ColorPaletteProfile


class SequenceMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    package_id: str
    sequence_file_id: str
    sequence_sha256: str
    xlights_version: str
    sequence_duration_ms: int
    media_file: str
    image_dir: str
    song: str
    artist: str
    album: str
    author: str


class AssetInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    assets: tuple[dict[str, str], ...]
    shaders: tuple[dict[str, str], ...]


class EnrichedEventRecord(BaseModel):
    """Effect event record enriched with optional layout context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    effect_event_id: str
    target_name: str
    layer_index: int
    layer_name: str
    effect_type: str
    start_ms: int
    end_ms: int
    config_fingerprint: str
    effectdb_ref: int | None = None
    effectdb_settings: str | None = None
    palette: str
    protected: bool
    label: str | None = None

    feat_duration_ms: int

    target_kind: TargetKind | None = None
    target_semantic_tags: tuple[str, ...] | None = None
    target_category: str | None = None
    target_pixel_count: int | None = None
    target_string_type: str | None = None
    target_layout_group: str | None = None
    target_is_homogeneous: bool | None = None
    target_x0: float | None = None
    target_y0: float | None = None
    target_x1: float | None = None
    target_y1: float | None = None

    @model_validator(mode="after")
    def validate_duration(self) -> EnrichedEventRecord:
        expected = self.end_ms - self.start_ms
        if self.feat_duration_ms != expected:
            raise ValueError("feat_duration_ms must equal end_ms - start_ms")
        return self


class LineageIndex(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    package_id: str
    zip_sha256: str
    sequence_file: dict[str, str]
    rgb_effects_file: dict[str, str] | None
    layout_id: str | None
    rgb_sha256: str | None


class SequencePackProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest: PackageManifest
    sequence_metadata: SequenceMetadata
    layout_profile: LayoutProfile | None
    effect_statistics: EffectStatistics
    palette_profile: ColorPaletteProfile
    asset_inventory: AssetInventory
    base_events: BaseEffectEventsFile
    enriched_events: tuple[EnrichedEventRecord, ...]
    lineage: LineageIndex
