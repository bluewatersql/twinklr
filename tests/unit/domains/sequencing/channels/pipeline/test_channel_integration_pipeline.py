"""Tests for ChannelIntegrationPipeline."""

from unittest.mock import Mock

import pytest

from blinkb0t.core.domains.sequencing.channels.pipeline.pipeline import (
    ChannelIntegrationPipeline,
)
from blinkb0t.core.domains.sequencing.models.channels import ChannelEffect, SequencedEffect


class TestChannelIntegrationPipeline:
    """Test ChannelIntegrationPipeline orchestrator."""

    @pytest.fixture
    def pipeline(self):
        """Create pipeline instance."""
        return ChannelIntegrationPipeline()

    @pytest.fixture
    def mock_fixture_group(self, mock_fixture):
        """Create mock FixtureGroup."""
        from blinkb0t.core.config.fixtures import FixtureGroup

        group = Mock(spec=FixtureGroup)
        group.group_id = "ALL"
        group.fixtures = [mock_fixture]
        group.xlights_group = "Dmx ALL"
        group.expand_fixtures.return_value = [mock_fixture]
        return group

    def test_pipeline_initialization(self, pipeline):
        """Test pipeline initializes all components."""
        assert pipeline.boundary_detector is not None
        assert pipeline.effect_splitter is not None
        assert pipeline.channel_filler is not None
        assert pipeline.gap_detector is not None
        assert pipeline.gap_filler is not None

    def test_process_section_single_movement_effect(
        self, pipeline, mock_channel_state, mock_fixture_group
    ):
        """Test processing section with single movement effect."""
        # Create a simple movement effect
        movement_effects = [
            SequencedEffect(
                targets=["ALL"],
                channels={"pan": mock_channel_state, "tilt": mock_channel_state},
                start_ms=0,
                end_ms=1000,
            )
        ]

        dmx_effects = pipeline.process_section(
            movement_effects=movement_effects,
            channel_effects=[],
            fixtures=mock_fixture_group,
            section_start_ms=0,
            section_end_ms=1000,
        )

        # Should have effects for the fixture
        assert len(dmx_effects) >= 1
        assert all(e.fixture_id == "MH1" for e in dmx_effects)

    def test_process_section_with_gaps(self, pipeline, mock_channel_state, mock_fixture_group):
        """Test processing section with gaps."""
        # Create effects with a gap
        movement_effects = [
            SequencedEffect(
                targets=["ALL"],
                channels={"pan": mock_channel_state},
                start_ms=100,
                end_ms=200,
            ),
            SequencedEffect(
                targets=["ALL"],
                channels={"pan": mock_channel_state},
                start_ms=300,
                end_ms=400,
            ),
        ]

        dmx_effects = pipeline.process_section(
            movement_effects=movement_effects,
            channel_effects=[],
            fixtures=mock_fixture_group,
            section_start_ms=0,
            section_end_ms=500,
        )

        # Should have gap-filling effects
        assert len(dmx_effects) > 2  # Original effects + gap fills

        # Check that gaps are filled
        gap_fills = [e for e in dmx_effects if e.metadata.get("type") == "gap_fill"]
        assert len(gap_fills) > 0

    def test_process_section_empty_effects(self, pipeline, mock_fixture_group):
        """Test processing section with no effects creates gap fill for entire section."""
        dmx_effects = pipeline.process_section(
            movement_effects=[],
            channel_effects=[],
            fixtures=mock_fixture_group,
            section_start_ms=0,
            section_end_ms=1000,
        )

        # Should have gap fill for entire section
        assert len(dmx_effects) == 1
        assert dmx_effects[0].metadata["type"] == "gap_fill"
        assert dmx_effects[0].start_ms == 0
        assert dmx_effects[0].end_ms == 1000

    def test_process_section_with_channel_effects(
        self, pipeline, mock_channel_state, mock_fixture_group
    ):
        """Test processing section with channel effects."""
        movement_effects = [
            SequencedEffect(
                targets=["ALL"],
                channels={"pan": mock_channel_state, "tilt": mock_channel_state},
                start_ms=0,
                end_ms=1000,
            )
        ]

        channel_effects = [
            ChannelEffect(
                fixture_id="MH1",
                channel_name="shutter",
                start_time_ms=0,
                end_time_ms=1000,
                dmx_values=[255],
                value_curve=None,
            )
        ]

        dmx_effects = pipeline.process_section(
            movement_effects=movement_effects,
            channel_effects=channel_effects,
            fixtures=mock_fixture_group,
            section_start_ms=0,
            section_end_ms=1000,
        )

        # Should have effects with shutter channel
        assert len(dmx_effects) >= 1
        # Check that at least one effect has shutter
        has_shutter = any("shutter" in e.channels for e in dmx_effects)
        assert has_shutter

    def test_process_section_multiple_fixtures(self, pipeline, mock_channel_state):
        """Test processing section with multiple fixtures."""
        from unittest.mock import Mock

        from blinkb0t.core.config.fixtures import FixtureGroup

        # Create two fixtures
        fixture1 = Mock()
        fixture1.fixture_id = "MH1"
        fixture1.config = Mock()
        fixture1.config.dmx_mapping = Mock()
        fixture1.config.dmx_mapping.pan = 1
        fixture1.config.dmx_mapping.tilt = 2
        fixture1.config.dmx_mapping.dimmer = 3
        fixture1.config.dmx_mapping.shutter = 4
        fixture1.config.dmx_mapping.color = 5
        fixture1.config.dmx_mapping.gobo = 6
        fixture1.config.degrees_to_dmx = Mock(return_value=(128, 64))

        fixture2 = Mock()
        fixture2.fixture_id = "MH2"
        fixture2.config = Mock()
        fixture2.config.dmx_mapping = Mock()
        fixture2.config.dmx_mapping.pan = 7
        fixture2.config.dmx_mapping.tilt = 8
        fixture2.config.dmx_mapping.dimmer = 9
        fixture2.config.dmx_mapping.shutter = 10
        fixture2.config.dmx_mapping.color = 11
        fixture2.config.dmx_mapping.gobo = 12
        fixture2.config.degrees_to_dmx = Mock(return_value=(128, 64))

        group = Mock(spec=FixtureGroup)
        group.group_id = "ALL"
        group.fixtures = [fixture1, fixture2]
        group.xlights_group = "Dmx ALL"
        group.expand_fixtures.return_value = [fixture1, fixture2]

        movement_effects = [
            SequencedEffect(
                targets=["ALL"],
                channels={"pan": mock_channel_state},
                start_ms=0,
                end_ms=1000,
            )
        ]

        dmx_effects = pipeline.process_section(
            movement_effects=movement_effects,
            channel_effects=[],
            fixtures=group,
            section_start_ms=0,
            section_end_ms=1000,
        )

        # Should have effects for both fixtures
        fixture_ids = {e.fixture_id for e in dmx_effects}
        assert "MH1" in fixture_ids
        assert "MH2" in fixture_ids

    def test_process_section_fills_all_channels(
        self, pipeline, mock_channel_state, mock_fixture_group
    ):
        """Test that all channels are filled (no missing channels)."""
        # Effect with only pan
        movement_effects = [
            SequencedEffect(
                targets=["ALL"],
                channels={"pan": mock_channel_state},
                start_ms=0,
                end_ms=1000,
            )
        ]

        dmx_effects = pipeline.process_section(
            movement_effects=movement_effects,
            channel_effects=[],
            fixtures=mock_fixture_group,
            section_start_ms=0,
            section_end_ms=1000,
        )

        # All effects should have complete channel sets
        for effect in dmx_effects:
            # Should have at least pan, tilt
            assert "pan" in effect.channels
            assert "tilt" in effect.channels
            # Should have filled channels (dimmer, shutter, color, gobo)
            assert len(effect.channels) > 2
