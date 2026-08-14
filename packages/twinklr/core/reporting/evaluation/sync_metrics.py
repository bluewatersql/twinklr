"""Deterministic musical-grid metrics for rendered xLights effects.

This module intentionally has no provider or vision imports. Beat/effect alignment is
known from Twinklr's own artifacts and must remain deterministic.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
import statistics

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.analyzer import analyze_delivered_sequence
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


class EffectInterval(BaseModel):
    """One rendered effect interval, optionally carrying source identity."""

    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    element_name: str | None = None
    layer_index: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)


class StructureSection(BaseModel):
    """A timestamped section used for boundary and density metrics."""

    name: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    bars: float = Field(gt=0)

    model_config = ConfigDict(extra="forbid", frozen=True)


class OffsetDistribution(BaseModel):
    """Signed offsets preserve phase and multimodal distributions."""

    count: int = Field(ge=0)
    signed_offsets_ms: list[float]
    mean_absolute_ms: float | None = Field(default=None, ge=0)
    median_absolute_ms: float | None = Field(default=None, ge=0)
    p95_absolute_ms: float | None = Field(default=None, ge=0)
    mean_signed_ms: float | None = None
    standard_deviation_ms: float | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)


class GridStartAlignment(BaseModel):
    """Effect-start alignment against one grid level."""

    tolerance_ms: float = Field(gt=0)
    on_grid_count: int = Field(ge=0)
    effect_count: int = Field(ge=0)
    on_grid_rate: float | None = Field(default=None, ge=0, le=1)
    offsets: OffsetDistribution

    model_config = ConfigDict(extra="forbid", frozen=True)


class BoundaryAlignment(BaseModel):
    """Section boundaries with a rendered effect boundary nearby."""

    tolerance_ms: float = Field(gt=0)
    aligned_count: int = Field(ge=0)
    boundary_count: int = Field(ge=0)
    alignment_rate: float = Field(ge=0, le=1)
    offsets: OffsetDistribution

    model_config = ConfigDict(extra="forbid", frozen=True)


class SectionDensity(BaseModel):
    """Effect-start density for one section."""

    section_name: str
    bar_count: float = Field(gt=0)
    effect_count: int = Field(ge=0)
    effects_per_bar: float = Field(ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)


class DeterministicSyncMetrics(BaseModel):
    """Combined deterministic metrics; no model-generated fields."""

    beat_starts: GridStartAlignment
    downbeat_starts: GridStartAlignment
    section_boundaries: BoundaryAlignment
    section_density: list[SectionDensity]

    model_config = ConfigDict(extra="forbid", frozen=True)


def effect_intervals_from_xsq(path: Path) -> list[EffectInterval]:
    """Read effect intervals from the rendered `.xsq` analysis model."""
    analysis = analyze_delivered_sequence(path)
    intervals = [
        EffectInterval(
            start_ms=effect.start_ms,
            end_ms=effect.end_ms,
            element_name=effect.element_name,
            layer_index=effect.layer_index,
        )
        for effect in analysis.effects
    ]
    return sorted(
        intervals,
        key=lambda effect: (
            effect.start_ms,
            effect.end_ms,
            effect.element_name or "",
            effect.layer_index or 0,
        ),
    )


def beat_grid_from_xsq(path: Path) -> BeatGrid:
    """Rebuild the delivered BeatGrid from Twinklr's exported timing tracks."""
    analysis = analyze_delivered_sequence(path)
    try:
        beat_markers = analysis.timing_tracks["Twinklr Beats"]
        bar_markers = analysis.timing_tracks["Twinklr Bars"]
    except KeyError as error:
        raise ValueError(
            f"Rendered artifact must contain Twinklr Beats and Twinklr Bars tracks: {path}"
        ) from error
    beats = [float(marker.time_ms) for marker in beat_markers]
    bars = [float(marker.time_ms) for marker in bar_markers]
    if len(beats) < 2 or not bars:
        raise ValueError(f"Rendered artifact has an incomplete musical grid: {path}")
    average_beat_ms = (beats[-1] - beats[0]) / (len(beats) - 1)
    beats_per_bar = _infer_beats_per_bar(beat_markers, beats, bars)
    return BeatGrid(
        bar_boundaries=bars,
        beat_boundaries=beats,
        eighth_boundaries=_subdivide(beats, 2),
        sixteenth_boundaries=_subdivide(beats, 4),
        tempo_bpm=60_000 / average_beat_ms,
        beats_per_bar=beats_per_bar,
        duration_ms=float(analysis.duration_ms),
    )


def score_sync_metrics(
    *,
    beat_grid: BeatGrid,
    effects: list[EffectInterval],
    sections: list[StructureSection],
    tolerance_ms: float = 50.0,
) -> DeterministicSyncMetrics:
    """Score rendered effect timing against Twinklr's authoritative grid."""
    if tolerance_ms <= 0:
        raise ValueError("tolerance_ms must be greater than zero")
    starts = [float(effect.start_ms) for effect in effects]
    beat_alignment = _grid_alignment(starts, beat_grid.beat_boundaries, tolerance_ms)
    downbeat_alignment = _grid_alignment(starts, beat_grid.bar_boundaries, tolerance_ms)

    section_points = sorted(
        {float(section.start_ms) for section in sections}
        | {float(section.end_ms) for section in sections}
    )
    effect_points = sorted(
        [float(effect.start_ms) for effect in effects]
        + [float(effect.end_ms) for effect in effects]
    )
    boundary_offsets = (
        [_nearest_signed(point, effect_points) for point in section_points] if effect_points else []
    )
    boundary_on_grid = sum(abs(offset) <= tolerance_ms for offset in boundary_offsets)
    boundary_count = len(section_points)

    densities = []
    for index, section in enumerate(sections):
        is_last = index == len(sections) - 1
        count = sum(
            section.start_ms <= effect.start_ms < section.end_ms
            or (is_last and effect.start_ms == section.end_ms)
            for effect in effects
        )
        densities.append(
            SectionDensity(
                section_name=section.name,
                bar_count=section.bars,
                effect_count=count,
                effects_per_bar=count / section.bars,
            )
        )

    return DeterministicSyncMetrics(
        beat_starts=beat_alignment,
        downbeat_starts=downbeat_alignment,
        section_boundaries=BoundaryAlignment(
            tolerance_ms=tolerance_ms,
            aligned_count=boundary_on_grid,
            boundary_count=boundary_count,
            alignment_rate=boundary_on_grid / boundary_count if boundary_count else 0.0,
            offsets=_distribution(boundary_offsets),
        ),
        section_density=densities,
    )


def _grid_alignment(
    starts: list[float], boundaries: list[float], tolerance_ms: float
) -> GridStartAlignment:
    offsets = [_nearest_signed(start, boundaries) for start in starts] if boundaries else []
    on_grid = sum(abs(offset) <= tolerance_ms for offset in offsets)
    return GridStartAlignment(
        tolerance_ms=tolerance_ms,
        on_grid_count=on_grid,
        effect_count=len(starts),
        on_grid_rate=on_grid / len(starts) if starts else None,
        offsets=_distribution(offsets),
    )


def _nearest_signed(value: float, boundaries: list[float]) -> float:
    """Return `value - nearest_boundary`, preferring the earlier point on ties."""
    if not boundaries:
        raise ValueError("At least one boundary is required for an offset")
    index = bisect_left(boundaries, value)
    if index == 0:
        return value - boundaries[0]
    if index == len(boundaries):
        return value - boundaries[-1]
    before = boundaries[index - 1]
    after = boundaries[index]
    nearest = before if value - before <= after - value else after
    return value - nearest


def _distribution(offsets: list[float]) -> OffsetDistribution:
    if not offsets:
        return OffsetDistribution(
            count=0,
            signed_offsets_ms=[],
        )
    absolute = sorted(abs(offset) for offset in offsets)
    p95_index = max(0, min(len(absolute) - 1, round(0.95 * len(absolute) + 0.5) - 1))
    return OffsetDistribution(
        count=len(offsets),
        signed_offsets_ms=offsets,
        mean_absolute_ms=statistics.fmean(absolute),
        median_absolute_ms=statistics.median(absolute),
        p95_absolute_ms=absolute[p95_index],
        mean_signed_ms=statistics.fmean(offsets),
        standard_deviation_ms=statistics.pstdev(offsets),
    )


def _infer_beats_per_bar(markers: Sequence[object], beats: list[float], bars: list[float]) -> int:
    labels = [str(getattr(marker, "name", "")) for marker in markers]
    beat_numbers = [
        int(label.rsplit(".", maxsplit=1)[-1])
        for label in labels
        if "." in label and label.rsplit(".", maxsplit=1)[-1].isdigit()
    ]
    if beat_numbers:
        return max(beat_numbers)
    if len(bars) >= 2:
        average_bar_ms = (bars[-1] - bars[0]) / (len(bars) - 1)
        average_beat_ms = (beats[-1] - beats[0]) / (len(beats) - 1)
        return max(1, round(average_bar_ms / average_beat_ms))
    return 4


def _subdivide(boundaries: list[float], parts: int) -> list[float]:
    subdivided: list[float] = []
    for start, end in pairwise(boundaries):
        step = (end - start) / parts
        subdivided.extend(start + step * index for index in range(parts))
    subdivided.append(boundaries[-1])
    return subdivided
