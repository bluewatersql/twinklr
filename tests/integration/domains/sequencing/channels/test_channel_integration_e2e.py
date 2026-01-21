"""End-to-end integration tests for channel integration pipeline."""

from unittest.mock import Mock

import pytest

from blinkb0t.core.config.fixtures import FixtureGroup
from blinkb0t.core.domains.sequencing.channels.pipeline import (
    ChannelIntegrationPipeline,
    XsqAdapter,
)
from blinkb0t.core.domains.sequencing.infrastructure.xsq import EffectPlacement
from blinkb0t.core.domains.sequencing.models.channels import ChannelEffect, SequencedEffect


@pytest.fixture
def create_fixture_group():
    """Factory to create fixture groups for testing."""

    def _create(num_fixtures=2):
        from blinkb0t.core.config.fixtures import (
            ChannelInversions,
            DmxMapping,
            FixtureCapabilities,
            FixtureConfig,
            FixtureInstance,
            MovementLimits,
            MovementSpeed,
            Orientation,
            PanTiltRange,
        )

        fixtures = []
        for i in range(1, num_fixtures + 1):
            fixture = Mock(spec=FixtureInstance)
            fixture.fixture_id = f"MH{i}"
            fixture.xlights_model_name = f"Dmx MH{i}"
            fixture.config = Mock(spec=FixtureConfig)
            fixture.config.fixture_id = f"MH{i}"
            fixture.config.dmx_mapping = Mock(spec=DmxMapping)
            fixture.config.dmx_mapping.pan_channel = 1 + (i - 1) * 6
            fixture.config.dmx_mapping.tilt_channel = 2 + (i - 1) * 6
            fixture.config.dmx_mapping.dimmer_channel = 3 + (i - 1) * 6
            fixture.config.dmx_mapping.shutter = 4 + (i - 1) * 6
            fixture.config.dmx_mapping.color = 5 + (i - 1) * 6
            fixture.config.dmx_mapping.gobo = 6 + (i - 1) * 6
            fixture.config.dmx_mapping.use_16bit_pan_tilt = False
            fixture.config.dmx_mapping.pan_fine_channel = None
            fixture.config.dmx_mapping.tilt_fine_channel = None
            fixture.config.inversions = ChannelInversions()
            fixture.config.limits = MovementLimits()
            fixture.config.capabilities = FixtureCapabilities()
            fixture.config.movement_speed = MovementSpeed()
            fixture.config.pan_tilt_range = PanTiltRange()
            fixture.config.orientation = Orientation()
            # Mock degrees_to_dmx
            fixture.config.degrees_to_dmx = Mock(return_value=(128, 64))
            fixtures.append(fixture)

        group = FixtureGroup(group_id="ALL", fixtures=fixtures, xlights_group="Dmx ALL")
        return group

    return _create


class TestChannelIntegrationE2E:
    """End-to-end integration tests for channel integration pipeline."""

    def test_e2e_single_movement_effect(self, create_fixture_group):
        """Test E2E: Single movement effect → DmxEffect → EffectPlacement."""
        # Arrange
        fixtures = create_fixture_group(num_fixtures=1)
        pipeline = ChannelIntegrationPipeline()
        adapter = XsqAdapter()

        from blinkb0t.core.domains.sequencing.channels.state import ChannelState

        state = ChannelState(fixture=fixtures.fixtures[0])
        state.set_channel("pan", 128)
        state.set_channel("tilt", 64)

        movement_effects = [
            SequencedEffect(
                targets=["ALL"],
                channels={"pan": state, "tilt": state},
                start_ms=0,
                end_ms=1000,
            )
        ]

        # Act
        dmx_effects = pipeline.process_section(
            movement_effects=movement_effects,
            channel_effects=[],
            fixtures=fixtures,
            section_start_ms=0,
            section_end_ms=1000,
        )

        placements = adapter.convert(dmx_effects, fixtures)

        # Assert
        # With only 1 fixture, should create individual placement (not group)
        assert len(placements) >= 1
        assert all(isinstance(p, EffectPlacement) for p in placements)
        element_names = {p.element_name for p in placements}
        assert "Dmx MH1" in element_names  # Individual fixture (no group for single fixture)
        assert all(p.effect_name == "DMX" for p in placements)

    def test_e2e_multiple_fixtures_with_gaps(self, create_fixture_group):
        """Test E2E: Multiple fixtures with gaps → complete timeline."""
        # Arrange
        fixtures = create_fixture_group(num_fixtures=2)
        pipeline = ChannelIntegrationPipeline()

        from blinkb0t.core.domains.sequencing.channels.state import ChannelState

        state1 = ChannelState(fixture=fixtures.fixtures[0])
        state1.set_channel("pan", 100)

        state2 = ChannelState(fixture=fixtures.fixtures[1])
        state2.set_channel("pan", 200)

        # Create effects with gaps
        movement_effects = [
            SequencedEffect(
                targets=["ALL"],
                channels={"pan": state1},
                start_ms=100,
                end_ms=200,
            ),
            SequencedEffect(
                targets=["ALL"],
                channels={"pan": state2},
                start_ms=300,
                end_ms=400,
            ),
        ]

        # Act
        dmx_effects = pipeline.process_section(
            movement_effects=movement_effects,
            channel_effects=[],
            fixtures=fixtures,
            section_start_ms=0,
            section_end_ms=500,
        )

        # Assert
        # Should have effects for both fixtures
        fixture_ids = {e.fixture_id for e in dmx_effects}
        assert "MH1" in fixture_ids
        assert "MH2" in fixture_ids

        # Should have gap fills
        gap_fills = [e for e in dmx_effects if e.metadata.get("type") == "gap_fill"]
        assert len(gap_fills) > 0

        # Timeline should be complete (no gaps)
        for fixture_id in ["MH1", "MH2"]:
            fixture_effects = sorted(
                [e for e in dmx_effects if e.fixture_id == fixture_id], key=lambda e: e.start_ms
            )
            # Check continuity
            for i in range(len(fixture_effects) - 1):
                assert fixture_effects[i].end_ms == fixture_effects[i + 1].start_ms

    def test_e2e_movement_plus_channel_effects(self, create_fixture_group):
        """Test E2E: Movement + channel effects integration."""
        # Arrange
        fixtures = create_fixture_group(num_fixtures=1)
        pipeline = ChannelIntegrationPipeline()

        from blinkb0t.core.domains.sequencing.channels.state import ChannelState

        movement_state = ChannelState(fixture=fixtures.fixtures[0])
        movement_state.set_channel("pan", 128)
        movement_state.set_channel("tilt", 64)

        movement_effects = [
            SequencedEffect(
                targets=["ALL"],
                channels={"pan": movement_state, "tilt": movement_state},
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

        # Act
        dmx_effects = pipeline.process_section(
            movement_effects=movement_effects,
            channel_effects=channel_effects,
            fixtures=fixtures,
            section_start_ms=0,
            section_end_ms=1000,
        )

        # Assert
        assert len(dmx_effects) >= 1
        # Check that effects have shutter channel
        has_shutter = any("shutter" in e.channels for e in dmx_effects)
        assert has_shutter

    def test_e2e_empty_section_creates_gap_fill(self, create_fixture_group):
        """Test E2E: Empty section fills entire duration with soft home."""
        # Arrange
        fixtures = create_fixture_group(num_fixtures=1)
        pipeline = ChannelIntegrationPipeline()
        adapter = XsqAdapter()

        # Act
        dmx_effects = pipeline.process_section(
            movement_effects=[],
            channel_effects=[],
            fixtures=fixtures,
            section_start_ms=0,
            section_end_ms=1000,
        )

        placements = adapter.convert(dmx_effects, fixtures)

        # Assert
        assert len(dmx_effects) == 1
        assert dmx_effects[0].metadata["type"] == "gap_fill"
        assert dmx_effects[0].start_ms == 0
        assert dmx_effects[0].end_ms == 1000
        # Placements include individual + group (if xlights_group configured)
        assert len(placements) >= 1

    def test_e2e_complete_pipeline_with_xsq_adapter(self, create_fixture_group):
        """Test E2E: Complete pipeline from effects to EffectPlacement."""
        # Arrange
        fixtures = create_fixture_group(num_fixtures=2)
        pipeline = ChannelIntegrationPipeline()
        adapter = XsqAdapter()

        from blinkb0t.core.domains.sequencing.channels.state import ChannelState

        state = ChannelState(fixture=fixtures.fixtures[0])
        state.set_channel("pan", 150)

        movement_effects = [
            SequencedEffect(
                targets=["ALL"],
                channels={"pan": state},
                start_ms=0,
                end_ms=500,
            )
        ]

        # Act
        dmx_effects = pipeline.process_section(
            movement_effects=movement_effects,
            channel_effects=[],
            fixtures=fixtures,
            section_start_ms=0,
            section_end_ms=500,
        )

        placements = adapter.convert(dmx_effects, fixtures)

        # Assert - complete E2E validation
        assert len(dmx_effects) > 0
        assert len(placements) > 0
        assert all(isinstance(p, EffectPlacement) for p in placements)
        assert all(p.effect_name == "DMX" for p in placements)
        # With 2 fixtures and ALL target, should create group effect
        element_names = {p.element_name for p in placements}
        assert "Dmx ALL" in element_names  # Group effect for ALL fixtures
