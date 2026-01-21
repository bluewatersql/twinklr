"""End-to-end integration test for renderer_v2 pipeline.

Tests the complete flow from AgentImplementation → XSQ file.
"""

from pathlib import Path

import pytest

from blinkb0t.core.agents.moving_heads.models_agent_plan import (
    AgentImplementation,
    ImplementationSection,
)
from blinkb0t.core.config.fixtures import (
    DmxMapping,
    FixtureConfig,
    FixtureGroup,
    FixtureInstance,
    FixturePosition,
    Orientation,
    PanTiltRange,
)
from blinkb0t.core.config.models import JobConfig
from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
    CurveGenerator,
    CustomCurveProvider,
    NativeCurveProvider,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
from blinkb0t.core.domains.sequencing.infrastructure.timing.beat_grid import BeatGrid
from blinkb0t.core.domains.sequencing.infrastructure.xsq import XSQParser
from blinkb0t.core.domains.sequencing.moving_heads.templates.loader import TemplateLoader
from blinkb0t.core.domains.sequencing.rendering.pipeline import RenderingPipeline

# Template directory
TEMPLATE_DIR = (
    Path(__file__).parent.parent.parent / "packages/blinkb0t/core/domains/sequencing/templates"
)


@pytest.fixture
def fixture_group():
    """Create test fixture group."""
    base_config = FixtureConfig(
        fixture_id="",
        dmx_start_address=1,
        position=FixturePosition(x=0.0, y=0.0, z=0.0),
        dmx_mapping=DmxMapping(
            pan_channel=1,
            tilt_channel=3,
            dimmer_channel=5,
        ),
        orientation=Orientation(
            pan_front_dmx=128,
            tilt_zero_dmx=0,
            tilt_up_dmx=255,
        ),
        pan_tilt_range=PanTiltRange(
            pan_deg=540.0,
            tilt_deg=270.0,
        ),
    )

    return FixtureGroup(
        group_id="MOVING_HEADS",
        xlights_group="ALL",
        fixtures=[
            FixtureInstance(
                fixture_id="MH1",
                config=base_config.model_copy(update={"fixture_id": "MH1", "dmx_start_address": 1}),
                xlights_model_name="Moving Head 1",
            ),
            FixtureInstance(
                fixture_id="MH2",
                config=base_config.model_copy(
                    update={"fixture_id": "MH2", "dmx_start_address": 20}
                ),
                xlights_model_name="Moving Head 2",
            ),
        ],
    )


@pytest.fixture
def beat_grid():
    """Create test beat grid."""
    # 120 BPM, 4/4 time, 16 bars = 32 seconds
    bar_boundaries = [i * 2000.0 for i in range(17)]  # 0, 2000, 4000, ...
    beat_boundaries = [i * 500.0 for i in range(65)]  # 4 beats per bar
    eighth_boundaries = BeatGrid._calculate_eighth_boundaries(beat_boundaries)
    sixteenth_boundaries = BeatGrid._calculate_sixteenth_boundaries(beat_boundaries)

    return BeatGrid(
        bar_boundaries=bar_boundaries,
        beat_boundaries=beat_boundaries,
        eighth_boundaries=eighth_boundaries,
        sixteenth_boundaries=sixteenth_boundaries,
        beats_per_bar=4,
        tempo_bpm=120.0,
        duration_ms=32000.0,
    )


@pytest.fixture
def agent_implementation():
    """Create test agent implementation."""
    return AgentImplementation(
        sections=[
            ImplementationSection(
                name="verse_1",
                plan_section_name="verse_1",
                start_bar=1,
                end_bar=8,
                template_id="gentle_sweep_breathe",
                params={"intensity": "SMOOTH"},
                base_pose="AUDIENCE_CENTER",
                targets=["ALL"],
                layer_priority=0,
                reasoning="Low energy verse with gentle movement",
            ),
            ImplementationSection(
                name="chorus_1",
                plan_section_name="chorus_1",
                start_bar=9,
                end_bar=16,
                template_id="energetic_fan_pulse",
                params={"intensity": "DRAMATIC"},
                base_pose="AUDIENCE_CENTER",
                targets=["ALL"],
                layer_priority=0,
                reasoning="High energy chorus with dynamic movement",
            ),
        ],
        total_duration_bars=16,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )


@pytest.fixture
def job_config():
    """Create test job configuration."""
    return JobConfig(
        job_id="test_job",
        audio_file="test.wav",
        xsq_input_path="input.xsq",
        xsq_output_path="output.xsq",
        fixture_config_path="fixtures.json",
    )


@pytest.fixture
def curve_generator():
    """Create curve generator."""
    # Empty library is fine for E2E tests - we're testing the pipeline, not curves
    curve_library = CurveLibrary()
    native_provider = NativeCurveProvider()
    custom_provider = CustomCurveProvider()

    return CurveGenerator(
        library=curve_library,
        native_provider=native_provider,
        custom_provider=custom_provider,
    )


def test_full_pipeline_agent_to_xsq(
    agent_implementation, fixture_group, beat_grid, job_config, curve_generator, tmp_path
):
    """Test complete pipeline: AgentImplementation → XSQ file.

    This test validates:
    1. Timeline planning (bars → segments)
    2. Channel overlay resolution
    3. Segment rendering (per-fixture)
    4. Gap rendering
    5. Curve generation & blending
    6. XSQ export
    """
    # Load template library
    template_loader = TemplateLoader(template_dir=TEMPLATE_DIR)
    template_library = template_loader.load_all()

    # Create output path
    output_path = tmp_path / "test_output.xsq"

    # Create and run pipeline
    pipeline = RenderingPipeline(
        curve_generator=curve_generator,
        fixture_group=fixture_group,
        job_config=job_config,
    )

    pipeline.render_to_xsq(
        implementation=agent_implementation,
        template_library=template_library,
        beat_grid=beat_grid,
        output_path=str(output_path),
        template_xsq=None,  # No template - create new sequence
    )

    # Verify output file was created
    assert output_path.exists(), "XSQ output file should be created"

    # Parse and validate XSQ
    parser = XSQParser()
    sequence = parser.parse(str(output_path))

    # Validate sequence structure
    assert sequence is not None, "Sequence should be parsed successfully"
    assert sequence.head is not None, "Sequence should have a head"

    # Check that effects were generated
    # Note: EffectDB is a custom class with .entries list
    assert sequence.effect_db is not None, "EffectDB should exist"
    assert len(sequence.effect_db.entries) > 0, "EffectDB should contain effects"

    # Verify element_effects were created (per-element effect collections)
    assert len(sequence.element_effects) > 0, "Sequence should have element_effects"

    for element in sequence.element_effects:
        if element.element_name.startswith("Moving Head"):
            assert len(element.effects) > 0, f"Fixture {element.element_name} should have effects"


def test_pipeline_with_layering(fixture_group, beat_grid, job_config, curve_generator, tmp_path):
    """Test pipeline with layered effects (multiple targets)."""
    # Create implementation with layering
    implementation = AgentImplementation(
        sections=[
            ImplementationSection(
                name="chorus_left",
                plan_section_name="chorus_1",
                start_bar=1,
                end_bar=8,
                template_id="energetic_fan_pulse",
                params={"intensity": "INTENSE"},
                base_pose="AUDIENCE_CENTER",
                targets=["MH1"],  # Layer 1
                layer_priority=0,
            ),
            ImplementationSection(
                name="chorus_right",
                plan_section_name="chorus_1",
                start_bar=1,
                end_bar=8,
                template_id="balanced_fan_swell",
                params={"intensity": "DRAMATIC"},
                base_pose="AUDIENCE_CENTER",
                targets=["MH2"],  # Layer 2 (different from MH1)
                layer_priority=1,
            ),
        ],
        total_duration_bars=8,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )

    # Load templates
    template_loader = TemplateLoader(template_dir=TEMPLATE_DIR)
    template_library = template_loader.load_all()

    output_path = tmp_path / "test_layered_output.xsq"

    # Create and run pipeline
    pipeline = RenderingPipeline(
        curve_generator=curve_generator,
        fixture_group=fixture_group,
        job_config=job_config,
    )

    pipeline.render_to_xsq(
        implementation=implementation,
        template_library=template_library,
        beat_grid=beat_grid,
        output_path=str(output_path),
    )

    # Verify output
    assert output_path.exists()

    # Parse and verify effects were generated for both layers
    parser = XSQParser()
    sequence = parser.parse(str(output_path))

    assert len(sequence.effect_db.entries) > 0, "Should have effects for both layers"
    assert len(sequence.element_effects) > 0, "Should have elements for fixtures"


def test_pipeline_with_gaps(fixture_group, beat_grid, job_config, curve_generator, tmp_path):
    """Test pipeline handles gaps correctly."""
    # Create implementation with gaps
    implementation = AgentImplementation(
        sections=[
            ImplementationSection(
                name="intro",
                plan_section_name="intro",
                start_bar=1,
                end_bar=4,
                template_id="gentle_sweep_breathe",
                params={"intensity": "SMOOTH"},
                base_pose="AUDIENCE_CENTER",
                targets=["ALL"],
                layer_priority=0,
            ),
            # Gap from bars 5-6
            ImplementationSection(
                name="verse",
                plan_section_name="verse",
                start_bar=7,
                end_bar=16,
                template_id="ambient_hold_pulse",
                params={"intensity": "SMOOTH"},
                base_pose="AUDIENCE_CENTER",
                targets=["ALL"],
                layer_priority=0,
            ),
        ],
        total_duration_bars=16,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )

    # Load templates
    template_loader = TemplateLoader(template_dir=TEMPLATE_DIR)
    template_library = template_loader.load_all()

    output_path = tmp_path / "test_gaps_output.xsq"

    # Create and run pipeline
    pipeline = RenderingPipeline(
        curve_generator=curve_generator,
        fixture_group=fixture_group,
        job_config=job_config,
    )

    pipeline.render_to_xsq(
        implementation=implementation,
        template_library=template_library,
        beat_grid=beat_grid,
        output_path=str(output_path),
    )

    # Verify output
    assert output_path.exists()

    parser = XSQParser()
    sequence = parser.parse(str(output_path))

    # Should have effects for both sections + gap fill
    assert len(sequence.effect_db.entries) > 0
    assert len(sequence.element_effects) > 0
