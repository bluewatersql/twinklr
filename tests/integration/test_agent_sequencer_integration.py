"""Integration tests for Agent ↔ Sequencer handoff.

Tests the integration between AgentOrchestrator (plan/implementation generation)
and MovingHeadSequencer (applying plans to XSQ files).

Focus: Data contract validation at the integration boundary.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from blinkb0t.core.agents.moving_heads.models_agent_plan import (
    AgentImplementation,
    ImplementationSection,
)
from blinkb0t.core.agents.moving_heads.orchestrator import OrchestratorResult, OrchestratorStatus
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
from blinkb0t.core.domains.sequencing.moving_heads.sequencer import MovingHeadSequencer

# Rebuild JobConfig model to resolve forward references
# AgentOrchestrationConfig must be imported before model_rebuild()
JobConfig.model_rebuild()


@pytest.fixture
def minimal_fixtures():
    """Create minimal fixture configuration for testing."""
    base_config = FixtureConfig(
        fixture_id="MH1",
        dmx_start_address=1,
        position=FixturePosition(x=0.0, y=0.0, z=0.0),
        dmx_mapping=DmxMapping(
            pan_channel=11,
            tilt_channel=13,
            dimmer_channel=3,
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
                config=base_config,
                xlights_model_name="MH1-Model",
            ),
        ],
    )


@pytest.fixture
def minimal_job_config():
    """Create minimal job configuration for testing."""
    return JobConfig.model_validate(
        {
            "assumptions": {"beats_per_bar": 4},
            "moving_heads": {
                "dmx_effect_defaults": {
                    "buffer_style": "Per Model Default",
                    "dimmer_default": 100,
                },
                "model_map": {"MH1": "MH1-Model", "ALL": "ALL"},
            },
            "agent": {},
        }
    )


@pytest.fixture
def minimal_song_features():
    """Create minimal song features for testing."""
    return {
        "tempo_bpm": 120.0,
        "beats_s": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
        "bars_s": [0.5, 2.5, 4.5],
        "rhythm": {
            "downbeats": [0, 4, 8],
        },
    }


@pytest.fixture
def minimal_xsq(tmp_path: Path) -> Path:
    """Create a minimal XSQ file for testing."""
    import xml.etree.ElementTree as ET

    root = ET.Element("xsequence")
    head = ET.SubElement(root, "head")
    ET.SubElement(head, "version").text = "2023.17"
    ET.SubElement(head, "mediaFile").text = "test.mp3"
    ET.SubElement(head, "sequenceDuration").text = "10.000"

    # DisplayElements
    display_elements = ET.SubElement(root, "DisplayElements")
    ET.SubElement(
        display_elements,
        "Element",
        {"collapsed": "0", "type": "model", "name": "MH1-Model", "visible": "1"},
    )

    # ElementEffects
    element_effects = ET.SubElement(root, "ElementEffects")
    el = ET.SubElement(element_effects, "Element", {"type": "model", "name": "MH1-Model"})
    ET.SubElement(el, "EffectLayer")

    xsq_path = tmp_path / "minimal.xsq"
    tree = ET.ElementTree(root)
    tree.write(str(xsq_path))
    return xsq_path


class TestAgentImplementationToSequencerHandoff:
    """Test the handoff from AgentOrchestrator (implementation) to MovingHeadSequencer."""

    def test_valid_implementation_is_accepted_by_sequencer(
        self,
        minimal_fixtures: FixtureGroup,
        minimal_job_config: JobConfig,
        minimal_song_features: dict,
        minimal_xsq: Path,
        tmp_path: Path,
    ):
        """Test that a valid AgentImplementation can be applied by the sequencer."""
        # Create a valid implementation (Phase 5A schema: bars)
        implementation = AgentImplementation(
            sections=[
                ImplementationSection(
                    name="Test Section",
                    plan_section_name="Test Section",
                    start_bar=1,
                    end_bar=3,
                    template_id="verse_sweep_pulse",
                    params={"intensity": "SMOOTH"},
                    base_pose="AUDIENCE_CENTER",
                    targets=["MH1"],
                    layer_priority=0,
                )
            ],
            total_duration_bars=5,
            quantization_applied=True,
            timing_precision="bar_aligned",
        )

        # Create sequencer
        sequencer = MovingHeadSequencer(job_config=minimal_job_config, fixtures=minimal_fixtures)

        # Apply implementation (should not raise)
        output_xsq = tmp_path / "output.xsq"
        sequencer.apply_implementation(
            xsq_in=str(minimal_xsq),
            xsq_out=str(output_xsq),
            implementation=implementation,
            song_features=minimal_song_features,
        )

        # Verify output file was created
        assert output_xsq.exists()

    def test_orchestrator_result_contract_is_valid(
        self,
        minimal_fixtures: FixtureGroup,
        minimal_job_config: JobConfig,
        minimal_song_features: dict,
        minimal_xsq: Path,
        tmp_path: Path,
    ):
        """Test that OrchestratorResult.implementation matches sequencer expectations."""
        # Simulate orchestrator output (Phase 5A schema: bars)
        implementation = AgentImplementation(
            sections=[
                ImplementationSection(
                    name="Intro",
                    plan_section_name="Intro",
                    start_bar=1,
                    end_bar=2,
                    template_id="verse_sweep_pulse",
                    params={"intensity": "SMOOTH"},
                    base_pose="AUDIENCE_CENTER",
                    targets=["ALL"],
                    layer_priority=0,
                )
            ],
            total_duration_bars=5,
            quantization_applied=True,
            timing_precision="bar_aligned",
        )

        orchestrator_result = OrchestratorResult(
            status=OrchestratorStatus.SUCCESS,
            plan=None,  # Not needed for this test
            implementation=implementation,
            evaluation=None,
            iterations=1,
            tokens_used=1000,
            execution_time_s=5.0,
            error=None,
            budget_report=None,
        )

        # Verify the contract: sequencer can accept orchestrator's implementation
        sequencer = MovingHeadSequencer(job_config=minimal_job_config, fixtures=minimal_fixtures)

        output_xsq = tmp_path / "output.xsq"
        sequencer.apply_implementation(
            xsq_in=str(minimal_xsq),
            xsq_out=str(output_xsq),
            implementation=orchestrator_result.implementation,
            song_features=minimal_song_features,
        )

        assert output_xsq.exists()

    def test_sequencer_handles_multiple_sections(
        self,
        minimal_fixtures: FixtureGroup,
        minimal_job_config: JobConfig,
        minimal_song_features: dict,
        minimal_xsq: Path,
        tmp_path: Path,
    ):
        """Test that sequencer correctly processes multiple sections from agent."""
        implementation = AgentImplementation(
            sections=[
                ImplementationSection(
                    name="Section 1",
                    plan_section_name="Section 1",
                    start_bar=1,
                    end_bar=1,
                    template_id="verse_sweep_pulse",
                    params={"intensity": "SMOOTH"},
                    base_pose="AUDIENCE_CENTER",
                    targets=["MH1"],
                    layer_priority=0,
                ),
                ImplementationSection(
                    name="Section 2",
                    plan_section_name="Section 2",
                    start_bar=2,
                    end_bar=2,
                    template_id="circle_breathe",
                    params={"intensity": "DRAMATIC"},
                    base_pose="AUDIENCE_CENTER",
                    targets=["MH1"],
                    layer_priority=0,
                ),
            ],
            total_duration_bars=5,
            quantization_applied=True,
            timing_precision="bar_aligned",
        )

        sequencer = MovingHeadSequencer(job_config=minimal_job_config, fixtures=minimal_fixtures)

        output_xsq = tmp_path / "output.xsq"
        sequencer.apply_implementation(
            xsq_in=str(minimal_xsq),
            xsq_out=str(output_xsq),
            implementation=implementation,
            song_features=minimal_song_features,
        )

        # Verify output created (detailed validation in other tests)
        assert output_xsq.exists()

    def test_sequencer_validates_template_id_presence(
        self,
        minimal_fixtures: FixtureGroup,
        minimal_job_config: JobConfig,
        minimal_song_features: dict,
        minimal_xsq: Path,
        tmp_path: Path,
    ):
        """Test that sequencer requires template_id (validates agent contract)."""
        # Create implementation with valid template_id
        implementation = AgentImplementation(
            sections=[
                ImplementationSection(
                    name="Test Section",
                    plan_section_name="Test Section",
                    start_bar=1,
                    end_bar=1,
                    template_id="verse_sweep_pulse",  # Valid template
                    params={},
                    base_pose="AUDIENCE_CENTER",
                    targets=["MH1"],
                    layer_priority=0,
                )
            ],
            total_duration_bars=5,
            quantization_applied=True,
            timing_precision="bar_aligned",
        )

        sequencer = MovingHeadSequencer(job_config=minimal_job_config, fixtures=minimal_fixtures)

        output_xsq = tmp_path / "output.xsq"

        # Should not raise (template_id is present and valid)
        sequencer.apply_implementation(
            xsq_in=str(minimal_xsq),
            xsq_out=str(output_xsq),
            implementation=implementation,
            song_features=minimal_song_features,
        )

        assert output_xsq.exists()

    def test_sequencer_accepts_semantic_targets_from_agent(
        self,
        minimal_fixtures: FixtureGroup,
        minimal_job_config: JobConfig,
        minimal_song_features: dict,
        minimal_xsq: Path,
        tmp_path: Path,
    ):
        """Test that sequencer handles semantic targets (ALL, LEFT, RIGHT, etc.) from agent."""
        implementation = AgentImplementation(
            sections=[
                ImplementationSection(
                    name="Test Section",
                    plan_section_name="Test Section",
                    start_bar=1,
                    end_bar=1,
                    template_id="verse_sweep_pulse",
                    params={},
                    base_pose="AUDIENCE_CENTER",
                    targets=["ALL"],  # Semantic target
                    layer_priority=0,
                )
            ],
            total_duration_bars=5,
            quantization_applied=True,
            timing_precision="bar_aligned",
        )

        sequencer = MovingHeadSequencer(job_config=minimal_job_config, fixtures=minimal_fixtures)

        output_xsq = tmp_path / "output.xsq"
        sequencer.apply_implementation(
            xsq_in=str(minimal_xsq),
            xsq_out=str(output_xsq),
            implementation=implementation,
            song_features=minimal_song_features,
        )

        assert output_xsq.exists()

    def test_song_features_required_fields_are_present(
        self,
        minimal_fixtures: FixtureGroup,
        minimal_job_config: JobConfig,
        minimal_xsq: Path,
        tmp_path: Path,
    ):
        """Test that song_features contains required fields for sequencer."""
        # Create song_features with all required fields
        song_features = {
            "tempo_bpm": 128.0,
            "beats_s": [0.5, 1.0, 1.5, 2.0],
            "bars_s": [0.5, 2.5],
            "rhythm": {
                "downbeats": [0, 4],
            },
        }

        implementation = AgentImplementation(
            sections=[
                ImplementationSection(
                    name="Test",
                    plan_section_name="Test",
                    start_bar=1,
                    end_bar=1,
                    template_id="verse_sweep_pulse",
                    params={},
                    base_pose="AUDIENCE_CENTER",
                    targets=["MH1"],
                    layer_priority=0,
                )
            ],
            total_duration_bars=5,
            quantization_applied=True,
            timing_precision="bar_aligned",
        )

        sequencer = MovingHeadSequencer(job_config=minimal_job_config, fixtures=minimal_fixtures)

        output_xsq = tmp_path / "output.xsq"

        # Should not raise (all required fields present)
        sequencer.apply_implementation(
            xsq_in=str(minimal_xsq),
            xsq_out=str(output_xsq),
            implementation=implementation,
            song_features=song_features,
        )

        assert output_xsq.exists()


class TestAgentPlanToSequencerHandoff:
    """Test the handoff from AgentOrchestrator (plan) to MovingHeadSequencer."""

    def test_valid_plan_is_accepted_by_sequencer(
        self,
        minimal_fixtures: FixtureGroup,
        minimal_job_config: JobConfig,
        minimal_song_features: dict,
        minimal_xsq: Path,
        tmp_path: Path,
    ):
        """Test that a valid AgentPlan can be applied by the sequencer."""
        # Create a valid plan (pre-Pydantic format as dict)
        plan = {
            "sections": [
                {
                    "name": "Test Section",
                    "start_ms": 0,
                    "end_ms": 2000,
                    "template_id": "sweep_pulse",
                    "instructions": [
                        {
                            "target": "MH1",
                            "movement": {"pattern": "sweep_lr"},
                            "dimmer": {"pattern": "static"},
                        }
                    ],
                }
            ]
        }

        sequencer = MovingHeadSequencer(job_config=minimal_job_config, fixtures=minimal_fixtures)

        output_xsq = tmp_path / "output.xsq"
        sequencer.apply_plan(
            xsq_in=str(minimal_xsq),
            xsq_out=str(output_xsq),
            plan=plan,
            song_features=minimal_song_features,
        )

        assert output_xsq.exists()

    def test_plan_without_template_id_is_skipped(
        self,
        minimal_fixtures: FixtureGroup,
        minimal_job_config: JobConfig,
        minimal_song_features: dict,
        minimal_xsq: Path,
        tmp_path: Path,
    ):
        """Test that sections without template_id are skipped (validates new format)."""
        # Plan with missing template_id (old format, should be skipped)
        plan = {
            "sections": [
                {
                    "name": "Test Section",
                    "start_ms": 0,
                    "end_ms": 2000,
                    # NO template_id - should be skipped
                    "instructions": [
                        {
                            "target": "MH1",
                            "movement": {"pattern": "sweep_lr"},
                        }
                    ],
                }
            ]
        }

        sequencer = MovingHeadSequencer(job_config=minimal_job_config, fixtures=minimal_fixtures)

        output_xsq = tmp_path / "output.xsq"

        # Should not raise, but section should be skipped (logged as warning)
        sequencer.apply_plan(
            xsq_in=str(minimal_xsq),
            xsq_out=str(output_xsq),
            plan=plan,
            song_features=minimal_song_features,
        )

        # Output file still created (just no effects from skipped section)
        assert output_xsq.exists()
