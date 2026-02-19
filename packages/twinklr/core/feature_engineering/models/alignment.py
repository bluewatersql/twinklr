"""Temporal alignment model contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AlignmentStatus(str, Enum):
    """Alignment result status for an event."""

    ALIGNED = "aligned"
    NO_AUDIO = "no_audio"
    NO_BEATS = "no_beats"


class AlignedEffectEvent(BaseModel):
    """Event enriched with musical-time alignment features."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    package_id: str
    sequence_file_id: str
    effect_event_id: str

    target_name: str
    layer_index: int
    effect_type: str

    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    start_s: float = Field(ge=0.0)
    end_s: float = Field(ge=0.0)

    start_beat_index: int | None = None
    end_beat_index: int | None = None
    beat_phase: float | None = Field(default=None, ge=0.0, le=1.0)
    bar_index: int | None = None
    bar_phase: float | None = Field(default=None, ge=0.0, le=1.0)
    duration_beats: float | None = Field(default=None, ge=0.0)

    section_index: int | None = None
    section_label: str | None = None

    local_tempo_bpm: float | None = Field(default=None, ge=0.0)
    onset_sync_score: float | None = Field(default=None, ge=0.0, le=1.0)
    silence_before_beats: float | None = Field(default=None, ge=0.0)

    energy_at_onset: float | None = None
    tension_at_onset: float | None = None
    chord_at_onset: str | None = None

    alignment_status: AlignmentStatus

