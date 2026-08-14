"""Sequence analyzer - extracts structure and fingerprints from xLights sequences."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

from twinklr.core.config.models import AppConfig, JobConfig
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


class SequenceAnalyzer:
    """Analyzes xLights sequences to extract structure and activity patterns.

    Provides sequence fingerprinting including:
    - Duration and timing information
    - Effect type distribution
    - Activity proxy (effects per time bin)
    - Timing track events (structural markers)
    - xLights version metadata
    """

    def __init__(self, app_config: AppConfig, job_config: JobConfig):
        """Initialize sequence analyzer with configuration.

        Args:
            app_config: Application configuration
            job_config: Job configuration
        """
        self.app_config = app_config
        self.job_config = job_config

    def fingerprint(
        self,
        xsq_path: str,
        *,
        bin_s: float = 1.0,
    ) -> dict[str, Any]:
        """Generate a fingerprint of an xLights sequence.

        Analyzes sequence structure including timing, effects, and activity patterns.
        Results are checkpointed for performance.

        Args:
            xsq_path: Path to xLights sequence file (.xsq)
            bin_s: Time bin size in seconds for activity proxy (default: 1.0)

        Returns:
            Fingerprint dictionary with schema_version 1.1

        Example:
            analyzer = SequenceAnalyzer(app_config, job_config)
            fp = analyzer.fingerprint("sequence.xsq")
            duration = fp["duration_s"]
            timing_tracks = fp["timing_tracks"]
        """
        # Load and analyze sequence
        parser = XSQParser()
        sequence = parser.parse(xsq_path)
        placements = sequence.iter_effect_placements()

        # Determine duration
        duration_s = sequence.get_sequence_duration_s() or 0.0
        if duration_s <= 0:
            # Fallback: infer duration from max endTime
            duration_s = max((p.end_ms for p in placements), default=0) / 1000.0

        # Build activity proxy (effect count per time bin)
        n_bins = max(1, math.ceil(duration_s / bin_s))
        bins = [0] * n_bins

        for p in placements:
            st = int(p.start_ms / 1000.0 / bin_s)
            en = int(p.end_ms / 1000.0 / bin_s)
            st = max(0, min(n_bins - 1, st))
            en = max(0, min(n_bins - 1, en))
            for i in range(st, en + 1):
                bins[i] += 1

        # Get effect type distribution
        hist = sequence.effect_type_histogram()
        timing_tracks = sequence.list_timing_tracks()

        # Extract timing events from each timing track for structural context
        timing_track_events: dict[str, list[dict[str, Any]]] = {}
        for track_name in timing_tracks:
            events = sequence.extract_timing_events(track_name)
            if events:  # Only include tracks with events
                timing_track_events[track_name] = events

        # Assemble results
        results = {
            "schema_version": "1.1",  # Bumped for timing_track_events addition
            "xsq_path": xsq_path,
            "xlights_version": sequence.get_version(),
            "duration_s": duration_s,
            "timing_tracks": timing_tracks,
            "timing_track_events": timing_track_events,
            "effect_type_histogram": dict(sorted(hist.items(), key=lambda kv: kv[1], reverse=True)),
            "activity_proxy": {
                "bin_s": bin_s,
                "bins": bins,
            },
            "notes": [
                "MVP fingerprint: ignores group expansion and true pixel coverage.",
                "activity_proxy is just 'how many effects are active' per time bin.",
                "timing_track_events: structural information from sequence timing tracks (v1.1+).",
            ],
        }

        return results
