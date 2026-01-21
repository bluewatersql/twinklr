"""Integration test for handler → pipeline → XSQ type safety.

This test would have caught the handler return type bug where handlers
were returning EffectPlacement instead of SequencedEffect.
"""

from __future__ import annotations

from unittest.mock import Mock

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
from blinkb0t.core.domains.sequencing.channels.pipeline.pipeline import (
    ChannelIntegrationPipeline,
)
from blinkb0t.core.domains.sequencing.channels.pipeline.xsq_adapter import XsqAdapter
from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
from blinkb0t.core.domains.sequencing.infrastructure.xsq import EffectPlacement, XSequence
from blinkb0t.core.domains.sequencing.models.channels import DmxEffect, SequencedEffect
from blinkb0t.core.domains.sequencing.moving_heads.boundary_enforcer import (
    BoundaryEnforcer,
)
from blinkb0t.core.domains.sequencing.moving_heads.context import (
    SequencerContext,
)
from blinkb0t.core.domains.sequencing.moving_heads.resolvers.context import ResolverContext
from blinkb0t.core.domains.sequencing.moving_heads.templates.handlers.default import (
    DefaultMovementHandler,
)


def _create_mock_fixture():
    """Helper to create a mock fixture."""
    fixture = Mock(spec=FixtureInstance)
    fixture.fixture_id = "TEST_MH1"
    fixture.xlights_model_name = "Dmx TEST_MH1"  # xLights model name for this fixture
    fixture.config = Mock(spec=FixtureConfig)
    fixture.config.dmx_mapping = Mock(spec=DmxMapping)

    # Mock channel properties
    fixture.config.dmx_mapping.pan = 1
    fixture.config.dmx_mapping.pan_channel = 1
    fixture.config.dmx_mapping.tilt = 2
    fixture.config.dmx_mapping.tilt_channel = 2
    fixture.config.dmx_mapping.dimmer = 3
    fixture.config.dmx_mapping.dimmer_channel = 3
    fixture.config.dmx_mapping.shutter = 4
    fixture.config.dmx_mapping.color = 5
    fixture.config.dmx_mapping.gobo = 6
    fixture.config.dmx_mapping.pan_fine_channel = None
    fixture.config.dmx_mapping.tilt_fine_channel = None
    fixture.config.dmx_mapping.use_16bit_pan_tilt = False

    # Mock inversions (no inversions by default)
    fixture.config.inversions = ChannelInversions()

    # Mock limits
    fixture.config.limits = MovementLimits()

    # Mock orientation
    fixture.config.orientation = Orientation(
        pan_front_dmx=128,
        tilt_zero_dmx=128,
        tilt_up_dmx=255,
    )

    # Mock pan_tilt_range
    fixture.config.pan_tilt_range = PanTiltRange(
        pan_deg=540.0,
        tilt_deg=270.0,
    )

    # Mock degrees_to_dmx method (returns tuple of (pan_dmx, tilt_dmx))
    def degrees_to_dmx(pose):
        pan_dmx = int((pose.pan_deg + 270) * 255 / 540)  # Normalize -270 to 270 -> 0 to 255
        tilt_dmx = int((pose.tilt_deg + 135) * 255 / 270)  # Normalize -135 to 135 -> 0 to 255
        return (pan_dmx, tilt_dmx)

    fixture.config.degrees_to_dmx = Mock(side_effect=degrees_to_dmx)

    return fixture


@pytest.fixture
def mock_fixture():
    """Create a mock fixture for testing."""
    return _create_mock_fixture()


@pytest.fixture
def mock_fixture_group(mock_fixture):
    """Create a mock fixture group."""
    group = Mock(spec=FixtureGroup)
    group.group_id = "test_group"
    group.fixtures = [mock_fixture]
    group.xlights_group = "GROUP - TEST"
    group.expand_fixtures.return_value = [mock_fixture]
    group.__iter__ = Mock(return_value=iter([mock_fixture]))
    return group


@pytest.fixture
def job_config():
    """Create a mock job config."""
    return JobConfig(fixture_config_path="test.json")


@pytest.fixture
def sequencer_context(mock_fixture):
    """Create a sequencer context."""
    boundaries = Mock(spec=BoundaryEnforcer)
    boundaries.pan_limits = (0, 255)  # Min/max DMX values
    boundaries.tilt_limits = (0, 255)  # Min/max DMX values
    boundaries.clamp_pan = Mock(side_effect=lambda x: max(0, min(255, int(x))))
    boundaries.clamp_tilt = Mock(side_effect=lambda x: max(0, min(255, int(x))))

    dmx_mapper = Mock(spec=DMXCurveMapper)
    dmx_mapper.map_to_channel = Mock(return_value=None)  # No value curves by default

    return SequencerContext(
        fixture=mock_fixture,
        boundaries=boundaries,
        dmx_curve_mapper=dmx_mapper,
        beats_s=[0.0, 0.5, 1.0, 1.5, 2.0],
        song_features={"tempo_bpm": 120},
    )


@pytest.fixture
def resolver_context(sequencer_context, mock_fixture_group, job_config):
    """Create a resolver context."""
    xsq = Mock(spec=XSequence)
    return ResolverContext(
        sequencer_context=sequencer_context,
        xsq=xsq,
        fixtures=mock_fixture_group,
        instruction={},
        section={},
        job_config=job_config,
    )


@pytest.fixture
def channel_pipeline() -> ChannelIntegrationPipeline:
    """Create a channel integration pipeline."""
    return ChannelIntegrationPipeline()


@pytest.fixture
def xsq_adapter() -> XsqAdapter:
    """Create an XSQ adapter."""
    return XsqAdapter()


class TestHandlerReturnType:
    """Test that handlers return SequencedEffect, not EffectPlacement."""

    def test_handler_returns_sequenced_effect(self, resolver_context: ResolverContext) -> None:
        """Verify handlers return SequencedEffect, not EffectPlacement.

        This test would have caught the bug where handlers were
        returning EffectPlacement instead of SequencedEffect.
        """
        handler = DefaultMovementHandler()
        instruction = {
            "movement": {
                "pattern": "sweep_lr",
                "rendering_mode": "value_curve",
                "amplitude_deg": 60,
                "frequency": 1.0,
            },
            "target": "ALL",
            "time_ms": {"start": 0, "end": 2000},  # 2 second duration
        }
        targets = ["Test MH"]

        # Update resolver_context with the instruction that has timing
        resolver_context.instruction = instruction

        result = handler.resolve(instruction, resolver_context, targets)

        # CRITICAL: Handlers must return SequencedEffect
        assert isinstance(result, list), "Handler must return a list"
        assert len(result) > 0, "Handler must return at least one effect"
        assert all(isinstance(effect, SequencedEffect) for effect in result), (
            f"All effects must be SequencedEffect, got {type(result[0])}"
        )

        # Verify SequencedEffect has expected attributes
        effect = result[0]
        assert hasattr(effect, "targets"), "SequencedEffect must have 'targets'"
        assert hasattr(effect, "channels"), "SequencedEffect must have 'channels'"
        assert hasattr(effect, "start_ms"), "SequencedEffect must have 'start_ms'"
        assert hasattr(effect, "end_ms"), "SequencedEffect must have 'end_ms'"

    def test_pipeline_processes_sequenced_effects(
        self,
        channel_pipeline: ChannelIntegrationPipeline,
        mock_fixture_group: FixtureGroup,
        resolver_context: ResolverContext,
    ) -> None:
        """Verify pipeline converts SequencedEffect → DmxEffect."""
        handler = DefaultMovementHandler()
        instruction = {
            "movement": {
                "pattern": "sweep_lr",
                "rendering_mode": "value_curve",
                "amplitude_deg": 60,
                "frequency": 1.0,
            },
            "target": "ALL",
            "time_ms": {"start": 0, "end": 1000},
        }
        targets = ["Test MH"]

        # Update resolver context with instruction
        resolver_context.instruction = instruction

        # Get SequencedEffect from handler
        sequenced_effects = handler.resolve(instruction, resolver_context, targets)

        # Process through pipeline
        dmx_effects = channel_pipeline.process_section(
            movement_effects=sequenced_effects,
            channel_effects=[],
            fixtures=mock_fixture_group,
            section_start_ms=0,
            section_end_ms=1000,
        )

        # CRITICAL: Pipeline must return DmxEffect
        assert isinstance(dmx_effects, list), "Pipeline must return a list"
        assert all(isinstance(effect, DmxEffect) for effect in dmx_effects), (
            f"All effects must be DmxEffect, got {type(dmx_effects[0]) if dmx_effects else 'empty'}"
        )

        # Verify DmxEffect has expected attributes
        if dmx_effects:
            effect = dmx_effects[0]
            assert hasattr(effect, "fixture_id"), "DmxEffect must have 'fixture_id'"
            assert hasattr(effect, "channels"), "DmxEffect must have 'channels'"
            assert hasattr(effect, "start_ms"), "DmxEffect must have 'start_ms'"
            assert hasattr(effect, "end_ms"), "DmxEffect must have 'end_ms'"

    def test_xsq_adapter_converts_dmx_effects(
        self,
        xsq_adapter: XsqAdapter,
        channel_pipeline: ChannelIntegrationPipeline,
        mock_fixture_group: FixtureGroup,
        resolver_context: ResolverContext,
    ) -> None:
        """Verify XSQ adapter converts DmxEffect → EffectPlacement."""
        handler = DefaultMovementHandler()
        instruction = {
            "movement": {
                "pattern": "sweep_lr",
                "rendering_mode": "value_curve",
                "amplitude_deg": 60,
                "frequency": 1.0,
            },
            "target": "ALL",
            "time_ms": {"start": 0, "end": 1000},
        }
        targets = ["Test MH"]

        # Update resolver context with instruction
        resolver_context.instruction = instruction

        # Get SequencedEffect from handler
        sequenced_effects = handler.resolve(instruction, resolver_context, targets)

        # Process through pipeline to get DmxEffect
        dmx_effects = channel_pipeline.process_section(
            movement_effects=sequenced_effects,
            channel_effects=[],
            fixtures=mock_fixture_group,
            section_start_ms=0,
            section_end_ms=1000,
        )

        # Convert to EffectPlacement (need mock xsq for EffectDB)
        mock_xsq = Mock()
        mock_xsq.append_effectdb = Mock(return_value=0)
        placements = xsq_adapter.convert(dmx_effects, mock_fixture_group, mock_xsq)

        # CRITICAL: XsqAdapter must return EffectPlacement
        assert isinstance(placements, list), "Adapter must return a list"
        assert all(isinstance(placement, EffectPlacement) for placement in placements), (
            f"All placements must be EffectPlacement, got {type(placements[0]) if placements else 'empty'}"
        )

        # Verify EffectPlacement has expected attributes
        if placements:
            placement = placements[0]
            assert hasattr(placement, "element_name"), "EffectPlacement must have 'element_name'"
            assert hasattr(placement, "start_ms"), "EffectPlacement must have 'start_ms'"
            assert hasattr(placement, "end_ms"), "EffectPlacement must have 'end_ms'"
            assert hasattr(placement, "effect_name"), "EffectPlacement must have 'effect_name'"

    def test_end_to_end_type_flow(
        self,
        resolver_context: ResolverContext,
        channel_pipeline: ChannelIntegrationPipeline,
        xsq_adapter: XsqAdapter,
        mock_fixture_group: FixtureGroup,
    ) -> None:
        """Test complete type flow: Handler → Pipeline → XSQ Adapter.

        This is the critical integration test that validates the entire
        data flow and would have caught the handler return type bug.
        """
        # Step 1: Handler returns SequencedEffect
        handler = DefaultMovementHandler()
        instruction = {
            "movement": {
                "pattern": "sweep_lr",
                "rendering_mode": "value_curve",
                "amplitude_deg": 60,
                "frequency": 1.0,
            },
            "target": "ALL",
            "time_ms": {"start": 0, "end": 1000},
        }
        targets = ["Test MH"]

        # Update resolver context with instruction
        resolver_context.instruction = instruction

        sequenced_effects = handler.resolve(instruction, resolver_context, targets)
        assert all(isinstance(e, SequencedEffect) for e in sequenced_effects), (
            "Handler must return SequencedEffect"
        )

        # Step 2: Pipeline converts SequencedEffect → DmxEffect
        dmx_effects = channel_pipeline.process_section(
            movement_effects=sequenced_effects,
            channel_effects=[],
            fixtures=mock_fixture_group,
            section_start_ms=0,
            section_end_ms=1000,
        )
        assert all(isinstance(e, DmxEffect) for e in dmx_effects), "Pipeline must return DmxEffect"

        # Step 3: XSQ Adapter converts DmxEffect → EffectPlacement (need mock xsq)
        mock_xsq = Mock()
        mock_xsq.append_effectdb = Mock(return_value=0)
        placements = xsq_adapter.convert(dmx_effects, mock_fixture_group, mock_xsq)
        assert all(isinstance(p, EffectPlacement) for p in placements), (
            "Adapter must return EffectPlacement"
        )

        # Verify data flow integrity
        assert len(sequenced_effects) > 0, "Must have sequenced effects"
        assert len(dmx_effects) > 0, "Must have DMX effects"
        assert len(placements) > 0, "Must have effect placements"
