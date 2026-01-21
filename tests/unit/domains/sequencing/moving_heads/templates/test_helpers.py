"""Simplified test helpers to reduce mocking complexity.

This module provides simplified test fixtures that use real objects where
possible and minimal mocking, following the principle of "don't mock what
you own."
"""

from unittest.mock import Mock

from blinkb0t.core.config.models import JobConfig
from blinkb0t.core.domains.sequencing.models.templates import (
    PatternStep,
    Template,
    TransitionConfig,
)
from blinkb0t.core.domains.sequencing.models.timing import MusicalTiming
from blinkb0t.core.domains.sequencing.moving_heads.templates.factory import (
    TemplateProcessorFactory,
)


def create_minimal_song_features() -> dict:
    """Create minimal song features for testing.

    Uses real data structure, not mocks.
    """
    return {
        "tempo_bpm": 120.0,
        "duration_s": 180.0,
        "beats_s": [i * 0.5 for i in range(360)],  # 360 beats @ 120 BPM
        "bars_s": [i * 2.0 for i in range(90)],  # 90 bars
        "time_signature": {"time_signature": "4/4"},
        "energy": {
            "times_s": [i * 0.1 for i in range(1800)],
            "phrase_level": [0.5 + (i % 10) * 0.05 for i in range(1800)],
            "section_level": [0.6 + (i % 5) * 0.02 for i in range(1800)],
        },
        "rhythm": {
            "beats_s": [i * 0.5 for i in range(360)],
            "downbeats_s": [i * 2.0 for i in range(90)],
        },
        "structure": {
            "sections": [
                {"start_s": 0.0, "end_s": 60.0, "name": "intro"},
                {"start_s": 60.0, "end_s": 120.0, "name": "verse"},
                {"start_s": 120.0, "end_s": 180.0, "name": "chorus"},
            ]
        },
    }


def create_simple_template(
    template_id: str = "test_template",
    movement_id: str = "sweep_lr",
    geometry_id: str | None = None,
    dimmer_id: str = "pulse",
) -> Template:
    """Create a simple single-step template for testing.

    Args:
        template_id: Template identifier
        movement_id: Movement pattern to use
        geometry_id: Optional geometry pattern
        dimmer_id: Dimmer pattern to use

    Returns:
        Template with one pattern step
    """
    return Template(
        template_id=template_id,
        name=f"Test {template_id}",
        category="medium_energy",
        timing={"mode": "musical", "default_duration_bars": 8.0},
        steps=[
            PatternStep(
                step_id="step1",
                target="ALL",
                timing={
                    "base_timing": MusicalTiming(
                        mode="musical",
                        start_offset_bars=0.0,
                        duration_bars=4.0,
                    ),
                    "loop": False,
                },
                movement_id=movement_id,
                movement_params={"intensity": "SMOOTH"},
                geometry_id=geometry_id,
                geometry_params={},
                dimmer_id=dimmer_id,
                dimmer_params={"intensity": "SMOOTH"},
                entry_transition=TransitionConfig(mode="snap", duration_bars=0.0),
                exit_transition=TransitionConfig(mode="snap", duration_bars=0.0),
                priority=0,
                blend_mode="override",
            )
        ],
        metadata={
            "description": "Test template",
            "recommended_sections": ["verse", "chorus"],
            "energy_range": [10, 30],
            "tags": ["test"],
        },
    )


class ProcessorTestHelper:
    """Helper class to simplify processor testing.

    Uses the real factory pattern to create processors with minimal mocking.
    Only mocks XSQ (external dependency) and optionally overrides specific
    components for focused testing.

    Example:
        helper = ProcessorTestHelper()
        processor = helper.create_processor()

        # Test with real dependencies
        result = processor.process_template(template, fixture, base_pose)

        # Or override specific components for focused testing
        mock_time_resolver = Mock()
        processor = helper.create_processor(time_resolver=mock_time_resolver)
    """

    def __init__(
        self,
        song_features: dict | None = None,
        job_config: JobConfig | None = None,
    ):
        """Initialize helper with test data.

        Args:
            song_features: Optional song features (uses minimal if None)
            job_config: Optional job config (uses default if None)
        """
        self.song_features = song_features or create_minimal_song_features()
        self.job_config = job_config or JobConfig(fixture_config_path="test.json")
        self.mock_xsq = Mock()  # Only external dependency we mock

    def create_factory(self, fixtures) -> TemplateProcessorFactory:
        """Create factory with real dependencies.

        Args:
            fixtures: FixtureGroup instance

        Returns:
            TemplateProcessorFactory with minimal mocking
        """
        return TemplateProcessorFactory(
            song_features=self.song_features,
            job_config=self.job_config,
            fixtures=fixtures,
            xsq=self.mock_xsq,
        )

    def create_processor(
        self,
        fixtures,
        time_resolver=None,
        pose_resolver=None,
        geometry_engine=None,
        resolver_registry=None,
        sequencer_context=None,
    ):
        """Create processor with optional component overrides.

        Args:
            fixtures: FixtureGroup instance
            time_resolver: Optional TimeResolver override
            pose_resolver: Optional PoseResolver override
            geometry_engine: Optional GeometryEngine override
            resolver_registry: Optional ResolverRegistry override
            sequencer_context: Optional SequencerContext override

        Returns:
            PatternStepProcessor configured for testing

        Example:
            # Use real dependencies
            processor = helper.create_processor(fixtures)

            # Override specific components
            mock_geometry = Mock()
            processor = helper.create_processor(
                fixtures,
                geometry_engine=mock_geometry
            )
        """
        factory = self.create_factory(fixtures)

        # Create processor using factory
        processor = factory.create_processor()

        # Override specific components if provided
        if time_resolver is not None:
            processor.time_resolver = time_resolver
        if pose_resolver is not None:
            processor.pose_resolver = pose_resolver
        if geometry_engine is not None:
            processor.geometry_engine = geometry_engine
        if resolver_registry is not None:
            processor.resolver_registry = resolver_registry
        if sequencer_context is not None:
            processor.sequencer_context = sequencer_context

        return processor


def create_mock_for_method(method_name: str, return_value=None):
    """Create a focused mock for a single method.

    Helper to create mocks that only respond to one method call.
    Reduces mock complexity and makes tests more explicit.

    Args:
        method_name: Name of method to mock
        return_value: Value to return from method

    Returns:
        Mock configured for single method

    Example:
        mock_resolver = create_mock_for_method("resolve_timing", (0.0, 1000.0))
        # mock_resolver.resolve_timing() returns (0.0, 1000.0)
    """
    mock = Mock()
    setattr(mock, method_name, Mock(return_value=return_value))
    return mock
