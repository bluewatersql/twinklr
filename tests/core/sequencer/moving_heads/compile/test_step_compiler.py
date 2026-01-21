"""Tests for Step Compiler.

Tests compiling a single template step to IR segments.
"""


from blinkb0t.core.sequencer.moving_heads.compile.step_compiler import (
    StepCompileContext,
    compile_step,
)
from blinkb0t.core.sequencer.moving_heads.handlers.defaults import (
    create_default_dimmer_registry,
    create_default_geometry_registry,
    create_default_movement_registry,
)
from blinkb0t.core.sequencer.moving_heads.models.channel import ChannelName
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

# =============================================================================
# Test Fixtures
# =============================================================================


def create_test_step(
    geometry_id: str = "ROLE_POSE",
    movement_id: str = "SWEEP_LR",
    dimmer_id: str = "PULSE",
    duration_bars: float = 4.0,
) -> TemplateStep:
    """Create a test template step."""
    return TemplateStep(
        step_id="test_step",
        target="all",
        timing=StepTiming(
            base_timing=BaseTiming(
                start_offset_bars=0.0,
                duration_bars=duration_bars,
            ),
            phase_offset=PhaseOffset(mode=PhaseOffsetMode.NONE),
        ),
        geometry=Geometry(
            geometry_id=geometry_id,
            pan_pose_by_role={
                "FRONT_LEFT": "LEFT",
                "FRONT_RIGHT": "RIGHT",
            },
            tilt_pose="CROWD",
        ),
        movement=Movement(
            movement_id=movement_id,
            intensity="SMOOTH",
            cycles=1.0,
        ),
        dimmer=Dimmer(
            dimmer_id=dimmer_id,
            intensity="SMOOTH",
            min_norm=0.0,
            max_norm=1.0,
            cycles=2.0,
        ),
    )


def create_test_context(
    fixture_id: str = "fixture1",
    role: str = "FRONT_LEFT",
    start_ms: int = 0,
    duration_ms: int = 4000,
) -> StepCompileContext:
    """Create a test compile context."""
    return StepCompileContext(
        fixture_id=fixture_id,
        role=role,
        calibration={},
        start_ms=start_ms,
        duration_ms=duration_ms,
        n_samples=64,
        geometry_registry=create_default_geometry_registry(),
        movement_registry=create_default_movement_registry(),
        dimmer_registry=create_default_dimmer_registry(),
    )


# =============================================================================
# Tests for Basic Compilation
# =============================================================================


class TestCompileStepBasic:
    """Tests for basic step compilation."""

    def test_compile_produces_three_segments(self) -> None:
        """Test compilation produces pan, tilt, and dimmer segments."""
        step = create_test_step()
        context = create_test_context()

        result = compile_step(step, context)

        assert result.pan_segment is not None
        assert result.tilt_segment is not None
        assert result.dimmer_segment is not None

    def test_segments_have_correct_fixture(self) -> None:
        """Test segments have the correct fixture ID."""
        step = create_test_step()
        context = create_test_context(fixture_id="my_fixture")

        result = compile_step(step, context)

        assert result.pan_segment.fixture_id == "my_fixture"
        assert result.tilt_segment.fixture_id == "my_fixture"
        assert result.dimmer_segment.fixture_id == "my_fixture"

    def test_segments_have_correct_channels(self) -> None:
        """Test segments have correct channel types."""
        step = create_test_step()
        context = create_test_context()

        result = compile_step(step, context)

        assert result.pan_segment.channel == ChannelName.PAN
        assert result.tilt_segment.channel == ChannelName.TILT
        assert result.dimmer_segment.channel == ChannelName.DIMMER

    def test_segments_have_correct_timing(self) -> None:
        """Test segments have correct start/end times."""
        step = create_test_step()
        context = create_test_context(start_ms=1000, duration_ms=2000)

        result = compile_step(step, context)

        assert result.pan_segment.t0_ms == 1000
        assert result.pan_segment.t1_ms == 3000
        assert result.tilt_segment.t0_ms == 1000
        assert result.tilt_segment.t1_ms == 3000
        assert result.dimmer_segment.t0_ms == 1000
        assert result.dimmer_segment.t1_ms == 3000


# =============================================================================
# Tests for Movement Segments
# =============================================================================


class TestCompileStepMovement:
    """Tests for movement segment compilation."""

    def test_pan_segment_is_offset_centered(self) -> None:
        """Test pan segment uses offset-centered interpretation."""
        step = create_test_step()
        context = create_test_context()

        result = compile_step(step, context)

        assert result.pan_segment.offset_centered is True
        assert result.pan_segment.base_dmx is not None
        assert result.pan_segment.amplitude_dmx is not None

    def test_tilt_segment_is_offset_centered(self) -> None:
        """Test tilt segment uses offset-centered interpretation."""
        step = create_test_step()
        context = create_test_context()

        result = compile_step(step, context)

        assert result.tilt_segment.offset_centered is True

    def test_pan_has_curve(self) -> None:
        """Test pan segment has a curve."""
        step = create_test_step()
        context = create_test_context()

        result = compile_step(step, context)

        assert result.pan_segment.curve is not None
        assert result.pan_segment.static_dmx is None


# =============================================================================
# Tests for Dimmer Segments
# =============================================================================


class TestCompileStepDimmer:
    """Tests for dimmer segment compilation."""

    def test_dimmer_is_absolute(self) -> None:
        """Test dimmer segment uses absolute interpretation."""
        step = create_test_step()
        context = create_test_context()

        result = compile_step(step, context)

        assert result.dimmer_segment.offset_centered is False

    def test_dimmer_has_curve(self) -> None:
        """Test dimmer segment has a curve."""
        step = create_test_step()
        context = create_test_context()

        result = compile_step(step, context)

        assert result.dimmer_segment.curve is not None
        assert result.dimmer_segment.static_dmx is None


# =============================================================================
# Tests for Geometry Integration
# =============================================================================


class TestCompileStepGeometry:
    """Tests for geometry integration in step compilation."""

    def test_left_role_has_left_base_pan(self) -> None:
        """Test LEFT role maps to left-of-center pan."""
        step = create_test_step()
        context = create_test_context(role="FRONT_LEFT")

        result = compile_step(step, context)

        # LEFT pose should be around 0.3 normalized, so base_dmx < 128
        assert result.pan_segment.base_dmx is not None
        assert result.pan_segment.base_dmx < 128

    def test_right_role_has_right_base_pan(self) -> None:
        """Test RIGHT role maps to right-of-center pan."""
        step = create_test_step()
        step_modified = TemplateStep(
            step_id=step.step_id,
            target=step.target,
            timing=step.timing,
            geometry=Geometry(
                geometry_id="ROLE_POSE",
                pan_pose_by_role={
                    "FRONT_LEFT": "LEFT",
                    "FRONT_RIGHT": "RIGHT",
                },
                tilt_pose="CROWD",
            ),
            movement=step.movement,
            dimmer=step.dimmer,
        )
        context = create_test_context(role="FRONT_RIGHT")

        result = compile_step(step_modified, context)

        # RIGHT pose should be around 0.7 normalized, so base_dmx > 128
        assert result.pan_segment.base_dmx is not None
        assert result.pan_segment.base_dmx > 128


# =============================================================================
# Tests for StepCompileResult
# =============================================================================


class TestStepCompileResult:
    """Tests for StepCompileResult model."""

    def test_result_has_step_id(self) -> None:
        """Test result contains step ID."""
        step = create_test_step()
        context = create_test_context()

        result = compile_step(step, context)

        assert result.step_id == "test_step"

    def test_result_has_fixture_id(self) -> None:
        """Test result contains fixture ID."""
        step = create_test_step()
        context = create_test_context(fixture_id="my_fixture")

        result = compile_step(step, context)

        assert result.fixture_id == "my_fixture"

    def test_all_segments_list(self) -> None:
        """Test all_segments returns list of all segments."""
        step = create_test_step()
        context = create_test_context()

        result = compile_step(step, context)

        segments = result.all_segments()
        assert len(segments) == 3
        channels = {seg.channel for seg in segments}
        assert ChannelName.PAN in channels
        assert ChannelName.TILT in channels
        assert ChannelName.DIMMER in channels


# =============================================================================
# Tests for Phase Offset Application
# =============================================================================


class TestCompileStepPhaseOffset:
    """Tests for phase offset in step compilation."""

    def test_compile_with_phase_offset(self) -> None:
        """Test compilation with a phase offset applied."""
        step = create_test_step()
        context = create_test_context()

        # Compile with a phase offset
        result = compile_step(step, context, phase_offset_norm=0.25)

        # The curves should have shifted values
        # This is a smoke test - actual offset testing done in phase module
        assert result.pan_segment.curve is not None

    def test_zero_phase_offset(self) -> None:
        """Test compilation with zero phase offset."""
        step = create_test_step()
        context = create_test_context()

        result_no_offset = compile_step(step, context, phase_offset_norm=0.0)
        result_with_offset = compile_step(step, context)

        # Both should produce valid results
        assert result_no_offset.pan_segment is not None
        assert result_with_offset.pan_segment is not None
