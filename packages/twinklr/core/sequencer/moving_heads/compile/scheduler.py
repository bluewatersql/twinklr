"""Repeat Scheduler for template compilation.

This module provides functions to schedule template repeats within
a playback window, handling PING_PONG and JOINER repeat modes,
and remainder policies.

Steps are placed at the ``start_offset_bars`` they declare, measured from the start
of the cycle. That field used to be ignored: the scheduler laid every loop step end
to end, which turned a template whose steps deliberately overlap (``left_sweep`` and
``right_sweep`` both at offset 0, targeting disjoint fixture groups) into a schedule
twice as long as the cycle it claimed to fill (P4-F6).
"""

import logging

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.models.compiler import ScheduledInstance
from twinklr.core.sequencer.models.template import (
    RemainderPolicy,
    RepeatContract,
    RepeatMode,
)

logger = logging.getLogger(__name__)

_EPSILON_BARS = 1e-9

# (step_id, offset_bars_within_cycle, duration_bars)
_Placement = tuple[str, float, float]


class ScheduleResult(BaseModel):
    """Result of scheduling repeats.

    Contains all scheduled step instances and metadata about the schedule.

    Attributes:
        instances: List of scheduled step instances.
        num_complete_cycles: Number of complete cycles that fit in the window.
        remainder_bars: Duration of remainder after last complete cycle.
        remainder_policy: Policy for handling the remainder.

    Example:
        >>> result = ScheduleResult(
        ...     instances=[...],
        ...     num_complete_cycles=2,
        ...     remainder_bars=1.5,
        ...     remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
        ... )
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    instances: list[ScheduledInstance] = Field(default_factory=list)
    num_complete_cycles: int = Field(default=0, ge=0)
    remainder_bars: float = Field(default=0.0, ge=0.0)
    remainder_policy: RemainderPolicy = Field(RemainderPolicy.HOLD_LAST_POSE)


def schedule_repeats(
    contract: RepeatContract,
    duration_bars: float,
    step_durations: dict[str, float] | None = None,
    step_offsets: dict[str, float] | None = None,
) -> ScheduleResult:
    """Schedule template repeats within a playback window.

    Calculates when each step instance should occur based on the
    repeat contract configuration.

    Instances may extend past ``duration_bars``: a window shorter than one cycle
    renders the *head* of the cycle at its nominal rate and is truncated at the
    section boundary by ``template_compiler``. Clamping in bars here would instead
    compress the pattern into the shorter window, which is the time-compression
    defect P4-F7 documents. Instances that begin at or after the window end are
    dropped outright.

    Args:
        contract: The repeat contract defining cycle behavior.
        duration_bars: Total window duration in bars.
        step_durations: Optional mapping of step_id to duration in bars.
            If not provided, steps split the cycle evenly.
        step_offsets: Optional mapping of step_id to its offset in bars from the
            start of the cycle. When omitted (or incomplete), steps are laid out
            back to back in ``loop_step_ids`` order.

    Returns:
        ScheduleResult with all scheduled instances and metadata.

    Example:
        >>> contract = RepeatContract(
        ...     cycle_bars=4.0,
        ...     loop_step_ids=["step1", "step2"],
        ...     mode=RepeatMode.PING_PONG,
        ... )
        >>> result = schedule_repeats(contract, duration_bars=8.0)
    """
    if duration_bars <= 0.0:
        return ScheduleResult(
            instances=[],
            num_complete_cycles=0,
            remainder_bars=0.0,
            remainder_policy=contract.remainder_policy,
        )

    # Calculate step durations if not provided
    if step_durations is None:
        num_steps = len(contract.loop_step_ids)
        default_duration = contract.cycle_bars / num_steps
        step_durations = dict.fromkeys(contract.loop_step_ids, default_duration)

    placements = _cycle_placements(contract, step_durations, step_offsets)

    # Calculate number of complete cycles
    num_complete_cycles = int(duration_bars // contract.cycle_bars)
    remainder_bars = duration_bars - (num_complete_cycles * contract.cycle_bars)

    # Window shorter than one cycle (P4-F4). This used to return an empty schedule
    # behind a logger.warning the CLI never surfaced, so a 1-bar section rendered
    # nothing at all for every one of the shipped templates. Render the head of the
    # cycle instead and let the boundary clip truncate it.
    if num_complete_cycles == 0:
        logger.debug(
            "Section window shorter than cycle, rendering a truncated cycle: "
            "duration_bars=%.3f cycle_bars=%.3f",
            duration_bars,
            contract.cycle_bars,
        )
        return ScheduleResult(
            instances=_schedule_cycle(
                placements,
                contract,
                cycle_num=0,
                cycle_start=0.0,
                window_end=duration_bars,
                is_partial=True,
                is_fade_out=contract.remainder_policy == RemainderPolicy.FADE_OUT,
            ),
            num_complete_cycles=0,
            remainder_bars=duration_bars,
            remainder_policy=contract.remainder_policy,
        )

    # Build schedule
    instances: list[ScheduledInstance] = []

    for cycle_num in range(num_complete_cycles):
        instances.extend(
            _schedule_cycle(
                placements,
                contract,
                cycle_num=cycle_num,
                cycle_start=cycle_num * contract.cycle_bars,
                window_end=duration_bars,
            )
        )

    # Handle remainder based on policy
    if remainder_bars > _EPSILON_BARS:
        remainder_start = num_complete_cycles * contract.cycle_bars

        if contract.remainder_policy == RemainderPolicy.HOLD_LAST_POSE:
            instances.extend(
                _hold_last_pose(
                    instances,
                    remainder_start=remainder_start,
                    remainder_bars=remainder_bars,
                    cycle_number=num_complete_cycles,
                )
            )
        else:
            # TRUNCATE and FADE_OUT both render the start of the next cycle and are
            # clipped at the section boundary; FADE_OUT additionally fades the dimmer.
            instances.extend(
                _schedule_cycle(
                    placements,
                    contract,
                    cycle_num=num_complete_cycles,
                    cycle_start=remainder_start,
                    window_end=duration_bars,
                    is_partial=True,
                    is_fade_out=contract.remainder_policy == RemainderPolicy.FADE_OUT,
                )
            )

    return ScheduleResult(
        instances=instances,
        num_complete_cycles=num_complete_cycles,
        remainder_bars=remainder_bars,
        remainder_policy=contract.remainder_policy,
    )


def _cycle_placements(
    contract: RepeatContract,
    step_durations: dict[str, float],
    step_offsets: dict[str, float] | None,
) -> list[_Placement]:
    """Resolve where each loop step sits inside one cycle.

    Args:
        contract: The repeat contract.
        step_durations: Duration in bars per step id.
        step_offsets: Offset in bars per step id, or None to lay steps end to end.

    Returns:
        Placements ordered by offset, declaration order preserved among ties.
    """
    placements: list[_Placement] = []

    if step_offsets is not None and all(
        step_id in step_offsets for step_id in contract.loop_step_ids
    ):
        for step_id in contract.loop_step_ids:
            duration = step_durations.get(step_id, contract.cycle_bars)
            placements.append((step_id, float(step_offsets[step_id]), float(duration)))

        span = max((offset + duration for _, offset, duration in placements), default=0.0)
        if span > contract.cycle_bars + _EPSILON_BARS:
            # The registration validator rejects this shape; a preset patching step
            # durations can still produce it at runtime.
            logger.warning(
                "Loop steps span %.3f bars but the cycle is %.3f bars; the overrun "
                "will be clipped at the section boundary",
                span,
                contract.cycle_bars,
            )
    else:
        current = 0.0
        for step_id in contract.loop_step_ids:
            duration = float(step_durations.get(step_id, contract.cycle_bars))
            placements.append((step_id, current, duration))
            current += duration

    return sorted(placements, key=lambda placement: placement[1])


def _schedule_cycle(
    placements: list[_Placement],
    contract: RepeatContract,
    *,
    cycle_num: int,
    cycle_start: float,
    window_end: float,
    is_partial: bool = False,
    is_fade_out: bool = False,
) -> list[ScheduledInstance]:
    """Instantiate one cycle of the loop, dropping steps that start past the window."""
    instances: list[ScheduledInstance] = []

    for step_id, offset, duration in _cycle_order(placements, contract, cycle_num):
        start_bars = cycle_start + offset
        if start_bars >= window_end - _EPSILON_BARS:
            continue

        end_bars = start_bars + duration
        instances.append(
            ScheduledInstance(
                step_id=step_id,
                start_bars=start_bars,
                end_bars=end_bars,
                cycle_number=cycle_num,
                is_partial=is_partial or end_bars > window_end + _EPSILON_BARS,
                is_fade_out=is_fade_out,
            )
        )

    return instances


def _cycle_order(
    placements: list[_Placement],
    contract: RepeatContract,
    cycle_num: int,
) -> list[_Placement]:
    """Get step placements for a given cycle.

    For JOINER mode, placements are used as declared.
    For PING_PONG mode, odd cycles mirror each placement about the cycle's midpoint,
    so a step at the head of the cycle plays at its tail. For the single-step and
    strictly sequential templates this is exactly the reversed step order the
    scheduler used before offsets were honored.

    Args:
        placements: Placements for one cycle.
        contract: The repeat contract.
        cycle_num: The cycle number (0-indexed).

    Returns:
        Placements in the order they should play.
    """
    if contract.mode != RepeatMode.PING_PONG or cycle_num % 2 == 0:
        return placements

    mirrored = [
        (step_id, max(0.0, contract.cycle_bars - (offset + duration)), duration)
        for step_id, offset, duration in placements
    ]
    return sorted(mirrored, key=lambda placement: placement[1])


def _hold_last_pose(
    instances: list[ScheduledInstance],
    *,
    remainder_start: float,
    remainder_bars: float,
    cycle_number: int,
) -> list[ScheduledInstance]:
    """Extend the steps that close the last cycle across the remainder.

    Every step ending on the cycle boundary is held, not just the last one in the
    list: templates whose steps run in parallel on disjoint fixture groups would
    otherwise hold one group and go dark on the other.
    """
    if not instances:
        return []

    closing = [
        instance
        for instance in instances
        if abs(instance.end_bars - remainder_start) <= _EPSILON_BARS
    ]
    if not closing:
        closing = [max(instances, key=lambda instance: instance.end_bars)]

    return [
        ScheduledInstance(
            step_id=instance.step_id,
            start_bars=remainder_start,
            end_bars=remainder_start + remainder_bars,
            cycle_number=cycle_number,
        )
        for instance in closing
    ]
