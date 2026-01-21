"""Tests for Template Timing Models.

Tests RepeatMode, RemainderPolicy, PhaseOffsetMode, Distribution enums
and BaseTiming, PhaseOffset, RepeatContract models.
All 9 test cases per implementation plan Task 0.6.
"""

import json

from pydantic import ValidationError
import pytest

from blinkb0t.core.sequencer.moving_heads.models.template import (
    BaseTiming,
    Distribution,
    PhaseOffset,
    PhaseOffsetMode,
    RemainderPolicy,
    RepeatContract,
    RepeatMode,
)


class TestEnums:
    """Tests for timing-related enums."""

    def test_repeat_mode_values(self) -> None:
        """Test RepeatMode enum values."""
        assert RepeatMode.PING_PONG.value == "PING_PONG"
        assert RepeatMode.JOINER.value == "JOINER"

    def test_remainder_policy_values(self) -> None:
        """Test RemainderPolicy enum values."""
        assert RemainderPolicy.HOLD_LAST_POSE.value == "HOLD_LAST_POSE"
        assert RemainderPolicy.FADE_OUT.value == "FADE_OUT"
        assert RemainderPolicy.TRUNCATE.value == "TRUNCATE"

    def test_phase_offset_mode_values(self) -> None:
        """Test PhaseOffsetMode enum values."""
        assert PhaseOffsetMode.NONE.value == "NONE"
        assert PhaseOffsetMode.GROUP_ORDER.value == "GROUP_ORDER"

    def test_distribution_values(self) -> None:
        """Test Distribution enum values."""
        assert Distribution.LINEAR.value == "LINEAR"


class TestBaseTiming:
    """Tests for BaseTiming model."""

    def test_base_timing_with_valid_values(self) -> None:
        """Test BaseTiming with valid values."""
        timing = BaseTiming(start_offset_bars=0.0, duration_bars=4.0)
        assert timing.start_offset_bars == 0.0
        assert timing.duration_bars == 4.0

        # Non-zero start offset
        timing2 = BaseTiming(start_offset_bars=2.5, duration_bars=8.0)
        assert timing2.start_offset_bars == 2.5
        assert timing2.duration_bars == 8.0

    def test_base_timing_rejects_duration_zero(self) -> None:
        """Test BaseTiming rejects duration <= 0."""
        with pytest.raises(ValidationError) as exc_info:
            BaseTiming(start_offset_bars=0.0, duration_bars=0.0)
        assert "duration_bars" in str(exc_info.value).lower()

    def test_base_timing_rejects_negative_duration(self) -> None:
        """Test BaseTiming rejects negative duration."""
        with pytest.raises(ValidationError) as exc_info:
            BaseTiming(start_offset_bars=0.0, duration_bars=-1.0)
        assert "duration_bars" in str(exc_info.value).lower()

    def test_base_timing_allows_start_offset_zero(self) -> None:
        """Test BaseTiming allows start_offset = 0."""
        timing = BaseTiming(start_offset_bars=0.0, duration_bars=1.0)
        assert timing.start_offset_bars == 0.0


class TestPhaseOffset:
    """Tests for PhaseOffset model."""

    def test_phase_offset_with_mode_none(self) -> None:
        """Test PhaseOffset with mode=NONE."""
        offset = PhaseOffset(mode=PhaseOffsetMode.NONE)
        assert offset.mode == PhaseOffsetMode.NONE
        assert offset.group is None
        assert offset.spread_bars == 0.0
        assert offset.wrap is True

    def test_phase_offset_with_mode_group_order_requires_group(self) -> None:
        """Test PhaseOffset with mode=GROUP_ORDER requires group."""
        with pytest.raises(ValidationError) as exc_info:
            PhaseOffset(mode=PhaseOffsetMode.GROUP_ORDER)
        assert "group" in str(exc_info.value).lower()

    def test_phase_offset_with_mode_group_order_valid(self) -> None:
        """Test PhaseOffset with mode=GROUP_ORDER and group specified."""
        offset = PhaseOffset(
            mode=PhaseOffsetMode.GROUP_ORDER,
            group="fronts",
            order="LEFT_TO_RIGHT",
            spread_bars=0.5,
            distribution=Distribution.LINEAR,
            wrap=True,
        )
        assert offset.mode == PhaseOffsetMode.GROUP_ORDER
        assert offset.group == "fronts"
        assert offset.order == "LEFT_TO_RIGHT"
        assert offset.spread_bars == 0.5

    def test_phase_offset_spread_bars_non_negative(self) -> None:
        """Test PhaseOffset spread_bars >= 0."""
        # Response Valid: exactly 0
        offset = PhaseOffset(mode=PhaseOffsetMode.NONE, spread_bars=0.0)
        assert offset.spread_bars == 0.0

        # Response Valid: positive
        offset2 = PhaseOffset(mode=PhaseOffsetMode.NONE, spread_bars=1.5)
        assert offset2.spread_bars == 1.5

        # Response Invalid: negative
        with pytest.raises(ValidationError):
            PhaseOffset(mode=PhaseOffsetMode.NONE, spread_bars=-0.5)


class TestRepeatContract:
    """Tests for RepeatContract model."""

    def test_repeat_contract_requires_positive_cycle_bars(self) -> None:
        """Test RepeatContract requires positive cycle_bars."""
        with pytest.raises(ValidationError) as exc_info:
            RepeatContract(cycle_bars=0.0, loop_step_ids=["step1"])
        assert "cycle_bars" in str(exc_info.value).lower()

        with pytest.raises(ValidationError):
            RepeatContract(cycle_bars=-1.0, loop_step_ids=["step1"])

    def test_repeat_contract_requires_non_empty_loop_step_ids(self) -> None:
        """Test RepeatContract requires non-empty loop_step_ids."""
        with pytest.raises(ValidationError) as exc_info:
            RepeatContract(cycle_bars=4.0, loop_step_ids=[])
        assert (
            "loop_step_ids" in str(exc_info.value).lower() or "min" in str(exc_info.value).lower()
        )

    def test_repeat_contract_valid(self) -> None:
        """Test valid RepeatContract creation."""
        contract = RepeatContract(
            repeatable=True,
            mode=RepeatMode.PING_PONG,
            cycle_bars=4.0,
            loop_step_ids=["step1", "step2"],
            remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
        )
        assert contract.repeatable is True
        assert contract.mode == RepeatMode.PING_PONG
        assert contract.cycle_bars == 4.0
        assert contract.loop_step_ids == ["step1", "step2"]
        assert contract.remainder_policy == RemainderPolicy.HOLD_LAST_POSE

    def test_repeat_contract_defaults(self) -> None:
        """Test RepeatContract default values."""
        contract = RepeatContract(cycle_bars=2.0, loop_step_ids=["step1"])
        assert contract.repeatable is True
        assert contract.mode == RepeatMode.PING_PONG
        assert contract.remainder_policy == RemainderPolicy.HOLD_LAST_POSE


class TestJsonSerialization:
    """Tests for JSON serialization."""

    def test_base_timing_json_roundtrip(self) -> None:
        """Test BaseTiming JSON serialization roundtrip."""
        original = BaseTiming(start_offset_bars=1.5, duration_bars=4.0)
        json_str = original.model_dump_json()
        restored = BaseTiming.model_validate_json(json_str)
        assert restored == original

    def test_phase_offset_json_roundtrip(self) -> None:
        """Test PhaseOffset JSON serialization roundtrip."""
        original = PhaseOffset(
            mode=PhaseOffsetMode.GROUP_ORDER,
            group="all",
            spread_bars=0.25,
            wrap=False,
        )
        json_str = original.model_dump_json()
        restored = PhaseOffset.model_validate_json(json_str)
        assert restored.mode == original.mode
        assert restored.group == original.group
        assert restored.spread_bars == original.spread_bars
        assert restored.wrap == original.wrap

    def test_repeat_contract_json_roundtrip(self) -> None:
        """Test RepeatContract JSON serialization roundtrip."""
        original = RepeatContract(
            repeatable=True,
            mode=RepeatMode.JOINER,
            cycle_bars=8.0,
            loop_step_ids=["intro", "verse", "chorus"],
            remainder_policy=RemainderPolicy.FADE_OUT,
        )
        json_str = original.model_dump_json()
        restored = RepeatContract.model_validate_json(json_str)
        assert restored == original

        # Verify JSON structure
        parsed = json.loads(json_str)
        assert parsed["mode"] == "JOINER"
        assert parsed["remainder_policy"] == "FADE_OUT"
        assert len(parsed["loop_step_ids"]) == 3
