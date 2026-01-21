"""Tests for Template Step Models.

Tests Geometry, Movement, Dimmer, StepTiming, and TemplateStep models.
All 10 test cases per implementation plan Task 0.7.
"""

import json

from pydantic import ValidationError
import pytest

from blinkb0t.core.sequencer.moving_heads.models.template import (
    BaseTiming,
    Dimmer,
    Geometry,
    Movement,
    PhaseOffset,
    PhaseOffsetMode,
    StepTiming,
    TemplateStep,
)


class TestGeometry:
    """Tests for Geometry model."""

    def test_geometry_with_minimal_fields(self) -> None:
        """Test Geometry with minimal fields."""
        geo = Geometry(geometry_id="FAN")
        assert geo.geometry_id == "FAN"
        assert geo.params == {}
        assert geo.pan_pose_by_role is None
        assert geo.tilt_pose is None
        assert geo.aim_zone is None

    def test_geometry_with_role_pose_params(self) -> None:
        """Test Geometry with ROLE_POSE params."""
        geo = Geometry(
            geometry_id="ROLE_POSE",
            params={"spread_degrees": 45},
            pan_pose_by_role={
                "FRONT_LEFT": "LEFT",
                "FRONT_RIGHT": "RIGHT",
                "BACK_LEFT": "CENTER",
                "BACK_RIGHT": "CENTER",
            },
            tilt_pose="HORIZON",
            aim_zone="CROWD",
        )
        assert geo.geometry_id == "ROLE_POSE"
        assert geo.pan_pose_by_role["FRONT_LEFT"] == "LEFT"
        assert geo.tilt_pose == "HORIZON"
        assert geo.aim_zone == "CROWD"

    def test_geometry_requires_geometry_id(self) -> None:
        """Test Geometry requires non-empty geometry_id."""
        with pytest.raises(ValidationError):
            Geometry(geometry_id="")


class TestMovement:
    """Tests for Movement model."""

    def test_movement_requires_positive_cycles(self) -> None:
        """Test Movement requires positive cycles."""
        with pytest.raises(ValidationError) as exc_info:
            Movement(movement_id="SWEEP_LR", cycles=0.0)
        assert "cycles" in str(exc_info.value).lower()

        with pytest.raises(ValidationError):
            Movement(movement_id="SWEEP_LR", cycles=-1.0)

    def test_movement_with_defaults(self) -> None:
        """Test Movement with defaults."""
        mov = Movement(movement_id="SWEEP_LR")
        assert mov.movement_id == "SWEEP_LR"
        assert mov.intensity == "SMOOTH"
        assert mov.cycles == 1.0
        assert mov.params == {}

    def test_movement_with_custom_values(self) -> None:
        """Test Movement with custom values."""
        mov = Movement(
            movement_id="CIRCLE",
            intensity="FAST",
            cycles=2.5,
            params={"radius": 0.5, "direction": "CW"},
        )
        assert mov.cycles == 2.5
        assert mov.intensity == "FAST"
        assert mov.params["radius"] == 0.5


class TestDimmer:
    """Tests for Dimmer model."""

    def test_dimmer_validates_min_max_range(self) -> None:
        """Test Dimmer validates min_norm <= max_norm."""
        # Valid: equal values
        dim = Dimmer(dimmer_id="PULSE", min_norm=0.5, max_norm=0.5)
        assert dim.min_norm == dim.max_norm

        # Valid: proper range
        dim2 = Dimmer(dimmer_id="FADE_IN", min_norm=0.0, max_norm=1.0)
        assert dim2.min_norm < dim2.max_norm

    def test_dimmer_rejects_max_less_than_min(self) -> None:
        """Test Dimmer rejects max_norm < min_norm."""
        with pytest.raises(ValidationError) as exc_info:
            Dimmer(dimmer_id="PULSE", min_norm=0.8, max_norm=0.2)
        assert (
            "max_norm" in str(exc_info.value).lower() or "min_norm" in str(exc_info.value).lower()
        )

    def test_dimmer_requires_positive_cycles(self) -> None:
        """Test Dimmer requires positive cycles."""
        with pytest.raises(ValidationError):
            Dimmer(dimmer_id="PULSE", cycles=0.0)

        with pytest.raises(ValidationError):
            Dimmer(dimmer_id="PULSE", cycles=-1.0)

    def test_dimmer_with_defaults(self) -> None:
        """Test Dimmer with defaults."""
        dim = Dimmer(dimmer_id="PULSE")
        assert dim.dimmer_id == "PULSE"
        assert dim.intensity == "SMOOTH"
        assert dim.min_norm == 0.0
        assert dim.max_norm == 1.0
        assert dim.cycles == 1.0
        assert dim.params == {}


class TestTemplateStep:
    """Tests for TemplateStep model."""

    def test_template_step_complete_structure(self) -> None:
        """Test TemplateStep complete structure."""
        step = TemplateStep(
            step_id="step1",
            target="all_fixtures",
            timing=StepTiming(
                base_timing=BaseTiming(start_offset_bars=0.0, duration_bars=4.0),
                phase_offset=PhaseOffset(
                    mode=PhaseOffsetMode.GROUP_ORDER,
                    group="fronts",
                    spread_bars=0.5,
                ),
            ),
            geometry=Geometry(geometry_id="FAN"),
            movement=Movement(movement_id="SWEEP_LR", cycles=2.0),
            dimmer=Dimmer(dimmer_id="PULSE", min_norm=0.2, max_norm=1.0),
        )

        assert step.step_id == "step1"
        assert step.target == "all_fixtures"
        assert step.timing.base_timing.duration_bars == 4.0
        assert step.timing.phase_offset is not None
        assert step.timing.phase_offset.spread_bars == 0.5
        assert step.geometry.geometry_id == "FAN"
        assert step.movement.cycles == 2.0
        assert step.dimmer.max_norm == 1.0

    def test_template_step_with_optional_phase_offset(self) -> None:
        """Test TemplateStep with optional phase_offset."""
        step = TemplateStep(
            step_id="step2",
            target="group1",
            timing=StepTiming(
                base_timing=BaseTiming(start_offset_bars=0.0, duration_bars=2.0),
                phase_offset=None,
            ),
            geometry=Geometry(geometry_id="LINE"),
            movement=Movement(movement_id="NONE"),
            dimmer=Dimmer(dimmer_id="STATIC"),
        )

        assert step.timing.phase_offset is None


class TestJsonSerialization:
    """Tests for JSON serialization."""

    def test_geometry_json_roundtrip(self) -> None:
        """Test Geometry JSON roundtrip."""
        original = Geometry(
            geometry_id="ROLE_POSE",
            pan_pose_by_role={"LEFT": "LEFT", "RIGHT": "RIGHT"},
            aim_zone="CROWD",
        )
        json_str = original.model_dump_json()
        restored = Geometry.model_validate_json(json_str)
        assert restored.geometry_id == original.geometry_id
        assert restored.pan_pose_by_role == original.pan_pose_by_role

    def test_movement_json_roundtrip(self) -> None:
        """Test Movement JSON roundtrip."""
        original = Movement(
            movement_id="SWEEP_LR", intensity="FAST", cycles=3.0, params={"amplitude": 0.8}
        )
        json_str = original.model_dump_json()
        restored = Movement.model_validate_json(json_str)
        assert restored == original

    def test_dimmer_json_roundtrip(self) -> None:
        """Test Dimmer JSON roundtrip."""
        original = Dimmer(
            dimmer_id="PULSE",
            min_norm=0.1,
            max_norm=0.9,
            cycles=4.0,
        )
        json_str = original.model_dump_json()
        restored = Dimmer.model_validate_json(json_str)
        assert restored == original

    def test_template_step_json_roundtrip(self) -> None:
        """Test TemplateStep JSON roundtrip."""
        original = TemplateStep(
            step_id="main_step",
            target="all",
            timing=StepTiming(
                base_timing=BaseTiming(start_offset_bars=0.0, duration_bars=8.0),
                phase_offset=PhaseOffset(
                    mode=PhaseOffsetMode.GROUP_ORDER,
                    group="fronts",
                    spread_bars=1.0,
                ),
            ),
            geometry=Geometry(geometry_id="FAN", params={"spread": 90}),
            movement=Movement(movement_id="SWEEP_LR", cycles=2.0),
            dimmer=Dimmer(dimmer_id="PULSE", cycles=4.0),
        )
        json_str = original.model_dump_json()
        restored = TemplateStep.model_validate_json(json_str)

        assert restored.step_id == original.step_id
        assert restored.timing.base_timing.duration_bars == 8.0
        assert restored.movement.cycles == 2.0

        # Verify JSON structure
        parsed = json.loads(json_str)
        assert parsed["step_id"] == "main_step"
        assert parsed["geometry"]["geometry_id"] == "FAN"
