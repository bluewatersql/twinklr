"""Tests for XsqAdapter."""

from unittest.mock import Mock

import pytest

from blinkb0t.core.domains.sequencing.channels.pipeline.xsq_adapter import XsqAdapter
from blinkb0t.core.domains.sequencing.infrastructure.xsq import EffectPlacement
from blinkb0t.core.domains.sequencing.models.channels import DmxEffect


class TestXsqAdapter:
    """Test XsqAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create XsqAdapter instance."""
        return XsqAdapter()

    @pytest.fixture
    def mock_xsq(self):
        """Create mock XSQ object."""
        xsq = Mock()
        xsq.append_effectdb = Mock(return_value=0)
        return xsq

    @pytest.fixture
    def mock_fixture_group_with_mapping(self, mock_fixture):
        """Create mock FixtureGroup with xLights mapping."""
        from blinkb0t.core.config.fixtures import FixtureGroup

        group = Mock(spec=FixtureGroup)
        group.group_id = "ALL"
        group.fixtures = [mock_fixture]
        group.xlights_group = "Dmx ALL"
        group.get_xlights_mapping = Mock(return_value={"MH1": "Dmx MH1", "ALL": "Dmx ALL"})
        # Mock expand_fixtures to return the fixtures list
        group.expand_fixtures.return_value = [mock_fixture]
        return group

    def test_adapter_initialization(self, adapter):
        """Test adapter initializes correctly."""
        assert adapter is not None

    def test_convert_single_dmx_effect(
        self, adapter, mock_channel_state, mock_fixture_group_with_mapping, mock_xsq
    ):
        """Test converting single DMX effect to EffectPlacement.

        Should create ONE placement: either individual fixture OR group (not both).
        With only 1 fixture active, it doesn't match ALL group, so creates individual placement.
        """
        dmx_effects = [
            DmxEffect(
                fixture_id="MH1",
                start_ms=0,
                end_ms=1000,
                channels={"pan": mock_channel_state, "tilt": mock_channel_state},
            )
        ]

        placements = adapter.convert(dmx_effects, mock_fixture_group_with_mapping, mock_xsq)

        # Should create 1 placement: individual (MH1) only (does NOT match ALL group)
        assert len(placements) == 1
        assert placements[0].element_name == "Dmx MH1"

        # Verify placement has correct timing
        placement = placements[0]
        assert isinstance(placement, EffectPlacement)
        assert placement.effect_name == "DMX"
        assert placement.start_ms == 0
        assert placement.end_ms == 1000

    def test_convert_multiple_dmx_effects(
        self, adapter, mock_channel_state, mock_fixture_group_with_mapping, mock_xsq
    ):
        """Test converting multiple DMX effects.

        Two different fixtures at different times = individual placements for each.
        """
        dmx_effects = [
            DmxEffect(
                fixture_id="MH1",
                start_ms=0,
                end_ms=500,
                channels={"pan": mock_channel_state},
            ),
            DmxEffect(
                fixture_id="MH1",
                start_ms=500,
                end_ms=1000,
                channels={"tilt": mock_channel_state},
            ),
        ]

        placements = adapter.convert(dmx_effects, mock_fixture_group_with_mapping, mock_xsq)

        # Should create 2 placements: 1 individual for each timing (no group match)
        assert len(placements) == 2

        # Check timing groups
        timing_0_500 = [p for p in placements if p.start_ms == 0 and p.end_ms == 500]
        timing_500_1000 = [p for p in placements if p.start_ms == 500 and p.end_ms == 1000]
        assert len(timing_0_500) == 1  # individual only
        assert len(timing_500_1000) == 1  # individual only

    def test_convert_with_missing_xlights_mapping(
        self, adapter, mock_channel_state, mock_fixture_group_with_mapping, mock_xsq
    ):
        """Test that effects without xLights mapping are skipped."""
        # Override mapping to not include MH2
        mock_fixture_group_with_mapping.get_xlights_mapping = Mock(return_value={"MH1": "Dmx MH1"})

        dmx_effects = [
            DmxEffect(
                fixture_id="MH1",
                start_ms=0,
                end_ms=500,
                channels={"pan": mock_channel_state},
            ),
            DmxEffect(
                fixture_id="MH2",  # No mapping
                start_ms=500,
                end_ms=1000,
                channels={"tilt": mock_channel_state},
            ),
        ]

        placements = adapter.convert(dmx_effects, mock_fixture_group_with_mapping, mock_xsq)

        # Only MH1 should be converted
        assert len(placements) == 1
        assert placements[0].element_name == "Dmx MH1"

    def test_convert_empty_effects_list(self, adapter, mock_fixture_group_with_mapping, mock_xsq):
        """Test converting empty effects list returns empty list."""
        placements = adapter.convert([], mock_fixture_group_with_mapping, mock_xsq)

        assert placements == []

    def test_convert_preserves_effect_timing(
        self, adapter, mock_channel_state, mock_fixture_group_with_mapping, mock_xsq
    ):
        """Test that timing is preserved correctly."""
        dmx_effects = [
            DmxEffect(
                fixture_id="MH1",
                start_ms=12345,
                end_ms=67890,
                channels={"pan": mock_channel_state},
            )
        ]

        placements = adapter.convert(dmx_effects, mock_fixture_group_with_mapping, mock_xsq)

        assert placements[0].start_ms == 12345
        assert placements[0].end_ms == 67890

    def test_convert_uses_dmx_effect_name(
        self, adapter, mock_channel_state, mock_fixture_group_with_mapping, mock_xsq
    ):
        """Test that effect name is always 'DMX'."""
        dmx_effects = [
            DmxEffect(
                fixture_id="MH1",
                start_ms=0,
                end_ms=1000,
                channels={"pan": mock_channel_state},
                metadata={"type": "movement", "source": "handler"},
            )
        ]

        placements = adapter.convert(dmx_effects, mock_fixture_group_with_mapping, mock_xsq)

        assert placements[0].effect_name == "DMX"

    def test_convert_with_multiple_fixtures(
        self, adapter, mock_channel_state, mock_xsq, mock_fixture
    ):
        """Test converting effects for multiple fixtures."""
        from blinkb0t.core.config.fixtures import FixtureGroup

        # Create a second mock fixture
        mock_fixture2 = Mock()
        mock_fixture2.fixture_id = "MH2"
        mock_fixture2.config = mock_fixture.config

        group = Mock(spec=FixtureGroup)
        group.fixtures = [mock_fixture, mock_fixture2]
        group.get_xlights_mapping = Mock(return_value={"MH1": "Dmx MH1", "MH2": "Dmx MH2"})
        group.expand_fixtures.return_value = [mock_fixture, mock_fixture2]

        dmx_effects = [
            DmxEffect(
                fixture_id="MH1",
                start_ms=0,
                end_ms=1000,
                channels={"pan": mock_channel_state},
            ),
            DmxEffect(
                fixture_id="MH2",
                start_ms=0,
                end_ms=1000,
                channels={"pan": mock_channel_state},
            ),
        ]

        placements = adapter.convert(dmx_effects, group, mock_xsq)

        # Should create 2 placements: individual only (no group configured in this mock)
        assert len(placements) == 2
        element_names = {p.element_name for p in placements}
        assert element_names == {"Dmx MH1", "Dmx MH2"}

    def test_convert_gap_fill_effects(
        self, adapter, mock_channel_state, mock_fixture_group_with_mapping, mock_xsq
    ):
        """Test converting gap fill effects.

        Gap fills should convert to individual fixtures (only 1 fixture, doesn't match ALL).
        """
        dmx_effects = [
            DmxEffect(
                fixture_id="MH1",
                start_ms=100,
                end_ms=200,
                channels={"pan": mock_channel_state, "tilt": mock_channel_state},
                metadata={"type": "gap_fill", "source": "gap_filler"},
            )
        ]

        placements = adapter.convert(dmx_effects, mock_fixture_group_with_mapping, mock_xsq)

        # Gap fills should convert to individual placement (only 1 fixture)
        assert len(placements) == 1
        assert all(p.effect_name == "DMX" for p in placements)
        assert placements[0].element_name == "Dmx MH1"

    def test_convert_channel_fill_effects(
        self, adapter, mock_channel_state, mock_fixture_group_with_mapping, mock_xsq
    ):
        """Test converting channel-filled effects.

        Channel fills should convert to individual fixtures (only 1 fixture, doesn't match ALL).
        """
        dmx_effects = [
            DmxEffect(
                fixture_id="MH1",
                start_ms=0,
                end_ms=1000,
                channels={
                    "pan": mock_channel_state,
                    "tilt": mock_channel_state,
                    "shutter": mock_channel_state,
                    "dimmer": mock_channel_state,
                    "color": mock_channel_state,
                    "gobo": mock_channel_state,
                },
                metadata={"type": "filled", "source": "channel_state_filler"},
            )
        ]

        placements = adapter.convert(dmx_effects, mock_fixture_group_with_mapping, mock_xsq)

        # Should create individual placement only (only 1 fixture)
        assert len(placements) == 1
        assert all(p.effect_name == "DMX" for p in placements)
        assert placements[0].element_name == "Dmx MH1"

    def test_convert_all_fixtures_creates_group(
        self, adapter, mock_channel_state, mock_xsq, mock_fixture
    ):
        """Test that when all fixtures are active at same time, it creates GROUP placement (not individual).
        This is the new behavior: semantic groups REPLACE individuals, not supplement them.
        """
        from blinkb0t.core.config.fixtures import FixtureGroup

        # Create a second mock fixture
        mock_fixture2 = Mock()
        mock_fixture2.fixture_id = "MH2"
        mock_fixture2.config = mock_fixture.config

        group = Mock(spec=FixtureGroup)
        group.fixtures = [mock_fixture, mock_fixture2]
        group.get_xlights_mapping = Mock(
            return_value={"MH1": "Dmx MH1", "MH2": "Dmx MH2", "ALL": "Dmx ALL"}
        )
        group.expand_fixtures.return_value = [mock_fixture, mock_fixture2]

        # Both fixtures active at same time = should create ALL group placement
        dmx_effects = [
            DmxEffect(
                fixture_id="MH1",
                start_ms=0,
                end_ms=1000,
                channels={"pan": mock_channel_state},
            ),
            DmxEffect(
                fixture_id="MH2",
                start_ms=0,
                end_ms=1000,
                channels={"pan": mock_channel_state},
            ),
        ]

        placements = adapter.convert(dmx_effects, group, mock_xsq)

        # Should create 1 placement: group (ALL) ONLY (not individuals)
        assert len(placements) == 1
        assert placements[0].element_name == "Dmx ALL"
