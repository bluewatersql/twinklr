"""Color palette profiling models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PaletteEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    colors: tuple[str, ...]
    palette_entry_indices: tuple[int, ...]


class PaletteClassifications(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    monochrome: tuple[PaletteEntry, ...]
    warm: tuple[PaletteEntry, ...]
    cool: tuple[PaletteEntry, ...]
    primary_only: tuple[PaletteEntry, ...]
    by_color_family: dict[str, tuple[PaletteEntry, ...]]


class ColorPaletteProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    unique_colors: tuple[str, ...]
    single_colors: tuple[PaletteEntry, ...]
    color_palettes: tuple[PaletteEntry, ...]
    classifications: PaletteClassifications
