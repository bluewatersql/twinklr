"""Unit tests for TemplatePipeline."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from blinkb0t.core.config.models import JobConfig
from blinkb0t.core.domains.sequencing.models.poses import PoseID
from blinkb0t.core.domains.sequencing.moving_heads.templates.pipeline import (
    TemplatePipeline,
)

from .conftest import create_test_fixture, create_test_fixture_group


class TestTemplatePipeline:
    @pytest.fixture
    def mock_song_features(self):
        """Mock song features."""
        return {
            "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0],
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
    def job_config(self):
        """Job configuration."""
        return JobConfig()

    @pytest.fixture
    def temp_template_dir(self, tmp_path):
        """Create temporary template directory."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        # Create a simple test template
        template_file = template_dir / "test_template.json"
        template_file.write_text("""{
            "template_id": "test_template",
            "name": "Test Template",
            "category": "medium_energy",
            "timing": {"mode": "musical", "default_duration_bars": 8.0},
            "steps": [{
                "step_id": "step1",
                "target": "ALL",
                "timing": {
                    "base_timing": {
                        "mode": "musical",
                        "start_offset_bars": 0.0,
                        "duration_bars": 4.0
                    },
                    "loop": false
                },
                "movement_id": "sweep_lr",
                "movement_params": {"intensity": "SMOOTH"},
                "geometry_id": null,
                "geometry_params": {},
                "dimmer_id": "pulse",
                "dimmer_params": {"intensity": "SMOOTH"},
                "entry_transition": {"mode": "snap", "duration_bars": 0.0},
                "exit_transition": {"mode": "snap", "duration_bars": 0.0},
                "priority": 0,
                "blend_mode": "override"
            }],
            "metadata": {
                "description": "Test template",
                "recommended_sections": [],
                "energy_range": [10, 30],
                "tags": []
            }
        }""")

        return template_dir

    @pytest.fixture
    def temp_xsq_path(self, tmp_path):
        """Create temporary XSQ file path."""
        xsq_path = tmp_path / "test.xsq"
        # Create minimal XSQ file
        xsq_path.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<xsequence>
    <head>
        <version>2022.20</version>
        <mediaFile>test.mp3</mediaFile>
        <sequenceDuration>30.000</sequenceDuration>
    </head>
    <nextid>1</nextid>
</xsequence>""")
        return xsq_path

    @patch("blinkb0t.core.domains.sequencing.moving_heads.templates.pipeline.XSQParser")
    def test_pipeline_initializes(
        self,
        mock_xsq_class,
        temp_template_dir,
        temp_xsq_path,
        mock_song_features,
        job_config,
        mock_fixtures,
    ):
        """Test pipeline initializes with all components."""
        mock_xsq = MagicMock()
        mock_parser_instance = MagicMock()
        mock_parser_instance.parse.return_value = mock_xsq
        mock_xsq_class.return_value = mock_parser_instance

        pipeline = TemplatePipeline(
            template_dir=temp_template_dir,
            song_features=mock_song_features,
            job_config=job_config,
            fixtures=mock_fixtures,
            xsq_path=temp_xsq_path,
        )

        assert pipeline.xsq == mock_xsq
        assert pipeline.factory is not None
        assert pipeline.processor is not None
        assert pipeline.loader is not None

    @patch("blinkb0t.core.domains.sequencing.moving_heads.templates.pipeline.XSQParser")
    def test_pipeline_render_template_loads_template(
        self,
        mock_xsq_class,
        temp_template_dir,
        temp_xsq_path,
        mock_song_features,
        job_config,
        mock_fixtures,
        mock_fixture,
    ):
        """Test render_template loads template via loader."""
        mock_xsq = MagicMock()
        mock_parser_instance = MagicMock()
        mock_parser_instance.parse.return_value = mock_xsq
        mock_xsq_class.return_value = mock_parser_instance

        pipeline = TemplatePipeline(
            template_dir=temp_template_dir,
            song_features=mock_song_features,
            job_config=job_config,
            fixtures=mock_fixtures,
            xsq_path=temp_xsq_path,
        )

        # Mock processor to return empty list
        pipeline.processor.process_template = Mock(return_value=[])

        pipeline.render_template(
            template_id="test_template",
            fixture=mock_fixture,
            base_pose=PoseID.FORWARD,
            section_start_ms=0.0,
            section_end_ms=16000.0,
        )

        # Should have called processor
        pipeline.processor.process_template.assert_called_once()

    @patch("blinkb0t.core.domains.sequencing.moving_heads.templates.pipeline.XSQParser")
    def test_pipeline_render_template_with_params(
        self,
        mock_xsq_class,
        temp_template_dir,
        temp_xsq_path,
        mock_song_features,
        job_config,
        mock_fixtures,
        mock_fixture,
    ):
        """Test render_template passes parameters to loader."""
        mock_xsq = MagicMock()
        mock_parser_instance = MagicMock()
        mock_parser_instance.parse.return_value = mock_xsq
        mock_xsq_class.return_value = mock_parser_instance

        pipeline = TemplatePipeline(
            template_dir=temp_template_dir,
            song_features=mock_song_features,
            job_config=job_config,
            fixtures=mock_fixtures,
            xsq_path=temp_xsq_path,
        )

        # Mock processor
        pipeline.processor.process_template = Mock(return_value=[])

        pipeline.render_template(
            template_id="test_template",
            fixture=mock_fixture,
            base_pose=PoseID.FORWARD,
            section_start_ms=0.0,
            section_end_ms=16000.0,
            params={"intensity": "DRAMATIC"},
        )

        # Verify template was loaded (can't easily check params without accessing loader internals)
        assert pipeline.processor.process_template.called
