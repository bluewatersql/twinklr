"""Discriminating tests for P3-T1 millisecond-native expansion."""

from twinklr.core.sequencer.vocabulary import CoordinationMode, PlanningTimeRef, StepUnit

from .p3_t1_fixtures import events_by_start, make_engine, make_grid, make_window_plan


def test_sequenced_start_matches_expander_ms() -> None:
    engine = make_engine()
    events = events_by_start(
        engine.compose(
            make_window_plan(
                CoordinationMode.SEQUENCED,
                group_ids=["G0", "G1"],
                step_duration=1,
            )
        )
    )

    assert [event.start_ms for _, event in events[:4]] == [140, 640, 1140, 1640]


def test_expansion_uses_local_irregular_beat_boundaries() -> None:
    intervals = [400.0, 600.0, 450.0, 550.0, 700.0, 300.0, 800.0, 200.0]
    boundaries = [137.0]
    for interval in intervals:
        boundaries.append(boundaries[-1] + interval)
    engine = make_engine(make_grid(boundaries, tempo_bpm=120.0))
    events = events_by_start(
        engine.compose(
            make_window_plan(
                CoordinationMode.SEQUENCED,
                group_ids=["G0"],
                end=PlanningTimeRef(bar=2, beat=1),
            )
        )
    )

    assert [event.start_ms for _, event in events[:4]] == [140, 540, 1140, 1580]


def test_fractional_beat_position_interpolates_and_endpoints_clamp() -> None:
    boundaries = [137.0, 537.0, 1137.0]
    resolver = make_engine(make_grid(boundaries))._timing_resolver

    assert resolver.resolve_beat_position_ms(0.5) == 337.0
    assert resolver.resolve_beat_position_ms(-1.0) == 137.0
    assert resolver.resolve_beat_position_ms(99.0) == 1137.0


def test_step_units_convert_to_beat_spans() -> None:
    engine = make_engine()

    assert engine._resolve_step_beats(StepUnit.BEAT, 3) == 3.0
    assert engine._resolve_step_beats(StepUnit.BAR, 2) == 8.0
    assert engine._resolve_step_beats(StepUnit.PHRASE, 2) == 32.0


def test_ripple_sub_beat_offsets_survive() -> None:
    events = events_by_start(
        make_engine().compose(
            make_window_plan(
                CoordinationMode.RIPPLE,
                group_ids=["G0", "G1", "G2", "G3"],
                phase_offset=0.5,
            )
        )
    )

    assert [event.start_ms for _, event in events[:4]] == [140, 380, 640, 880]


def test_slot_duration_not_rebucketed() -> None:
    engine = make_engine()
    three_beat = events_by_start(
        engine.compose(
            make_window_plan(
                CoordinationMode.SEQUENCED,
                group_ids=["G0"],
                end=PlanningTimeRef(bar=2, beat=1),
                step_duration=3,
            )
        )
    )[0][1]
    five_beat = events_by_start(
        engine.compose(
            make_window_plan(
                CoordinationMode.SEQUENCED,
                group_ids=["G0"],
                end=PlanningTimeRef(bar=3, beat=1),
                step_duration=5,
            )
        )
    )[0][1]

    assert three_beat.duration_ms == 1500
    assert five_beat.duration_ms == 2500


def test_planner_authored_timing_remains_categorical() -> None:
    from .p3_t1_fixtures import make_authored_plan

    engine = make_engine()
    event = events_by_start(engine.compose(make_authored_plan()))[0][1]

    assert event.start_ms == engine._timing_resolver.resolve_start_ms(
        PlanningTimeRef(bar=1, beat=2)
    )
    assert event.end_ms == engine._timing_resolver.resolve_end_ms(
        event.start_ms,
        duration=make_authored_plan()
        .section_plans[0]
        .lane_plans[0]
        .coordination_plans[0]
        .placements[0]
        .duration,
    )
