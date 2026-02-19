"""Effect event extraction models for profiling."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from twinklr.core.profiling.models.effectdb import EffectDbParam
from twinklr.core.profiling.models.enums import EffectDbParseStatus


class EffectEventRecord(BaseModel):
    """One flattened effect placement extracted from an xLights sequence."""

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
    effectdb_settings_raw: str | None = None
    effectdb_parser_version: str | None = None
    effectdb_parse_status: EffectDbParseStatus = EffectDbParseStatus.EMPTY
    effectdb_params: tuple[EffectDbParam, ...] = ()
    effectdb_parse_errors: tuple[str, ...] = ()
    palette: str
    protected: bool
    label: str | None = None

    @model_validator(mode="after")
    def validate_timing(self) -> EffectEventRecord:
        """Ensure each event has non-negative duration."""
        if self.end_ms < self.start_ms:
            raise ValueError("end_ms must be >= start_ms")
        return self


class BaseEffectEventsFile(BaseModel):
    """Envelope model for extracted base effect events."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    package_id: str
    sequence_file_id: str
    sequence_sha256: str
    events: tuple[EffectEventRecord, ...]
