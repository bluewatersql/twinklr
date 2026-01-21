"""Tests for SequencerContext using FixtureInstance."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from blinkb0t.core.config.fixtures import (
    ChannelInversions,
    DmxMapping,
    FixtureConfig,
    FixtureInstance,
    MovementLimits,
    Orientation,
    PanTiltRange,
)
from blinkb0t.core.domains.sequencing.moving_heads.boundary_enforcer import BoundaryEnforcer

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
from blinkb0t.core.domains.sequencing.moving_heads.context import SequencerContext


@pytest.fixture
def basic_fixture() -> FixtureInstance:
    """Create a basic fixture for testing."""
    config = FixtureConfig(
        fixture_id="TEST_MH1",
        dmx_universe=1,
        dmx_start_address=1,
        channel_count=16,
        dmx_mapping=DmxMapping(
            pan_channel=1,
            tilt_channel=2,
            dimmer_channel=3,
        ),
        inversions=ChannelInversions(),
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
            pan_min=50,
            pan_max=190,
            tilt_min=5,
            tilt_max=125,
            avoid_backward=True,
        ),
    )
    return FixtureInstance(
        fixture_id="TEST_MH1",
        config=config,
        xlights_model_name="Dmx MH1",
    )


class TestSequencerContextInit:
    """Tests for SequencerContext initialization."""

    def test_init_with_fixture(
        self, basic_fixture: FixtureInstance, dmx_curve_mapper: DMXCurveMapper
    ) -> None:
        """Test creating SequencerContext with FixtureInstance."""
        boundaries = BoundaryEnforcer(basic_fixture)

        context = SequencerContext(
            fixture=basic_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=dmx_curve_mapper,
            beats_s=[0.0, 0.5, 1.0, 1.5],
            song_features={"tempo_bpm": 120.0},
        )

        assert context.fixture == basic_fixture
        assert context.boundaries == boundaries
        assert context.beats_s == [0.0, 0.5, 1.0, 1.5]
        assert context.song_features["tempo_bpm"] == 120.0

    def test_fixture_accessible(
        self, basic_fixture: FixtureInstance, dmx_curve_mapper: DMXCurveMapper
    ) -> None:
        """Test that fixture config is accessible through context."""
        boundaries = BoundaryEnforcer(basic_fixture)
        context = SequencerContext(
            fixture=basic_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=dmx_curve_mapper,
            beats_s=[],
            song_features={},
        )

        # Should be able to access fixture config
        assert context.fixture.config.pan_tilt_range.pan_range_deg == 540.0
        assert context.fixture.config.dmx_mapping.pan_channel == 1


class TestSequencerContextConversionMethods:
    """Tests for degree conversion methods in context."""

    def test_deg_to_pan_dmx_delegates(
        self, basic_fixture: FixtureInstance, dmx_curve_mapper: DMXCurveMapper
    ) -> None:
        """Test deg_to_pan_dmx delegates to boundaries."""
        boundaries = BoundaryEnforcer(basic_fixture)
        context = SequencerContext(
            fixture=basic_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=dmx_curve_mapper,
            beats_s=[],
            song_features={},
        )

        result = context.deg_to_pan_dmx(45.0)
        expected = boundaries.deg_to_pan_dmx(45.0)
        assert result == expected

    def test_deg_to_tilt_dmx_delegates(
        self, basic_fixture: FixtureInstance, dmx_curve_mapper: DMXCurveMapper
    ) -> None:
        """Test deg_to_tilt_dmx delegates to boundaries."""
        boundaries = BoundaryEnforcer(basic_fixture)
        context = SequencerContext(
            fixture=basic_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=dmx_curve_mapper,
            beats_s=[],
            song_features={},
        )

        result = context.deg_to_tilt_dmx(25.0)
        expected = boundaries.deg_to_tilt_dmx(25.0)
        assert result == expected


class TestBackwardCompatibility:
    """Tests for backward compatibility properties."""

    def test_pan_range_deg_property(
        self, basic_fixture: FixtureInstance, dmx_curve_mapper: DMXCurveMapper
    ) -> None:
        """Test pan_range_deg property returns correct value."""
        boundaries = BoundaryEnforcer(basic_fixture)
        context = SequencerContext(
            fixture=basic_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=dmx_curve_mapper,
            beats_s=[],
            song_features={},
        )

        assert context.pan_range_deg == 540.0

    def test_tilt_range_deg_property(
        self, basic_fixture: FixtureInstance, dmx_curve_mapper: DMXCurveMapper
    ) -> None:
        """Test tilt_range_deg property returns correct value."""
        boundaries = BoundaryEnforcer(basic_fixture)
        context = SequencerContext(
            fixture=basic_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=dmx_curve_mapper,
            beats_s=[],
            song_features={},
        )

        assert context.tilt_range_deg == 270.0

    def test_pan_limits_property(
        self, basic_fixture: FixtureInstance, dmx_curve_mapper: DMXCurveMapper
    ) -> None:
        """Test pan_limits property returns effective limits."""
        boundaries = BoundaryEnforcer(basic_fixture)
        context = SequencerContext(
            fixture=basic_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=dmx_curve_mapper,
            beats_s=[],
            song_features={},
        )

        # Should return effective limits from boundaries (with avoid_backward)
        pan_min, pan_max = context.pan_limits
        assert isinstance(pan_min, int)
        assert isinstance(pan_max, int)
        assert pan_min < pan_max

    def test_tilt_limits_property(
        self, basic_fixture: FixtureInstance, dmx_curve_mapper: DMXCurveMapper
    ) -> None:
        """Test tilt_limits property returns fixture limits."""
        boundaries = BoundaryEnforcer(basic_fixture)
        context = SequencerContext(
            fixture=basic_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=dmx_curve_mapper,
            beats_s=[],
            song_features={},
        )

        tilt_min, tilt_max = context.tilt_limits
        assert tilt_min == 5
        assert tilt_max == 125

    def test_orientation_properties(
        self, basic_fixture: FixtureInstance, dmx_curve_mapper: DMXCurveMapper
    ) -> None:
        """Test orientation properties return correct values."""
        boundaries = BoundaryEnforcer(basic_fixture)
        context = SequencerContext(
            fixture=basic_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=dmx_curve_mapper,
            beats_s=[],
            song_features={},
        )

        assert context.pan_front_dmx == 128
        assert context.tilt_zero_dmx == 22
        assert context.tilt_up_dmx == 112


class TestIntegration:
    """Integration tests for SequencerContext."""

    def test_context_provides_all_needed_data(
        self, basic_fixture: FixtureInstance, dmx_curve_mapper: DMXCurveMapper
    ) -> None:
        """Test that context provides all data handlers need."""
        boundaries = BoundaryEnforcer(basic_fixture)
        context = SequencerContext(
            fixture=basic_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=dmx_curve_mapper,
            beats_s=[0.0, 0.5, 1.0],
            song_features={"tempo_bpm": 120.0, "energy": 0.8},
        )

        # Handlers need these:
        assert context.fixture is not None
        assert context.boundaries is not None
        assert len(context.beats_s) == 3
        assert "tempo_bpm" in context.song_features

        # Backward compat properties work:
        assert context.pan_range_deg == 540.0
        assert context.tilt_range_deg == 270.0
        assert context.pan_front_dmx == 128

        # Conversion methods work:
        pan_dmx = context.deg_to_pan_dmx(30.0)
        assert isinstance(pan_dmx, int)
        assert 0 <= pan_dmx <= 255
