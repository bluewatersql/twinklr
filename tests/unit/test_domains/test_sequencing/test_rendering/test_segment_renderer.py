"""Tests for SegmentRenderer - per-fixture segment rendering.

TDD Approach:
1. Test initialization
2. Test target expansion
3. Test boundary detection
4. Test per-fixture rendering
5. Test full render_segments flow
"""

import pytest

from blinkb0t.core.config.fixtures import (
    DmxMapping,
    FixtureConfig,
    FixtureGroup,
    FixtureInstance,
)
from blinkb0t.core.domains.sequencing.models.poses import PoseID
from blinkb0t.core.domains.sequencing.models.timeline import TemplateStepSegment
from blinkb0t.core.domains.sequencing.moving_heads.dimmer_handler import DimmerHandler
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.engine import (
    GeometryEngine,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.handlers.default import (
    DefaultMovementHandler,
)
from blinkb0t.core.domains.sequencing.poses.resolver import PoseResolver
from blinkb0t.core.domains.sequencing.rendering.segment_renderer import SegmentRenderer


class TestSegmentRendererInitialization:
    """Test SegmentRenderer initialization."""

    def test_init_with_all_dependencies(self):
        """Test SegmentRenderer initializes with all required dependencies."""
        # Create minimal fixture group
        fixture_group = FixtureGroup(
            group_id="test_group",
            name="test_group",
            fixtures=[
                FixtureInstance(
                    fixture_id="MH1",
                    config=FixtureConfig(
                        fixture_id="test_fixture",
                        pan_range_deg=540.0,
                        tilt_range_deg=270.0,
                        dmx_mapping=DmxMapping(
                            pan_channel=1,
                            tilt_channel=3,
                            dimmer_channel=5,
                        ),
                    ),
                    xlights_model_name="Dmx MH1",
                )
            ],
        )

        pose_resolver = PoseResolver()
        movement_handler = DefaultMovementHandler()
        geometry_engine = GeometryEngine()
        dimmer_handler = DimmerHandler()

        # Should initialize without error
        renderer = SegmentRenderer(
            fixture_group=fixture_group,
            pose_resolver=pose_resolver,
            movement_handler=movement_handler,
            geometry_engine=geometry_engine,
            dimmer_handler=dimmer_handler,
        )

        assert renderer.fixture_group == fixture_group
        assert renderer.pose_resolver == pose_resolver
        assert renderer.movement_handler == movement_handler
        assert renderer.geometry_engine == geometry_engine
        assert renderer.dimmer_handler == dimmer_handler


class TestTargetExpansion:
    """Test target expansion to fixtures."""

    @pytest.fixture
    def fixture_group(self):
        """Create a fixture group with 3 fixtures."""
        return FixtureGroup(
            group_id="test_group",
            name="test_group",
            fixtures=[
                FixtureInstance(
                    fixture_id=f"MH{i}",
                    config=FixtureConfig(
                        fixture_id=f"test_fixture_{i}",
                        pan_range_deg=540.0,
                        tilt_range_deg=270.0,
                        dmx_mapping=DmxMapping(
                            pan_channel=1 + i * 10,
                            tilt_channel=3 + i * 10,
                            dimmer_channel=5 + i * 10,
                        ),
                    ),
                    xlights_model_name=f"Dmx MH{i}",
                )
                for i in range(1, 4)
            ],
        )

    @pytest.fixture
    def renderer(self, fixture_group):
        """Create SegmentRenderer instance."""
        return SegmentRenderer(
            fixture_group=fixture_group,
            pose_resolver=PoseResolver(),
            movement_handler=DefaultMovementHandler(),
            geometry_engine=GeometryEngine(),
            dimmer_handler=DimmerHandler(),
        )

    def test_expand_target_all(self, renderer, fixture_group):
        """Test expanding 'all' target to all fixtures."""
        fixtures = renderer._expand_target("all")
        assert len(fixtures) == 3
        assert [f.fixture_id for f in fixtures] == ["MH1", "MH2", "MH3"]

    def test_expand_target_single_fixture(self, renderer):
        """Test expanding single fixture ID."""
        fixtures = renderer._expand_target("MH2")
        assert len(fixtures) == 1
        assert fixtures[0].fixture_id == "MH2"

    def test_expand_target_fixture_range(self, renderer):
        """Test expanding fixture range (e.g., 'MH1-MH3')."""
        fixtures = renderer._expand_target("MH1-MH3")
        assert len(fixtures) == 3
        assert [f.fixture_id for f in fixtures] == ["MH1", "MH2", "MH3"]

    def test_expand_target_multiple_fixtures(self, renderer):
        """Test expanding comma-separated fixture IDs."""
        fixtures = renderer._expand_target("MH1,MH3")
        assert len(fixtures) == 2
        assert [f.fixture_id for f in fixtures] == ["MH1", "MH3"]

    def test_expand_target_unknown_fixture(self, renderer):
        """Test expanding unknown fixture ID raises error."""
        with pytest.raises(ValueError, match="Unknown fixture"):
            renderer._expand_target("MH99")


class TestBoundaryDetection:
    """Test section boundary detection."""

    @pytest.fixture
    def renderer(self):
        """Create minimal SegmentRenderer."""
        fixture_group = FixtureGroup(
            group_id="test_group",
            name="test_group",
            fixtures=[
                FixtureInstance(
                    fixture_id="MH1",
                    config=FixtureConfig(
                        fixture_id="test_fixture",
                        pan_range_deg=540.0,
                        tilt_range_deg=270.0,
                        dmx_mapping=DmxMapping(
                            pan_channel=1,
                            tilt_channel=3,
                            dimmer_channel=5,
                        ),
                    ),
                    xlights_model_name="Dmx MH1",
                )
            ],
        )
        return SegmentRenderer(
            fixture_group=fixture_group,
            pose_resolver=PoseResolver(),
            movement_handler=DefaultMovementHandler(),
            geometry_engine=GeometryEngine(),
            dimmer_handler=DimmerHandler(),
        )

    def test_is_first_segment(self, renderer):
        """Test detecting first segment in section."""
        segment = TemplateStepSegment(
            step_id="intro_all_step_0",
            section_id="intro",
            start_ms=0,
            end_ms=1000,
            template_id="test_template",
            movement_id="PAN_SWEEP",
            movement_params={},
            dimmer_id="FADE_IN",
            dimmer_params={},
            base_pose=PoseID.FORWARD,
            target="all",
        )

        section_info = {
            "intro": (0, 4000),  # Section spans 0-4000ms
        }

        # Segment starts at section start (0ms)
        is_first = renderer._is_first_segment(segment, section_info)
        assert is_first is True

    def test_is_last_segment(self, renderer):
        """Test detecting last segment in section."""
        segment = TemplateStepSegment(
            step_id="intro_all_step_3",
            section_id="intro",
            start_ms=3000,
            end_ms=4000,
            template_id="test_template",
            movement_id="PAN_SWEEP",
            movement_params={},
            dimmer_id="FADE_OUT",
            dimmer_params={},
            base_pose=PoseID.FORWARD,
            target="all",
        )

        section_info = {
            "intro": (0, 4000),  # Section spans 0-4000ms
        }

        # Segment ends at section end (4000ms)
        is_last = renderer._is_last_segment(segment, section_info)
        assert is_last is True

    def test_middle_segment_not_boundary(self, renderer):
        """Test middle segment is not a boundary."""
        segment = TemplateStepSegment(
            step_id="intro_all_step_1",
            section_id="intro",
            start_ms=1000,
            end_ms=2000,
            template_id="test_template",
            movement_id="PAN_SWEEP",
            movement_params={},
            dimmer_id="HOLD",
            dimmer_params={},
            base_pose=PoseID.FORWARD,
            target="all",
        )

        section_info = {
            "intro": (0, 4000),
        }

        is_first = renderer._is_first_segment(segment, section_info)
        is_last = renderer._is_last_segment(segment, section_info)

        assert is_first is False
        assert is_last is False


class TestBoundaryInfoCreation:
    """Test BoundaryInfo creation."""

    @pytest.fixture
    def renderer(self):
        """Create minimal SegmentRenderer."""
        fixture_group = FixtureGroup(
            group_id="test_group",
            name="test_group",
            fixtures=[
                FixtureInstance(
                    fixture_id="MH1",
                    config=FixtureConfig(
                        fixture_id="test_fixture",
                        pan_range_deg=540.0,
                        tilt_range_deg=270.0,
                        dmx_mapping=DmxMapping(
                            pan_channel=1,
                            tilt_channel=3,
                            dimmer_channel=5,
                        ),
                    ),
                    xlights_model_name="Dmx MH1",
                )
            ],
        )
        return SegmentRenderer(
            fixture_group=fixture_group,
            pose_resolver=PoseResolver(),
            movement_handler=DefaultMovementHandler(),
            geometry_engine=GeometryEngine(),
            dimmer_handler=DimmerHandler(),
        )

    def test_create_boundary_info_first_segment(self, renderer):
        """Test BoundaryInfo for first segment."""
        boundary_info = renderer._create_boundary_info(
            is_first=True,
            is_last=False,
            section_id="intro",
        )

        assert boundary_info.is_section_start is True
        assert boundary_info.is_section_end is False
        assert boundary_info.section_id == "intro"
        assert boundary_info.is_gap_fill is False

    def test_create_boundary_info_last_segment(self, renderer):
        """Test BoundaryInfo for last segment."""
        boundary_info = renderer._create_boundary_info(
            is_first=False,
            is_last=True,
            section_id="outro",
        )

        assert boundary_info.is_section_start is False
        assert boundary_info.is_section_end is True
        assert boundary_info.section_id == "outro"

    def test_create_boundary_info_middle_segment(self, renderer):
        """Test BoundaryInfo for middle segment."""
        boundary_info = renderer._create_boundary_info(
            is_first=False,
            is_last=False,
            section_id="verse",
        )

        assert boundary_info.is_section_start is False
        assert boundary_info.is_section_end is False
        assert boundary_info.section_id == "verse"


class TestRenderSegmentForFixture:
    """Test _render_segment_for_fixture method."""

    @pytest.fixture
    def renderer(self):
        """Create minimal SegmentRenderer."""
        fixture_group = FixtureGroup(
            group_id="test_group",
            name="test_group",
            fixtures=[
                FixtureInstance(
                    fixture_id="MH1",
                    config=FixtureConfig(
                        fixture_id="test_fixture",
                        pan_range_deg=540.0,
                        tilt_range_deg=270.0,
                        dmx_mapping=DmxMapping(
                            pan_channel=1,
                            tilt_channel=3,
                            dimmer_channel=5,
                        ),
                    ),
                    xlights_model_name="Dmx MH1",
                )
            ],
        )
        return SegmentRenderer(
            fixture_group=fixture_group,
            pose_resolver=PoseResolver(),
            movement_handler=DefaultMovementHandler(),
            geometry_engine=GeometryEngine(),
            dimmer_handler=DimmerHandler(),
        )

    def test_render_segment_basic(self, renderer):
        """Test rendering a basic segment."""
        segment = TemplateStepSegment(
            step_id="test_step",
            section_id="intro",
            start_ms=0,
            end_ms=1000,
            template_id="test_template",
            movement_id="PAN_SWEEP",
            movement_params={},
            dimmer_id="full",
            dimmer_params={},
            base_pose=PoseID.FORWARD,
            target="all",
        )

        fixture = renderer.fixture_group.fixtures[0]

        effect = renderer._render_segment_for_fixture(
            segment=segment,
            fixture=fixture,
            fixture_idx=0,
            total_fixtures=1,
            is_first=True,
            is_last=False,
            channel_overlay=None,
        )

        # Verify effect structure
        assert effect.fixture_id == "MH1"
        assert effect.start_ms == 0
        assert effect.end_ms == 1000
        assert effect.channels.pan is not None
        assert effect.channels.tilt is not None
        assert effect.channels.dimmer is not None
        assert effect.boundary_info.is_section_start is True
        assert effect.boundary_info.is_section_end is False

    def test_render_segment_with_dimmer(self, renderer):
        """Test segment with dimmer pattern."""
        segment = TemplateStepSegment(
            step_id="test_step",
            section_id="verse",
            start_ms=1000,
            end_ms=2000,
            template_id="test_template",
            movement_id="HOLD",
            movement_params={},
            dimmer_id="full",
            dimmer_params={},
            base_pose=PoseID.UP,
            target="all",
        )

        fixture = renderer.fixture_group.fixtures[0]

        effect = renderer._render_segment_for_fixture(
            segment=segment,
            fixture=fixture,
            fixture_idx=0,
            total_fixtures=1,
            is_first=False,
            is_last=False,
            channel_overlay=None,
        )

        # Dimmer should be full (255)
        assert effect.channels.dimmer == 255

    def test_render_segment_with_channel_overlay(self, renderer):
        """Test segment with channel overlay."""
        from blinkb0t.core.domains.sequencing.rendering.models import ChannelOverlay

        segment = TemplateStepSegment(
            step_id="test_step",
            section_id="chorus",
            start_ms=2000,
            end_ms=3000,
            template_id="test_template",
            movement_id="CIRCLE",
            movement_params={},
            dimmer_id="hold",
            dimmer_params={"base_pct": 80},
            base_pose=PoseID.AUDIENCE_CENTER,
            target="all",
        )

        fixture = renderer.fixture_group.fixtures[0]

        channel_overlay = ChannelOverlay(
            shutter=255,  # Open
            color=(255, 0, 0),  # Red
            gobo=1,  # Gobo 1
        )

        effect = renderer._render_segment_for_fixture(
            segment=segment,
            fixture=fixture,
            fixture_idx=0,
            total_fixtures=1,
            is_first=False,
            is_last=True,
            channel_overlay=channel_overlay,
        )

        # Appearance channels from overlay
        assert effect.channels.shutter == 255
        assert effect.channels.color == (255, 0, 0)
        assert effect.channels.gobo == 1

        # Dimmer at 80%
        assert effect.channels.dimmer == int(0.8 * 255)

        # Boundary info
        assert effect.boundary_info.is_section_end is True


# Integration test placeholder - will be implemented after basic methods work
class TestRenderSegmentsIntegration:
    """Integration tests for full render_segments flow."""

    def test_render_segments_placeholder(self):
        """Placeholder for integration test."""
        # Will implement after basic methods are working
        pytest.skip("Integration test - implement after basic methods work")
