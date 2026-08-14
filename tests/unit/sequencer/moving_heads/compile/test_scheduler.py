"""Unit tests for the repeat scheduler.

The scheduler is where three of P1P-T5's defects live: a window shorter than one
cycle produced no instances at all (P4-F4), steps absent from `loop_step_ids` were
never instantiated (P4-F5), and steps were laid end to end regardless of the offsets
they declare, so a template whose steps run in parallel scheduled twice the bars its
cycle claimed (P4-F6).
"""

from __future__ import annotations

from twinklr.core.sequencer.models.template import (
    RemainderPolicy,
    RepeatContract,
    RepeatMode,
)
from twinklr.core.sequencer.moving_heads.compile.scheduler import schedule_repeats


def _contract(**overrides: object) -> RepeatContract:
    kwargs: dict[str, object] = {
        "repeatable": True,
        "mode": RepeatMode.PING_PONG,
        "cycle_bars": 4.0,
        "loop_step_ids": ["step_a", "step_b"],
    }
    kwargs.update(overrides)
    return RepeatContract(**kwargs)  # type: ignore[arg-type]


def test_sub_cycle_window_renders_the_head_of_the_cycle() -> None:
    """P4-F4: a window shorter than one cycle is no longer silence.

    It used to return `instances=[]` behind a `logger.warning` the CLI never
    surfaced at default verbosity, so a 1-bar section was simply dark.
    """
    result = schedule_repeats(_contract(), duration_bars=2.0)

    assert result.num_complete_cycles == 0
    assert [instance.step_id for instance in result.instances] == ["step_a"]
    assert result.instances[0].start_bars == 0.0
    assert result.instances[0].is_partial


def test_sub_cycle_window_keeps_the_nominal_step_duration() -> None:
    """The head is truncated at the boundary, not compressed into the window.

    Ending the instance at `duration_bars` here would squeeze a 2-bar step into 1
    bar and play it at double rate — the time-compression defect P4-F7 describes.
    The overrun is clipped in milliseconds by `template_compiler` instead.
    """
    result = schedule_repeats(_contract(), duration_bars=1.0)

    assert result.instances[0].end_bars == 2.0


def test_steps_are_placed_at_their_declared_offsets() -> None:
    """P4-F6: parallel steps are scheduled in parallel, not end to end.

    `split_lr_sweep_counter`'s shape: two 4-bar steps, both at offset 0, targeting
    disjoint fixture groups. Laid end to end they span 8 bars against a 4-bar cycle,
    which is how a 16-bar section came to schedule 32 bars of segments.
    """
    result = schedule_repeats(
        _contract(cycle_bars=4.0),
        duration_bars=8.0,
        step_durations={"step_a": 4.0, "step_b": 4.0},
        step_offsets={"step_a": 0.0, "step_b": 0.0},
    )

    assert result.num_complete_cycles == 2
    assert [(i.step_id, i.start_bars, i.end_bars) for i in result.instances] == [
        ("step_a", 0.0, 4.0),
        ("step_b", 0.0, 4.0),
        ("step_a", 4.0, 8.0),
        ("step_b", 4.0, 8.0),
    ]
    assert max(instance.end_bars for instance in result.instances) == 8.0


def test_sequential_offsets_reproduce_end_to_end_placement() -> None:
    """Steps that declare consecutive offsets schedule exactly as they used to."""
    result = schedule_repeats(
        _contract(mode=RepeatMode.JOINER),
        duration_bars=4.0,
        step_durations={"step_a": 2.0, "step_b": 2.0},
        step_offsets={"step_a": 0.0, "step_b": 2.0},
    )

    assert [(i.step_id, i.start_bars) for i in result.instances] == [
        ("step_a", 0.0),
        ("step_b", 2.0),
    ]


def test_ping_pong_mirrors_placements_on_odd_cycles() -> None:
    """PING_PONG still reverses the sequential case; mirroring generalizes it."""
    result = schedule_repeats(
        _contract(),
        duration_bars=8.0,
        step_durations={"step_a": 2.0, "step_b": 2.0},
        step_offsets={"step_a": 0.0, "step_b": 2.0},
    )

    assert [(i.step_id, i.start_bars) for i in result.instances] == [
        ("step_a", 0.0),
        ("step_b", 2.0),
        ("step_b", 4.0),
        ("step_a", 6.0),
    ]


def test_steps_starting_past_the_window_are_dropped() -> None:
    """A step whose slot begins after the section ends is not scheduled at all."""
    result = schedule_repeats(
        _contract(cycle_bars=6.0, loop_step_ids=["a", "b", "c"]),
        duration_bars=3.0,
        step_durations={"a": 2.0, "b": 2.0, "c": 2.0},
        step_offsets={"a": 0.0, "b": 2.0, "c": 4.0},
    )

    assert [instance.step_id for instance in result.instances] == ["a", "b"]


def test_hold_last_pose_holds_every_step_that_closes_the_cycle() -> None:
    """Parallel closing steps are both held; holding one would go dark on the other."""
    result = schedule_repeats(
        _contract(remainder_policy=RemainderPolicy.HOLD_LAST_POSE),
        duration_bars=6.0,
        step_durations={"step_a": 4.0, "step_b": 4.0},
        step_offsets={"step_a": 0.0, "step_b": 0.0},
    )

    remainder = [instance for instance in result.instances if instance.cycle_number == 1]
    assert {instance.step_id for instance in remainder} == {"step_a", "step_b"}
    assert all(instance.start_bars == 4.0 for instance in remainder)
    assert all(instance.end_bars == 6.0 for instance in remainder)


def test_zero_duration_window_schedules_nothing() -> None:
    assert schedule_repeats(_contract(), duration_bars=0.0).instances == []
