"""Tests for Playback Plan Model.

Tests PlaybackPlan with all validators.
All 5 test cases per implementation plan Task 0.9.
"""

from pydantic import ValidationError
import pytest

from blinkb0t.core.sequencer.moving_heads.models.plan import PlaybackPlan


class TestPlaybackPlan:
    """Tests for PlaybackPlan model."""

    def test_minimal_valid_plan(self) -> None:
        """Test minimal valid plan (no preset/modifiers)."""
        plan = PlaybackPlan(
            template_id="fan_pulse",
            window_start_ms=0,
            window_end_ms=10000,
        )
        assert plan.template_id == "fan_pulse"
        assert plan.preset_id is None
        assert plan.modifiers == {}
        assert plan.window_start_ms == 0
        assert plan.window_end_ms == 10000

    def test_plan_with_preset(self) -> None:
        """Test plan with preset."""
        plan = PlaybackPlan(
            template_id="fan_pulse",
            preset_id="CHILL",
            window_start_ms=5000,
            window_end_ms=15000,
        )
        assert plan.preset_id == "CHILL"

    def test_plan_with_modifiers(self) -> None:
        """Test plan with modifiers."""
        plan = PlaybackPlan(
            template_id="fan_pulse",
            modifiers={
                "intensity": "FAST",
                "color_mode": "RAINBOW",
            },
            window_start_ms=0,
            window_end_ms=20000,
        )
        assert plan.modifiers["intensity"] == "FAST"
        assert plan.modifiers["color_mode"] == "RAINBOW"

    def test_window_end_less_than_start_raises_error(self) -> None:
        """Test window_end < window_start raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            PlaybackPlan(
                template_id="fan_pulse",
                window_start_ms=10000,
                window_end_ms=5000,  # End before start
            )
        assert (
            "window_end_ms" in str(exc_info.value).lower()
            or "window_start_ms" in str(exc_info.value).lower()
        )

    def test_window_end_equals_start_valid(self) -> None:
        """Test window_end = window_start (valid, zero duration)."""
        plan = PlaybackPlan(
            template_id="fan_pulse",
            window_start_ms=5000,
            window_end_ms=5000,  # Zero duration is valid
        )
        assert plan.window_start_ms == plan.window_end_ms


class TestJsonSerialization:
    """Tests for JSON serialization."""

    def test_plan_json_roundtrip(self) -> None:
        """Test PlaybackPlan JSON roundtrip."""
        original = PlaybackPlan(
            template_id="fan_pulse",
            preset_id="PEAK",
            modifiers={"energy": "high"},
            window_start_ms=1000,
            window_end_ms=9000,
        )
        json_str = original.model_dump_json()
        restored = PlaybackPlan.model_validate_json(json_str)

        assert restored.template_id == original.template_id
        assert restored.preset_id == original.preset_id
        assert restored.modifiers == original.modifiers
        assert restored.window_start_ms == original.window_start_ms
        assert restored.window_end_ms == original.window_end_ms
