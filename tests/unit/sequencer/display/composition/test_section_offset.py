"""Section anchoring tests for millisecond-native expanded placements."""

from twinklr.core.sequencer.vocabulary import CoordinationMode, PlanningTimeRef

from .p3_t1_fixtures import events_by_start, make_engine, make_grid, make_window_plan


def test_section_offset_applied_once_mapped() -> None:
    intervals = [
        400.0,
        600.0,
        450.0,
        550.0,
        700.0,
        300.0,
        800.0,
        200.0,
        650.0,
        350.0,
        500.0,
        900.0,
        100.0,
        750.0,
        250.0,
        620.0,
    ]
    boundaries = [137.0]
    for interval in intervals:
        boundaries.append(boundaries[-1] + interval)
    grid = make_grid(boundaries)
    section_start = int(grid.bar_boundaries[2])
    section_end = int(grid.bar_boundaries[4])
    engine = make_engine(
        grid,
        section_boundaries=[("section", section_start, section_end)],
    )

    event = events_by_start(
        engine.compose(
            make_window_plan(
                CoordinationMode.SEQUENCED,
                group_ids=["G0"],
                start=PlanningTimeRef(bar=2, beat=1),
                end=PlanningTimeRef(bar=2, beat=3),
            )
        )
    )[0][1]

    # Relative beat 4 plus mapped section beat 8 must resolve at absolute beat 12.
    assert event.start_ms == engine._timing_resolver.snap(grid.beat_boundaries[12])


def test_section_offset_applied_once_unmapped() -> None:
    intervals = [400.0, 600.0, 450.0, 550.0, 700.0, 300.0, 800.0, 200.0]
    boundaries = [137.0]
    for interval in intervals:
        boundaries.append(boundaries[-1] + interval)
    grid = make_grid(boundaries)
    engine = make_engine(grid)
    event = events_by_start(
        engine.compose(
            make_window_plan(
                CoordinationMode.SEQUENCED,
                group_ids=["G0"],
                start=PlanningTimeRef(bar=2, beat=1),
                end=PlanningTimeRef(bar=2, beat=3),
            )
        )
    )[0][1]

    assert event.start_ms == engine._timing_resolver.snap(grid.beat_boundaries[4])


def test_mapped_ripple_interpolates_local_fractional_beats() -> None:
    intervals = [
        400.0,
        600.0,
        450.0,
        550.0,
        700.0,
        300.0,
        800.0,
        200.0,
        650.0,
        350.0,
        500.0,
        900.0,
        100.0,
        750.0,
        250.0,
        620.0,
    ]
    boundaries = [137.0]
    for interval in intervals:
        boundaries.append(boundaries[-1] + interval)
    grid = make_grid(boundaries)
    engine = make_engine(
        grid,
        section_boundaries=[("section", int(grid.bar_boundaries[2]), int(grid.bar_boundaries[4]))],
    )

    events = events_by_start(
        engine.compose(
            make_window_plan(
                CoordinationMode.RIPPLE,
                group_ids=["G0", "G1", "G2", "G3"],
                end=PlanningTimeRef(bar=1, beat=3),
                phase_offset=0.5,
            )
        )
    )

    assert [event.start_ms for _, event in events[:4]] == [4140, 4460, 4780, 4960]
