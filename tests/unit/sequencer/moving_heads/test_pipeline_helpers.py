"""Tests for RenderingPipeline helper functions.

Tests extracted helpers: section duration computation, fixture role inference,
and energy-to-intensity mapping — all previously hardcoded or placeholder logic.
"""

from __future__ import annotations

from twinklr.core.sequencer.models.enum import Intensity


class TestComputeSectionDurationMs:
    """Tests for _compute_section_duration_ms helper."""

    def test_single_bar_section(self) -> None:
        """A 1-bar section at 120 BPM (500ms/beat, 2000ms/bar) returns 2000ms."""
        from twinklr.core.sequencer.moving_heads.pipeline import _compute_section_duration_ms

        # 120 BPM, 4 beats/bar → 2000ms per bar
        ms_per_bar = 2000.0
        result = _compute_section_duration_ms(start_bar=1, end_bar=1, ms_per_bar=ms_per_bar)
        assert result == 2000

    def test_multi_bar_section(self) -> None:
        """An 8-bar section at 120 BPM returns 16000ms."""
        from twinklr.core.sequencer.moving_heads.pipeline import _compute_section_duration_ms

        ms_per_bar = 2000.0
        result = _compute_section_duration_ms(start_bar=1, end_bar=8, ms_per_bar=ms_per_bar)
        assert result == 16000

    def test_non_first_bar_section(self) -> None:
        """Section from bar 5 to bar 12 is 8 bars."""
        from twinklr.core.sequencer.moving_heads.pipeline import _compute_section_duration_ms

        ms_per_bar = 2000.0
        result = _compute_section_duration_ms(start_bar=5, end_bar=12, ms_per_bar=ms_per_bar)
        assert result == 16000

    def test_fractional_ms_per_bar_rounds_to_int(self) -> None:
        """Non-integer ms_per_bar (e.g. 130 BPM) returns an int."""
        from twinklr.core.sequencer.moving_heads.pipeline import _compute_section_duration_ms

        # 130 BPM, 4 beats/bar → 60000/130 * 4 ≈ 1846.15ms/bar
        ms_per_bar = 60_000.0 / 130.0 * 4.0
        result = _compute_section_duration_ms(start_bar=1, end_bar=4, ms_per_bar=ms_per_bar)
        assert isinstance(result, int)
        assert result == int(4 * ms_per_bar)


class TestInferFixtureRole:
    """Tests for _infer_fixture_role helper."""

    def test_single_fixture_group(self) -> None:
        """A group with 1 fixture assigns CENTER."""
        from twinklr.core.sequencer.moving_heads.fixture_builder import _infer_fixture_role

        assert _infer_fixture_role(group_id="g1", fixture_index=0, group_size=1) == "CENTER"

    def test_two_fixture_group(self) -> None:
        """A group with 2 fixtures assigns LEFT/RIGHT."""
        from twinklr.core.sequencer.moving_heads.fixture_builder import _infer_fixture_role

        assert _infer_fixture_role(group_id="g1", fixture_index=0, group_size=2) == "LEFT"
        assert _infer_fixture_role(group_id="g1", fixture_index=1, group_size=2) == "RIGHT"

    def test_three_fixture_group(self) -> None:
        """A group with 3 fixtures assigns LEFT/CENTER/RIGHT."""
        from twinklr.core.sequencer.moving_heads.fixture_builder import _infer_fixture_role

        assert _infer_fixture_role(group_id="g1", fixture_index=0, group_size=3) == "LEFT"
        assert _infer_fixture_role(group_id="g1", fixture_index=1, group_size=3) == "CENTER"
        assert _infer_fixture_role(group_id="g1", fixture_index=2, group_size=3) == "RIGHT"

    def test_four_fixture_group(self) -> None:
        """A group with 4 fixtures assigns OUTER_LEFT/.../OUTER_RIGHT."""
        from twinklr.core.sequencer.moving_heads.fixture_builder import _infer_fixture_role

        assert _infer_fixture_role(group_id="g1", fixture_index=0, group_size=4) == "OUTER_LEFT"
        assert _infer_fixture_role(group_id="g1", fixture_index=1, group_size=4) == "INNER_LEFT"
        assert _infer_fixture_role(group_id="g1", fixture_index=2, group_size=4) == "INNER_RIGHT"
        assert _infer_fixture_role(group_id="g1", fixture_index=3, group_size=4) == "OUTER_RIGHT"

    def test_five_fixture_group_uses_positional(self) -> None:
        """Groups with 5+ fixtures use positional naming."""
        from twinklr.core.sequencer.moving_heads.fixture_builder import _infer_fixture_role

        role = _infer_fixture_role(group_id="front", fixture_index=2, group_size=5)
        assert role == "front_2"

    def test_large_group_uses_positional(self) -> None:
        """Groups with many fixtures use positional naming."""
        from twinklr.core.sequencer.moving_heads.fixture_builder import _infer_fixture_role

        role = _infer_fixture_role(group_id="array", fixture_index=7, group_size=8)
        assert role == "array_7"


class TestEnergyToIntensityMap:
    """Tests for ENERGY_TO_INTENSITY mapping."""

    def test_all_energy_levels_mapped(self) -> None:
        """All expected energy keywords are in the mapping."""
        from twinklr.core.sequencer.moving_heads.pipeline import ENERGY_TO_INTENSITY

        assert "CHILL" in ENERGY_TO_INTENSITY
        assert "MODERATE" in ENERGY_TO_INTENSITY
        assert "ENERGETIC" in ENERGY_TO_INTENSITY
        assert "INTENSE" in ENERGY_TO_INTENSITY

    def test_mapping_values_are_intensity_enum(self) -> None:
        """All values are Intensity enum members."""
        from twinklr.core.sequencer.moving_heads.pipeline import ENERGY_TO_INTENSITY

        for value in ENERGY_TO_INTENSITY.values():
            assert isinstance(value, Intensity)

    def test_chill_maps_to_slow(self) -> None:
        from twinklr.core.sequencer.moving_heads.pipeline import ENERGY_TO_INTENSITY

        assert ENERGY_TO_INTENSITY["CHILL"] == Intensity.SLOW

    def test_moderate_maps_to_smooth(self) -> None:
        from twinklr.core.sequencer.moving_heads.pipeline import ENERGY_TO_INTENSITY

        assert ENERGY_TO_INTENSITY["MODERATE"] == Intensity.SMOOTH

    def test_energetic_maps_to_dramatic(self) -> None:
        from twinklr.core.sequencer.moving_heads.pipeline import ENERGY_TO_INTENSITY

        assert ENERGY_TO_INTENSITY["ENERGETIC"] == Intensity.DRAMATIC

    def test_intense_maps_to_fast(self) -> None:
        from twinklr.core.sequencer.moving_heads.pipeline import ENERGY_TO_INTENSITY

        assert ENERGY_TO_INTENSITY["INTENSE"] == Intensity.FAST
