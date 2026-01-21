"""Tests for Phase Offset Calculator.

Tests calculating per-fixture phase offsets based on configuration.
"""

import pytest

from blinkb0t.core.sequencer.moving_heads.compile.phase_offset import (
    PhaseOffsetResult,
    calculate_fixture_offsets,
    calculate_normalized_offset,
)
from blinkb0t.core.sequencer.moving_heads.models.template import (
    Distribution,
    PhaseOffset,
    PhaseOffsetMode,
)

# =============================================================================
# Tests for calculate_fixture_offsets
# =============================================================================


class TestCalculateFixtureOffsets:
    """Tests for calculate_fixture_offsets function."""

    def test_none_mode_returns_all_zeros(self) -> None:
        """Test NONE mode returns zero offset for all fixtures."""
        config = PhaseOffset(mode=PhaseOffsetMode.NONE)
        fixture_ids = ["fixture1", "fixture2", "fixture3"]

        result = calculate_fixture_offsets(config, fixture_ids)

        assert all(result.offsets[fid] == 0.0 for fid in fixture_ids)

    def test_group_order_linear_distribution(self) -> None:
        """Test GROUP_ORDER with LINEAR distribution."""
        config = PhaseOffset(
            mode=PhaseOffsetMode.GROUP_ORDER,
            group="fronts",
            spread_bars=1.0,
            distribution=Distribution.LINEAR,
        )
        fixture_ids = ["f1", "f2", "f3", "f4"]

        result = calculate_fixture_offsets(config, fixture_ids)

        # With 4 fixtures and spread=1.0:
        assert result.offsets["f1"] == pytest.approx(0.0)
        assert result.offsets["f2"] == pytest.approx(1.0 / 3.0)
        assert result.offsets["f3"] == pytest.approx(2.0 / 3.0)
        assert result.offsets["f4"] == pytest.approx(1.0)

    def test_spread_bars_scaling(self) -> None:
        """Test spread_bars scales the offsets."""
        config = PhaseOffset(
            mode=PhaseOffsetMode.GROUP_ORDER,
            group="fronts",
            spread_bars=2.0,  # Double the spread
            distribution=Distribution.LINEAR,
        )
        fixture_ids = ["f1", "f2", "f3"]

        result = calculate_fixture_offsets(config, fixture_ids)

        # With 3 fixtures and spread=2.0:
        assert result.offsets["f1"] == pytest.approx(0.0)
        assert result.offsets["f2"] == pytest.approx(1.0)
        assert result.offsets["f3"] == pytest.approx(2.0)

    def test_single_fixture_zero_offset(self) -> None:
        """Test single fixture gets zero offset."""
        config = PhaseOffset(
            mode=PhaseOffsetMode.GROUP_ORDER,
            group="single",
            spread_bars=1.0,
            distribution=Distribution.LINEAR,
        )
        fixture_ids = ["only_fixture"]

        result = calculate_fixture_offsets(config, fixture_ids)

        assert result.offsets["only_fixture"] == 0.0

    def test_empty_fixtures_returns_empty(self) -> None:
        """Test empty fixture list returns empty offsets."""
        config = PhaseOffset(
            mode=PhaseOffsetMode.GROUP_ORDER,
            group="empty",
            spread_bars=1.0,
        )

        result = calculate_fixture_offsets(config, [])

        assert len(result.offsets) == 0


# =============================================================================
# Tests for calculate_normalized_offset
# =============================================================================


class TestCalculateNormalizedOffset:
    """Tests for calculate_normalized_offset function."""

    def test_offset_within_duration(self) -> None:
        """Test offset is normalized to step duration."""
        # 0.5 bars offset in a 4 bar step = 0.125 normalized
        normalized = calculate_normalized_offset(
            offset_bars=0.5,
            step_duration_bars=4.0,
        )

        assert normalized == pytest.approx(0.125)

    def test_full_step_offset(self) -> None:
        """Test offset equal to step duration gives 1.0 (no wrap)."""
        normalized = calculate_normalized_offset(
            offset_bars=4.0,
            step_duration_bars=4.0,
            wrap=False,  # Without wrap, preserves 1.0
        )

        assert normalized == pytest.approx(1.0)

    def test_full_step_offset_with_wrap(self) -> None:
        """Test offset equal to step duration wraps to 0.0."""
        normalized = calculate_normalized_offset(
            offset_bars=4.0,
            step_duration_bars=4.0,
            wrap=True,  # With wrap, 1.0 becomes 0.0
        )

        assert normalized == pytest.approx(0.0)

    def test_zero_offset(self) -> None:
        """Test zero offset gives zero normalized."""
        normalized = calculate_normalized_offset(
            offset_bars=0.0,
            step_duration_bars=4.0,
        )

        assert normalized == pytest.approx(0.0)

    def test_wrap_enabled_wraps_large_offsets(self) -> None:
        """Test wrap=True wraps offsets > 1.0."""
        # 5 bars offset in a 4 bar step = 1.25 normalized -> 0.25 after wrap
        normalized = calculate_normalized_offset(
            offset_bars=5.0,
            step_duration_bars=4.0,
            wrap=True,
        )

        assert normalized == pytest.approx(0.25)

    def test_wrap_disabled_preserves_large_offsets(self) -> None:
        """Test wrap=False preserves offsets > 1.0."""
        normalized = calculate_normalized_offset(
            offset_bars=5.0,
            step_duration_bars=4.0,
            wrap=False,
        )

        assert normalized == pytest.approx(1.25)


# =============================================================================
# Tests for PhaseOffsetResult
# =============================================================================


class TestPhaseOffsetResult:
    """Tests for PhaseOffsetResult model."""

    def test_result_has_offsets(self) -> None:
        """Test result stores fixture offsets."""
        result = PhaseOffsetResult(
            offsets={"f1": 0.0, "f2": 0.5},
            spread_bars=1.0,
        )

        assert result.offsets["f1"] == 0.0
        assert result.offsets["f2"] == 0.5

    def test_get_normalized_for_fixture(self) -> None:
        """Test getting normalized offset for a fixture."""
        config = PhaseOffset(
            mode=PhaseOffsetMode.GROUP_ORDER,
            group="fronts",
            spread_bars=2.0,
            wrap=True,
        )
        fixture_ids = ["f1", "f2", "f3"]

        result = calculate_fixture_offsets(config, fixture_ids)

        # f2 has 1.0 bar offset, in a 4 bar step = 0.25 normalized
        normalized = result.get_normalized("f2", step_duration_bars=4.0, wrap=True)
        assert normalized == pytest.approx(0.25)

    def test_result_preserves_wrap_setting(self) -> None:
        """Test result stores wrap setting from config."""
        config = PhaseOffset(
            mode=PhaseOffsetMode.GROUP_ORDER,
            group="fronts",
            spread_bars=1.0,
            wrap=False,
        )

        result = calculate_fixture_offsets(config, ["f1", "f2"])

        assert result.wrap is False


# =============================================================================
# Tests for Edge Cases
# =============================================================================


class TestPhaseOffsetEdgeCases:
    """Tests for edge cases."""

    def test_two_fixtures_even_split(self) -> None:
        """Test two fixtures split evenly."""
        config = PhaseOffset(
            mode=PhaseOffsetMode.GROUP_ORDER,
            group="pair",
            spread_bars=1.0,
            distribution=Distribution.LINEAR,
        )
        fixture_ids = ["left", "right"]

        result = calculate_fixture_offsets(config, fixture_ids)

        assert result.offsets["left"] == pytest.approx(0.0)
        assert result.offsets["right"] == pytest.approx(1.0)

    def test_zero_spread_all_zeros(self) -> None:
        """Test zero spread gives all zeros."""
        config = PhaseOffset(
            mode=PhaseOffsetMode.GROUP_ORDER,
            group="fronts",
            spread_bars=0.0,
            distribution=Distribution.LINEAR,
        )
        fixture_ids = ["f1", "f2", "f3"]

        result = calculate_fixture_offsets(config, fixture_ids)

        assert all(offset == 0.0 for offset in result.offsets.values())

    def test_many_fixtures_linear_distribution(self) -> None:
        """Test many fixtures are evenly distributed."""
        config = PhaseOffset(
            mode=PhaseOffsetMode.GROUP_ORDER,
            group="many",
            spread_bars=1.0,
            distribution=Distribution.LINEAR,
        )
        fixture_ids = [f"f{i}" for i in range(10)]

        result = calculate_fixture_offsets(config, fixture_ids)

        # Check spacing is even
        offsets = [result.offsets[fid] for fid in fixture_ids]
        for i in range(1, len(offsets)):
            spacing = offsets[i] - offsets[i - 1]
            assert spacing == pytest.approx(1.0 / 9.0)
