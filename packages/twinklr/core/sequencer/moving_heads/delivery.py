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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import logging
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any

from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import MHRenderPolicy
from twinklr.core.formats.xlights.sequence.emission import EmissionRequest, EmissionSession
from twinklr.core.formats.xlights.sequence.exporter import XSQExporter
from twinklr.core.formats.xlights.sequence.fresh import build_fresh_sequence
from twinklr.core.formats.xlights.sequence.models.xsq import (
    TimeMarker,
    TimingTrack,
    XSequence,
)
from twinklr.core.formats.xlights.sequence.trace import write_xsq_trace_sidecar
from twinklr.core.formats.xlights.sequence.xmap import XMAP_SUFFIX, write_xmap
from twinklr.core.formats.xlights.sequence.xtiming import export_timing_tracks
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    FrameRun,
    check_output_budget,
    measure_output,
)
from twinklr.core.sequencer.moving_heads.export.xsq_adapter import XsqAdapter

logger = logging.getLogger(__name__)

SECTIONS_TRACK_NAME = "Twinklr AudioSections"


class DeliveryRollbackError(OSError):
    """Publishing failed and its rollback could not finish.

    A new file could not be removed or an earlier one could not be put back. The
    earlier files set aside are kept in `kept_dir`, which is not deleted.
    """

    def __init__(self, kept_dir: Path, unrestored: Sequence[str]) -> None:
        self.kept_dir = kept_dir
        super().__init__(
            f"publishing the delivery failed and rolling it back did not finish: "
            f"{', '.join(unrestored)}; the earlier files are kept in {kept_dir}"
        )


@dataclass(frozen=True)
class DeliveryArtifacts:
    """The files one run produced."""

    xsq_path: Path
    xtiming_paths: tuple[Path, ...]
    xmap_path: Path
    trace_path: Path
    model_names: tuple[str, ...]

    @property
    def all_paths(self) -> tuple[Path, ...]:
        return (self.xsq_path, *self.xtiming_paths, self.xmap_path, self.trace_path)


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
    xsq = _fresh_sequence(
        time_markers,
        media_file=media_file,
        duration_ms=max(last_segment_ms, duration_ms or 0),
        song=song,
        artist=artist,
        timeline_tracks=timeline_tracks,
    )

    placements = XsqAdapter().convert(segments, fixture_group, xsq)

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
    return _write_sidecars(xsq, output_path)


def build_physical_sequence(
    requests: Sequence[EmissionRequest],
    time_markers: list[TimeMarker],
    *,
    media_file: str,
    duration_ms: int,
    song: str = "",
    artist: str = "",
    timeline_tracks: list[TimingTrack] | None = None,
) -> XSequence:
    """Build the fresh sequence for physical frame-run requests, in request order.

    The sequence keeps the song's duration; the last frame run may end past it, on the
    next frame boundary.

    Raises:
        ValueError: If `media_file` is empty or the emission session refuses a request.
    """
    xsq = _fresh_sequence(
        time_markers,
        media_file=media_file,
        duration_ms=duration_ms,
        song=song,
        artist=artist,
        timeline_tracks=timeline_tracks,
    )
    session = EmissionSession(xsq)
    for request in requests:
        session.queue(request)
    session.flush()
    return xsq


def export_physical_delivery(
    xsq: XSequence,
    runs: Sequence[FrameRun],
    *,
    output_path: Path,
    policy: MHRenderPolicy,
    render: Mapping[str, Any],
) -> DeliveryArtifacts:
    """Write a physical render's delivery only after its serialized size fits the budgets.

    Every file is written to a staging directory beside `output_path` first. The
    `.xsq` is serialized, measured (effect count and exact bytes) and checked against
    the policy's budgets; only then are the sidecars written and every file moved into
    place, the `.xsq` last. A failure before publishing leaves the destination
    untouched; a failure while publishing restores every file already moved, including
    any earlier deliverable it replaced. The trace carries `render` plus the measured
    output and serialization time.

    Raises:
        PhysicalOutputError: If the output exceeds `policy.max_effects` or
            `policy.max_xsq_bytes`.
        DeliveryRollbackError: If publishing failed and an earlier file could not be
            put back; the staging directory is then kept and named.
    """
    destination = output_path.parent
    destination.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_path.stem}.", dir=destination))
    try:
        staged_xsq = staging / output_path.name
        started = time.perf_counter()
        XSQExporter().export(xsq, staged_xsq, pretty=True)
        serialization_ms = (time.perf_counter() - started) * 1000
        measure = measure_output(runs, staged_xsq.read_bytes())
        check_output_budget(measure, policy)
        output = {
            "effect_count": measure.effect_count,
            "xsq_bytes": measure.xsq_bytes,
            "serialization_ms": round(serialization_ms, 3),
        }
        staged = _write_sidecars(xsq, staged_xsq, render={**render, "output": output})
        _publish(
            (*staged.xtiming_paths, staged.xmap_path, staged.trace_path, staged_xsq),
            destination,
            backup_dir=staging / ".replaced",
        )
    except DeliveryRollbackError:
        raise  # the staging directory holds files that could not be put back
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    shutil.rmtree(staging, ignore_errors=True)
    return DeliveryArtifacts(
        xsq_path=output_path,
        xtiming_paths=tuple(destination / path.name for path in staged.xtiming_paths),
        xmap_path=destination / staged.xmap_path.name,
        trace_path=destination / staged.trace_path.name,
        model_names=staged.model_names,
    )


def _publish(files: Sequence[Path], destination: Path, *, backup_dir: Path) -> None:
    """Move `files` into `destination` all or nothing.

    A file already at a target is set aside in `backup_dir` first; if any move fails,
    every file placed so far is removed and every set-aside file is put back.

    Raises:
        DeliveryRollbackError: If a placed file cannot be removed or a set-aside file
            cannot be put back; every other step of the rollback still runs, and the
            set-aside files stay in `backup_dir`.
    """
    backup_dir.mkdir()
    placed: list[Path] = []
    replaced: list[tuple[Path, Path]] = []
    try:
        for path in files:
            target = destination / path.name
            if target.exists():
                backup = backup_dir / path.name
                target.replace(backup)
                replaced.append((backup, target))
            path.replace(target)
            placed.append(target)
    except BaseException as error:
        unrestored: list[str] = []
        for target in placed:
            try:
                target.unlink(missing_ok=True)
            except OSError as remove_error:
                unrestored.append(f"new {target.name} ({remove_error})")
        for backup, target in replaced:
            try:
                backup.replace(target)
            except OSError as restore_error:
                unrestored.append(f"{target.name} ({restore_error})")
        if unrestored:
            raise DeliveryRollbackError(backup_dir, unrestored) from error
        raise


def _fresh_sequence(
    time_markers: list[TimeMarker],
    *,
    media_file: str,
    duration_ms: int,
    song: str,
    artist: str,
    timeline_tracks: list[TimingTrack] | None,
) -> XSequence:
    """A fresh sequence carrying the section markers and the analysis timing tracks."""
    xsq = build_fresh_sequence(
        media_file=media_file,
        duration_ms=duration_ms,
        song=song,
        artist=artist,
    )
    xsq.add_timing_layer(timing_name=SECTIONS_TRACK_NAME, markers=time_markers)
    for track in timeline_tracks or []:
        xsq.add_timing_layer(timing_name=track.name, markers=track.markers)
    return xsq


def _write_sidecars(
    xsq: XSequence, xsq_path: Path, *, render: Mapping[str, Any] | None = None
) -> DeliveryArtifacts:
    """Write the trace, `.xtiming` files and `.xmap` beside an exported `.xsq`."""
    trace_path = write_xsq_trace_sidecar(xsq_path, xsq.emission_trace_entries, render=render)

    xtiming_paths = export_timing_tracks(
        xsq.timing_tracks, output_dir=xsq_path.parent, stem=xsq_path.stem
    )
    model_names = [element.element_name for element in xsq.element_effects]
    xmap_path = write_xmap(model_names, xsq_path.with_suffix(XMAP_SUFFIX))

    logger.debug(
        "Delivery written: %s (+%d .xtiming, %s)",
        xsq_path,
        len(xtiming_paths),
        xmap_path.name,
    )
    return DeliveryArtifacts(
        xsq_path=xsq_path,
        xtiming_paths=tuple(xtiming_paths),
        xmap_path=xmap_path,
        trace_path=trace_path,
        model_names=tuple(model_names),
    )
