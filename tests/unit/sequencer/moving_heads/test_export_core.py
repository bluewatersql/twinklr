"""P3-T6 moving-head adapter coverage through the shared emission seam."""

from __future__ import annotations

import pytest

from twinklr.core.config.fixtures import DmxMapping, FixtureConfig, FixtureGroup, FixtureInstance
from twinklr.core.formats.xlights.sequence.fresh import build_fresh_sequence
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.export.xsq_adapter import XsqAdapter


def _rig(count: int = 1, *, grouped: bool = False) -> FixtureGroup:
    rig = FixtureGroup(
        group_id="MOVING_HEADS",
        xlights_semantic_groups={"ALL": "Moving Heads"} if grouped else {},
    )
    for index in range(count):
        fixture_id = f"MH{index + 1}"
        rig.add_fixture(
            FixtureInstance(
                fixture_id=fixture_id,
                config=FixtureConfig(
                    fixture_id=fixture_id,
                    dmx_mapping=DmxMapping(pan_channel=2, tilt_channel=3, dimmer_channel=1),
                ),
                xlights_model_name=f"Dmx {fixture_id}",
            )
        )
    return rig


def _segment(fixture_id: str, segment_id: str, start: int, end: int) -> FixtureSegment:
    return FixtureSegment(
        section_id="chorus",
        segment_id=segment_id,
        step_id=f"step-{segment_id}",
        template_id="sweep",
        fixture_id=fixture_id,
        t0_ms=start,
        t1_ms=end,
        channels={ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=200)},
        allow_grouping=True,
    )


def test_zero_duration_segments_are_skipped_not_fatal() -> None:
    """A zero-duration segment must be dropped, not crash emission.

    ``FixtureSegment`` permits ``t1_ms == t0_ms`` (its validator only rejects ``t1 < t0``),
    but ``EmissionRequest`` requires a strictly positive duration (``0 <= start < end``).
    A live moving-head run produced a zero-duration transition segment that terminated the
    whole render with ``Emission requires 0 <= start_ms < end_ms``. The adapter already
    skips other unusable segments (empty channels, unmapped fixtures); a degenerate
    duration carries no visible effect and must be skipped the same way.
    """
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1_000)
    placements = XsqAdapter().convert(
        [_segment("MH1", "ok", 0, 200), _segment("MH1", "zero", 200, 200)],
        _rig(),
        sequence,
    )

    assert len(placements) == 1
    assert (placements[0].start_ms, placements[0].end_ms) == (0, 200)


def test_identical_mh_settings_deduplicate_and_times_use_twenty_ms_grid() -> None:
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1_000)
    placements = XsqAdapter().convert(
        [_segment("MH1", "a", 11, 29), _segment("MH1", "b", 31, 59)],
        _rig(),
        sequence,
    )

    assert sequence.effect_db.entries[0] == ""
    assert len(sequence.effect_db.entries) == 2
    assert [item.ref for item in placements] == [1, 1]
    assert [(item.start_ms, item.end_ms) for item in placements] == [(20, 40), (40, 60)]


def test_group_trace_retains_every_contributing_source_in_stable_order() -> None:
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1_000)
    XsqAdapter().convert(
        [_segment("MH2", "b", 0, 100), _segment("MH1", "a", 0, 100)],
        _rig(2, grouped=True),
        sequence,
    )

    assert len(sequence.emission_trace_entries) == 1
    trace = sequence.emission_trace_entries[0]
    assert trace["backend"] == "moving_head"
    assert trace["element_name"] == "Moving Heads"
    assert trace["sources"] == [
        {"fixture_id": "MH1", "segment_id": "a", "step_id": "step-a"},
        {"fixture_id": "MH2", "segment_id": "b", "step_id": "step-b"},
    ]


def test_group_emission_is_permutation_invariant_and_representative_coherent() -> None:
    segments = [_segment("MH2", "b", 0, 100), _segment("MH1", "a", 0, 100)]

    def snapshot(items: list[FixtureSegment]) -> tuple[object, object, object]:
        sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1_000)
        placements = XsqAdapter().convert(items, _rig(2, grouped=True), sequence)
        return placements, sequence.effect_db.entries, sequence.emission_trace_entries

    assert snapshot(segments) == snapshot(list(reversed(segments)))


@pytest.mark.parametrize("field,value", [("section_id", "bridge"), ("template_id", "other")])
def test_group_emission_rejects_conflicting_shared_provenance(field: str, value: str) -> None:
    first = _segment("MH1", "a", 0, 100)
    second = _segment("MH2", "b", 0, 100).model_copy(update={field: value})
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1_000)
    before = sequence.model_copy(deep=True)

    with pytest.raises(ValueError, match="group provenance"):
        XsqAdapter().convert([first, second], _rig(2, grouped=True), sequence)

    assert sequence == before
