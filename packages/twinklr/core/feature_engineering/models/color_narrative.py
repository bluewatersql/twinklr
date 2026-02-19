"""Color narrative contracts (V1.8)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ColorNarrativeRow(BaseModel):
    """Section-level color narrative summary row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    package_id: str
    sequence_file_id: str

    section_label: str
    section_index: int = Field(ge=0)
    phrase_count: int = Field(ge=0)

    dominant_color_class: str
    contrast_shift_from_prev: float = Field(ge=0.0, le=1.0)
    hue_family_movement: str

