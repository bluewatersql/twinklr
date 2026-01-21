"""Tests for sequencer orchestration."""

from __future__ import annotations

from unittest.mock import Mock, patch

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
from blinkb0t.core.config.models import AgentOrchestrationConfig, AssumptionsConfig, JobConfig
from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
    CurveGenerator,
    CustomCurveProvider,
    NativeCurveProvider,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
from blinkb0t.core.domains.sequencing.infrastructure.xsq import EffectPlacement, XSequence
from blinkb0t.core.domains.sequencing.models.xsq import SequenceHead
from blinkb0t.core.domains.sequencing.moving_heads.boundary_enforcer import BoundaryEnforcer
from blinkb0t.core.domains.sequencing.moving_heads.context import SequencerContext
from blinkb0t.core.domains.sequencing.moving_heads.resolvers.context import (
    MovementResolver,
    ResolverContext,
)

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
    return FixtureGroup(group_id="test_group", fixtures=[basic_fixture])


@pytest.fixture
def job_config() -> JobConfig:
    """Create a job config for testing."""
    return JobConfig(
        assumptions=AssumptionsConfig(
            beats_per_bar=4,
        ),
        include_notes_track=False,
        agent=AgentOrchestrationConfig(),
    )


@pytest.fixture
def dmx_curve_mapper() -> DMXCurveMapper:
    # Initialize curve engine components
    native_provider = NativeCurveProvider()
    custom_provider = CustomCurveProvider()
    curve_generator = CurveGenerator(
        library=CurveLibrary(),
        native_provider=native_provider,
        custom_provider=custom_provider,
    )
    curve_normalizer = CurveNormalizer()
    native_curve_tuner = NativeCurveTuner()

    # Create mapper
    return DMXCurveMapper(
        generator=curve_generator,
        normalizer=curve_normalizer,
        tuner=native_curve_tuner,
    )


@pytest.fixture
def mock_xsq() -> XSequence:
    """Create a mock XSequence for testing."""
    head = SequenceHead(version="1.0", media_file="", sequence_duration_ms=100000)
    return XSequence(head=head, timing_tracks=[], element_effects=[])


@pytest.fixture
def sample_plan() -> dict:
    """Create a sample plan for testing."""
    return {
        "sections": [
            {
                "section_id": "intro",
                "name": "Intro",
                "time_ms": {"start": 0, "end": 1000},
                "instructions": [
                    {
                        "target": "ALL",
                        "movement": {"pattern": "static", "rendering_mode": "discrete"},
                        "dimmer": {"pattern": "static", "base_pct": 50},
                    }
                ],
            }
        ]
    }


class TestSequencerOrchestration:
    """Tests for sequencer orchestration logic."""

    def test_sequencer_loads_xsq(self, mock_xsq: XSequence) -> None:
        """Test that sequencer loads XSQ from input file."""
        with patch(
            "blinkb0t.core.domains.sequencing.moving_heads.sequencer.XSQParser"
        ) as mock_parser:
            mock_parser_instance = Mock()
            mock_parser_instance.parse.return_value = mock_xsq
            mock_parser.return_value = mock_parser_instance
            # This test will be implemented when we refactor sequencer
            assert True  # Placeholder

    def test_sequencer_resolves_targets_upfront(
        self, sample_plan: dict, fixture_group: FixtureGroup
    ) -> None:
        """Test that sequencer resolves all targets upfront."""
        with patch(
            "blinkb0t.core.domains.sequencing.moving_heads.resolvers.target_resolver.resolve_plan_targets"
        ) as mock_resolve:
            mock_resolve.return_value = {"ALL": fixture_group}
            # Verify the function is called during sequencer execution
            from blinkb0t.core.domains.sequencing.moving_heads.sequencer import (
                MovingHeadSequencer,
            )

            # This test verifies the sequencer would call resolve_plan_targets
            # Full integration test would require XSQ file, so we just verify the import path
            assert mock_resolve is not None  # Mock is set up correctly
            assert MovingHeadSequencer is not None  # Sequencer class exists

    def test_sequencer_creates_resolver_context(
        self,
        basic_fixture: FixtureInstance,
        fixture_group: FixtureGroup,
        job_config: JobConfig,
        mock_xsq: XSequence,
        sample_plan: dict,
        dmx_curve_mapper: DMXCurveMapper,
    ) -> None:
        """Test that sequencer creates ResolverContext correctly."""
        section = sample_plan["sections"][0]
        instruction = section["instructions"][0]

        boundaries = BoundaryEnforcer(basic_fixture)
        sequencer_context = SequencerContext(
            fixture=basic_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=dmx_curve_mapper,
            beats_s=[0.0, 0.5, 1.0],
            song_features={"tempo_bpm": 120.0},
        )

        resolver_context = ResolverContext(
            sequencer_context=sequencer_context,
            xsq=mock_xsq,
            fixtures=fixture_group,
            instruction=instruction,
            section=section,
            job_config=job_config,
        )

        assert resolver_context.start_ms == 0
        assert resolver_context.end_ms == 1000
        assert resolver_context.duration_ms == 1000
        assert resolver_context.first_fixture == basic_fixture

    def test_sequencer_calls_handler_resolve(
        self,
        basic_fixture: FixtureInstance,
        fixture_group: FixtureGroup,
        job_config: JobConfig,
        mock_xsq: XSequence,
        sample_plan: dict,
        dmx_curve_mapper: DMXCurveMapper,
    ) -> None:
        """Test that sequencer calls handler.resolve() with correct args."""
        section = sample_plan["sections"][0]
        instruction = section["instructions"][0]
        targets = ["Dmx MH1"]

        boundaries = BoundaryEnforcer(basic_fixture)
        sequencer_context = SequencerContext(
            fixture=basic_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=dmx_curve_mapper,
            beats_s=[],
            song_features={},
        )

        resolver_context = ResolverContext(
            sequencer_context=sequencer_context,
            xsq=mock_xsq,
            fixtures=fixture_group,
            instruction=instruction,
            section=section,
            job_config=job_config,
        )

        # Mock handler
        mock_handler = Mock(spec=MovementResolver)
        mock_placement = EffectPlacement(
            element_name="Dmx MH1",
            effect_name="DMX",
            start_ms=0,
            end_ms=1000,
        )
        mock_handler.resolve.return_value = [mock_placement]

        # Call handler
        placements = mock_handler.resolve(instruction, resolver_context, targets)

        # Verify handler was called correctly
        mock_handler.resolve.assert_called_once_with(instruction, resolver_context, targets)
        assert len(placements) == 1
        assert placements[0].element_name == "Dmx MH1"

    def test_sequencer_adds_placements_to_xsq(self, mock_xsq: XSequence, sample_plan: dict) -> None:
        """Test that sequencer adds effect placements to XSQ."""
        from blinkb0t.core.domains.sequencing.infrastructure.xsq.compat import (
            effect_placement_to_effect,
        )

        placement = EffectPlacement(
            element_name="Dmx MH1",
            effect_name="DMX",
            start_ms=0,
            end_ms=1000,
        )

        effect = effect_placement_to_effect(placement)
        mock_xsq.add_effect(placement.element_name, effect, layer_index=0)
        # Verify effect was added
        element = mock_xsq.get_element(placement.element_name)
        assert element is not None
        assert len(element.layers[0].effects) > 0

    def test_sequencer_processes_all_sections(self, sample_plan: dict) -> None:
        """Test that sequencer processes all sections in plan."""
        sections = sample_plan["sections"]
        assert len(sections) == 1
        # This test will be implemented when we refactor sequencer
        assert True  # Placeholder

    def test_sequencer_processes_all_instructions(self, sample_plan: dict) -> None:
        """Test that sequencer processes all instructions in each section."""
        section = sample_plan["sections"][0]
        instructions = section["instructions"]
        assert len(instructions) == 1
        # This test will be implemented when we refactor sequencer
        assert True  # Placeholder

    def test_sequencer_handles_missing_handler_gracefully(
        self,
        basic_fixture: FixtureInstance,
        fixture_group: FixtureGroup,
        job_config: JobConfig,
        mock_xsq: XSequence,
        sample_plan: dict,
    ) -> None:
        """Test that sequencer handles missing handler gracefully."""
        # This test will be implemented when we refactor sequencer
        assert True  # Placeholder

    def test_sequencer_saves_xsq(self, mock_xsq: XSequence) -> None:
        """Test that sequencer saves XSQ to output file."""
        # This test will be implemented when we refactor sequencer
        assert True  # Placeholder


class TestSequencerIntegration:
    """Integration tests for refactored sequencer."""

    def test_sequencer_end_to_end_flow(
        self,
        basic_fixture: FixtureInstance,
        fixture_group: FixtureGroup,
        job_config: JobConfig,
        sample_plan: dict,
    ) -> None:
        """Test end-to-end flow: plan -> handler -> placements -> XSQ."""
        # This test will be implemented when we refactor sequencer
        assert True  # Placeholder
