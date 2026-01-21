"""Tests for GapRenderer - gap segment rendering.

TDD Approach:
1. Test initialization
2. Test basic gap rendering
3. Test channel overlay application
4. Test multiple fixtures
5. Test multiple gaps
"""

import pytest

from blinkb0t.core.config.fixtures import (
    DmxMapping,
    FixtureConfig,
    FixtureGroup,
    FixtureInstance,
)
from blinkb0t.core.domains.sequencing.models.timeline import GapSegment
from blinkb0t.core.domains.sequencing.rendering.gap_renderer import GapRenderer
from blinkb0t.core.domains.sequencing.rendering.models import ChannelOverlay


class TestGapRendererInitialization:
    """Test GapRenderer initialization."""

    def test_init(self):
        """Test GapRenderer initializes correctly."""
        renderer = GapRenderer()
        assert renderer is not None


class TestGapRendering:
    """Test gap rendering to per-fixture effects."""

    @pytest.fixture
    def fixture_group(self):
        """Create a fixture group with 2 fixtures."""
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
                for i in range(1, 3)
            ],
        )

    @pytest.fixture
    def renderer(self):
        """Create GapRenderer instance."""
        return GapRenderer()

    def test_render_single_gap_single_fixture(self, renderer, fixture_group):
        """Test rendering a single gap for one fixture."""
        # Create a single fixture group
        single_fixture_group = FixtureGroup(
            group_id="test_group",
            name="test_group",
            fixtures=[fixture_group.fixtures[0]],
        )

        gap = GapSegment(
            start_ms=1000,
            end_ms=2000,
            gap_type="inter_section",
            section_id="intro",
        )

        effects = renderer.render_gaps(
            gaps=[gap],
            fixture_group=single_fixture_group,
            channel_overlays={},
        )

        # Should return 1 effect (1 gap x 1 fixture)
        assert len(effects) == 1
        effect = effects[0]

        # Verify effect properties
        assert effect.fixture_id == "MH1"
        assert effect.start_ms == 1000
        assert effect.end_ms == 2000

        # Verify channels - should be at SOFT_HOME with dimmer off
        assert isinstance(effect.channels.pan, int)
        assert isinstance(effect.channels.tilt, int)
        assert effect.channels.dimmer == 0  # Off during gap

        # Verify boundary info
        assert effect.boundary_info.is_gap_fill is True
        assert effect.boundary_info.gap_type == "inter_section"
        assert effect.boundary_info.section_id == "intro"

    def test_render_single_gap_multiple_fixtures(self, renderer, fixture_group):
        """Test rendering a single gap for multiple fixtures."""
        gap = GapSegment(
            start_ms=2000,
            end_ms=3000,
            gap_type="intra_section",
            section_id="verse",
        )

        effects = renderer.render_gaps(
            gaps=[gap],
            fixture_group=fixture_group,
            channel_overlays={},
        )

        # Should return 2 effects (1 gap x 2 fixtures)
        assert len(effects) == 2

        # Verify both fixtures
        assert effects[0].fixture_id == "MH1"
        assert effects[1].fixture_id == "MH2"

        # Both should have dimmer off
        assert effects[0].channels.dimmer == 0
        assert effects[1].channels.dimmer == 0

    def test_render_multiple_gaps(self, renderer, fixture_group):
        """Test rendering multiple gaps."""
        gaps = [
            GapSegment(
                start_ms=1000,
                end_ms=2000,
                gap_type="inter_section",
                section_id="intro",
            ),
            GapSegment(
                start_ms=5000,
                end_ms=6000,
                gap_type="inter_section",
                section_id="chorus",
            ),
        ]

        effects = renderer.render_gaps(
            gaps=gaps,
            fixture_group=fixture_group,
            channel_overlays={},
        )

        # Should return 4 effects (2 gaps x 2 fixtures)
        assert len(effects) == 4

        # Verify timing
        assert effects[0].start_ms == 1000
        assert effects[0].end_ms == 2000
        assert effects[2].start_ms == 5000
        assert effects[2].end_ms == 6000

    def test_render_gap_with_channel_overlay(self, renderer, fixture_group):
        """Test gap rendering with channel overlay."""
        gap = GapSegment(
            start_ms=3000,
            end_ms=4000,
            gap_type="intra_section",
            section_id="bridge",
        )

        channel_overlays = {
            "bridge": ChannelOverlay(
                shutter=128,  # Slow strobe
                color=(0, 0, 255),  # Blue
                gobo=2,  # Gobo 2
            )
        }

        effects = renderer.render_gaps(
            gaps=[gap],
            fixture_group=fixture_group,
            channel_overlays=channel_overlays,
        )

        # Verify appearance channels from overlay
        effect = effects[0]
        assert effect.channels.shutter == 128
        assert effect.channels.color == (0, 0, 255)
        assert effect.channels.gobo == 2

        # Movement should still be SOFT_HOME
        assert isinstance(effect.channels.pan, int)
        assert isinstance(effect.channels.tilt, int)

        # Dimmer still off
        assert effect.channels.dimmer == 0

    def test_render_gap_no_overlay(self, renderer, fixture_group):
        """Test gap rendering without channel overlay."""
        gap = GapSegment(
            start_ms=4000,
            end_ms=5000,
            gap_type="end_of_song",
            section_id=None,
        )

        effects = renderer.render_gaps(
            gaps=[gap],
            fixture_group=fixture_group,
            channel_overlays={},
        )

        # Appearance channels should be None
        effect = effects[0]
        assert effect.channels.shutter is None
        assert effect.channels.color is None
        assert effect.channels.gobo is None

    def test_get_gap_overlay_with_section_id(self, renderer):
        """Test _get_gap_overlay finds overlay by section ID."""
        gap = GapSegment(
            start_ms=1000,
            end_ms=2000,
            gap_type="inter_section",
            section_id="intro",
        )

        overlays = {
            "intro": ChannelOverlay(shutter=255, color=255, gobo=1),
            "verse": ChannelOverlay(shutter=128, color=128, gobo=2),
        }

        overlay = renderer._get_gap_overlay(gap, overlays)
        assert overlay is not None
        assert overlay.shutter == 255  # intro overlay

    def test_get_gap_overlay_fallback(self, renderer):
        """Test _get_gap_overlay falls back to first overlay."""
        gap = GapSegment(
            start_ms=1000,
            end_ms=2000,
            gap_type="inter_section",
            section_id="unknown_section",
        )

        overlays = {
            "intro": ChannelOverlay(shutter=255, color=255, gobo=1),
        }

        overlay = renderer._get_gap_overlay(gap, overlays)
        assert overlay is not None
        assert overlay.shutter == 255  # First available overlay

    def test_get_gap_overlay_no_overlays(self, renderer):
        """Test _get_gap_overlay returns None when no overlays."""
        gap = GapSegment(
            start_ms=1000,
            end_ms=2000,
            gap_type="end_of_song",
            section_id=None,
        )

        overlay = renderer._get_gap_overlay(gap, {})
        assert overlay is None
