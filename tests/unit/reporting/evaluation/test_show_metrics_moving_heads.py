"""Show metrics on a moving-head trace: onsets, not 20 ms frame runs.

A render writes each moving head as constant DMX frame runs, so its trace has
one entry per run: the dark transactions and parks between cues, every run of a cue,
and the runs of a cue held dark through a dark span. The metrics count where a cue is
seen to begin.
"""

from __future__ import annotations

from tests.unit.reporting.evaluation.show_test_support import entry, grid, manifest, trace
from twinklr.core.reporting.evaluation.show_manifest import ShowTraceEntry, ShowTraceV2
from twinklr.core.reporting.evaluation.show_metrics import (
    score_cross_part_alignment,
    show_emissions,
)


def _run(
    start: int, end: int, *sources: tuple[str, str], section: str = "section"
) -> ShowTraceEntry:
    """One frame run of Dmx MH1; `sources` are `(segment_id, step_id)`, earliest first."""
    park = section == ""
    return ShowTraceEntry.model_validate(
        {
            **entry("moving_head", start, end).model_dump(mode="json"),
            "element_name": "Dmx MH1",
            "group_id": "Dmx MH1",
            "event_id": f"mh:Dmx MH1:{start}:{end}:0",
            "section_id": section,
            "template_id": "" if park else "swing_template",
            "sources": [
                {"fixture_id": "MH1", "segment_id": segment, "step_id": step}
                for segment, step in sources
            ],
        }
    )


_TRANSACTION = ("A/preposition", "preposition")
_SWING = ("A", "swing")
_HOLD = ("B", "hold")
_PARK = ("MH1/park/preposition", "preposition")


def _moving_head_trace() -> ShowTraceV2:
    """The manifest's section (0-2000 ms): the display calls on beats 1 and 3, the heads
    answer on beats 2 and 4, so the render holds them dark over 0-500 and 1000-1500.

    Hand-computed onsets for Dmx MH1: the transaction at 0 and the park at 2000 are
    dark; the swing's runs in 0-500 and 1000-1500 are inside dark spans; the swing is
    seen from 500 (three runs, one onset to 1000) and again from 1500 (two runs, the
    second shared with the hold that follows, to 1700); the hold from 1700."""
    rows = trace(
        entry("display", 0, 500),
        _run(0, 20, _TRANSACTION),
        _run(20, 260, _SWING),
        _run(260, 500, _SWING),
        _run(500, 520, _SWING),
        _run(520, 740, _SWING),
        _run(740, 1_000, _SWING),
        entry("display", 1_000, 1_500),
        _run(1_000, 1_500, _SWING),
        _run(1_500, 1_600, _SWING),
        _run(1_600, 1_700, _SWING, _HOLD),
        _run(1_700, 2_000, _HOLD),
        _run(2_000, 2_020, _PARK, section=""),
    )
    return rows.model_copy(
        update={"render": {"renderer_revision": "2", "dark_spans": [[0, 500], [1_000, 1_500]]}}
    )


def test_moving_head_frame_runs_become_one_onset_per_seen_cue() -> None:
    emissions = show_emissions(_moving_head_trace())

    assert [(item.backend, item.start_ms, item.end_ms) for item in emissions] == [
        ("display", 0, 500),
        ("moving_head", 500, 1_000),
        ("display", 1_000, 1_500),
        ("moving_head", 1_500, 1_700),
        ("moving_head", 1_700, 2_000),
    ]


def test_cross_part_metrics_read_the_onsets_of_a_moving_head_trace() -> None:
    rows = _moving_head_trace()

    result = score_cross_part_alignment(manifest=manifest(), trace=rows, beat_grid=grid())

    assert result.emitted_entry_count == len(rows.entries) == 13
    assert result.deduplicated_entry_count == 5
    boundary = result.section_boundaries[0]
    # The heads are first seen at 500 ms, not at the dark transaction at 0.
    assert (boundary.moving_head_start_ms, boundary.display_start_ms) == (500, 0)
    assert boundary.signed_offset_ms == -500
    expected = {
        (row.phase, row.expected_start_ms): row.observed_start_ms
        for row in result.pair_alignments[0].expected
    }
    assert expected == {
        ("call", 0): 0,
        ("response", 500): 500,
        ("call", 1_000): 1_000,
        ("response", 1_500): 1_500,
    }
