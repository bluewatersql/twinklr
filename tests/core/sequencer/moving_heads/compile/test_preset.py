"""Tests for Preset Application.

Tests applying preset patches to templates using immutable merging.
"""

from blinkb0t.core.sequencer.moving_heads.compile.preset import (
    apply_preset,
    apply_step_patch,
)
from blinkb0t.core.sequencer.moving_heads.models.template import (
    BaseTiming,
    Dimmer,
    Geometry,
    Movement,
    PhaseOffset,
    PhaseOffsetMode,
    RepeatContract,
    StepPatch,
    StepTiming,
    Template,
    TemplatePreset,
    TemplateStep,
)

# =============================================================================
# Test Fixtures (Factory Functions)
# =============================================================================


def create_minimal_step(
    step_id: str = "main",
    target: str = "all",
    duration_bars: float = 4.0,
) -> TemplateStep:
    """Create a minimal template step for testing."""
    return TemplateStep(
        step_id=step_id,
        target=target,
        timing=StepTiming(
            base_timing=BaseTiming(start_offset_bars=0.0, duration_bars=duration_bars),
            phase_offset=PhaseOffset(mode=PhaseOffsetMode.NONE),
        ),
        geometry=Geometry(
            geometry_id="ROLE_POSE",
            pan_pose_by_role={"FRONT_LEFT": "LEFT"},
            tilt_pose="CROWD",
        ),
        movement=Movement(
            movement_id="SWEEP_LR",
            intensity="SMOOTH",
            cycles=1.0,
        ),
        dimmer=Dimmer(
            dimmer_id="PULSE",
            intensity="SMOOTH",
            min_norm=0.0,
            max_norm=1.0,
            cycles=2.0,
        ),
    )


def create_minimal_template(
    template_id: str = "test_template",
    steps: list[TemplateStep] | None = None,
    defaults: dict | None = None,
) -> Template:
    """Create a minimal template for testing."""
    if steps is None:
        steps = [create_minimal_step()]
    return Template(
        template_id=template_id,
        version=1,
        name="Test Template",
        category="test",
        roles=["FRONT_LEFT", "FRONT_RIGHT"],
        groups={"all": ["FRONT_LEFT", "FRONT_RIGHT"]},
        repeat=RepeatContract(cycle_bars=4.0, loop_step_ids=["main"]),
        defaults=defaults or {},
        steps=steps,
    )


def create_minimal_preset(
    preset_id: str = "CHILL",
    defaults: dict | None = None,
    step_patches: dict[str, StepPatch] | None = None,
) -> TemplatePreset:
    """Create a minimal preset for testing."""
    return TemplatePreset(
        preset_id=preset_id,
        name=preset_id.title(),
        defaults=defaults or {},
        step_patches=step_patches or {},
    )


# =============================================================================
# Tests for apply_step_patch
# =============================================================================


class TestApplyStepPatch:
    """Tests for apply_step_patch function."""

    def test_patch_empty_returns_unchanged(self) -> None:
        """Test empty patch returns identical step data."""
        step = create_minimal_step()
        patch = StepPatch()

        result = apply_step_patch(step, patch)

        # Step should be unchanged (but a new instance)
        assert result.step_id == step.step_id
        assert result.geometry.geometry_id == step.geometry.geometry_id
        assert result.movement.movement_id == step.movement.movement_id
        assert result.dimmer.dimmer_id == step.dimmer.dimmer_id

    def test_patch_movement_cycles(self) -> None:
        """Test patching movement cycles."""
        step = create_minimal_step()
        patch = StepPatch(movement={"cycles": 4.0})

        result = apply_step_patch(step, patch)

        assert result.movement.cycles == 4.0
        # Other movement fields unchanged
        assert result.movement.movement_id == "SWEEP_LR"
        assert result.movement.intensity == "SMOOTH"

    def test_patch_dimmer_range(self) -> None:
        """Test patching dimmer min/max."""
        step = create_minimal_step()
        patch = StepPatch(dimmer={"min_norm": 0.2, "max_norm": 0.8})

        result = apply_step_patch(step, patch)

        assert result.dimmer.min_norm == 0.2
        assert result.dimmer.max_norm == 0.8
        # Other dimmer fields unchanged
        assert result.dimmer.dimmer_id == "PULSE"
        assert result.dimmer.cycles == 2.0

    def test_patch_geometry_tilt(self) -> None:
        """Test patching geometry tilt pose."""
        step = create_minimal_step()
        patch = StepPatch(geometry={"tilt_pose": "SKY"})

        result = apply_step_patch(step, patch)

        assert result.geometry.tilt_pose == "SKY"
        # Other geometry fields unchanged
        assert result.geometry.geometry_id == "ROLE_POSE"
        assert result.geometry.pan_pose_by_role == {"FRONT_LEFT": "LEFT"}

    def test_patch_timing_duration(self) -> None:
        """Test patching timing duration."""
        step = create_minimal_step()
        patch = StepPatch(timing={"base_timing": {"duration_bars": 8.0}})

        result = apply_step_patch(step, patch)

        assert result.timing.base_timing.duration_bars == 8.0
        # Start offset unchanged
        assert result.timing.base_timing.start_offset_bars == 0.0

    def test_patch_multiple_components(self) -> None:
        """Test patching multiple components at once."""
        step = create_minimal_step()
        patch = StepPatch(
            movement={"cycles": 3.0},
            dimmer={"max_norm": 0.5},
            geometry={"aim_zone": "STAGE"},
        )

        result = apply_step_patch(step, patch)

        assert result.movement.cycles == 3.0
        assert result.dimmer.max_norm == 0.5
        assert result.geometry.aim_zone == "STAGE"

    def test_original_step_unchanged(self) -> None:
        """Test original step is not modified (immutability)."""
        step = create_minimal_step()
        original_cycles = step.movement.cycles
        patch = StepPatch(movement={"cycles": 10.0})

        apply_step_patch(step, patch)

        # Original unchanged
        assert step.movement.cycles == original_cycles

    def test_patch_nested_geometry_params(self) -> None:
        """Test patching nested params dict in geometry."""
        step = create_minimal_step()
        patch = StepPatch(geometry={"params": {"new_param": "value"}})

        result = apply_step_patch(step, patch)

        assert result.geometry.params == {"new_param": "value"}


# =============================================================================
# Tests for apply_preset
# =============================================================================


class TestApplyPreset:
    """Tests for apply_preset function."""

    def test_empty_preset_returns_unchanged(self) -> None:
        """Test empty preset returns identical template data."""
        template = create_minimal_template()
        preset = create_minimal_preset()

        result = apply_preset(template, preset)

        assert result.template_id == template.template_id
        assert len(result.steps) == len(template.steps)

    def test_preset_defaults_merged(self) -> None:
        """Test preset defaults are merged into template defaults."""
        template = create_minimal_template(defaults={"a": 1, "b": 2})
        preset = create_minimal_preset(defaults={"b": 99, "c": 3})

        result = apply_preset(template, preset)

        assert result.defaults == {"a": 1, "b": 99, "c": 3}

    def test_preset_step_patch_applied(self) -> None:
        """Test preset step patches are applied."""
        step = create_minimal_step(step_id="main")
        template = create_minimal_template(steps=[step])
        preset = create_minimal_preset(step_patches={"main": StepPatch(movement={"cycles": 5.0})})

        result = apply_preset(template, preset)

        assert result.steps[0].movement.cycles == 5.0

    def test_preset_patches_only_matching_steps(self) -> None:
        """Test preset only patches steps that match by step_id."""
        step1 = create_minimal_step(step_id="step1")
        step2 = create_minimal_step(step_id="step2")
        template = Template(
            template_id="multi_step",
            version=1,
            name="Multi Step Template",
            category="test",
            roles=["FRONT_LEFT", "FRONT_RIGHT"],
            groups={"all": ["FRONT_LEFT", "FRONT_RIGHT"]},
            repeat=RepeatContract(cycle_bars=4.0, loop_step_ids=["step1", "step2"]),
            defaults={},
            steps=[step1, step2],
        )
        preset = create_minimal_preset(step_patches={"step1": StepPatch(dimmer={"max_norm": 0.5})})

        result = apply_preset(template, preset)

        # step1 patched
        assert result.steps[0].dimmer.max_norm == 0.5
        # step2 unchanged
        assert result.steps[1].dimmer.max_norm == 1.0

    def test_original_template_unchanged(self) -> None:
        """Test original template is not modified (immutability)."""
        template = create_minimal_template(defaults={"original": True})
        preset = create_minimal_preset(defaults={"added": True})

        apply_preset(template, preset)

        # Original unchanged
        assert template.defaults == {"original": True}

    def test_preset_with_unknown_step_patch_ignored(self) -> None:
        """Test step patches for non-existent steps are ignored."""
        template = create_minimal_template()
        preset = create_minimal_preset(
            step_patches={"nonexistent": StepPatch(movement={"cycles": 10.0})}
        )

        # Should not raise, just ignore unknown step
        result = apply_preset(template, preset)

        assert len(result.steps) == 1
        assert result.steps[0].movement.cycles == 1.0  # Unchanged

    def test_preset_preserves_template_structure(self) -> None:
        """Test preset preserves all template fields."""
        template = create_minimal_template()
        preset = create_minimal_preset(defaults={"new": "value"})

        result = apply_preset(template, preset)

        # All structural fields preserved
        assert result.template_id == template.template_id
        assert result.version == template.version
        assert result.name == template.name
        assert result.category == template.category
        assert result.roles == template.roles
        assert result.groups == template.groups
        assert result.repeat == template.repeat

    def test_multiple_step_patches(self) -> None:
        """Test multiple step patches applied correctly."""
        step1 = create_minimal_step(step_id="intro")
        step2 = create_minimal_step(step_id="main")
        template = Template(
            template_id="multi_step",
            version=1,
            name="Multi Step Template",
            category="test",
            roles=["FRONT_LEFT", "FRONT_RIGHT"],
            groups={"all": ["FRONT_LEFT", "FRONT_RIGHT"]},
            repeat=RepeatContract(cycle_bars=4.0, loop_step_ids=["intro", "main"]),
            defaults={},
            steps=[step1, step2],
        )
        preset = create_minimal_preset(
            step_patches={
                "intro": StepPatch(dimmer={"max_norm": 0.3}),
                "main": StepPatch(movement={"cycles": 2.0}),
            }
        )

        result = apply_preset(template, preset)

        assert result.steps[0].dimmer.max_norm == 0.3
        assert result.steps[1].movement.cycles == 2.0


class TestApplyPresetProvenance:
    """Tests for provenance tracking in apply_preset."""

    def test_returns_provenance_info(self) -> None:
        """Test apply_preset can return provenance information."""
        template = create_minimal_template()
        preset = create_minimal_preset(preset_id="CHILL")

        _, provenance = apply_preset(template, preset, return_provenance=True)

        assert "template:" in provenance[0]
        assert "preset:CHILL" in provenance

    def test_provenance_tracks_multiple_presets(self) -> None:
        """Test provenance tracks applying multiple presets."""
        template = create_minimal_template()
        preset1 = create_minimal_preset(preset_id="BASE")
        preset2 = create_minimal_preset(preset_id="CHILL")

        result1, prov1 = apply_preset(template, preset1, return_provenance=True)
        # Apply second preset starting from result of first
        _, prov2 = apply_preset(
            result1,
            preset2,
            return_provenance=True,
            base_provenance=prov1,
        )

        assert "preset:BASE" in prov2
        assert "preset:CHILL" in prov2
