"""Sequence analyzer - extracts structure and fingerprints from xLights sequences."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from twinklr.core.formats.xlights.sequence.parser import XSQParser


@dataclass(frozen=True)
class AnalyzedTimingMarker:
    """One timing marker read through the analysis-only XSQ seam."""

    name: str
    time_ms: int


@dataclass(frozen=True)
class AnalyzedEffectInterval:
    """One non-timing effect interval read from a delivered sequence."""

    start_ms: int
    end_ms: int
    element_name: str
    layer_index: int


@dataclass(frozen=True)
class DeliveredSequenceAnalysis:
    """Minimal rendered-sequence facts needed by deterministic evaluation."""

    duration_ms: int
    timing_tracks: dict[str, tuple[AnalyzedTimingMarker, ...]]
    effects: tuple[AnalyzedEffectInterval, ...]


def analyze_delivered_sequence(path: Path) -> DeliveredSequenceAnalysis:
    """Read evaluation facts without making reporting an XSQ parser consumer."""
    sequence = XSQParser().parse(path)
    tracks = {
        track.name: tuple(
            AnalyzedTimingMarker(name=marker.name, time_ms=marker.time_ms)
            for marker in track.markers
        )
        for track in sequence.timing_tracks
    }
    effects = tuple(
        AnalyzedEffectInterval(
            start_ms=effect.start_time_ms,
            end_ms=effect.end_time_ms,
            element_name=element.element_name,
            layer_index=layer.index,
        )
        for element in sequence.element_effects
        for layer in element.layers
        for effect in layer.effects
    )
    return DeliveredSequenceAnalysis(
        duration_ms=sequence.head.sequence_duration_ms,
        timing_tracks=tracks,
        effects=effects,
    )
