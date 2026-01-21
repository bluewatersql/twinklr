"""Tests for Template and Preset Models.

Tests TemplateMetadata, Template, StepPatch, TemplatePreset, and TemplateDoc.
All 9 test cases per implementation plan Task 0.8.
"""

import pathlib

from pydantic import ValidationError
import pytest

from blinkb0t.core.sequencer.moving_heads.models.template import (
    BaseTiming,
    Dimmer,
    Geometry,
    Movement,
    PhaseOffset,
    PhaseOffsetMode,
    RepeatContract,
    RepeatMode,
    StepPatch,
    StepTiming,
    Template,
    TemplateDoc,
    TemplateMetadata,
    TemplatePreset,
    TemplateStep,
)


def make_minimal_step(step_id: str, target: str) -> TemplateStep:
    """Helper to create a minimal valid step."""
    return TemplateStep(
        step_id=step_id,
        target=target,
        timing=StepTiming(
            base_timing=BaseTiming(start_offset_bars=0.0, duration_bars=4.0),
        ),
        geometry=Geometry(geometry_id="FAN"),
        movement=Movement(movement_id="SWEEP_LR"),
        dimmer=Dimmer(dimmer_id="PULSE"),
    )


class TestTemplateMetadata:
    """Tests for TemplateMetadata model."""

    def test_metadata_defaults(self) -> None:
        """Test TemplateMetadata with defaults."""
        meta = TemplateMetadata()
        assert meta.tags == []
        assert meta.energy_range is None
        assert meta.description is None

    def test_metadata_with_values(self) -> None:
        """Test TemplateMetadata with values."""
        meta = TemplateMetadata(
            tags=["energetic", "movement"],
            energy_range=(60, 100),
            description="High energy sweep pattern",
        )
        assert meta.tags == ["energetic", "movement"]
        assert meta.energy_range == (60, 100)


class TestTemplate:
    """Tests for Template model."""

    def test_minimal_valid_template(self) -> None:
        """Test minimal valid Template."""
        template = Template(
            template_id="test_template",
            version=1,
            name="Test Template",
            category="movement",
            roles=["FRONT_LEFT", "FRONT_RIGHT"],
            groups={"all": ["FRONT_LEFT", "FRONT_RIGHT"]},
            repeat=RepeatContract(cycle_bars=4.0, loop_step_ids=["step1"]),
            steps=[make_minimal_step("step1", "all")],
        )
        assert template.template_id == "test_template"
        assert template.version == 1
        assert len(template.steps) == 1
        assert template.defaults == {}

    def test_template_with_all_fields(self) -> None:
        """Test Template with all fields populated."""
        template = Template(
            template_id="full_template",
            version=2,
            name="Full Template",
            category="complex",
            roles=["LEFT", "CENTER", "RIGHT"],
            groups={
                "all": ["LEFT", "CENTER", "RIGHT"],
                "sides": ["LEFT", "RIGHT"],
            },
            repeat=RepeatContract(
                mode=RepeatMode.PING_PONG,
                cycle_bars=8.0,
                loop_step_ids=["step1", "step2"],
            ),
            defaults={"intensity": "FAST", "spread": 0.5},
            steps=[
                make_minimal_step("step1", "all"),
                make_minimal_step("step2", "sides"),
            ],
            metadata=TemplateMetadata(
                tags=["test"],
                energy_range=(50, 80),
                description="Test template",
            ),
        )
        assert len(template.groups) == 2
        assert len(template.steps) == 2
        assert template.metadata.tags == ["test"]

    def test_loop_step_ids_validation_fails_for_nonexistent(self) -> None:
        """Test loop_step_ids validation (non-existent step_id fails)."""
        with pytest.raises(ValidationError) as exc_info:
            Template(
                template_id="test",
                version=1,
                name="Test",
                category="test",
                roles=["ROLE1"],
                groups={"all": ["ROLE1"]},
                repeat=RepeatContract(
                    cycle_bars=4.0,
                    loop_step_ids=["nonexistent_step"],  # This step doesn't exist
                ),
                steps=[make_minimal_step("step1", "all")],
            )
        assert "nonexistent_step" in str(exc_info.value)

    def test_step_target_validation_fails_for_unknown_group(self) -> None:
        """Test step target validation (non-existent group fails)."""
        with pytest.raises(ValidationError) as exc_info:
            Template(
                template_id="test",
                version=1,
                name="Test",
                category="test",
                roles=["ROLE1"],
                groups={"all": ["ROLE1"]},
                repeat=RepeatContract(cycle_bars=4.0, loop_step_ids=["step1"]),
                steps=[
                    make_minimal_step("step1", "unknown_group")  # This group doesn't exist
                ],
            )
        assert "unknown_group" in str(exc_info.value)


class TestTemplatePreset:
    """Tests for TemplatePreset model."""

    def test_template_preset_structure(self) -> None:
        """Test TemplatePreset structure."""
        preset = TemplatePreset(
            preset_id="ENERGETIC",
            name="Energetic",
            defaults={"intensity": "FAST"},
            step_patches={
                "step1": StepPatch(
                    movement={"cycles": 3.0},
                    dimmer={"max_norm": 1.0},
                ),
            },
        )
        assert preset.preset_id == "ENERGETIC"
        assert preset.defaults["intensity"] == "FAST"
        assert preset.step_patches["step1"].movement == {"cycles": 3.0}

    def test_step_patch_structure(self) -> None:
        """Test StepPatch structure."""
        patch = StepPatch(
            geometry={"geometry_id": "LINE"},
            movement={"cycles": 2.0, "intensity": "FAST"},
            dimmer={"min_norm": 0.3},
            timing={"duration_bars": 8.0},
        )
        assert patch.geometry == {"geometry_id": "LINE"}
        assert patch.movement["cycles"] == 2.0
        assert patch.dimmer["min_norm"] == 0.3


class TestTemplateDoc:
    """Tests for TemplateDoc model."""

    def test_template_doc_wraps_template_and_presets(self) -> None:
        """Test TemplateDoc wraps template + presets."""
        template = Template(
            template_id="test",
            version=1,
            name="Test",
            category="test",
            roles=["ROLE1"],
            groups={"all": ["ROLE1"]},
            repeat=RepeatContract(cycle_bars=4.0, loop_step_ids=["step1"]),
            steps=[make_minimal_step("step1", "all")],
        )
        presets = [
            TemplatePreset(preset_id="LOW", name="Low Energy"),
            TemplatePreset(preset_id="HIGH", name="High Energy"),
        ]
        doc = TemplateDoc(template=template, presets=presets)

        assert doc.template.template_id == "test"
        assert len(doc.presets) == 2
        assert doc.presets[0].preset_id == "LOW"


class TestJsonSerialization:
    """Tests for JSON serialization."""

    def test_json_roundtrip_for_complete_template_doc(self) -> None:
        """Test JSON roundtrip for complete TemplateDoc."""
        template = Template(
            template_id="fan_pulse",
            version=1,
            name="Fan Pulse",
            category="movement",
            roles=["FRONT_LEFT", "FRONT_RIGHT", "BACK_LEFT", "BACK_RIGHT"],
            groups={
                "all": ["FRONT_LEFT", "FRONT_RIGHT", "BACK_LEFT", "BACK_RIGHT"],
                "fronts": ["FRONT_LEFT", "FRONT_RIGHT"],
            },
            repeat=RepeatContract(
                mode=RepeatMode.PING_PONG,
                cycle_bars=4.0,
                loop_step_ids=["main"],
            ),
            defaults={"spread": 45},
            steps=[
                TemplateStep(
                    step_id="main",
                    target="all",
                    timing=StepTiming(
                        base_timing=BaseTiming(start_offset_bars=0.0, duration_bars=4.0),
                        phase_offset=PhaseOffset(
                            mode=PhaseOffsetMode.GROUP_ORDER,
                            group="all",
                            spread_bars=0.5,
                        ),
                    ),
                    geometry=Geometry(geometry_id="FAN", params={"spread_degrees": 90}),
                    movement=Movement(movement_id="SWEEP_LR", cycles=2.0),
                    dimmer=Dimmer(dimmer_id="PULSE", min_norm=0.2, max_norm=1.0, cycles=4.0),
                )
            ],
            metadata=TemplateMetadata(
                tags=["energetic", "sweep"],
                energy_range=(60, 100),
            ),
        )
        presets = [
            TemplatePreset(
                preset_id="CHILL",
                name="Chill",
                defaults={"intensity": "SMOOTH"},
                step_patches={
                    "main": StepPatch(
                        movement={"cycles": 1.0},
                        dimmer={"min_norm": 0.1, "max_norm": 0.7},
                    ),
                },
            )
        ]
        original = TemplateDoc(template=template, presets=presets)
        json_str = original.model_dump_json()
        restored = TemplateDoc.model_validate_json(json_str)

        assert restored.template.template_id == "fan_pulse"
        assert len(restored.template.steps) == 1
        assert restored.template.steps[0].movement.cycles == 2.0
        assert len(restored.presets) == 1
        assert restored.presets[0].preset_id == "CHILL"


class TestExampleTemplateFixture:
    """Tests for example template fixture file."""

    def test_example_template_validates(self) -> None:
        """Test example template from Section 2.8 validates."""
        # First, check if fixture file exists - if not, this test is skipped
        fixture_path = (
            pathlib.Path(__file__).parent.parent.parent.parent.parent
            / "fixtures"
            / "fan_pulse_template.json"
        )
        if not fixture_path.exists():
            pytest.skip("Example fixture not yet created")

        doc = TemplateDoc.model_validate_json(fixture_path.read_text())
        assert doc.template.template_id is not None
        assert len(doc.template.steps) >= 1
