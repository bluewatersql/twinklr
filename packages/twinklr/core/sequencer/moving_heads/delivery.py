"""What a moving-heads run hands the user: a fresh `.xsq`, `.xtiming` files, an `.xmap`.

This module replaces `xsq_export.py`, which loaded the user's own `.xsq`, regenerated
it and wrote it back. That merge dropped the user's jukebox, their per-element display
state, every root section Twinklr does not model, and flattened multi-layer lyric timing
tracks (P5-F5), and it re-based `EffectDB`/`ColorPalettes` under the user's positional
`ref=`/`palette=` indices (P5-F4). None of that is repaired here — it is gone by
construction, because nothing on this path opens a user document any more.

What the user does instead is *import* these artifacts into their own sequence, which is
why the delivery is three files rather than one: the `.xsq` carries the effects, the
`.xtiming` files carry Twinklr's audio analysis and import standalone with no mapping at
all, and the `.xmap` pre-fills the model mapping the effect import would otherwise ask
for row by row.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.formats.xlights.sequence.exporter import XSQExporter
from twinklr.core.formats.xlights.sequence.fresh import build_fresh_sequence
from twinklr.core.formats.xlights.sequence.models.xsq import (
    Effect,
    TimeMarker,
    TimingTrack,
    XSequence,
)
from twinklr.core.formats.xlights.sequence.xmap import XMAP_SUFFIX, write_xmap
from twinklr.core.formats.xlights.sequence.xtiming import export_timing_tracks
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.export.xsq_adapter import XsqAdapter

logger = logging.getLogger(__name__)

SECTIONS_TRACK_NAME = "Twinklr AudioSections"


@dataclass(frozen=True)
class DeliveryArtifacts:
    """The files one run produced."""

    xsq_path: Path
    xtiming_paths: tuple[Path, ...]
    xmap_path: Path
    model_names: tuple[str, ...]

    @property
    def all_paths(self) -> tuple[Path, ...]:
        return (self.xsq_path, *self.xtiming_paths, self.xmap_path)


def build_sequence(
    segments: list[FixtureSegment],
    time_markers: list[TimeMarker],
    *,
    fixture_group: FixtureGroup,
    media_file: str,
    duration_ms: int | None = None,
    song: str = "",
    artist: str = "",
    timeline_tracks: list[TimingTrack] | None = None,
) -> XSequence:
    """Build the fresh sequence for `segments` — no user document involved.

    Args:
        segments: Compiled fixture segments to export.
        time_markers: Section markers built during the render.
        fixture_group: Fixture group for DMX mapping and model names.
        media_file: Audio file the sequence plays against; must be non-empty.
        duration_ms: Sequence duration. Defaults to the last segment's end; when given
            (normally the song's length) the longer of the two wins, so a plan that
            stops before the song ends still yields a sequence spanning the song.
        song: Song title for the head.
        artist: Artist for the head.
        timeline_tracks: Timing tracks from the audio analysis (beats, bars, lyrics…).

    Returns:
        The populated `XSequence`.

    Raises:
        ValueError: If `media_file` is empty.
    """
    last_segment_ms = max((segment.t1_ms for segment in segments), default=0)
    xsq = build_fresh_sequence(
        media_file=media_file,
        duration_ms=max(last_segment_ms, duration_ms or 0),
        song=song,
        artist=artist,
    )

    xsq.add_timing_layer(timing_name=SECTIONS_TRACK_NAME, markers=time_markers)
    for track in timeline_tracks or []:
        xsq.add_timing_layer(timing_name=track.name, markers=track.markers)

    placements = XsqAdapter().convert(segments, fixture_group, xsq)
    for placement in placements:
        xsq.add_effect(
            element_name=placement.element_name,
            effect=Effect(
                effect_type=placement.effect_name,
                start_time_ms=placement.start_ms,
                end_time_ms=placement.end_ms,
                ref=placement.ref,
                label=placement.effect_label or "",
                palette=str(placement.palette) if placement.palette else "",
            ),
            layer_index=placement.layer_index,
        )

    logger.debug(
        "Built fresh sequence: %d segments, %d placements, %d models",
        len(segments),
        len(placements),
        len(xsq.element_effects),
    )
    return xsq


def export_delivery(
    segments: list[FixtureSegment],
    time_markers: list[TimeMarker],
    *,
    fixture_group: FixtureGroup,
    output_path: Path,
    media_file: str,
    duration_ms: int | None = None,
    song: str = "",
    artist: str = "",
    timeline_tracks: list[TimingTrack] | None = None,
) -> DeliveryArtifacts:
    """Write the run's `.xsq`, `.xtiming` files and `.xmap`.

    The sidecars are named from `output_path`'s stem and land beside it.

    Args:
        segments: Compiled fixture segments to export.
        time_markers: Section markers built during the render.
        fixture_group: Fixture group for DMX mapping and model names.
        output_path: Destination for the `.xsq`.
        media_file: Audio file the sequence plays against; must be non-empty.
        duration_ms: Song duration, when known.
        song: Song title for the head.
        artist: Artist for the head.
        timeline_tracks: Timing tracks from the audio analysis.

    Returns:
        The artifacts written.

    Raises:
        ValueError: If `media_file` is empty.
    """
    xsq = build_sequence(
        segments,
        time_markers,
        fixture_group=fixture_group,
        media_file=media_file,
        duration_ms=duration_ms,
        song=song,
        artist=artist,
        timeline_tracks=timeline_tracks,
    )

    XSQExporter().export(xsq, output_path, pretty=True)

    xtiming_paths = export_timing_tracks(
        xsq.timing_tracks, output_dir=output_path.parent, stem=output_path.stem
    )
    model_names = [element.element_name for element in xsq.element_effects]
    xmap_path = write_xmap(model_names, output_path.with_suffix(XMAP_SUFFIX))

    logger.debug(
        "Delivery written: %s (+%d .xtiming, %s)",
        output_path,
        len(xtiming_paths),
        xmap_path.name,
    )
    return DeliveryArtifacts(
        xsq_path=output_path,
        xtiming_paths=tuple(xtiming_paths),
        xmap_path=xmap_path,
        model_names=tuple(model_names),
    )
