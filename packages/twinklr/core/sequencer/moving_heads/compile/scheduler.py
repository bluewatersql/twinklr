"""Repeat Scheduler for template compilation.

This module provides functions to schedule template repeats within
a playback window, handling PING_PONG and JOINER repeat modes,
and remainder policies.
"""

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.sequencer.models.compiler import ScheduledInstance
from blinkb0t.core.sequencer.models.template import (
    RemainderPolicy,
    RepeatContract,
    RepeatMode,
)


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
) -> ScheduleResult:
    """Schedule template repeats within a playback window.

    Calculates when each step instance should occur based on the
    repeat contract configuration.

    Args:
        contract: The repeat contract defining cycle behavior.
        duration_bars: Total window duration in bars.
        step_durations: Optional mapping of step_id to duration in bars.
            If not provided, steps split the cycle evenly.

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

    # Calculate number of complete cycles
    num_complete_cycles = int(duration_bars // contract.cycle_bars)
    remainder_bars = duration_bars - (num_complete_cycles * contract.cycle_bars)

    # Handle case where window is smaller than one cycle
    if num_complete_cycles == 0:
        return ScheduleResult(
            instances=[],
            num_complete_cycles=0,
            remainder_bars=duration_bars,
            remainder_policy=contract.remainder_policy,
        )

    # Build schedule
    instances: list[ScheduledInstance] = []
    current_time = 0.0

    # Schedule complete cycles
    for cycle_num in range(num_complete_cycles):
        # Determine step order based on mode
        step_ids = _get_step_order(contract, cycle_num)

        for step_id in step_ids:
            duration = step_durations.get(step_id, contract.cycle_bars)
            end_time = current_time + duration

            instances.append(
                ScheduledInstance(
                    step_id=step_id,
                    start_bars=current_time,
                    end_bars=end_time,
                    cycle_number=cycle_num,
                )
            )
            current_time = end_time

    # Handle remainder based on policy
    if remainder_bars > 0.0:
        if contract.remainder_policy == RemainderPolicy.HOLD_LAST_POSE:
            # Add an instance for the last step that extends to fill the remainder
            if instances:
                last_step_id = instances[-1].step_id
                instances.append(
                    ScheduledInstance(
                        step_id=last_step_id,
                        start_bars=current_time,
                        end_bars=current_time + remainder_bars,
                        cycle_number=num_complete_cycles,  # Remainder cycle
                    )
                )

        elif contract.remainder_policy == RemainderPolicy.TRUNCATE:
            # Schedule a partial cycle that will be clipped to window boundary
            # This renders the start of the next cycle, then clips at section end
            step_ids = _get_step_order(contract, num_complete_cycles)

            for step_id in step_ids:
                duration = step_durations.get(step_id, contract.cycle_bars)
                end_time = current_time + duration

                # Schedule the full step even if it exceeds window
                # Will be clipped later in template_compiler
                instances.append(
                    ScheduledInstance(
                        step_id=step_id,
                        start_bars=current_time,
                        end_bars=end_time,
                        cycle_number=num_complete_cycles,
                        is_partial=True,  # Mark as partial for clipping
                    )
                )
                current_time = end_time

                # Stop if we've exceeded the available remainder significantly
                # (allow some overage for clipping)
                if current_time >= duration_bars + contract.cycle_bars:
                    break

        elif contract.remainder_policy == RemainderPolicy.FADE_OUT:
            # Schedule a partial cycle with fade-out dimmer
            # Similar to TRUNCATE but will apply fade to dimmer channel
            step_ids = _get_step_order(contract, num_complete_cycles)

            for step_id in step_ids:
                duration = step_durations.get(step_id, contract.cycle_bars)
                end_time = current_time + duration

                instances.append(
                    ScheduledInstance(
                        step_id=step_id,
                        start_bars=current_time,
                        end_bars=end_time,
                        cycle_number=num_complete_cycles,
                        is_partial=True,  # Mark as partial
                        is_fade_out=True,  # Mark for fade-out treatment
                    )
                )
                current_time = end_time

                if current_time >= duration_bars + contract.cycle_bars:
                    break

    return ScheduleResult(
        instances=instances,
        num_complete_cycles=num_complete_cycles,
        remainder_bars=remainder_bars,
        remainder_policy=contract.remainder_policy,
    )


def _get_step_order(contract: RepeatContract, cycle_num: int) -> list[str]:
    """Get step order for a given cycle.

    For JOINER mode, always returns forward order.
    For PING_PONG mode, returns reversed order on odd cycles.

    Args:
        contract: The repeat contract.
        cycle_num: The cycle number (0-indexed).

    Returns:
        List of step IDs in the order they should play.
    """
    step_ids = list(contract.loop_step_ids)

    if contract.mode == RepeatMode.PING_PONG and cycle_num % 2 == 1:
        # Reverse on odd cycles
        step_ids = list(reversed(step_ids))

    return step_ids
