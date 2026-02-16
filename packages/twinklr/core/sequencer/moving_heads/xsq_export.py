"""XSQ export logic extracted from RenderingPipeline.

Handles loading/creating XSQ files, adding timing layers, converting
segments to effect placements, and writing the final output.
"""

from __future__ import annotations

import logging
from pathlib import Path

from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.formats.xlights.sequence.exporter import XSQExporter
from twinklr.core.formats.xlights.sequence.models.xsq import (
    Effect,
    SequenceHead,
    TimeMarker,
    TimingTrack,
    XSequence,
)
from twinklr.core.formats.xlights.sequence.parser import XSQParser
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.export.xsq_adapter import XsqAdapter

logger = logging.getLogger(__name__)


def export_to_xsq(
    segments: list[FixtureSegment],
    time_markers: list[TimeMarker],
    *,
    fixture_group: FixtureGroup,
    output_path: Path,
    template_xsq: Path | None = None,
    timeline_tracks: list[TimingTrack] | None = None,
) -> None:
    """Export fixture segments to an xLights .xsq sequence file.

    Args:
        segments: Compiled fixture segments to export.
        time_markers: Section timing markers (legacy section markers).
        fixture_group: Fixture group for DMX mapping.
        output_path: Destination path for the .xsq file.
        template_xsq: Optional existing .xsq to use as a base.
        timeline_tracks: Additional timing tracks (beats, bars, lyrics, etc.).

    Raises:
        ValueError: If XSQ operations fail.
    """
    logger.debug("Exporting %d segments to %s", len(segments), output_path)

    # Load template XSQ if provided, otherwise create new
    if template_xsq and Path(template_xsq).exists():
        logger.debug("Loading template XSQ from %s", template_xsq)
        parser = XSQParser()
        xsq = parser.parse(template_xsq)
        logger.debug(
            "Template loaded: %d elements, %d effects in DB",
            len(xsq.element_effects),
            len(xsq.effect_db.entries),
        )
    else:
        logger.debug("Creating new XSQ (no template provided)")
        duration_ms = max((s.t1_ms for s in segments), default=0)
        xsq = XSequence(
            head=SequenceHead(
                version="2024.10",
                media_file="",
                sequence_duration_ms=duration_ms,
                song="Generated Sequence",
                artist="Twinklr",
                sequence_timing="50 ms",
            )
        )

    # Add section timing markers (legacy — kept for backward compatibility)
    xsq.add_timing_layer(timing_name="Twinklr AudioSections", markers=time_markers)

    # Add timeline tracks (beats, bars, lyrics, phonemes, etc.)
    for track in timeline_tracks or []:
        xsq.add_timing_layer(timing_name=track.name, markers=track.markers)

    adapter = XsqAdapter()
    placements = adapter.convert(segments, fixture_group, xsq)
    logger.debug("Converted to %d effect placements", len(placements))

    # Add placements to XSQ
    for placement in placements:
        effect = Effect(
            effect_type=placement.effect_name,
            start_time_ms=placement.start_ms,
            end_time_ms=placement.end_ms,
            ref=placement.ref,
            label=placement.effect_label or "",
            palette=str(placement.palette) if placement.palette else "",
        )
        xsq.add_effect(
            element_name=placement.element_name,
            effect=effect,
            layer_index=placement.layer_index,
        )

    logger.debug("Added %d effects to XSQ", len(placements))

    # Export to file
    exporter = XSQExporter()
    exporter.export(xsq, output_path, pretty=True)
    logger.debug("Successfully exported XSQ to %s", output_path)
