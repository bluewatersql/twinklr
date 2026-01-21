"""Tests for BaseMovementHandler and DefaultMovementHandler."""

from __future__ import annotations

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
from blinkb0t.core.config.models import AgentOrchestrationConfig, JobConfig
from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
    CurveGenerator,
    CustomCurveProvider,
    NativeCurveProvider,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
from blinkb0t.core.domains.sequencing.models.channels import SequencedEffect
from blinkb0t.core.domains.sequencing.models.xsq import SequenceHead, XSequence
from blinkb0t.core.domains.sequencing.moving_heads.boundary_enforcer import BoundaryEnforcer
from blinkb0t.core.domains.sequencing.moving_heads.context import SequencerContext
from blinkb0t.core.domains.sequencing.moving_heads.resolvers.context import ResolverContext
from blinkb0t.core.domains.sequencing.moving_heads.templates.handlers import DefaultMovementHandler

# Rebuild JobConfig model to resolve forward references
JobConfig.model_rebuild()


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
        agent=AgentOrchestrationConfig(),
    )


@pytest.fixture
def dmx_curve_mapper() -> DMXCurveMapper:
    """Create a DMXCurveMapper for testing."""
    curve_library = CurveLibrary()
    native_provider = NativeCurveProvider()
    custom_provider = CustomCurveProvider()
    curve_generator = CurveGenerator(
        library=curve_library,
        native_provider=native_provider,
        custom_provider=custom_provider,
    )
    curve_normalizer = CurveNormalizer()
    native_curve_tuner = NativeCurveTuner()

    return DMXCurveMapper(
        generator=curve_generator,
        normalizer=curve_normalizer,
        tuner=native_curve_tuner,
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


@pytest.fixture
def resolver_context(
    sequencer_context: SequencerContext,
    fixture_group: FixtureGroup,
    mock_xsq: XSequence,
    job_config: JobConfig,
) -> ResolverContext:
    """Create a ResolverContext for testing."""
    instruction = {
        "movement": {"pattern": "sweep_lr", "rendering_mode": "value_curve"},
        "dimmer": {"pattern": "static", "base_pct": 50},
    }
    section = {"name": "Intro", "time_ms": {"start": 0, "end": 1000}}

    return ResolverContext(
        sequencer_context=sequencer_context,
        xsq=mock_xsq,
        fixtures=fixture_group,
        instruction=instruction,
        section=section,
        job_config=job_config,
    )


class TestDefaultMovementHandler:
    """Tests for DefaultMovementHandler."""

    def test_default_handler_exists(self) -> None:
        """Test that DefaultMovementHandler can be instantiated."""
        handler = DefaultMovementHandler()
        assert handler is not None

    def test_default_handler_resolves_value_curves(
        self,
        resolver_context: ResolverContext,
    ) -> None:
        """Test that default handler resolves value curve instructions."""
        handler = DefaultMovementHandler()
        targets = ["Dmx MH1"]

        # Instruction with value curves
        instruction = {
            "movement": {
                "pattern": "sweep_lr",
                "rendering_mode": "value_curve",
                "curve_preset": "sine",
            },
            "dimmer": {"pattern": "static", "base_pct": 50},
        }
        resolver_context.instruction = instruction

        # Should return list of SequencedEffect (not EffectPlacement)
        effects = handler.resolve(instruction, resolver_context, targets)

        assert isinstance(effects, list)
        assert len(effects) > 0
        assert all(isinstance(e, SequencedEffect) for e in effects)

    def test_default_handler_resolves_static_movement(
        self,
        resolver_context: ResolverContext,
    ) -> None:
        """Test that default handler resolves static movement (no curves)."""
        handler = DefaultMovementHandler()
        targets = ["Dmx MH1"]

        # Instruction without value curves (static movement)
        instruction = {
            "movement": {
                "pattern": "static",
                "rendering_mode": "discrete_blocks",
            },
            "dimmer": {"pattern": "static", "base_pct": 50},
        }
        resolver_context.instruction = instruction

        # Should return list of SequencedEffect (static movement)
        effects = handler.resolve(instruction, resolver_context, targets)

        assert isinstance(effects, list)
        assert len(effects) > 0
        assert all(isinstance(e, SequencedEffect) for e in effects)

    def test_default_handler_creates_effect_placements_with_correct_timing(
        self,
        resolver_context: ResolverContext,
    ) -> None:
        """Test that effect placements have correct timing from section."""
        handler = DefaultMovementHandler()
        targets = ["Dmx MH1"]

        # Section with specific timing
        resolver_context.section = {"time_ms": {"start": 500, "end": 2500}}

        instruction = {
            "movement": {"pattern": "static", "rendering_mode": "discrete_blocks"},
            "dimmer": {"pattern": "static", "base_pct": 50},
        }
        resolver_context.instruction = instruction

        effects = handler.resolve(instruction, resolver_context, targets)

        # All effects should have correct timing
        for effect in effects:
            assert effect.start_ms == 500
            assert effect.end_ms == 2500

    def test_default_handler_creates_effect_placements_for_all_targets(
        self,
        resolver_context: ResolverContext,
        basic_fixture: FixtureInstance,
    ) -> None:
        """Test that handler creates placements for all target fixtures."""
        handler = DefaultMovementHandler()

        # Create second fixture
        fixture2 = FixtureInstance(
            fixture_id="TEST_MH2",
            config=basic_fixture.config,
            xlights_model_name="Dmx MH2",
        )
        resolver_context.fixtures.add_fixture(fixture2)

        targets = ["Dmx MH1", "Dmx MH2"]

        instruction = {
            "movement": {"pattern": "static", "rendering_mode": "discrete_blocks"},
            "dimmer": {"pattern": "static", "base_pct": 50},
        }
        resolver_context.instruction = instruction

        effects = handler.resolve(instruction, resolver_context, targets)

        # Should have effects with both targets
        # SequencedEffect has 'targets' list instead of 'element_name'
        all_targets = []
        for effect in effects:
            all_targets.extend(effect.targets)
        assert "Dmx MH1" in all_targets
        assert "Dmx MH2" in all_targets
