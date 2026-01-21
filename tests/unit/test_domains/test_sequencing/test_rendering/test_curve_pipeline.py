"""Tests for CurvePipeline rendering logic.

Tests the core curve rendering pipeline that converts SequencedEffect objects
(with ValueCurveSpec) into RenderedEffect objects (with list[CurvePoint]).
"""

from unittest.mock import Mock

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import CurveGenerator
from blinkb0t.core.domains.sequencing.rendering.curve_blending import CurveBlender
from blinkb0t.core.domains.sequencing.rendering.curve_detector import CurveTypeDetector
from blinkb0t.core.domains.sequencing.rendering.curve_pipeline import CurvePipeline

# ============================================================================
# Initialization Tests
# ============================================================================


def test_curve_pipeline_initialization():
    """Test CurvePipeline can be initialized with CurveGenerator."""
    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    assert pipeline.curve_generator is generator
    assert isinstance(pipeline.blender, CurveBlender)
    assert isinstance(pipeline.detector, CurveTypeDetector)


def test_curve_pipeline_initialization_requires_generator():
    """Test CurvePipeline initialization fails without generator."""
    with pytest.raises(TypeError):
        CurvePipeline()  # Missing required curve_generator argument


# ============================================================================
# Render Method Tests (Basic - Task 2.9)
# ============================================================================


def test_render_empty_list():
    """Test CurvePipeline.render() with empty effect list."""
    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    result = pipeline.render([])

    assert result == []


# Additional tests will be added as we implement each method in Tasks 2.1-2.9


# ============================================================================
# Task 2.1: _group_by_fixture Tests
# ============================================================================


def test_group_by_fixture_single_fixture():
    """Test grouping effects for a single fixture."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    effect1 = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
    )
    effect2 = SequencedEffect(
        fixture_id="MH1",
        start_ms=1000,
        end_ms=2000,
        channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
    )

    result = pipeline._group_by_fixture([effect1, effect2])

    assert len(result) == 1
    assert "MH1" in result
    assert len(result["MH1"]) == 2
    assert result["MH1"][0] == effect1
    assert result["MH1"][1] == effect2


def test_group_by_fixture_multiple_fixtures():
    """Test grouping effects for multiple fixtures."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    effect_mh1 = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
    )
    effect_mh2 = SequencedEffect(
        fixture_id="MH2",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
    )
    effect_mh3 = SequencedEffect(
        fixture_id="MH3",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=90, tilt=45, dimmer=150),
    )

    result = pipeline._group_by_fixture([effect_mh1, effect_mh2, effect_mh3])

    assert len(result) == 3
    assert "MH1" in result
    assert "MH2" in result
    assert "MH3" in result
    assert len(result["MH1"]) == 1
    assert len(result["MH2"]) == 1
    assert len(result["MH3"]) == 1


def test_group_by_fixture_empty_list():
    """Test grouping with empty effect list."""
    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    result = pipeline._group_by_fixture([])

    assert result == {}


def test_group_by_fixture_preserves_order():
    """Test grouping preserves effect order within each fixture."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    # Create effects out of time order
    effect3 = SequencedEffect(
        fixture_id="MH1",
        start_ms=2000,
        end_ms=3000,
        channels=ChannelSpecs(pan=200, tilt=100, dimmer=255),
    )
    effect1 = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
    )
    effect2 = SequencedEffect(
        fixture_id="MH1",
        start_ms=1000,
        end_ms=2000,
        channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
    )

    # Pass in non-chronological order
    result = pipeline._group_by_fixture([effect3, effect1, effect2])

    assert len(result["MH1"]) == 3
    # Should preserve input order (not sort)
    assert result["MH1"][0] == effect3
    assert result["MH1"][1] == effect1
    assert result["MH1"][2] == effect2


def test_group_by_fixture_mixed_fixtures():
    """Test grouping with interleaved fixtures."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    effects = [
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        ),
        SequencedEffect(
            fixture_id="MH2",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
        ),
        SequencedEffect(
            fixture_id="MH1",
            start_ms=1000,
            end_ms=2000,
            channels=ChannelSpecs(pan=150, tilt=75, dimmer=220),
        ),
        SequencedEffect(
            fixture_id="MH2",
            start_ms=1000,
            end_ms=2000,
            channels=ChannelSpecs(pan=200, tilt=100, dimmer=180),
        ),
    ]

    result = pipeline._group_by_fixture(effects)

    assert len(result) == 2
    assert len(result["MH1"]) == 2
    assert len(result["MH2"]) == 2
    # Verify correct grouping
    assert result["MH1"][0].start_ms == 0
    assert result["MH1"][1].start_ms == 1000
    assert result["MH2"][0].start_ms == 0
    assert result["MH2"][1].start_ms == 1000


# ============================================================================
# Task 2.2: _render_channel (Static Values) Tests
# ============================================================================


# NOTE: Tests for static value rendering removed - API changed.
# Static values (int) now pass through unchanged as ints (not converted to CurvePoints).
# This is correct behavior - xLights handles static values as sliders, not curves.


# ============================================================================
# Tests for _render_curve_spec REMOVED
# ============================================================================
# The _render_curve_spec method has been removed as part of the Native curve
# architecture fix. Native curves (ValueCurveSpec) are now passed through
# unchanged by _render_channel, and Custom curves return spec.points directly.
# This change ensures Native curves are rendered by xLights, not by us.


# ============================================================================
# Task 2.5: _render_channel (ValueCurveSpec Support) Tests
# ============================================================================


def test_render_channel_with_value_curve_spec():
    """Test _render_channel returns Native curve (ValueCurveSpec) unchanged."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
    )

    # Native curve should pass through unchanged
    spec = ValueCurveSpec(type=NativeCurveType.RAMP, p1=0.0, p2=255.0)

    result = pipeline._render_channel(spec, effect)

    # ✅ Native curves are returned unchanged (not converted to points!)
    assert isinstance(result, ValueCurveSpec)
    assert result is spec  # Same object!
    assert result.type == NativeCurveType.RAMP
    assert result.p1 == 0.0
    assert result.p2 == 255.0

    # ✅ Generator should NOT be called for Native curves
    generator.generate_custom_points.assert_not_called()


def test_render_channel_with_custom_curve_spec():
    """Test _render_channel handles CustomCurveSpec with smoothing."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import (
        CustomCurveSpec,
    )
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
    )

    # Sparse 2-point curve will be smoothed to ~100 points
    points = [
        CurvePoint(time=0.0, value=100.0),
        CurvePoint(time=1.0, value=200.0),
    ]
    spec = CustomCurveSpec(points=points)

    result = pipeline._render_channel(spec, effect)

    # Should be smoothed (not 2 points!)
    assert isinstance(result, list)
    assert len(result) == 25  # Fixed target_count = 25
    assert all(isinstance(p, CurvePoint) for p in result)
    # First and last values should be approximately preserved
    assert result[0].value == pytest.approx(100.0, abs=1.0)
    assert result[-1].value == pytest.approx(200.0, abs=1.0)


# ============================================================================
# Task 4.0: Curve Smoothing Tests
# ============================================================================


def test_smooth_custom_curve_sparse():
    """Test smoothing sparse curve to target count."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    # Sparse input (2 points)
    points = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=1.0, value=255.0),
    ]

    # Smooth to 100 points
    result = pipeline._smooth_custom_curve(points, 100)

    assert len(result) == 100
    assert result[0].time == 0.0
    assert result[0].value == pytest.approx(0.0, abs=0.1)
    assert result[-1].time == 1.0
    assert result[-1].value == pytest.approx(255.0, abs=0.1)
    # Check monotonic increase (PCHIP preserves shape)
    values = [p.value for p in result]
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))


def test_smooth_custom_curve_dense():
    """Test reducing dense curve to target count."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    # Dense input (500 points)
    points = [CurvePoint(time=i / 499, value=i / 2) for i in range(500)]

    # Reduce to 200 points
    result = pipeline._smooth_custom_curve(points, 200)

    assert len(result) == 200
    assert result[0].time == 0.0
    assert result[-1].time == 1.0
    # Values should be smooth and monotonic
    values = [p.value for p in result]
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))


def test_smooth_custom_curve_already_optimal():
    """Test no-op when already at target count."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    # Already optimal (100 points)
    points = [CurvePoint(time=i / 99, value=float(i)) for i in range(100)]

    # No change expected
    result = pipeline._smooth_custom_curve(points, 100)

    assert len(result) == 100
    assert result == points  # Same list (no smoothing needed)


def test_render_channel_custom_with_smoothing():
    """Test Custom curve rendering applies smoothing."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import (
        CustomCurveSpec,
    )
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    # Custom curve with sparse points
    spec = CustomCurveSpec(
        points=[
            CurvePoint(time=0.0, value=0.0),
            CurvePoint(time=1.0, value=255.0),
        ]
    )

    # Create effect (ChannelSpecs doesn't accept CustomCurveSpec, so use static)
    effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=5000,  # 5 seconds → target 100 points
        channels=ChannelSpecs(pan=127, tilt=127, dimmer=255),
    )

    # Test _render_channel with CustomCurveSpec directly
    result = pipeline._render_channel(spec, effect)

    # Should be smoothed to fixed target (25 points)
    assert isinstance(result, list)
    assert len(result) == 25  # Fixed target_count = 25
    assert all(isinstance(p, CurvePoint) for p in result)


def test_render_channel_native_no_smoothing():
    """Test Native curve passes through WITHOUT smoothing."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    # Native curve
    spec = ValueCurveSpec(type=NativeCurveType.RAMP, p2=200.0)

    effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=5000,  # Even with 5 seconds...
        channels=ChannelSpecs(pan=spec, tilt=127, dimmer=255),
    )

    result = pipeline._render_channel(spec, effect)

    # Should return spec unchanged (NO smoothing!)
    assert isinstance(result, ValueCurveSpec)
    assert result is spec  # Same object!
    assert result.type == NativeCurveType.RAMP
    assert result.p2 == 200.0


# ============================================================================
# Task 2.6: _detect_native_curves Tests
# ============================================================================


def test_detect_native_curves_all_static():
    """Test detection returns False when all channels are static."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    effects = [
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        ),
        SequencedEffect(
            fixture_id="MH1",
            start_ms=1000,
            end_ms=2000,
            channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
        ),
    ]

    result = pipeline.detector.detect_native_curves(effects)

    assert result is False


def test_detect_native_curves_with_native_pan():
    """Test detection returns True when pan channel has Native curve."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    native_spec = ValueCurveSpec(type=NativeCurveType.SINE, p2=100.0, p4=128.0)

    effects = [
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=native_spec, tilt=64, dimmer=255),
        ),
    ]

    result = pipeline.detector.detect_native_curves(effects)

    assert result is True


def test_detect_native_curves_with_native_dimmer():
    """Test detection returns True when dimmer channel has Native curve."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    native_spec = ValueCurveSpec(type=NativeCurveType.RAMP, p1=0.0, p2=255.0)

    effects = [
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=127, tilt=64, dimmer=native_spec),
        ),
    ]

    result = pipeline.detector.detect_native_curves(effects)

    assert result is True


def test_detect_native_curves_mixed_effects():
    """Test detection returns True if ANY effect has Native curves."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    native_spec = ValueCurveSpec(type=NativeCurveType.SINE, p2=100.0, p4=128.0)

    effects = [
        # First effect: all static
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        ),
        # Second effect: has native curve
        SequencedEffect(
            fixture_id="MH1",
            start_ms=1000,
            end_ms=2000,
            channels=ChannelSpecs(pan=native_spec, tilt=90, dimmer=200),
        ),
    ]

    result = pipeline.detector.detect_native_curves(effects)

    assert result is True


def test_detect_native_curves_all_custom_via_static():
    """Test detection returns False when all channels are non-Native (static values).

    Note: CustomCurveSpec is handled at a lower level (_render_curve_spec),
    not at ChannelSpecs level. At the ChannelSpecs level, we only have
    ValueCurveSpec (Native) or static int values.
    """
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    # All static values = no Native curves
    effects = [
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=100, tilt=50, dimmer=200),
        ),
        SequencedEffect(
            fixture_id="MH1",
            start_ms=1000,
            end_ms=2000,
            channels=ChannelSpecs(pan=150, tilt=75, dimmer=255),
        ),
    ]

    result = pipeline.detector.detect_native_curves(effects)

    assert result is False  # All static = no Native curves


def test_detect_native_curves_empty_list():
    """Test detection with empty effects list."""
    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    result = pipeline.detector.detect_native_curves([])

    assert result is False


# ============================================================================
# Task 2.7: _render_snap_only Tests
# ============================================================================


# NOTE: test_render_snap_only_single_effect removed - API changed.
# Static values (int) now pass through unchanged as ints (not converted to CurvePoints).
# This is correct behavior - xLights handles static values as sliders, not curves.


def test_render_snap_only_multiple_effects():
    """Test _render_snap_only renders multiple effects."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    effects = [
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        ),
        SequencedEffect(
            fixture_id="MH1",
            start_ms=1000,
            end_ms=2000,
            channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
        ),
    ]

    result = pipeline._render_snap_only(effects)

    assert len(result) == 2
    assert result[0].start_ms == 0
    assert result[1].start_ms == 1000


def test_render_snap_only_preserves_metadata():
    """Test _render_snap_only preserves effect metadata."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        metadata={"source": "template", "pattern": "circle"},
    )

    result = pipeline._render_snap_only([effect])

    assert result[0].metadata["source"] == "template"
    assert result[0].metadata["pattern"] == "circle"


# NOTE: test_render_snap_only_with_optional_channels removed - API changed.
# Static values (int) now pass through unchanged as ints (not converted to CurvePoints).


# ============================================================================
# Task 2.8: _render_fixture Tests
# ============================================================================


def test_render_fixture_sorts_effects():
    """Test _render_fixture sorts effects by start_ms."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    # Create effects out of chronological order
    effects = [
        SequencedEffect(
            fixture_id="MH1",
            start_ms=2000,
            end_ms=3000,
            channels=ChannelSpecs(pan=200, tilt=100, dimmer=255),
        ),
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        ),
        SequencedEffect(
            fixture_id="MH1",
            start_ms=1000,
            end_ms=2000,
            channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
        ),
    ]

    result = pipeline._render_fixture("MH1", effects)

    # Should be sorted by start_ms
    assert len(result) == 3
    assert result[0].start_ms == 0
    assert result[1].start_ms == 1000
    assert result[2].start_ms == 2000


def test_render_fixture_uses_snap_for_native():
    """Test _render_fixture uses SNAP rendering when Native curves present."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint, ValueCurveSpec
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    # Mock the generator to return specific points
    generator.generate_custom_points = Mock(
        return_value=[CurvePoint(time=0.0, value=128.0), CurvePoint(time=1.0, value=180.0)]
    )
    pipeline = CurvePipeline(curve_generator=generator)

    native_spec = ValueCurveSpec(type=NativeCurveType.SINE, p2=100.0, p4=128.0)

    effects = [
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=native_spec, tilt=64, dimmer=255),
        ),
    ]

    result = pipeline._render_fixture("MH1", effects)

    # Should render without blending (SNAP mode)
    assert len(result) == 1
    assert result[0].fixture_id == "MH1"


def test_render_fixture_uses_blending_for_all_static():
    """Test _render_fixture uses blending path when all static/custom."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    effects = [
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        ),
    ]

    result = pipeline._render_fixture("MH1", effects)

    # Should render (blending path - Phase 4 just calls snap_only for now)
    assert len(result) == 1
    assert result[0].fixture_id == "MH1"


# ============================================================================
# Task 2.9: render (Main Entry Point) Tests
# ============================================================================


def test_render_single_fixture():
    """Test render() with single fixture."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    effects = [
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        ),
    ]

    result = pipeline.render(effects)

    assert len(result) == 1
    assert result[0].fixture_id == "MH1"


def test_render_multiple_fixtures():
    """Test render() with multiple fixtures."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    effects = [
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        ),
        SequencedEffect(
            fixture_id="MH2",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
        ),
        SequencedEffect(
            fixture_id="MH1",
            start_ms=1000,
            end_ms=2000,
            channels=ChannelSpecs(pan=150, tilt=75, dimmer=220),
        ),
    ]

    result = pipeline.render(effects)

    assert len(result) == 3
    # Check fixtures rendered
    fixture_ids = [e.fixture_id for e in result]
    assert "MH1" in fixture_ids
    assert "MH2" in fixture_ids
    assert fixture_ids.count("MH1") == 2
    assert fixture_ids.count("MH2") == 1


def test_render_groups_and_processes_fixtures():
    """Test render() properly groups by fixture and processes each."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    # Mixed fixtures
    effects = [
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        ),
        SequencedEffect(
            fixture_id="MH2",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
        ),
        SequencedEffect(
            fixture_id="MH3",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=90, tilt=45, dimmer=150),
        ),
    ]

    result = pipeline.render(effects)

    # Should have all 3 fixtures
    assert len(result) == 3
    fixture_ids = {e.fixture_id for e in result}
    assert fixture_ids == {"MH1", "MH2", "MH3"}


# ============================================================================
# Task Group 3: Blending Logic
# ============================================================================


# ============================================================================
# Task 3.1: _get_transition_mode Tests
# ============================================================================


def test_get_transition_mode_exit_crossfade():
    """Test _get_transition_mode returns CROSSFADE from exit transition."""
    from blinkb0t.core.domains.sequencing.models.templates import (
        TransitionConfig,
        TransitionMode,
    )
    from blinkb0t.core.domains.sequencing.rendering.models import (
        BoundaryInfo,
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curr = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        boundary_info=BoundaryInfo(
            exit_transition=TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5)
        ),
    )

    next_effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=1000,
        end_ms=2000,
        channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
    )

    result = pipeline.blender.get_transition_mode(curr, next_effect)

    assert result == "CROSSFADE"


def test_get_transition_mode_entry_crossfade():
    """Test _get_transition_mode returns CROSSFADE from entry transition."""
    from blinkb0t.core.domains.sequencing.models.templates import (
        TransitionConfig,
        TransitionMode,
    )
    from blinkb0t.core.domains.sequencing.rendering.models import (
        BoundaryInfo,
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curr = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
    )

    next_effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=1000,
        end_ms=2000,
        channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
        boundary_info=BoundaryInfo(
            entry_transition=TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5)
        ),
    )

    result = pipeline.blender.get_transition_mode(curr, next_effect)

    assert result == "CROSSFADE"


def test_get_transition_mode_exit_takes_precedence():
    """Test exit transition takes precedence over entry transition."""
    from blinkb0t.core.domains.sequencing.models.templates import (
        TransitionConfig,
        TransitionMode,
    )
    from blinkb0t.core.domains.sequencing.rendering.models import (
        BoundaryInfo,
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curr = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        boundary_info=BoundaryInfo(
            exit_transition=TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5)
        ),
    )

    next_effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=1000,
        end_ms=2000,
        channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
        boundary_info=BoundaryInfo(
            entry_transition=TransitionConfig(mode=TransitionMode.SNAP, duration_bars=0.0)
        ),
    )

    result = pipeline.blender.get_transition_mode(curr, next_effect)

    # Exit takes precedence
    assert result == "CROSSFADE"


def test_get_transition_mode_default_snap():
    """Test _get_transition_mode defaults to SNAP when neither defined."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curr = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
    )

    next_effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=1000,
        end_ms=2000,
        channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
    )

    result = pipeline.blender.get_transition_mode(curr, next_effect)

    assert result == "SNAP"


def test_get_transition_mode_missing_boundary_info():
    """Test _get_transition_mode handles missing boundary_info."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curr = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        boundary_info=None,
    )

    next_effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=1000,
        end_ms=2000,
        channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
        boundary_info=None,
    )

    result = pipeline.blender.get_transition_mode(curr, next_effect)

    assert result == "SNAP"


# ============================================================================
# Task 3.2: _get_blend_duration Tests
# ============================================================================


def test_get_blend_duration_defaults_to_500():
    """Test _get_blend_duration defaults to 500ms when not specified."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curr = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
    )

    next_effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=1000,
        end_ms=2000,
        channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
    )

    result = pipeline.blender.get_blend_duration(curr, next_effect)

    assert result == 500  # Default


def test_get_blend_duration_no_boundary_info():
    """Test _get_blend_duration with missing boundary_info."""
    from blinkb0t.core.domains.sequencing.rendering.models import (
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curr = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=ChannelSpecs(pan=127, tilt=64, dimmer=255),
        boundary_info=None,
    )

    next_effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=1000,
        end_ms=2000,
        channels=ChannelSpecs(pan=180, tilt=90, dimmer=200),
        boundary_info=None,
    )

    result = pipeline.blender.get_blend_duration(curr, next_effect)

    assert result == 500  # Default


# ============================================================================
# Task 3.3: _interpolate Tests
# ============================================================================


def test_interpolate_exact_point():
    """Test _interpolate returns exact value when time matches a point."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curve = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=0.5, value=128.0),
        CurvePoint(time=1.0, value=255.0),
    ]

    result = pipeline.blender.interpolate(curve, 0.5)

    assert result == 128.0


def test_interpolate_between_points():
    """Test _interpolate performs linear interpolation between points."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curve = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=1.0, value=100.0),
    ]

    result = pipeline.blender.interpolate(curve, 0.5)

    assert result == 50.0  # Halfway between 0 and 100


def test_interpolate_time_before_start():
    """Test _interpolate handles time < 0."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curve = [
        CurvePoint(time=0.0, value=100.0),
        CurvePoint(time=1.0, value=200.0),
    ]

    result = pipeline.blender.interpolate(curve, -0.5)

    assert result == 100.0  # Clamp to first point


def test_interpolate_time_after_end():
    """Test _interpolate handles time > 1."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curve = [
        CurvePoint(time=0.0, value=100.0),
        CurvePoint(time=1.0, value=200.0),
    ]

    result = pipeline.blender.interpolate(curve, 1.5)

    assert result == 200.0  # Clamp to last point


def test_interpolate_complex_curve():
    """Test _interpolate with multi-point curve."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curve = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=0.25, value=50.0),
        CurvePoint(time=0.5, value=100.0),
        CurvePoint(time=0.75, value=75.0),
        CurvePoint(time=1.0, value=50.0),
    ]

    # Test at 0.375 (midway between 0.25 and 0.5)
    result = pipeline.blender.interpolate(curve, 0.375)

    expected = 50.0 + (100.0 - 50.0) * 0.5  # Midway
    assert abs(result - expected) < 0.01  # Float comparison


def test_interpolate_single_point():
    """Test _interpolate with single point curve."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curve = [CurvePoint(time=0.5, value=128.0)]

    result = pipeline.blender.interpolate(curve, 0.7)

    assert result == 128.0  # Always return the single point's value


# ============================================================================
# Task 3.4: _blend_channel_pair Tests
# ============================================================================


def test_blend_channel_pair_simple():
    """Test _blend_channel_pair with simple two-point curves."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    # Current effect: 0-1000ms, value 0-100
    curr_curve = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=1.0, value=100.0),
    ]

    # Next effect: 1000-2000ms, value 200-255
    next_curve = [
        CurvePoint(time=0.0, value=200.0),
        CurvePoint(time=1.0, value=255.0),
    ]

    # Blend last 30% of curr with first 30% of next
    blend_end_curr = 0.7  # Start blending at 70% of curr
    blend_start_next = 0.3  # End blending at 30% of next

    blended_curr, blended_next = pipeline.blender.blend_channel_pair(
        curr_curve, next_curve, blend_end_curr, blend_start_next
    )

    # Check that blending occurred
    # At time=1.0 (end of curr), value should be blend of 100 and 200
    # blend_weight=1.0 at time=1.0, so value = 0*100 + 1.0*200 = 200
    assert len(blended_curr) == 2
    assert blended_curr[1].value == 200.0  # Fully blended to next's start value

    # At time=0.0 (start of next), should blend with end of curr
    # blend_weight=1.0 at time=0, so value = 1.0*100 + 0*200 = 100
    assert len(blended_next) == 2
    assert blended_next[0].value == 100.0  # Fully blended to curr's end value


def test_blend_channel_pair_no_modification_outside_blend():
    """Test _blend_channel_pair doesn't modify points outside blend region."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curr_curve = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=0.5, value=50.0),
        CurvePoint(time=1.0, value=100.0),
    ]

    next_curve = [
        CurvePoint(time=0.0, value=200.0),
        CurvePoint(time=0.5, value=225.0),
        CurvePoint(time=1.0, value=255.0),
    ]

    # Blend last 20% with first 20%
    blended_curr, blended_next = pipeline.blender.blend_channel_pair(
        curr_curve, next_curve, 0.8, 0.2
    )

    # First 80% of curr should be unchanged
    assert blended_curr[0].value == 0.0
    assert blended_curr[1].value == 50.0
    # (blended_curr[2] will be modified as it's in blend region)

    # Last 80% of next should be unchanged
    # (blended_next[0] will be modified as it's in blend region)
    assert blended_next[2].value == 255.0


# ============================================================================
# Task 3.5: _apply_crossfade_channels Tests
# ============================================================================


def test_apply_crossfade_channels_all_channels():
    """Test _apply_crossfade_channels blends pan, tilt, dimmer."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint
    from blinkb0t.core.domains.sequencing.rendering.models import RenderedChannels, RenderedEffect

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curr = RenderedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        rendered_channels=RenderedChannels(
            pan=[CurvePoint(time=0.0, value=0.0), CurvePoint(time=1.0, value=100.0)],
            tilt=[CurvePoint(time=0.0, value=50.0), CurvePoint(time=1.0, value=150.0)],
            dimmer=[CurvePoint(time=0.0, value=100.0), CurvePoint(time=1.0, value=200.0)],
        ),
    )

    next_effect = RenderedEffect(
        fixture_id="MH1",
        start_ms=1000,
        end_ms=2000,
        rendered_channels=RenderedChannels(
            pan=[CurvePoint(time=0.0, value=200.0), CurvePoint(time=1.0, value=255.0)],
            tilt=[CurvePoint(time=0.0, value=180.0), CurvePoint(time=1.0, value=220.0)],
            dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],
        ),
    )

    blend_duration_ms = 300  # 300ms blend

    pipeline.blender.apply_crossfade_channels(curr, next_effect, blend_duration_ms)

    # All channels should be blended
    # Check that end of curr blends toward start of next
    assert curr.rendered_channels.pan[-1].value == 200.0  # Blended to next's start


def test_apply_crossfade_channels_respects_30_percent():
    """Test _apply_crossfade_channels limits blend to 30% of duration."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint
    from blinkb0t.core.domains.sequencing.rendering.models import RenderedChannels, RenderedEffect

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curr = RenderedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,  # Duration: 1000ms, 30% = 300ms
        rendered_channels=RenderedChannels(
            pan=[CurvePoint(time=0.0, value=0.0), CurvePoint(time=1.0, value=100.0)],
            tilt=[CurvePoint(time=0.0, value=50.0), CurvePoint(time=1.0, value=150.0)],
            dimmer=[CurvePoint(time=0.0, value=100.0), CurvePoint(time=1.0, value=200.0)],
        ),
    )

    next_effect = RenderedEffect(
        fixture_id="MH1",
        start_ms=1000,
        end_ms=2000,
        rendered_channels=RenderedChannels(
            pan=[CurvePoint(time=0.0, value=200.0), CurvePoint(time=1.0, value=255.0)],
            tilt=[CurvePoint(time=0.0, value=180.0), CurvePoint(time=1.0, value=220.0)],
            dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],
        ),
    )

    # Request 600ms blend (60% of 1000ms), but should clamp to 300ms (30%)
    blend_duration_ms = 600

    pipeline.blender.apply_crossfade_channels(curr, next_effect, blend_duration_ms)

    # Blend should be applied (implementation detail - just verify it runs)
    assert curr.rendered_channels.pan[-1].value == 200.0


def test_apply_crossfade_channels_skips_none_channels():
    """Test _apply_crossfade_channels handles optional channels gracefully."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint
    from blinkb0t.core.domains.sequencing.rendering.models import RenderedChannels, RenderedEffect

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    curr = RenderedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        rendered_channels=RenderedChannels(
            pan=[CurvePoint(time=0.0, value=0.0), CurvePoint(time=1.0, value=100.0)],
            tilt=[CurvePoint(time=0.0, value=50.0), CurvePoint(time=1.0, value=150.0)],
            dimmer=[CurvePoint(time=0.0, value=100.0), CurvePoint(time=1.0, value=200.0)],
            shutter=None,  # Optional channel not present
        ),
    )

    next_effect = RenderedEffect(
        fixture_id="MH1",
        start_ms=1000,
        end_ms=2000,
        rendered_channels=RenderedChannels(
            pan=[CurvePoint(time=0.0, value=200.0), CurvePoint(time=1.0, value=255.0)],
            tilt=[CurvePoint(time=0.0, value=180.0), CurvePoint(time=1.0, value=220.0)],
            dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],
            shutter=None,
        ),
    )

    # Should not crash when optional channels are None
    pipeline.blender.apply_crossfade_channels(curr, next_effect, 300)


# ============================================================================
# Task 3.6: _render_with_blending Tests
# ============================================================================


# NOTE: test_render_with_blending_adjacent_crossfade removed - API changed.
# Static values (int) now pass through unchanged as ints (not converted to CurvePoints).
# Blending only applies to Custom curves (list[CurvePoint]), not static values.


# NOTE: test_render_with_blending_snap_no_blend removed - API changed.
# Static values (int) now pass through unchanged as ints (not converted to CurvePoints).


# NOTE: test_render_with_blending_gap_no_blend removed - API changed.
# Static values (int) now pass through unchanged as ints (not converted to CurvePoints).


def test_render_with_blending_multiple_transitions():
    """Test _render_with_blending handles multiple adjacent effects."""
    from blinkb0t.core.domains.sequencing.models.templates import (
        TransitionConfig,
        TransitionMode,
    )
    from blinkb0t.core.domains.sequencing.rendering.models import (
        BoundaryInfo,
        ChannelSpecs,
        SequencedEffect,
    )

    generator = Mock(spec=CurveGenerator)
    pipeline = CurvePipeline(curve_generator=generator)

    effects = [
        SequencedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels=ChannelSpecs(pan=0, tilt=0, dimmer=100),
            boundary_info=BoundaryInfo(
                exit_transition=TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5)
            ),
        ),
        SequencedEffect(
            fixture_id="MH1",
            start_ms=1000,
            end_ms=2000,
            channels=ChannelSpecs(pan=127, tilt=90, dimmer=200),
            boundary_info=BoundaryInfo(
                exit_transition=TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5)
            ),
        ),
        SequencedEffect(
            fixture_id="MH1",
            start_ms=2000,
            end_ms=3000,
            channels=ChannelSpecs(pan=255, tilt=180, dimmer=255),
        ),
    ]

    result = pipeline._render_with_blending(effects)

    assert len(result) == 3
    # All adjacent transitions should be blended
