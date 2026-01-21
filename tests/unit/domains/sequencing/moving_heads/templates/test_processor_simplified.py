"""Simplified PatternStepProcessor tests using test helpers.

This demonstrates the simplified testing approach:
- Use real objects where possible (don't mock what you own)
- Only mock external dependencies (XSQ)
- Use factory pattern to reduce setup complexity
- Focus mocks on specific behaviors under test
"""

import pytest

from blinkb0t.core.domains.sequencing.models.poses import PoseID

from .conftest import create_test_fixture, create_test_fixture_group
from .test_helpers import (
    ProcessorTestHelper,
    create_mock_for_method,
    create_simple_template,
)


class TestPatternStepProcessorSimplified:
    """Simplified tests with reduced mocking complexity."""

    @pytest.fixture
    def helper(self):
        """Create test helper with minimal configuration."""
        return ProcessorTestHelper()

    @pytest.fixture
    def fixture(self):
        """Create real test fixture (not a mock)."""
        return create_test_fixture("MH1")

    @pytest.fixture
    def fixtures(self):
        """Create real fixture group (not a mock)."""
        return create_test_fixture_group(["MH1"])

    @pytest.fixture
    def template(self):
        """Create real template (not a mock)."""
        return create_simple_template()

    def test_processor_uses_real_dependencies(self, helper, fixtures):
        """Test processor works with real dependencies (integration-style).

        This test uses the factory pattern to create a processor with
        real implementations. Only XSQ is mocked (external dependency).
        """
        processor = helper.create_processor(fixtures)

        # Verify processor has real dependencies
        assert processor.time_resolver is not None
        assert processor.pose_resolver is not None
        assert processor.geometry_engine is not None
        assert processor.resolver_registry is not None
        assert processor.sequencer_context is not None

        # All are real objects, not mocks
        assert not hasattr(processor.time_resolver, "_mock_name")
        assert not hasattr(processor.pose_resolver, "_mock_name")

    def test_processor_with_focused_mock(self, helper, fixtures, fixture, template):
        """Test specific behavior with focused mocking.

        Only mocks the component under test, uses real dependencies
        for everything else.
        """
        # Create focused mock for time resolver
        mock_time_resolver = create_mock_for_method(
            "resolve_timing",
            return_value=(0.0, 1000.0),  # start_ms, end_ms
        )

        # Create processor with ONE mocked component
        processor = helper.create_processor(fixtures, time_resolver=mock_time_resolver)

        # Process template
        processor.process_template(
            template=template,
            fixture=fixture,
            base_pose=PoseID.FORWARD,
            section_start_ms=0.0,
            section_end_ms=8000.0,  # 8 seconds
        )

        # Verify only the mocked component was called
        mock_time_resolver.resolve_timing.assert_called()

    def test_processor_with_custom_song_features(self, fixtures, fixture, template):
        """Test processor with custom song features.

        Demonstrates how to test with different configurations
        without excessive mocking.
        """
        custom_features = {
            "tempo_bpm": 140.0,  # Faster tempo
            "duration_s": 120.0,
            "beats_s": [i * 0.4286 for i in range(280)],  # 280 beats @ 140 BPM
            "bars_s": [i * 1.714 for i in range(70)],
            "time_signature": {"time_signature": "4/4"},
            "energy": {
                "times_s": [i * 0.1 for i in range(1200)],
                "phrase_level": [0.7] * 1200,  # High energy
                "section_level": [0.8] * 1200,
            },
            "rhythm": {
                "beats_s": [i * 0.4286 for i in range(280)],
                "downbeats_s": [i * 1.714 for i in range(70)],
            },
            "structure": {
                "sections": [
                    {"start_s": 0.0, "end_s": 120.0, "name": "full_song"},
                ]
            },
        }

        helper = ProcessorTestHelper(song_features=custom_features)
        processor = helper.create_processor(fixtures)

        # Processor now uses custom features
        result = processor.process_template(
            template=template,
            fixture=fixture,
            base_pose=PoseID.FORWARD,
            section_start_ms=0.0,
            section_end_ms=8000.0,
        )

        assert result is not None

    def test_multiple_templates_same_processor(self, helper, fixtures, fixture):
        """Test processing multiple templates with same processor.

        Demonstrates reusing processor setup across tests.
        """
        processor = helper.create_processor(fixtures)

        # Process different movement templates
        templates = [
            create_simple_template("sweep_template", movement_id="sweep_lr"),
            create_simple_template("circle_template", movement_id="circle"),
            create_simple_template("figure8_template", movement_id="figure8"),
        ]

        for template in templates:
            result = processor.process_template(
                template=template,
                fixture=fixture,
                base_pose=PoseID.FORWARD,
                section_start_ms=0.0,
                section_end_ms=8000.0,
            )
            assert result is not None


class TestComparisonWithOldApproach:
    """Comparison showing improvement over complex mocking.

    OLD APPROACH (7 mock fixtures):
    ```python
    def test_something(
        self,
        mock_time_resolver,
        mock_pose_resolver,
        mock_geometry_engine,
        mock_resolver_registry,
        mock_sequencer_context,
        mock_xsq,
        mock_fixtures,
    ):
        processor = PatternStepProcessor(
            time_resolver=mock_time_resolver,
            pose_resolver=mock_pose_resolver,
            geometry_engine=mock_geometry_engine,
            resolver_registry=mock_resolver_registry,
            sequencer_context=mock_sequencer_context,
            xsq=mock_xsq,
            song_features=...,
            fixtures=mock_fixtures,
        )
        # 50+ lines of mock setup...
    ```

    NEW APPROACH (1 helper, real objects):
    ```python
    def test_something(self, helper, fixtures):
        processor = helper.create_processor(fixtures)
        # Real dependencies, works immediately
    ```

    Benefits:
    - Reduces test setup from 50+ lines to 1-2 lines
    - Uses real objects (better integration coverage)
    - Only mocks external dependencies
    - Tests are more maintainable
    - Easier to understand test intent
    """
