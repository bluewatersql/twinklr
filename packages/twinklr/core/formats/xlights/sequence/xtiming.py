"""`.xtiming` writer — Twinklr's timing tracks as standalone importable files.

An `.xtiming` file carries one timing track and nothing else: no models, no effects, no
mapping. That makes it the one deliverable that needs nothing from the user's layout to
be useful, which is why it is the floor Twinklr ships under the `.xsq` (M6b: "timing
tracks import standalone as `.xtiming` — a mapping-free minimum-viable deliverable").

Structure written per file::

    <timing name="Twinklr Beats" SourceVersion="2026.15">
      <EffectLayer>
        <Effect label="1.1" starttime="0" endtime="1" />
      </EffectLayer>
    </timing>

One file per track rather than one file listing every track: a timing *track* is the
unit xLights imports, and a multi-layer track (the phrases/words/phonemes shape of a
lyric track) is the only case where one file holds more than one `<EffectLayer>`.
UNVERIFIED against a real xLights — P1P-T12 owns that check; if the import wants a
different root element, this is the only place that changes.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from twinklr.core.formats.xlights.sequence.fresh import XLIGHTS_VERSION_STAMP
from twinklr.core.formats.xlights.sequence.models.xsq import TimingTrack

logger = logging.getLogger(__name__)

XTIMING_SUFFIX = ".xtiming"

_SLUG_STRIP_PREFIX = "twinklr"
_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def track_slug(track_name: str) -> str:
    """Turn a track name into the file-name fragment identifying it.

    `"Twinklr Beats"` becomes `"beats"`, so a run writes `song.beats.xtiming` next to
    `song.xsq`. The `Twinklr` prefix is dropped because the file already sits in a
    Twinklr artifact directory and the track name inside the file keeps it.

    Args:
        track_name: Timing track name.

    Returns:
        A lowercase slug; `"track"` when the name has no usable characters.
    """
    slug = _SLUG_NON_ALNUM.sub("_", track_name.strip().lower()).strip("_")
    if slug.startswith(f"{_SLUG_STRIP_PREFIX}_"):
        slug = slug[len(_SLUG_STRIP_PREFIX) + 1 :]
    return slug or "track"


def build_xtiming_tree(track: TimingTrack) -> ET.ElementTree:
    """Build the XML document for one timing track.

    Args:
        track: Track whose markers are written.

    Returns:
        An `ElementTree` rooted at `<timing>`.
    """
    root = ET.Element("timing", {"name": track.name, "SourceVersion": XLIGHTS_VERSION_STAMP})
    layer = ET.SubElement(root, "EffectLayer")
    for marker in track.markers:
        ET.SubElement(
            layer,
            "Effect",
            {
                "label": marker.name,
                "starttime": str(marker.time_ms),
                "endtime": str(marker.resolved_end_time_ms),
            },
        )
    return ET.ElementTree(root)


def write_xtiming(track: TimingTrack, path: Path) -> Path:
    """Write one timing track to `path`.

    Args:
        track: Track to write.
        path: Destination `.xtiming` file; parent directories are created.

    Returns:
        The path written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = build_xtiming_tree(track)
    ET.indent(tree, space="  ", level=0)
    tree.write(str(path), encoding="UTF-8", xml_declaration=True)
    logger.debug("Wrote %d markers to %s", len(track.markers), path)
    return path


def export_timing_tracks(tracks: list[TimingTrack], *, output_dir: Path, stem: str) -> list[Path]:
    """Write every non-empty track as its own `.xtiming` file.

    Args:
        tracks: Timing tracks to write.
        output_dir: Directory the files are written into.
        stem: Base name shared with the run's other artifacts.

    Returns:
        Paths written, in track order. Empty tracks are skipped — an `.xtiming` with no
        markers imports as an empty track and only adds noise to the delivery.
    """
    written: list[Path] = []
    for track in tracks:
        if not track.markers:
            logger.debug("Skipping empty timing track %r", track.name)
            continue
        written.append(
            write_xtiming(track, output_dir / f"{stem}.{track_slug(track.name)}{XTIMING_SUFFIX}")
        )
    return written
