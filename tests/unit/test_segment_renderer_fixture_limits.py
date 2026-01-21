"""Test that SegmentRenderer respects fixture-specific boundaries."""

import pytest

from blinkb0t.core.config.fixtures import (
    DmxMapping,
    FixtureConfig,
    FixtureGroup,
    FixtureInstance,
    MovementLimits,
    Orientation,
    PanTiltRange,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import CustomCurveSpec
from blinkb0t.core.domains.sequencing.libraries.moving_heads import (
    MOVEMENT_LIBRARY,
    CategoricalIntensity,
    MovementID,
)
from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec
from blinkb0t.core.domains.sequencing.moving_heads.dimmer_handler import DimmerHandler
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.engine import GeometryEngine
from blinkb0t.core.domains.sequencing.moving_heads.templates.handlers.default import (
    DefaultMovementHandler,
)
from blinkb0t.core.domains.sequencing.poses.resolver import PoseResolver
from blinkb0t.core.domains.sequencing.rendering.segment_renderer import SegmentRenderer


@pytest.fixture
def fixture_with_limits() -> FixtureInstance:
    """Create fixture with specific pan/tilt limits."""
    config = FixtureConfig(
        fixture_id="TEST_MH",
        dmx_universe=1,
        dmx_start_address=1,
        channel_count=16,
        dmx_mapping=DmxMapping(
            pan_channel=11,
            tilt_channel=13,
            dimmer_channel=3,
        ),
        pan_tilt_range=PanTiltRange(
            pan_range_deg=540.0,
            tilt_range_deg=270.0,
        ),
        orientation=Orientation(
            pan_front_dmx=128,
            tilt_zero_dmx=22,
            tilt_up_dmx=112,
        ),
        limits=MovementLimits(
            pan_min=50,  # Restricted pan range
            pan_max=190,  # 50-190 (not 0-255)
            tilt_min=5,  # Restricted tilt range
            tilt_max=125,  # 5-125 (not 0-255)
            avoid_backward=True,
        ),
    )
    return FixtureInstance(
        fixture_id="TEST_MH",
        config=config,
        xlights_model_name="Dmx TEST_MH",
    )


@pytest.fixture
def segment_renderer(fixture_with_limits: FixtureInstance) -> SegmentRenderer:
    """Create SegmentRenderer with test fixture."""
    fixture_group = FixtureGroup(
        group_id="TEST_GROUP",
        fixtures=[fixture_with_limits],
    )

    pose_resolver = PoseResolver()
    movement_handler = DefaultMovementHandler()
    geometry_engine = GeometryEngine()
    dimmer_handler = DimmerHandler()

    return SegmentRenderer(
        fixture_group=fixture_group,
        pose_resolver=pose_resolver,
        movement_handler=movement_handler,
        geometry_engine=geometry_engine,
        dimmer_handler=dimmer_handler,
    )


def test_pan_curve_respects_fixture_limits(
    segment_renderer: SegmentRenderer,
    fixture_with_limits: FixtureInstance,
):
    """Test that pan curves are generated within fixture limits (50-190), not 0-255."""
    # Create a curve from a movement pattern
    curve_spec = segment_renderer._create_curve_from_movement(
        movement_id="sweep_lr",
        intensity="DRAMATIC",
        base_dmx=128,  # Center position
        fixture=fixture_with_limits,
        channel="pan",
    )

    # Check that the curve uses fixture limits
    if isinstance(curve_spec, ValueCurveSpec):
        # Native curve - check min/max
        assert curve_spec.min_val >= 50, (
            f"Native curve min {curve_spec.min_val} below fixture limit 50"
        )
        assert curve_spec.max_val <= 190, (
            f"Native curve max {curve_spec.max_val} above fixture limit 190"
        )

    elif isinstance(curve_spec, CustomCurveSpec):
        # Custom curve - check all points
        for point in curve_spec.points:
            assert point.value >= 50, f"Custom curve point {point.value} below fixture limit 50"
            assert point.value <= 190, f"Custom curve point {point.value} above fixture limit 190"

    else:
        # Static value
        assert 50 <= curve_spec <= 190, (
            f"Static value {curve_spec} outside fixture limits [50, 190]"
        )


def test_tilt_curve_respects_fixture_limits(
    segment_renderer: SegmentRenderer,
    fixture_with_limits: FixtureInstance,
):
    """Test that tilt curves are generated within fixture limits (5-125), not 0-255."""
    curve_spec = segment_renderer._create_curve_from_movement(
        movement_id="tilt_rock",
        intensity="INTENSE",
        base_dmx=65,  # Center position for tilt
        fixture=fixture_with_limits,
        channel="tilt",
    )

    # Check that the curve uses fixture limits
    if isinstance(curve_spec, ValueCurveSpec):
        # Native curve - check min/max
        assert curve_spec.min_val >= 5, (
            f"Native curve min {curve_spec.min_val} below fixture limit 5"
        )
        assert curve_spec.max_val <= 125, (
            f"Native curve max {curve_spec.max_val} above fixture limit 125"
        )

    elif isinstance(curve_spec, CustomCurveSpec):
        # Custom curve - check all points
        for point in curve_spec.points:
            assert point.value >= 5, f"Custom curve point {point.value} below fixture limit 5"
            assert point.value <= 125, f"Custom curve point {point.value} above fixture limit 125"

    else:
        # Static value
        assert 5 <= curve_spec <= 125, f"Static value {curve_spec} outside fixture limits [5, 125]"


def test_amplitude_scaled_to_fixture_range(
    segment_renderer: SegmentRenderer,
    fixture_with_limits: FixtureInstance,
):
    """Test that amplitude is calculated relative to fixture range, not full 0-255 range."""
    # Get DRAMATIC intensity params
    movement = MOVEMENT_LIBRARY[MovementID.SWEEP_LR]
    cat_params = movement.categorical_params[CategoricalIntensity.DRAMATIC]
    amplitude_fraction = cat_params.amplitude  # Should be ~0.6 for DRAMATIC

    # Create curve
    base_dmx = 128
    curve_spec = segment_renderer._create_curve_from_movement(
        movement_id="sweep_lr",
        intensity="DRAMATIC",
        base_dmx=base_dmx,
        fixture=fixture_with_limits,
        channel="pan",
    )

    # Calculate expected range based on fixture limits (not 0-255)
    fixture_range = 190 - 50  # 140
    expected_amplitude_dmx = fixture_range * amplitude_fraction  # ~84

    # For generic 0-255 range (WRONG):
    generic_amplitude_dmx = 255 * amplitude_fraction  # ~153 (WRONG!)

    # Check that curve range matches fixture-based calculation, not generic
    if isinstance(curve_spec, ValueCurveSpec):
        curve_range = curve_spec.max_val - curve_spec.min_val

        # Should be close to fixture-based amplitude (±10% tolerance for clamping)
        assert abs(curve_range - expected_amplitude_dmx) < expected_amplitude_dmx * 0.2, (
            f"Curve range {curve_range} doesn't match fixture-based amplitude {expected_amplitude_dmx:.1f}"
        )

        # Should NOT match generic amplitude
        assert abs(curve_range - generic_amplitude_dmx) > 20, (
            f"Curve range {curve_range} incorrectly matches generic amplitude {generic_amplitude_dmx:.1f}"
        )


def test_dimmer_uses_full_range(
    segment_renderer: SegmentRenderer,
    fixture_with_limits: FixtureInstance,
):
    """Test that dimmer curves use full 0-255 range (no fixture-specific dimmer limits)."""
    curve_spec = segment_renderer._create_curve_from_dimmer(
        dimmer_id="pulse",
        dimmer_params={},
        intensity="SMOOTH",
    )

    # Dimmer should use full 0-255 range (no fixture limits for dimmer)
    if isinstance(curve_spec, ValueCurveSpec):
        # Allow some margin for intensity-based variations
        assert curve_spec.min_val <= 10, f"Dimmer min {curve_spec.min_val} should be near 0"
        assert curve_spec.max_val >= 200, f"Dimmer max {curve_spec.max_val} should be near 255"
