"""Factory for creating PatternStepProcessor with all dependencies."""

from __future__ import annotations

from typing import Any

from blinkb0t.core.config.fixtures import FixtureGroup
from blinkb0t.core.config.models import JobConfig
from blinkb0t.core.domains.sequencing.channels.pipeline import ChannelIntegrationPipeline
from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
    CurveGenerator,
    CustomCurveProvider,
    NativeCurveProvider,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
from blinkb0t.core.domains.sequencing.infrastructure.timing.resolver import TimeResolver
from blinkb0t.core.domains.sequencing.models.xsq import XSequence
from blinkb0t.core.domains.sequencing.moving_heads.resolvers.template_handler_registry import (
    ResolverRegistry,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.boundary_enforcer import (
    BoundaryEnforcer,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.engine import GeometryEngine
from blinkb0t.core.domains.sequencing.moving_heads.templates.handlers.base import SequencerContext
from blinkb0t.core.domains.sequencing.poses import PoseResolver


class TemplateProcessorFactory:
    """Factory for creating PatternStepProcessor with proper dependency injection.

    Follows Factory Pattern to centralize complex object construction.
    Creates shared infrastructure components once and injects them.
    """

    def __init__(
        self,
        song_features: dict[str, Any],
        job_config: JobConfig,
        fixtures: FixtureGroup,
        xsq: XSequence,
    ):
        """Initialize factory with runtime configuration.

        Args:
            song_features: Song features from audio analysis
            job_config: Job configuration with settings
            fixtures: Fixture group
            xsq: XSequence object
        """
        self.song_features = song_features
        self.job_config = job_config
        self.fixtures = fixtures
        self.xsq = xsq

        # Create shared infrastructure (ONCE, not per-render)
        self.time_resolver = TimeResolver(song_features=song_features)
        self.pose_resolver = PoseResolver()
        self.dmx_curve_mapper = self._create_curve_mapper()
        self.geometry_engine = GeometryEngine()
        self.resolver_registry = ResolverRegistry()
        self.channel_pipeline = ChannelIntegrationPipeline()

        # Create shared sequencer context
        # Expand fixtures to ensure we have FixtureInstance (not SimplifiedFixtureInstance)
        expanded_fixtures = fixtures.expand_fixtures()
        if not expanded_fixtures:
            raise ValueError("FixtureGroup must contain at least one fixture")
        first_fixture = expanded_fixtures[0]
        boundaries = BoundaryEnforcer(first_fixture)
        beats_s = song_features.get("beats_s", []) or []

        self.sequencer_context = SequencerContext(
            fixture=first_fixture,
            boundaries=boundaries,
            dmx_curve_mapper=self.dmx_curve_mapper,
            beats_s=beats_s,
            song_features=song_features,
        )

    def _create_curve_mapper(self) -> DMXCurveMapper:
        """Create DMXCurveMapper (follows MovingHeadSequencer pattern)."""
        # Load curve library
        curve_library = CurveLibrary()
        # TODO: Load from file if exists

        # Create curve engine components
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

    def create_processor(self):
        """Create PatternStepProcessor with all dependencies injected."""
        from .processor import PatternStepProcessor

        return PatternStepProcessor(
            time_resolver=self.time_resolver,
            pose_resolver=self.pose_resolver,
            geometry_engine=self.geometry_engine,
            resolver_registry=self.resolver_registry,
            sequencer_context=self.sequencer_context,
            xsq=self.xsq,
            song_features=self.song_features,
            fixtures=self.fixtures,
            job_config=self.job_config,
            channel_pipeline=self.channel_pipeline,
        )
