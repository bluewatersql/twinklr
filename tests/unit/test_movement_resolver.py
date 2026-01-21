"""Tests for MovementResolver interface and ResolverContext."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from blinkb0t.core.config.fixtures import (
    ChannelInversions,
    DmxMapping,
    FixtureConfig,
    FixtureGroup,
    FixtureInstance,
    MovementLimits,
    Orientation,
    PanTiltRange,
)
from blinkb0t.core.config.models import JobConfig
from blinkb0t.core.domains.sequencing.models.xsq import SequenceHead, XSequence

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
from blinkb0t.core.domains.sequencing.moving_heads.boundary_enforcer import BoundaryEnforcer
from blinkb0t.core.domains.sequencing.moving_heads.context import SequencerContext
from blinkb0t.core.domains.sequencing.moving_heads.resolvers.context import (
    MovementResolver,
    ResolverContext,
)


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


@pytest.fixture
def fixture_group(basic_fixture: FixtureInstance) -> FixtureGroup:
    """Create a fixture group for testing."""
    return FixtureGroup(group_id="TEST_GROUP", fixtures=[basic_fixture])


@pytest.fixture
def mock_xsq() -> XSequence:
    """Create a mock XSequence for testing."""
    head = SequenceHead(version="1.0", media_file="", sequence_duration_ms=100000)
    return XSequence(head=head, timing_tracks=[], element_effects=[])


@pytest.fixture
def job_config() -> JobConfig:
    """Create a job config for testing."""
    return JobConfig(
        assumptions={"beats_per_bar": 4},
        include_notes_track=False,
    )


@pytest.fixture
def sequencer_context(
    basic_fixture: FixtureInstance, dmx_curve_mapper: DMXCurveMapper
) -> SequencerContext:
    """Create a SequencerContext for testing."""
    boundaries = BoundaryEnforcer(basic_fixture)
    return SequencerContext(
        fixture=basic_fixture,
        boundaries=boundaries,
        dmx_curve_mapper=dmx_curve_mapper,
        beats_s=[0.0, 0.5, 1.0, 1.5],
        song_features={"tempo_bpm": 120.0},
    )


class TestMovementResolver:
    """Tests for MovementResolver interface."""

    def test_movement_resolver_is_abstract(self) -> None:
        """Test that MovementResolver is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            MovementResolver()  # type: ignore

    def test_movement_resolver_requires_resolve_method(self) -> None:
        """Test that subclasses must implement resolve()."""

        class IncompleteResolver(MovementResolver):
            pass

        # ABC prevents instantiation of abstract classes
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteResolver()


class TestResolverContext:
    """Tests for ResolverContext."""

    def test_resolver_context_extends_sequencer_context(
        self,
        basic_fixture: FixtureInstance,
        fixture_group: FixtureGroup,
        mock_xsq: XSequence,
        job_config: JobConfig,
        sequencer_context: SequencerContext,
    ) -> None:
        """Test that ResolverContext extends SequencerContext."""
        instruction = {"movement": {"pattern": "sweep_lr"}}
        section = {"name": "Intro", "time_ms": {"start": 0, "end": 1000}}

        context = ResolverContext(
            sequencer_context=sequencer_context,
            xsq=mock_xsq,
            fixtures=fixture_group,
            instruction=instruction,
            section=section,
            job_config=job_config,
        )

        # Should have all SequencerContext properties
        assert context.fixture == basic_fixture
        assert context.boundaries == sequencer_context.boundaries
        assert context.beats_s == sequencer_context.beats_s
        assert context.song_features == sequencer_context.song_features

        # Should have new properties
        assert context.xsq == mock_xsq
        assert context.fixtures == fixture_group
        assert context.instruction == instruction
        assert context.section == section
        assert context.job_config == job_config

    def test_resolver_context_provides_first_fixture(
        self,
        basic_fixture: FixtureInstance,
        fixture_group: FixtureGroup,
        mock_xsq: XSequence,
        job_config: JobConfig,
        sequencer_context: SequencerContext,
    ) -> None:
        """Test that ResolverContext provides first_fixture convenience."""
        context = ResolverContext(
            sequencer_context=sequencer_context,
            xsq=mock_xsq,
            fixtures=fixture_group,
            instruction={},
            section={},
            job_config=job_config,
        )

        assert context.first_fixture == basic_fixture

    def test_resolver_context_provides_timing(
        self,
        basic_fixture: FixtureInstance,
        fixture_group: FixtureGroup,
        mock_xsq: XSequence,
        job_config: JobConfig,
        sequencer_context: SequencerContext,
    ) -> None:
        """Test that ResolverContext provides timing from section."""
        section = {"time_ms": {"start": 1000, "end": 5000}}

        context = ResolverContext(
            sequencer_context=sequencer_context,
            xsq=mock_xsq,
            fixtures=fixture_group,
            instruction={},
            section=section,
            job_config=job_config,
        )

        assert context.start_ms == 1000
        assert context.end_ms == 5000
        assert context.duration_ms == 4000
