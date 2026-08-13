"""The repository's first `.xsq` parse -> export -> parse round-trip test.

Before this module there was no sample `.xsq` anywhere in the tree, no golden file, no
fixture, and no round-trip test (P5 SS-V4; CC-7 records "zero round-trip tests" as a
repo-wide defect), so nothing could tell a lossy exporter from a correct one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from twinklr.core.formats.xlights.sequence.exporter import XSQExporter
from twinklr.core.formats.xlights.sequence.models.xsq import XSequence
from twinklr.core.formats.xlights.sequence.parser import XSQParser

FIXTURE_XSQ = Path(__file__).resolve().parent / "fixtures" / "minimal.xsq"


@pytest.fixture
def parsed() -> XSequence:
    return XSQParser().parse(FIXTURE_XSQ)


@pytest.fixture
def round_tripped(parsed: XSequence, tmp_path: Path) -> XSequence:
    """parse(fixture) -> export -> parse again."""
    exported = tmp_path / "round_trip.xsq"
    XSQExporter().export(parsed, exported, pretty=True)
    return XSQParser().parse(exported)


def test_fixture_parses(parsed: XSequence) -> None:
    assert parsed.head.version == "2024.10"
    assert parsed.sequence_duration_ms == 4000
    assert len(parsed.effect_db.entries) == 2
    assert [track.name for track in parsed.timing_tracks] == ["Bars"]
    assert [element.element_name for element in parsed.element_effects] == ["Dmx MH1"]


def test_xsq_round_trip_preserves_effect_parameters(round_tripped: XSequence) -> None:
    """Effect-level attributes no model field knows about survive the round trip.

    `Effect.parameters` is the one documented survivor in P5-F5 item 7: the parser
    sweeps unrecognised attributes into it and the exporter writes them back out. If
    that link breaks, every xLights-authored attribute on an effect is silently dropped
    the first time Twinklr rewrites a sequence.
    """
    element = round_tripped.get_element("Dmx MH1")
    assert element is not None
    effects = element.layers[0].effects
    assert len(effects) == 2
    assert effects[1].parameters == {"selected": "0", "bufferTransform": "None"}
    assert effects[0].parameters == {}


def test_xsq_round_trip_media_file_non_empty(parsed: XSequence, tmp_path: Path) -> None:
    """The exported head carries a non-empty `mediaFile`.

    This is the assertion that catches the self-fatal fresh-emit branch in
    `xsq_export.py`, which builds `SequenceHead(media_file="")`. xLights will not open
    such a sequence. P1P-T11 turns that branch on; when it does, this test is what stops
    an empty `mediaFile` reaching a `.xsq`.
    """
    exported = tmp_path / "media.xsq"
    XSQExporter().export(parsed, exported, pretty=True)

    reparsed = XSQParser().parse(exported)
    assert reparsed.head.media_file == "minimal_round_trip.mp3"
    assert "<mediaFile>minimal_round_trip.mp3</mediaFile>" in exported.read_text(encoding="utf-8")


def test_xsq_round_trip_preserves_effectdb_and_refs(round_tripped: XSequence) -> None:
    """Settings strings and the ref indices pointing at them both survive."""
    assert round_tripped.effect_db.entries[0].startswith("B_CHOICE_BufferStyle=")
    assert "E_VALUECURVE_DMX2=" in round_tripped.effect_db.entries[1]

    element = round_tripped.get_element("Dmx MH1")
    assert element is not None
    effects = element.layers[0].effects
    assert [effect.ref for effect in effects] == [0, 1]
    assert [effect.label for effect in effects] == ["bar1_hold", "bar2_sweep"]
    assert [(effect.start_time_ms, effect.end_time_ms) for effect in effects] == [
        (0, 2000),
        (2000, 4000),
    ]


def test_xsq_round_trip_preserves_timing_track(round_tripped: XSequence) -> None:
    assert [track.name for track in round_tripped.timing_tracks] == ["Bars"]
    markers = round_tripped.timing_tracks[0].markers
    assert [(marker.name, marker.time_ms, marker.end_time_ms) for marker in markers] == [
        ("1", 0, 2000),
        ("2", 2000, 4000),
    ]


def test_xsq_round_trip_is_a_fixed_point(parsed: XSequence, round_tripped: XSequence) -> None:
    """The whole model survives, not just the fields spelled out above."""
    assert round_tripped == parsed


def test_xsq_round_trip_is_byte_stable(parsed: XSequence, tmp_path: Path) -> None:
    """Exporting the same model twice produces identical bytes — no timestamps or ids."""
    first = tmp_path / "first.xsq"
    second = tmp_path / "second.xsq"
    XSQExporter().export(parsed, first, pretty=True)
    XSQExporter().export(XSQParser().parse(first), second, pretty=True)

    assert first.read_bytes() == second.read_bytes()
