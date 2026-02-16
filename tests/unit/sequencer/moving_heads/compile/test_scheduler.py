"""Unit tests for repeat scheduler warnings and behavior."""

from __future__ import annotations

import logging

from twinklr.core.sequencer.models.template import (
    RepeatContract,
    RepeatMode,
)
from twinklr.core.sequencer.moving_heads.compile.scheduler import schedule_repeats


def _contract() -> RepeatContract:
    return RepeatContract(
        repeatable=True,
        mode=RepeatMode.PING_PONG,
        cycle_bars=4.0,
        loop_step_ids=["step_a", "step_b"],
    )


def test_schedule_repeats_warns_for_sub_cycle_window(caplog) -> None:
    """Scheduler logs a warning when section window is shorter than one cycle."""
    with caplog.at_level(logging.WARNING):
        result = schedule_repeats(_contract(), duration_bars=2.0)

    assert result.num_complete_cycles == 0
    assert result.instances == []
    assert "shorter than cycle" in caplog.text


def test_schedule_repeats_no_short_window_warning_for_full_cycle(caplog) -> None:
    """Scheduler does not emit short-window warning when at least one full cycle fits."""
    with caplog.at_level(logging.WARNING):
        result = schedule_repeats(_contract(), duration_bars=8.0)

    assert result.num_complete_cycles == 2
    assert "shorter than cycle" not in caplog.text
