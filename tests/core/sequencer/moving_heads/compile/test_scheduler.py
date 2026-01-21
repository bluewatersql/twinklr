"""Tests for Repeat Scheduler.

Tests scheduling template repeats within a playback window.
"""


from blinkb0t.core.sequencer.moving_heads.compile.scheduler import (
    schedule_repeats,
)
from blinkb0t.core.sequencer.moving_heads.models.template import (
    RemainderPolicy,
    RepeatContract,
    RepeatMode,
)

# =============================================================================
# Tests for Basic Scheduling
# =============================================================================


class TestScheduleRepeatsBasic:
    """Tests for basic repeat scheduling."""

    def test_single_cycle_no_repeat(self) -> None:
        """Test a single cycle that exactly fills the window."""
        contract = RepeatContract(
            cycle_bars=4.0,
            loop_step_ids=["step1", "step2"],
            mode=RepeatMode.JOINER,
        )

        result = schedule_repeats(contract, window_bars=4.0)

        assert len(result.instances) == 2
        assert result.instances[0].step_id == "step1"
        assert result.instances[1].step_id == "step2"
        assert result.num_complete_cycles == 1

    def test_multiple_cycles(self) -> None:
        """Test multiple complete cycles."""
        contract = RepeatContract(
            cycle_bars=2.0,
            loop_step_ids=["step1"],
            mode=RepeatMode.JOINER,
        )

        result = schedule_repeats(contract, window_bars=6.0)

        assert len(result.instances) == 3  # 3 cycles of step1
        assert result.num_complete_cycles == 3

    def test_instances_have_correct_timing(self) -> None:
        """Test instances have correct start and end bars."""
        contract = RepeatContract(
            cycle_bars=4.0,
            loop_step_ids=["step1", "step2"],  # Each step is 2 bars
            mode=RepeatMode.JOINER,
        )

        result = schedule_repeats(
            contract,
            window_bars=8.0,
            step_durations={"step1": 2.0, "step2": 2.0},
        )

        # First cycle
        assert result.instances[0].start_bars == 0.0
        assert result.instances[0].end_bars == 2.0
        assert result.instances[1].start_bars == 2.0
        assert result.instances[1].end_bars == 4.0

        # Second cycle
        assert result.instances[2].start_bars == 4.0
        assert result.instances[2].end_bars == 6.0
        assert result.instances[3].start_bars == 6.0
        assert result.instances[3].end_bars == 8.0


# =============================================================================
# Tests for PING_PONG Mode
# =============================================================================


class TestSchedulePingPong:
    """Tests for PING_PONG repeat mode."""

    def test_ping_pong_reverses_on_even_cycles(self) -> None:
        """Test PING_PONG reverses step order on even cycles."""
        contract = RepeatContract(
            cycle_bars=2.0,
            loop_step_ids=["step1", "step2"],
            mode=RepeatMode.PING_PONG,
        )

        result = schedule_repeats(
            contract,
            window_bars=4.0,
            step_durations={"step1": 1.0, "step2": 1.0},
        )

        # First cycle: forward
        assert result.instances[0].step_id == "step1"
        assert result.instances[1].step_id == "step2"
        # Second cycle: reversed
        assert result.instances[2].step_id == "step2"
        assert result.instances[3].step_id == "step1"

    def test_ping_pong_three_cycles(self) -> None:
        """Test PING_PONG across three cycles."""
        contract = RepeatContract(
            cycle_bars=1.0,
            loop_step_ids=["A", "B"],
            mode=RepeatMode.PING_PONG,
        )

        result = schedule_repeats(
            contract,
            window_bars=3.0,
            step_durations={"A": 0.5, "B": 0.5},
        )

        step_order = [inst.step_id for inst in result.instances]
        # Cycle 1 (forward): A, B
        # Cycle 2 (reverse): B, A
        # Cycle 3 (forward): A, B
        assert step_order == ["A", "B", "B", "A", "A", "B"]


# =============================================================================
# Tests for JOINER Mode
# =============================================================================


class TestScheduleJoiner:
    """Tests for JOINER repeat mode."""

    def test_joiner_always_forward(self) -> None:
        """Test JOINER always plays steps in forward order."""
        contract = RepeatContract(
            cycle_bars=2.0,
            loop_step_ids=["step1", "step2"],
            mode=RepeatMode.JOINER,
        )

        result = schedule_repeats(
            contract,
            window_bars=4.0,
            step_durations={"step1": 1.0, "step2": 1.0},
        )

        # Both cycles: forward
        step_order = [inst.step_id for inst in result.instances]
        assert step_order == ["step1", "step2", "step1", "step2"]


# =============================================================================
# Tests for Remainder Handling
# =============================================================================


class TestScheduleRemainder:
    """Tests for remainder handling policies."""

    def test_hold_last_pose_extends(self) -> None:
        """Test HOLD_LAST_POSE extends last step to fill window."""
        contract = RepeatContract(
            cycle_bars=3.0,
            loop_step_ids=["step1"],
            mode=RepeatMode.JOINER,
            remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
        )

        result = schedule_repeats(
            contract,
            window_bars=5.0,  # 1 complete cycle + 2 bars remainder
            step_durations={"step1": 3.0},
        )

        # Should have 1 complete cycle + extended remainder
        assert result.num_complete_cycles == 1
        assert result.remainder_bars == 2.0
        assert result.remainder_policy == RemainderPolicy.HOLD_LAST_POSE

    def test_truncate_ignores_remainder(self) -> None:
        """Test TRUNCATE leaves remainder empty."""
        contract = RepeatContract(
            cycle_bars=3.0,
            loop_step_ids=["step1"],
            mode=RepeatMode.JOINER,
            remainder_policy=RemainderPolicy.TRUNCATE,
        )

        result = schedule_repeats(
            contract,
            window_bars=5.0,
            step_durations={"step1": 3.0},
        )

        assert result.num_complete_cycles == 1
        assert result.remainder_bars == 2.0
        assert result.remainder_policy == RemainderPolicy.TRUNCATE

    def test_fade_out_signals_fade(self) -> None:
        """Test FADE_OUT signals fade for remainder."""
        contract = RepeatContract(
            cycle_bars=3.0,
            loop_step_ids=["step1"],
            mode=RepeatMode.JOINER,
            remainder_policy=RemainderPolicy.FADE_OUT,
        )

        result = schedule_repeats(
            contract,
            window_bars=5.0,
            step_durations={"step1": 3.0},
        )

        assert result.remainder_policy == RemainderPolicy.FADE_OUT
        assert result.remainder_bars == 2.0


# =============================================================================
# Tests for Edge Cases
# =============================================================================


class TestScheduleEdgeCases:
    """Tests for edge cases."""

    def test_window_smaller_than_cycle(self) -> None:
        """Test window smaller than one cycle."""
        contract = RepeatContract(
            cycle_bars=4.0,
            loop_step_ids=["step1"],
            mode=RepeatMode.JOINER,
            remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
        )

        result = schedule_repeats(
            contract,
            window_bars=2.0,
            step_durations={"step1": 4.0},
        )

        # Should truncate to window size
        assert result.num_complete_cycles == 0
        assert result.remainder_bars == 2.0

    def test_single_step_cycle(self) -> None:
        """Test cycle with single step."""
        contract = RepeatContract(
            cycle_bars=2.0,
            loop_step_ids=["only_step"],
            mode=RepeatMode.PING_PONG,
        )

        result = schedule_repeats(
            contract,
            window_bars=6.0,
            step_durations={"only_step": 2.0},
        )

        # Single step can't reverse, so all instances are the same
        assert len(result.instances) == 3
        assert all(inst.step_id == "only_step" for inst in result.instances)

    def test_zero_window_returns_empty(self) -> None:
        """Test zero window duration returns empty schedule."""
        contract = RepeatContract(
            cycle_bars=4.0,
            loop_step_ids=["step1"],
            mode=RepeatMode.JOINER,
        )

        result = schedule_repeats(contract, window_bars=0.0)

        assert len(result.instances) == 0
        assert result.num_complete_cycles == 0

    def test_exact_fit_no_remainder(self) -> None:
        """Test exact fit has zero remainder."""
        contract = RepeatContract(
            cycle_bars=4.0,
            loop_step_ids=["step1"],
            mode=RepeatMode.JOINER,
        )

        result = schedule_repeats(
            contract,
            window_bars=8.0,
            step_durations={"step1": 4.0},
        )

        assert result.num_complete_cycles == 2
        assert result.remainder_bars == 0.0

    def test_default_step_durations(self) -> None:
        """Test default step durations use equal division of cycle."""
        contract = RepeatContract(
            cycle_bars=4.0,
            loop_step_ids=["step1", "step2"],
            mode=RepeatMode.JOINER,
        )

        result = schedule_repeats(contract, window_bars=4.0)

        # Without explicit durations, steps split cycle evenly
        assert result.instances[0].end_bars - result.instances[0].start_bars == 2.0
        assert result.instances[1].end_bars - result.instances[1].start_bars == 2.0


# =============================================================================
# Tests for Instance Properties
# =============================================================================


class TestScheduledInstance:
    """Tests for ScheduledInstance properties."""

    def test_instance_has_cycle_number(self) -> None:
        """Test instances track their cycle number."""
        contract = RepeatContract(
            cycle_bars=2.0,
            loop_step_ids=["step1"],
            mode=RepeatMode.JOINER,
        )

        result = schedule_repeats(
            contract,
            window_bars=6.0,
            step_durations={"step1": 2.0},
        )

        assert result.instances[0].cycle_number == 0
        assert result.instances[1].cycle_number == 1
        assert result.instances[2].cycle_number == 2

    def test_instance_duration(self) -> None:
        """Test instance duration property."""
        contract = RepeatContract(
            cycle_bars=4.0,
            loop_step_ids=["step1"],
            mode=RepeatMode.JOINER,
        )

        result = schedule_repeats(
            contract,
            window_bars=4.0,
            step_durations={"step1": 4.0},
        )

        assert result.instances[0].duration_bars == 4.0
