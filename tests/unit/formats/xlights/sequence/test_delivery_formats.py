"""The three delivery formats P1P-T11 ships: fresh `.xsq`, `.xtiming`, `.xmap`.

Every test here fails on the pre-task tree: the fresh `.xsq` emitter wrote
`media_file=""` (which `XSQParser` rejects as fatal) under one of two disagreeing
version stamps, and neither `.xtiming` nor `.xmap` existed anywhere in the repository.
"""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from twinklr.core.formats.xlights.sequence.exporter import XSQExporter
from twinklr.core.formats.xlights.sequence.fresh import (
    PLACEHOLDER_MEDIA_FILE,
    SEQUENCE_TIMING,
    XLIGHTS_VERSION_STAMP,
    build_fresh_sequence,
    resolve_media_file,
)
from twinklr.core.formats.xlights.sequence.models.xsq import TimeMarker, TimingTrack
from twinklr.core.formats.xlights.sequence.parser import XSQParser
from twinklr.core.formats.xlights.sequence.xmap import build_xmap_text, write_xmap
from twinklr.core.formats.xlights.sequence.xtiming import (
    export_timing_tracks,
    track_slug,
    write_xtiming,
)


@pytest.fixture
def beats_track() -> TimingTrack:
    """A point-marker track: no end times, so the 1 ms rule applies to every marker."""
    return TimingTrack(
        name="Twinklr Beats",
        markers=[TimeMarker(name=f"1.{i + 1}", time_ms=i * 500) for i in range(4)],
    )


@pytest.fixture
def sections_track() -> TimingTrack:
    """An interval track: markers carry their own end times."""
    return TimingTrack(
        name="Twinklr Sections",
        markers=[
            TimeMarker(name="intro", time_ms=0, end_time_ms=2000),
            TimeMarker(name="chorus", time_ms=2000, end_time_ms=6000),
        ],
    )


# --- .xtiming ---------------------------------------------------------------------


def test_xtiming_export_structure(tmp_path: Path, beats_track: TimingTrack) -> None:
    """The file is well-formed and carries the track's name and every marker."""
    path = write_xtiming(beats_track, tmp_path / "song.beats.xtiming")

    root = ET.parse(path).getroot()
    assert root.tag == "timing"
    assert root.get("name") == "Twinklr Beats"
    assert root.get("SourceVersion") == XLIGHTS_VERSION_STAMP

    layers = root.findall("EffectLayer")
    assert len(layers) == 1
    effects = layers[0].findall("Effect")
    assert [effect.get("label") for effect in effects] == ["1.1", "1.2", "1.3", "1.4"]
    assert [effect.get("starttime") for effect in effects] == ["0", "500", "1000", "1500"]


def test_xtiming_carries_interval_markers_unchanged(
    tmp_path: Path, sections_track: TimingTrack
) -> None:
    """A marker that already has an end time keeps it — the 1 ms rule is for points."""
    root = ET.parse(write_xtiming(sections_track, tmp_path / "s.xtiming")).getroot()
    effects = root.findall("EffectLayer/Effect")
    assert [(e.get("starttime"), e.get("endtime")) for e in effects] == [
        ("0", "2000"),
        ("2000", "6000"),
    ]


def test_xtiming_markers_match_xsq_timing_tracks(
    tmp_path: Path, beats_track: TimingTrack, sections_track: TimingTrack
) -> None:
    """The two deliverables cannot drift apart.

    Both writers resolve a marker's end time through `TimeMarker.resolved_end_time_ms`,
    so a change to the point-marker rule moves both files or neither.
    """
    sequence = build_fresh_sequence(media_file="song.mp3", duration_ms=6000)
    for track in (beats_track, sections_track):
        sequence.add_timing_layer(timing_name=track.name, markers=track.markers)

    xsq_path = tmp_path / "song.xsq"
    XSQExporter().export(sequence, xsq_path, pretty=True)
    export_timing_tracks(sequence.timing_tracks, output_dir=tmp_path, stem="song")

    xsq_root = ET.parse(xsq_path).getroot()
    for track in sequence.timing_tracks:
        xsq_element = xsq_root.find(f"ElementEffects/Element[@name='{track.name}']")
        assert xsq_element is not None
        from_xsq = [
            (e.get("label"), e.get("startTime"), e.get("endTime"))
            for e in xsq_element.findall("EffectLayer/Effect")
        ]

        xtiming_root = ET.parse(tmp_path / f"song.{track_slug(track.name)}.xtiming").getroot()
        from_xtiming = [
            (e.get("label"), e.get("starttime"), e.get("endtime"))
            for e in xtiming_root.findall("EffectLayer/Effect")
        ]

        assert from_xtiming == from_xsq, f"{track.name} differs between .xsq and .xtiming"


def test_xtiming_export_skips_empty_tracks(tmp_path: Path, beats_track: TimingTrack) -> None:
    """An empty track would import as an empty timing track — not worth shipping."""
    empty = TimingTrack(name="Twinklr Lyrics", markers=[])
    written = export_timing_tracks([beats_track, empty], output_dir=tmp_path, stem="song")
    assert [path.name for path in written] == ["song.beats.xtiming"]


def test_track_slug_drops_the_twinklr_prefix() -> None:
    assert track_slug("Twinklr Beats") == "beats"
    assert track_slug("Twinklr AudioSections") == "audiosections"
    assert track_slug("Bars") == "bars"


# --- fresh .xsq -------------------------------------------------------------------


def test_fresh_xsq_reparses(tmp_path: Path) -> None:
    """The self-fatal `media_file=""` defect cannot return.

    Twinklr's own parser treats a missing or empty `mediaFile` as fatal, so before this
    task the only from-nothing emitter produced a file its own parser rejected — and
    that branch is now the only branch.
    """
    sequence = build_fresh_sequence(media_file="song.mp3", duration_ms=4000)
    path = tmp_path / "fresh.xsq"
    XSQExporter().export(sequence, path, pretty=True)

    reparsed = XSQParser().parse(path)
    assert reparsed.head.media_file == "song.mp3"


def test_fresh_xsq_refuses_empty_media_file() -> None:
    """The emitter will not build the unopenable file in the first place."""
    with pytest.raises(ValueError, match="media_file must be non-empty"):
        build_fresh_sequence(media_file="", duration_ms=4000)


def test_resolve_media_file_never_returns_empty() -> None:
    """A caller with no audio path still gets something xLights can open."""
    assert resolve_media_file(Path("/music/My Song.mp3")) == "My Song.mp3"
    assert resolve_media_file(None) == PLACEHOLDER_MEDIA_FILE
    assert resolve_media_file("   ") == PLACEHOLDER_MEDIA_FILE


def test_fresh_xsq_has_current_version_stamp(tmp_path: Path) -> None:
    """P5-F17: the stamp is the version the project targets, not an inherited 2024.x."""
    sequence = build_fresh_sequence(media_file="song.mp3", duration_ms=4000)
    assert sequence.head.version == XLIGHTS_VERSION_STAMP
    assert int(XLIGHTS_VERSION_STAMP.split(".")[0]) >= 2026


def test_fresh_emitters_agree_on_stamp_and_grid() -> None:
    """P5-M3: the moving-heads and display fresh emitters are one function now.

    They used to disagree on both the version stamp (2024.10 vs 2024.01) and the timing
    grid (50 ms vs 20 ms), so which of Twinklr's own paths wrote a file changed what the
    file claimed to be.
    """
    import inspect

    from twinklr.core.pipeline import display_stages
    from twinklr.core.sequencer.moving_heads import delivery

    for module in (display_stages, delivery):
        source = inspect.getsource(module)
        assert "build_fresh_sequence" in source
        assert "SequenceHead(" not in source, (
            f"{module.__name__} builds its own head instead of using the shared emitter"
        )

    mh = build_fresh_sequence(media_file="a.mp3", duration_ms=1000)
    display = build_fresh_sequence(media_file="a.mp3", duration_ms=1000, author="Display")
    assert mh.head.version == display.head.version == XLIGHTS_VERSION_STAMP
    assert mh.head.sequence_timing == display.head.sequence_timing == SEQUENCE_TIMING


# --- .xmap ------------------------------------------------------------------------


def test_xmap_names_emitted_models(tmp_path: Path) -> None:
    """Every model Twinklr emitted appears, mapped to a same-named layout model."""
    path = write_xmap(["Dmx MH1", "Dmx MH2"], tmp_path / "song.xmap")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "false"
    assert lines[1].split("\t")[0] == "Dmx MH1"
    assert lines[1].split("\t")[3] == "Dmx MH1"
    assert [line.split("\t")[0] for line in lines[1:]] == ["Dmx MH1", "Dmx MH2"]


def test_xmap_deduplicates_and_honours_targets() -> None:
    """Repeated models collapse; a known layout name overrides the identity hint."""
    text = build_xmap_text(
        ["GROUP - MOVING HEADS", "GROUP - MOVING HEADS", "Dmx MH1"],
        targets={"Dmx MH1": "My MH 1"},
    )
    rows = [line.split("\t") for line in text.splitlines()[1:]]
    assert [row[0] for row in rows] == ["GROUP - MOVING HEADS", "Dmx MH1"]
    assert rows[1][3] == "My MH 1"
