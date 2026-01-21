"""Tests for Template Compiler (Orchestrator).

Tests the top-level template compilation that orchestrates all components.
"""


from blinkb0t.core.sequencer.moving_heads.compile.template_compiler import (
    FixtureContext,
    TemplateCompileContext,
    compile_template,
)
from blinkb0t.core.sequencer.moving_heads.handlers.defaults import create_default_registries
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
    TemplatePreset,
    TemplateStep,
)

# =============================================================================
# Test Fixtures
# =============================================================================


def create_test_template(
    template_id: str = "test_template",
    cycle_bars: float = 4.0,
    steps: list[TemplateStep] | None = None,
) -> Template:
    """Create a test template."""
    if steps is None:
        steps = [
            TemplateStep(
                step_id="main",
                target="all",
                timing=StepTiming(
                    base_timing=BaseTiming(
                        start_offset_bars=0.0,
                        duration_bars=cycle_bars,
                    ),
                    phase_offset=PhaseOffset(mode=PhaseOffsetMode.NONE),
                ),
                geometry=Geometry(
                    geometry_id="ROLE_POSE",
                    pan_pose_by_role={
                        "FRONT_LEFT": "LEFT",
                        "FRONT_RIGHT": "RIGHT",
                    },
                    tilt_pose="CROWD",
                ),
                movement=Movement(
                    movement_id="SWEEP_LR",
                    intensity="SMOOTH",
                    cycles=1.0,
                ),
                dimmer=Dimmer(
                    dimmer_id="PULSE",
                    min_norm=0.0,
                    max_norm=1.0,
                    cycles=2.0,
                ),
            )
        ]

    return Template(
        template_id=template_id,
        version=1,
        name="Test Template",
        category="test",
        roles=["FRONT_LEFT", "FRONT_RIGHT"],
        groups={"all": ["FRONT_LEFT", "FRONT_RIGHT"]},
        repeat=RepeatContract(
            cycle_bars=cycle_bars,
            loop_step_ids=[s.step_id for s in steps],
            mode=RepeatMode.JOINER,
        ),
        defaults={},
        steps=steps,
    )


def create_fixture_contexts() -> list[FixtureContext]:
    """Create test fixture contexts."""
    return [
        FixtureContext(
            fixture_id="fixture1",
            role="FRONT_LEFT",
            calibration={},
        ),
        FixtureContext(
            fixture_id="fixture2",
            role="FRONT_RIGHT",
            calibration={},
        ),
    ]


def create_compile_context(
    window_bars: float = 8.0,
    bpm: float = 120.0,
) -> TemplateCompileContext:
    """Create a test compile context."""
    registries = create_default_registries()
    # Calculate ms from bars: ms = bars * beats_per_bar * ms_per_beat
    # At 120 BPM: ms_per_beat = 500, so 1 bar (4 beats) = 2000 ms
    ms_per_bar = (60000 / bpm) * 4  # Assuming 4/4 time
    window_ms = int(window_bars * ms_per_bar)

    return TemplateCompileContext(
        fixtures=create_fixture_contexts(),
        start_ms=0,
        window_ms=window_ms,
        bpm=bpm,
        n_samples=32,
        geometry_registry=registries["geometry"],
        movement_registry=registries["movement"],
        dimmer_registry=registries["dimmer"],
    )


# =============================================================================
# Tests for Basic Compilation
# =============================================================================


class TestCompileTemplateBasic:
    """Tests for basic template compilation."""

    def test_compile_produces_segments(self) -> None:
        """Test compilation produces segments."""
        template = create_test_template()
        context = create_compile_context()

        result = compile_template(template, context)

        assert len(result.segments) > 0

    def test_compile_produces_segments_for_each_fixture(self) -> None:
        """Test compilation produces segments for each fixture."""
        template = create_test_template()
        context = create_compile_context()

        result = compile_template(template, context)

        fixture_ids = {seg.fixture_id for seg in result.segments}
        assert "fixture1" in fixture_ids
        assert "fixture2" in fixture_ids

    def test_compile_produces_all_channel_types(self) -> None:
        """Test compilation produces pan, tilt, and dimmer segments."""
        template = create_test_template()
        context = create_compile_context()

        result = compile_template(template, context)

        from blinkb0t.core.sequencer.moving_heads.models.channel import ChannelName

        channels = {seg.channel for seg in result.segments}
        assert ChannelName.PAN in channels
        assert ChannelName.TILT in channels
        assert ChannelName.DIMMER in channels


# =============================================================================
# Tests for Repeat Handling
# =============================================================================


class TestCompileTemplateRepeats:
    """Tests for repeat handling in compilation."""

    def test_compile_repeats_steps(self) -> None:
        """Test compilation repeats steps to fill window."""
        template = create_test_template(cycle_bars=4.0)
        context = create_compile_context(window_bars=8.0)

        result = compile_template(template, context)

        # Should have 2 cycles * 2 fixtures * 3 channels = 12 segments
        # Actually: each step produces 3 segments per fixture
        # 2 cycles * 1 step * 2 fixtures * 3 channels = 12
        # But segments may be merged or counted differently
        # Just verify we have segments for the window
        assert result.num_complete_cycles == 2

    def test_single_cycle_in_window(self) -> None:
        """Test compilation with window equal to cycle."""
        template = create_test_template(cycle_bars=4.0)
        context = create_compile_context(window_bars=4.0)

        result = compile_template(template, context)

        assert result.num_complete_cycles == 1


# =============================================================================
# Tests for Preset Application
# =============================================================================


class TestCompileTemplateWithPreset:
    """Tests for preset application during compilation."""

    def test_compile_with_preset(self) -> None:
        """Test compilation with preset applied."""
        template = create_test_template()
        preset = TemplatePreset(
            preset_id="CHILL",
            name="Chill",
            defaults={},
            step_patches={
                "main": StepPatch(movement={"cycles": 2.0}),
            },
        )
        context = create_compile_context()

        result = compile_template(template, context, preset=preset)

        # Should compile successfully with preset applied
        assert len(result.segments) > 0
        assert "preset:CHILL" in result.provenance


# =============================================================================
# Tests for Phase Offset
# =============================================================================


class TestCompileTemplatePhaseOffset:
    """Tests for phase offset in compilation."""

    def test_compile_with_group_order_phase_offset(self) -> None:
        """Test compilation with GROUP_ORDER phase offset."""
        step = TemplateStep(
            step_id="main",
            target="all",
            timing=StepTiming(
                base_timing=BaseTiming(
                    start_offset_bars=0.0,
                    duration_bars=4.0,
                ),
                phase_offset=PhaseOffset(
                    mode=PhaseOffsetMode.GROUP_ORDER,
                    group="all",
                    spread_bars=0.5,
                ),
            ),
            geometry=Geometry(
                geometry_id="ROLE_POSE",
                pan_pose_by_role={
                    "FRONT_LEFT": "LEFT",
                    "FRONT_RIGHT": "RIGHT",
                },
                tilt_pose="CROWD",
            ),
            movement=Movement(
                movement_id="SWEEP_LR",
                intensity="SMOOTH",
                cycles=1.0,
            ),
            dimmer=Dimmer(
                dimmer_id="PULSE",
                min_norm=0.0,
                max_norm=1.0,
                cycles=2.0,
            ),
        )
        template = create_test_template(steps=[step])
        context = create_compile_context(window_bars=4.0)

        result = compile_template(template, context)

        # Should compile successfully with phase offsets
        assert len(result.segments) > 0


# =============================================================================
# Tests for TemplateCompileResult
# =============================================================================


class TestTemplateCompileResult:
    """Tests for TemplateCompileResult model."""

    def test_result_has_template_id(self) -> None:
        """Test result contains template ID."""
        template = create_test_template(template_id="my_template")
        context = create_compile_context()

        result = compile_template(template, context)

        assert result.template_id == "my_template"

    def test_result_has_provenance(self) -> None:
        """Test result contains provenance tracking."""
        template = create_test_template()
        context = create_compile_context()

        result = compile_template(template, context)

        assert "template:test_template" in result.provenance

    def test_result_segments_by_fixture(self) -> None:
        """Test getting segments by fixture."""
        template = create_test_template()
        context = create_compile_context()

        result = compile_template(template, context)

        fixture1_segments = result.segments_by_fixture("fixture1")
        assert all(seg.fixture_id == "fixture1" for seg in fixture1_segments)

    def test_result_segments_by_channel(self) -> None:
        """Test getting segments by channel."""
        template = create_test_template()
        context = create_compile_context()

        result = compile_template(template, context)

        from blinkb0t.core.sequencer.moving_heads.models.channel import ChannelName

        pan_segments = result.segments_by_channel(ChannelName.PAN)
        assert all(seg.channel == ChannelName.PAN for seg in pan_segments)
