"""Unit tests for ResolverContextBuilder."""

from unittest.mock import Mock

import pytest

from blinkb0t.core.config.fixtures import FixtureGroup
from blinkb0t.core.config.models import JobConfig
from blinkb0t.core.domains.sequencing.moving_heads.context import SequencerContext
from blinkb0t.core.domains.sequencing.moving_heads.templates.context_builder import (
    ResolverContextBuilder,
)

from .conftest import create_test_fixture


class TestResolverContextBuilder:
    @pytest.fixture
    def mock_fixture(self):
        """Create a real fixture instance for testing."""
        return create_test_fixture("MH1")

    @pytest.fixture
    def mock_sequencer_context(self, mock_fixture):
        """Mock sequencer context."""
        context = Mock(spec=SequencerContext)
        context.fixture = mock_fixture
        context.boundaries = Mock()
        context.dmx_curve_mapper = Mock()
        context.beats_s = [0.0, 0.5, 1.0]
        context.song_features = {"tempo_bpm": 120.0}
        return context

    @pytest.fixture
    def mock_xsq(self):
        """Mock XSQ object."""
        return Mock()

    @pytest.fixture
    def job_config(self):
        """Job configuration."""
        return JobConfig()

    @pytest.fixture
    def builder(self, mock_sequencer_context, mock_xsq, job_config):
        """Create builder instance."""
        return ResolverContextBuilder(
            sequencer_context=mock_sequencer_context,
            xsq=mock_xsq,
            job_config=job_config,
        )

    def test_builder_initializes(self, builder, mock_sequencer_context, mock_xsq):
        """Test builder initializes with dependencies."""
        assert builder.sequencer_context == mock_sequencer_context
        assert builder.xsq == mock_xsq
        assert builder.job_config is not None

    def test_build_context_reuses_sequencer_context(
        self, builder, mock_fixture, mock_sequencer_context
    ):
        """Test builder reuses sequencer context for same fixture."""
        instruction = {"movement": {}, "dimmer": {}, "time_ms": {"start": 0, "end": 1000}}
        section = {"time_ms": {"start": 0, "end": 1000}}
        fixtures = Mock(spec=FixtureGroup)

        context = builder.build_context(
            fixture=mock_fixture,
            instruction=instruction,
            section=section,
            fixtures=fixtures,
        )

        assert context is not None
        assert context.sequencer_context == mock_sequencer_context

    def test_build_context_creates_new_for_different_fixture(self, builder, mock_sequencer_context):
        """Test builder creates new sequencer context for different fixture."""
        # Create a different fixture
        different_fixture = create_test_fixture("MH2")

        instruction = {"movement": {}, "dimmer": {}, "time_ms": {"start": 0, "end": 1000}}
        section = {"time_ms": {"start": 0, "end": 1000}}
        fixtures = Mock(spec=FixtureGroup)

        context = builder.build_context(
            fixture=different_fixture,
            instruction=instruction,
            section=section,
            fixtures=fixtures,
        )

        assert context is not None
        # Should have different sequencer context (not same object)
        assert context.sequencer_context != mock_sequencer_context

    def test_build_context_includes_all_fields(self, builder, mock_fixture):
        """Test built context includes all required fields."""
        instruction = {"movement": {}, "dimmer": {}, "time_ms": {"start": 0, "end": 1000}}
        section = {"time_ms": {"start": 0, "end": 1000}, "template_id": "test"}
        fixtures = Mock(spec=FixtureGroup)

        context = builder.build_context(
            fixture=mock_fixture,
            instruction=instruction,
            section=section,
            fixtures=fixtures,
        )

        assert context.sequencer_context is not None
        assert context.xsq is not None
        assert context.fixtures == fixtures
        assert context.instruction == instruction
        assert context.section == section
        assert context.job_config is not None
