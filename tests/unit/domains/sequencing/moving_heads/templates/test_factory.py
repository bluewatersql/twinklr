"""Unit tests for TemplateProcessorFactory."""

from unittest.mock import MagicMock

import pytest

from blinkb0t.core.config.models import AgentOrchestrationConfig, JobConfig
from blinkb0t.core.domains.sequencing.moving_heads.templates.factory import (
    TemplateProcessorFactory,
)

from .conftest import create_test_fixture, create_test_fixture_group

# Rebuild JobConfig model to resolve forward references
JobConfig.model_rebuild()


class TestTemplateProcessorFactory:
    @pytest.fixture
    def mock_song_features(self):
        """Mock song features."""
        return {
            "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0],
            "bars": [0.0, 2.0, 4.0],
            "tempo_bpm": 120.0,
        }

    @pytest.fixture
    def mock_fixture(self):
        """Create a real fixture instance for testing."""
        return create_test_fixture("MH1")

    @pytest.fixture
    def mock_fixtures(self):
        """Create a real fixture group for testing."""
        return create_test_fixture_group(["MH1"])

    @pytest.fixture
    def mock_xsq(self):
        """Mock XSQ object."""
        return MagicMock()

    @pytest.fixture
    def job_config(self):
        """Job configuration."""
        return JobConfig(agent=AgentOrchestrationConfig())

    @pytest.fixture
    def factory(self, mock_song_features, job_config, mock_fixtures, mock_xsq):
        """Create factory instance."""
        return TemplateProcessorFactory(
            song_features=mock_song_features,
            job_config=job_config,
            fixtures=mock_fixtures,
            xsq=mock_xsq,
        )

    def test_factory_initializes_dependencies(self, factory):
        """Test factory creates all dependencies once."""
        # Verify all dependencies are created
        assert factory.time_resolver is not None
        assert factory.pose_resolver is not None
        assert factory.dmx_curve_mapper is not None
        assert factory.geometry_engine is not None
        assert factory.resolver_registry is not None
        assert factory.sequencer_context is not None

    def test_factory_creates_time_resolver(self, factory, mock_song_features):
        """Test factory creates TimeResolver with song features."""
        assert factory.time_resolver is not None
        # Time resolver should have parsed song features
        assert factory.time_resolver.tempo_bpm == mock_song_features["tempo_bpm"]
        assert len(factory.time_resolver.beats_s) == len(mock_song_features["beats_s"])

    def test_factory_creates_dmx_curve_mapper(self, factory):
        """Test factory creates DMXCurveMapper with all components."""
        mapper = factory.dmx_curve_mapper
        assert mapper is not None
        # DMXCurveMapper stores dependencies as private attributes
        assert mapper._generator is not None
        assert mapper._normalizer is not None
        assert mapper._tuner is not None

    def test_factory_creates_sequencer_context(self, factory, mock_song_features):
        """Test factory creates SequencerContext."""
        context = factory.sequencer_context
        assert context is not None
        assert context.fixture is not None
        assert context.boundaries is not None
        assert context.dmx_curve_mapper is not None
        assert context.beats_s == mock_song_features.get("beats_s", [])
        assert context.song_features == mock_song_features

    def test_factory_creates_processor(self, factory):
        """Test factory creates PatternStepProcessor."""
        processor = factory.create_processor()

        assert processor is not None
        assert processor.time_resolver == factory.time_resolver
        assert processor.pose_resolver == factory.pose_resolver
        assert processor.geometry_engine == factory.geometry_engine
        assert processor.resolver_registry == factory.resolver_registry
        assert processor.sequencer_context == factory.sequencer_context

    def test_factory_reuses_dependencies(self, factory):
        """Test factory doesn't recreate dependencies per processor."""
        processor1 = factory.create_processor()
        processor2 = factory.create_processor()

        # Should reuse same dependencies
        assert processor1.time_resolver is processor2.time_resolver
        assert processor1.pose_resolver is processor2.pose_resolver
        assert processor1.geometry_engine is processor2.geometry_engine
        # sequencer_context has dmx_curve_mapper
        assert (
            processor1.sequencer_context.dmx_curve_mapper
            is processor2.sequencer_context.dmx_curve_mapper
        )

    def test_factory_with_empty_beats(self, job_config, mock_xsq):
        """Test factory handles missing beats gracefully."""
        song_features = {"tempo_bpm": 120.0}  # No beats_s
        mock_fixtures = create_test_fixture_group(["MH1"])

        factory = TemplateProcessorFactory(
            song_features=song_features,
            job_config=job_config,
            fixtures=mock_fixtures,
            xsq=mock_xsq,
        )

        # Should use empty list for beats
        assert factory.sequencer_context.beats_s == []
