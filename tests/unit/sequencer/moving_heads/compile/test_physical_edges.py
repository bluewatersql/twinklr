"""Silent song edges: a physical compile covers only the detected span of the song (P2.0).

A cue that would start before the covered start, or at or after the covered end, is
dropped with a record; one that runs past the covered end is cut there on the frame
grid. Limits come from `physical_cue_limits`, as the render and the gate take them.
"""

from __future__ import annotations

from typing import Any

from tests.support.mh_physical import (
    TEMPLATE_DIR,
    TEMPLATE_ID,
    physical_edge_grid,
    physical_grid,
    physical_rig,
)
from twinklr.core.sequencer.models.context import TemplateCompileContext
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.models.template import Template
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    TemplateCompileResult,
    compile_physical_template,
)
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
from twinklr.core.sequencer.moving_heads.pipeline import physical_cue_limits
from twinklr.core.sequencer.moving_heads.templates.data_loader import load_template_document
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import build_musical_phase_map

_EDGE_GRID = physical_edge_grid(lead_in_ms=3000, tail_ms=4000)
"""Beats from 3015 ms (500 ms apart, then 400 ms) to 6615 ms; the song ends at 10615 ms.
Covered from 2515 ms to 7015 ms; cue limits 2520 and 7000 ms."""


def _template(*, whole_bar: bool = False) -> Template:
    """The test template; `whole_bar` makes its step fill each bar from the downbeat."""
    template = load_template_document(TEMPLATE_DIR / f"{TEMPLATE_ID}.json").template
    if whole_bar:
        template = template.model_copy(deep=True)
        template.steps[0].timing.base_timing.start_offset_bars = 0.0
        template.steps[0].timing.base_timing.duration_bars = 1.0
    return template


def _compile(
    grid: BeatGrid, *, start_bar: int, duration_bars: int, template: Template | None = None
) -> TemplateCompileResult:
    rig = physical_rig()
    template = template or _template()
    context = TemplateCompileContext(
        section_id="verse",
        template_id=template.template_id,
        fixtures=build_fixture_contexts(rig_profile_from_fixture_group(rig), rig),
        beat_grid=grid,
        start_bar=start_bar,
        duration_bars=duration_bars,
    )
    phase_map = build_musical_phase_map(grid)
    start_limit, end_limit = physical_cue_limits(phase_map, int(grid.duration_ms))
    return compile_physical_template(
        template, context, phase_map=phase_map, start_limit_ms=start_limit, end_limit_ms=end_limit
    )


def _spans(result: TemplateCompileResult) -> list[tuple[str, int, int]]:
    return [(s.fixture_id, s.t0_ms, s.t1_ms) for s in result.segments]


def test_cue_limits_round_the_covered_span_inward_to_the_frame_grid() -> None:
    phase_map = build_musical_phase_map(_EDGE_GRID)

    assert (phase_map.covered_start_ms, phase_map.covered_end_ms) == (2515, 7015)
    assert physical_cue_limits(phase_map, 10615) == (2520, 7000)
    # A covered end past the song's last whole frame is limited by the frame.
    assert physical_cue_limits(build_musical_phase_map(physical_grid()), 3615) == (0, 3600)


def test_cue_before_covered_start_is_dropped_with_a_record() -> None:
    """A section from bar 0 puts its first reveal at 2115 ms, a bar before the first
    downbeat and before the covered start: dropped, not cut, since its phase origin
    would lie outside the map."""
    result = _compile(_EDGE_GRID, start_bar=0, duration_bars=2)

    assert result.dropped_steps == [
        {
            "fixture_id": fixture_id,
            "section_id": "verse",
            "step_id": "reveal",
            "requested_start_ms": 2115,
            "requested_end_ms": 3015,
            "start_ms": 2120,
            "end_ms": 3020,
            "start_limit_ms": 2520,
            "end_limit_ms": 7000,
        }
        for fixture_id in ("MH1", "MH2")
    ]
    assert _spans(result) == [("MH1", 4020, 5020), ("MH2", 4020, 5020)]


def test_cue_past_covered_end_is_cut_on_the_frame_grid() -> None:
    """Bar 3 starts on the last observed beat (6615 ms); its whole-bar step would run to
    8415 ms and is cut at the covered end's frame, 7000 ms."""
    result = _compile(_EDGE_GRID, start_bar=3, duration_bars=1, template=_template(whole_bar=True))

    assert result.dropped_steps == []
    assert _spans(result) == [("MH1", 6620, 7000), ("MH2", 6620, 7000)]
    for segment in result.segments:
        assert segment.metadata["requested_t0_ms"] == "6615"
        assert segment.metadata["requested_t1_ms"] == "8415"


def test_cue_starting_at_covered_end_is_dropped() -> None:
    """At 120 BPM from 0 ms with three silent seconds after the last beat (3500 ms), the
    covered end is 4000 ms, where bar 3 starts: its step has no covered frame."""
    grid = physical_edge_grid(
        lead_in_ms=0, tail_ms=3000, grid=BeatGrid.from_tempo(tempo_bpm=120, total_bars=2)
    )
    result = _compile(grid, start_bar=1, duration_bars=3, template=_template(whole_bar=True))

    assert [(d["fixture_id"], d["requested_start_ms"]) for d in result.dropped_steps] == [
        ("MH1", 4000),
        ("MH2", 4000),
    ]
    assert all(d["end_limit_ms"] == 4000 for d in result.dropped_steps)
    assert _spans(result) == [
        ("MH1", 0, 2000),
        ("MH2", 0, 2000),
        ("MH1", 2000, 4000),
        ("MH2", 2000, 4000),
    ]


def test_phase1_grid_compiles_identical_segments() -> None:
    """On a grid Phase 1 accepted, the limits are Phase 1's (0 and the last whole frame)
    and the compile is the one Phase 1 made without a start limit."""
    grid = physical_grid()
    rig = physical_rig()
    context: dict[str, Any] = {
        "section_id": "verse",
        "template_id": TEMPLATE_ID,
        "fixtures": build_fixture_contexts(rig_profile_from_fixture_group(rig), rig),
        "beat_grid": grid,
        "start_bar": 1,
        "duration_bars": 2,
    }
    phase1 = compile_physical_template(
        _template(),
        TemplateCompileContext(**context),
        phase_map=build_musical_phase_map(grid),
        end_limit_ms=3600,
    )

    result = _compile(grid, start_bar=1, duration_bars=2)

    assert [s.model_dump() for s in result.segments] == [s.model_dump() for s in phase1.segments]
    assert _spans(result) == [
        ("MH1", 1020, 2020),
        ("MH2", 1020, 2020),
        ("MH1", 2820, 3600),
        ("MH2", 2820, 3600),
    ]
    assert result.dropped_steps == phase1.dropped_steps == []
