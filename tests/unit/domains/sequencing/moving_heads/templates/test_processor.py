"""Unit tests for PatternStepProcessor."""

from unittest.mock import MagicMock, Mock

import pytest

from blinkb0t.core.domains.sequencing.models.poses import PoseID
from blinkb0t.core.domains.sequencing.models.templates import (
    PatternStep,
    Template,
    TransitionConfig,
)
from blinkb0t.core.domains.sequencing.models.timing import MusicalTiming
from blinkb0t.core.domains.sequencing.moving_heads.templates.processor import (
    PatternStepProcessor,
)

from .conftest import create_test_fixture, create_test_fixture_group


class TestPatternStepProcessor:
    @pytest.fixture
    def mock_time_resolver(self):
        """Mock TimeResolver."""
        resolver = Mock()
        resolver.resolve_timing = Mock(return_value=(0.0, 1000.0))
        return resolver

    @pytest.fixture
    def mock_pose_resolver(self):
        """Mock PoseResolver."""
        resolver = Mock()
        resolver.resolve_pose = Mock(return_value=(0.0, 45.0))  # pan, tilt
        return resolver

    @pytest.fixture
    def mock_geometry_engine(self):
        """Mock GeometryEngine."""
        engine = Mock()
        engine.apply_geometry = Mock(return_value={"MH1": {"pattern": "sweep_lr"}})
        return engine

    @pytest.fixture
    def mock_resolver_registry(self):
        """Mock ResolverRegistry."""
        registry = Mock()
        mock_resolver = Mock()
        mock_resolver.resolve = Mock(return_value=[])
        registry.get_resolver = Mock(return_value=mock_resolver)
        return registry

    @pytest.fixture
    def mock_sequencer_context(self):
        """Mock SequencerContext."""
        return Mock()

    @pytest.fixture
    def mock_xsq(self):
        """Mock XSQ."""
        return MagicMock()

    @pytest.fixture
    def mock_fixture(self):
        """Create a real fixture instance for testing."""
        return create_test_fixture("MH1")

    @pytest.fixture
    def mock_fixtures(self):
        """Create a real fixture group for testing."""
        return create_test_fixture_group(["MH1"])

    @pytest.fixture
    def mock_job_config(self):
        """Mock JobConfig."""
        from blinkb0t.core.config.models import AgentOrchestrationConfig, JobConfig

        # Rebuild JobConfig model to resolve forward references
        JobConfig.model_rebuild()

        return JobConfig(agent=AgentOrchestrationConfig())

    @pytest.fixture
    def mock_channel_pipeline(self):
        """Mock ChannelIntegrationPipeline."""
        pipeline = Mock()
        pipeline.process_section = Mock(return_value=[])
        return pipeline

    @pytest.fixture
    def processor(
        self,
        mock_time_resolver,
        mock_pose_resolver,
        mock_geometry_engine,
        mock_resolver_registry,
        mock_sequencer_context,
        mock_xsq,
        mock_fixtures,
        mock_job_config,
        mock_channel_pipeline,
    ):
        """Create processor instance."""
        processor_instance = PatternStepProcessor(
            time_resolver=mock_time_resolver,
            pose_resolver=mock_pose_resolver,
            geometry_engine=mock_geometry_engine,
            resolver_registry=mock_resolver_registry,
            sequencer_context=mock_sequencer_context,
            xsq=mock_xsq,
            song_features={"tempo_bpm": 120.0},
            fixtures=mock_fixtures,
            job_config=mock_job_config,
            channel_pipeline=mock_channel_pipeline,
        )

        # Mock the transition processor to avoid timeline processing issues with Mocks
        mock_transition_processor = Mock()
        mock_transition_processor.process = Mock(return_value=[])
        processor_instance.transition_processor = mock_transition_processor

        return processor_instance

    @pytest.fixture
    def simple_template(self):
        """Create a simple template for testing."""
        return Template(
            template_id="test_template",
            name="Test Template",
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
                    movement_id="sweep_lr",
                    movement_params={"intensity": "SMOOTH"},
                    geometry_id=None,
                    geometry_params={},
                    dimmer_id="pulse",
                    dimmer_params={"intensity": "SMOOTH"},
                    entry_transition=TransitionConfig(mode="snap", duration_bars=0.0),
                    exit_transition=TransitionConfig(mode="snap", duration_bars=0.0),
                    priority=0,
                    blend_mode="override",
                )
            ],
            metadata={
                "description": "Test template",
                "recommended_sections": [],
                "energy_range": [10, 30],
                "tags": [],
            },
        )

    def test_processor_initializes_with_dependencies(self, processor):
        """Test processor initializes with all injected dependencies."""
        assert processor.time_resolver is not None
        assert processor.pose_resolver is not None
        assert processor.geometry_engine is not None
        assert processor.resolver_registry is not None
        assert processor.sequencer_context is not None
        assert processor.xsq is not None
        assert processor.context_builder is not None

    def test_process_template_calls_time_resolver(
        self, processor, simple_template, mock_fixture, mock_time_resolver
    ):
        """Test processing calls time resolver for each step."""
        processor.process_template(
            template=simple_template,
            fixture=mock_fixture,
            base_pose=PoseID.FORWARD,
            section_start_ms=0.0,
            section_end_ms=16000.0,
        )

        # Should call time resolver for the step
        assert mock_time_resolver.resolve_timing.called

    def test_process_template_calls_pose_resolver(
        self, processor, simple_template, mock_fixture, mock_pose_resolver
    ):
        """Test processing calls pose resolver."""
        processor.process_template(
            template=simple_template,
            fixture=mock_fixture,
            base_pose=PoseID.FORWARD,
            section_start_ms=0.0,
            section_end_ms=16000.0,
        )

        # Should call pose resolver with base pose
        mock_pose_resolver.resolve_pose.assert_called_with(PoseID.FORWARD)

    def test_process_template_applies_geometry(self, processor, mock_fixture, mock_geometry_engine):
        """Test processing applies geometry when specified."""
        template = Template(
            template_id="geo_template",
            name="Geometry Template",
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
                    movement_id="sweep_lr",
                    movement_params={},
                    geometry_id="fan",  # Geometry specified
                    geometry_params={"fan_width": 0.7},
                    dimmer_id="pulse",
                    dimmer_params={},
                    entry_transition=TransitionConfig(mode="snap", duration_bars=0.0),
                    exit_transition=TransitionConfig(mode="snap", duration_bars=0.0),
                    priority=0,
                    blend_mode="override",
                )
            ],
            metadata={
                "description": "Test",
                "recommended_sections": [],
                "energy_range": [10, 30],
                "tags": [],
            },
        )

        processor.process_template(
            template=template,
            fixture=mock_fixture,
            base_pose=PoseID.FORWARD,
            section_start_ms=0.0,
            section_end_ms=16000.0,
        )

        # Should call geometry engine
        assert mock_geometry_engine.apply_geometry.called

    def test_process_template_routes_to_handler(
        self, processor, simple_template, mock_fixture, mock_resolver_registry
    ):
        """Test processing routes to handler via registry."""
        processor.process_template(
            template=simple_template,
            fixture=mock_fixture,
            base_pose=PoseID.FORWARD,
            section_start_ms=0.0,
            section_end_ms=16000.0,
        )

        # Should get resolver from registry
        mock_resolver_registry.get_resolver.assert_called_with("sweep_lr")

    def test_process_template_returns_effects(
        self, processor, simple_template, mock_fixture, mock_resolver_registry
    ):
        """Test processing returns effects from handler through pipeline."""
        # Handler returns SequencedEffect (mocked)
        mock_sequenced_effects = [Mock(), Mock()]
        mock_resolver = Mock()
        mock_resolver.resolve = Mock(return_value=mock_sequenced_effects)
        mock_resolver_registry.get_resolver = Mock(return_value=mock_resolver)

        # Pipeline returns DmxEffect (mocked)
        mock_dmx_effects = [Mock(), Mock()]
        processor.channel_pipeline.process_section = Mock(return_value=mock_dmx_effects)

        # XsqAdapter returns EffectPlacement (mocked)
        mock_placements = [Mock(), Mock()]
        processor.xsq_adapter.convert = Mock(return_value=mock_placements)

        # Mock transition processor to return mock placements (after gap filling)
        processor.transition_processor.process = Mock(return_value=mock_placements)

        effects = processor.process_template(
            template=simple_template,
            fixture=mock_fixture,
            base_pose=PoseID.FORWARD,
            section_start_ms=0.0,
            section_end_ms=16000.0,
        )

        # Verify pipeline was called with handler output
        processor.channel_pipeline.process_section.assert_called_once()
        # Verify adapter was called with pipeline output
        processor.xsq_adapter.convert.assert_called_once()
        # Verify transition processor was called
        processor.transition_processor.process.assert_called_once()
        # Verify final output is from transition processor (which includes gap-filled effects)
        assert effects == mock_placements

    def test_apply_parameters_movement_categorical_smooth(self, processor):
        """Test categorical parameter mapping for SMOOTH movement intensity."""
        resolved = processor._apply_parameters(
            library_id="sweep_lr",
            template_params={"intensity": "SMOOTH"},
            library_type="movement",
        )

        # SMOOTH should map to specific numeric values (low amplitude)
        assert "amplitude" in resolved
        assert "frequency" in resolved
        assert "center" in resolved
        assert resolved["amplitude"] < 0.5  # Low amplitude for SMOOTH
        assert resolved["frequency"] > 0.0
        assert resolved["center"] == 128

    def test_apply_parameters_movement_categorical_dramatic(self, processor):
        """Test categorical parameter mapping for DRAMATIC movement intensity."""
        resolved = processor._apply_parameters(
            library_id="sweep_lr",
            template_params={"intensity": "DRAMATIC"},
            library_type="movement",
        )

        # DRAMATIC should have higher amplitude than SMOOTH
        assert "amplitude" in resolved
        assert "frequency" in resolved
        assert resolved["amplitude"] > 0.5  # Higher amplitude
        assert resolved["frequency"] > 0.0

    def test_apply_parameters_movement_categorical_intense(self, processor):
        """Test categorical parameter mapping for INTENSE movement intensity."""
        # Note: Library uses 3-level system (SMOOTH, DRAMATIC, INTENSE), not EXTREME
        resolved = processor._apply_parameters(
            library_id="sweep_lr",
            template_params={"intensity": "INTENSE"},
            library_type="movement",
        )

        # INTENSE should have highest amplitude (1.0 for sweep_lr)
        assert "amplitude" in resolved
        assert resolved["amplitude"] >= 0.9  # Very high amplitude (INTENSE = 1.0)

    def test_apply_parameters_dimmer_categorical(self, processor):
        """Test categorical parameter mapping for dimmer intensity."""
        # Note: Library uses 3-level system (SMOOTH, DRAMATIC, INTENSE), not MEDIUM
        resolved = processor._apply_parameters(
            library_id="pulse",
            template_params={"intensity": "DRAMATIC"},
            library_type="dimmer",
        )

        # Dimmer should resolve to dimmer-specific numeric parameters
        # DimmerCategoricalParams has: min_intensity, max_intensity, period
        assert "min_intensity" in resolved
        assert "max_intensity" in resolved
        assert "period" in resolved
        assert isinstance(resolved["min_intensity"], int)
        assert isinstance(resolved["max_intensity"], int)
        assert isinstance(resolved["period"], (int, float))

    def test_apply_parameters_geometry_passthrough(self, processor):
        """Test that geometry parameters pass through as-is (no categorical mapping)."""
        resolved = processor._apply_parameters(
            library_id="fan",
            template_params={"intensity": "SMOOTH", "custom": 42},
            library_type="geometry",
        )

        # Geometry params should pass through unchanged (no categorical mapping)
        assert resolved == {"intensity": "SMOOTH", "custom": 42}

    def test_apply_parameters_direct_passthrough(self, processor):
        """Test direct (non-categorical) parameters pass through unchanged."""
        resolved = processor._apply_parameters(
            library_id="sweep_lr",
            template_params={"custom_param": 42, "another": "value"},
            library_type="movement",
        )

        # Direct params should pass through
        assert resolved["custom_param"] == 42
        assert resolved["another"] == "value"

    def test_apply_parameters_invalid_library_id(self, processor):
        """Test error handling for invalid library ID."""
        with pytest.raises(ValueError, match="not found in movement library"):
            processor._apply_parameters(
                library_id="nonexistent_pattern",
                template_params={"intensity": "SMOOTH"},
                library_type="movement",
            )

    def test_apply_parameters_invalid_library_type(self, processor):
        """Test error handling for invalid library type."""
        with pytest.raises(ValueError, match="not found in invalid_type library"):
            processor._apply_parameters(
                library_id="sweep_lr",
                template_params={"intensity": "SMOOTH"},
                library_type="invalid_type",
            )

    def test_apply_parameters_unknown_categorical_value(self, processor):
        """Test handling of unknown categorical intensity value."""
        # Should log warning but not crash
        resolved = processor._apply_parameters(
            library_id="sweep_lr",
            template_params={"intensity": "UNKNOWN_INTENSITY"},
            library_type="movement",
        )

        # Should still return base params
        assert isinstance(resolved, dict)

    def test_build_step_context_full_resolution(
        self, processor, mock_fixture, mock_time_resolver, mock_pose_resolver
    ):
        """Test building complete StepContext with all resolution."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.processor import StepContext

        step = PatternStep(
            step_id="test_step",
            target="ALL",
            timing={
                "base_timing": MusicalTiming(
                    mode="musical",
                    start_offset_bars=0.0,
                    duration_bars=4.0,
                ),
                "loop": False,
            },
            movement_id="sweep_lr",
            movement_params={"intensity": "SMOOTH"},
            geometry_id="fan",
            geometry_params={"intensity": "SMOOTH"},
            dimmer_id="pulse",
            dimmer_params={"intensity": "SMOOTH"},
            entry_transition=TransitionConfig(mode="snap", duration_bars=0.0),
            exit_transition=TransitionConfig(mode="snap", duration_bars=0.0),
            priority=0,
            blend_mode="override",
        )

        context = processor._build_step_context(
            step=step,
            fixture=mock_fixture,
            base_pose=PoseID.FORWARD,
            section_start_ms=1000.0,
            section_end_ms=9000.0,
        )

        # Verify StepContext structure
        assert isinstance(context, StepContext)
        assert context.step == step
        assert isinstance(context.start_ms, int)
        assert isinstance(context.end_ms, int)
        assert isinstance(context.pan_deg, float)
        assert isinstance(context.tilt_deg, float)
        assert context.fixture == mock_fixture

        # Verify numeric parameters resolved
        assert isinstance(context.movement_numeric_params, dict)
        assert isinstance(context.geometry_numeric_params, dict)
        assert isinstance(context.dimmer_numeric_params, dict)

        # Verify categorical params were resolved to numeric
        # Movement and dimmer should have numeric params
        assert "amplitude" in context.movement_numeric_params
        assert "frequency" in context.movement_numeric_params
        # Dimmer uses different params (min_intensity, max_intensity, period)
        assert (
            "min_intensity" in context.dimmer_numeric_params
            or "amplitude" in context.dimmer_numeric_params
        )

        # Geometry params are passed through as-is (no categorical mapping for geometry)
        assert context.geometry_numeric_params == {"intensity": "SMOOTH"}

        # Verify time resolver was called
        mock_time_resolver.resolve_timing.assert_called_once()

        # Verify pose resolver was called
        mock_pose_resolver.resolve_pose.assert_called_once_with(PoseID.FORWARD)

    def test_build_step_context_without_geometry(
        self, processor, mock_fixture, mock_time_resolver, mock_pose_resolver
    ):
        """Test building StepContext without geometry."""
        step = PatternStep(
            step_id="test_step",
            target="ALL",
            timing={
                "base_timing": MusicalTiming(
                    mode="musical",
                    start_offset_bars=0.0,
                    duration_bars=4.0,
                ),
                "loop": False,
            },
            movement_id="sweep_lr",
            movement_params={"intensity": "DRAMATIC"},
            geometry_id=None,  # No geometry
            geometry_params={},
            dimmer_id="pulse",
            dimmer_params={"intensity": "DRAMATIC"},
            entry_transition=TransitionConfig(mode="snap", duration_bars=0.0),
            exit_transition=TransitionConfig(mode="snap", duration_bars=0.0),
            priority=0,
            blend_mode="override",
        )

        context = processor._build_step_context(
            step=step,
            fixture=mock_fixture,
            base_pose=PoseID.FORWARD,
            section_start_ms=0.0,
            section_end_ms=8000.0,
        )

        # Geometry params should be empty dict
        assert context.geometry_numeric_params == {}

        # But movement and dimmer should still be resolved
        assert "amplitude" in context.movement_numeric_params
        # Dimmer uses different params
        assert (
            "min_intensity" in context.dimmer_numeric_params
            or "amplitude" in context.dimmer_numeric_params
        )

    def test_process_step_uses_resolved_numeric_params(
        self,
        processor,
        mock_fixture,
        mock_time_resolver,
        mock_pose_resolver,
        mock_resolver_registry,
    ):
        """Test that _process_step uses resolved numeric parameters."""
        # Setup mock resolver
        mock_resolver = Mock()
        mock_resolver.resolve = Mock(return_value=[])
        mock_resolver_registry.get_resolver = Mock(return_value=mock_resolver)

        step = PatternStep(
            step_id="test_step",
            target="ALL",
            timing={
                "base_timing": MusicalTiming(
                    mode="musical",
                    start_offset_bars=0.0,
                    duration_bars=4.0,
                ),
                "loop": False,
            },
            movement_id="sweep_lr",
            movement_params={"intensity": "DRAMATIC"},  # Categorical
            geometry_id=None,
            geometry_params={},
            dimmer_id="pulse",
            dimmer_params={"intensity": "DRAMATIC"},  # Categorical
            entry_transition=TransitionConfig(mode="snap", duration_bars=0.0),
            exit_transition=TransitionConfig(mode="snap", duration_bars=0.0),
            priority=0,
            blend_mode="override",
        )

        processor._process_step(
            step=step,
            fixture=mock_fixture,
            base_pose=PoseID.FORWARD,
            section_start_ms=0.0,
            section_end_ms=8000.0,
        )

        # Verify resolver was called
        assert mock_resolver.resolve.called

        # Get the instruction passed to resolver
        call_args = mock_resolver.resolve.call_args
        instruction = call_args.kwargs.get("instruction") or call_args[1]["instruction"]

        # Verify movement spec has NUMERIC params (not "DRAMATIC")
        movement_spec = instruction["movement"]
        assert "amplitude" in movement_spec
        assert "frequency" in movement_spec
        assert isinstance(movement_spec["amplitude"], (int, float))
        assert isinstance(movement_spec["frequency"], (int, float))

        # Verify dimmer spec has NUMERIC params (not "DRAMATIC")
        dimmer_spec = instruction["dimmer"]
        # Dimmer uses different param names: min_intensity, max_intensity, period
        assert "min_intensity" in dimmer_spec or "amplitude" in dimmer_spec
        has_numeric = any(
            key in dimmer_spec for key in ["min_intensity", "max_intensity", "period", "amplitude"]
        )
        assert has_numeric, f"No numeric params found in dimmer_spec: {dimmer_spec}"
