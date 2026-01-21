"""Tests for template loader."""

import json
from pathlib import Path
import tempfile

import pytest

from blinkb0t.core.domains.sequencing.models.templates import Template
from blinkb0t.core.domains.sequencing.moving_heads.templates import (
    TemplateLoader,
    TemplateLoadError,
    TemplateValidationError,
)


class TestTemplateLoader:
    """Test template loader functionality."""

    @pytest.fixture
    def template_dir(self) -> Path:
        """Get path to test templates directory."""
        # Navigate from test file location to fixtures
        return Path(__file__).parent.parent.parent.parent.parent.parent / "fixtures" / "templates"

    @pytest.fixture
    def loader(self, template_dir: Path) -> TemplateLoader:
        """Create template loader for tests."""
        return TemplateLoader(template_dir)

    def test_loader_initialization(self, template_dir: Path):
        """Test loader initializes successfully."""
        loader = TemplateLoader(template_dir)
        assert loader.template_dir == template_dir
        assert loader.enable_cache is True
        assert len(loader._cache) == 0

    def test_loader_invalid_directory(self):
        """Test loader raises error for non-existent directory."""
        with pytest.raises(TemplateLoadError, match="does not exist"):
            TemplateLoader("/nonexistent/directory")

    def test_list_templates(self, loader: TemplateLoader):
        """Test listing available templates."""
        templates = loader.list_templates()
        assert isinstance(templates, list)
        assert "test_sweep_pulse" in templates

    def test_load_template_basic(self, loader: TemplateLoader):
        """Test loading template without parameters."""
        template = loader.load_template("test_sweep_pulse")
        assert isinstance(template, Template)
        assert template.template_id == "test_sweep_pulse"
        assert template.name == "Test Sweep Pulse"
        assert len(template.steps) == 2

    def test_load_template_with_params(self, loader: TemplateLoader):
        """Test loading template with parameter substitution."""
        template = loader.load_template("test_sweep_pulse", params={"intensity": "DRAMATIC"})

        # Check parameter was substituted
        assert template.steps[0].movement_params["intensity"] == "DRAMATIC"
        assert template.steps[1].dimmer_params["intensity"] == "DRAMATIC"

    def test_load_template_caching(self, loader: TemplateLoader):
        """Test template caching works."""
        # Load template twice
        template1 = loader.load_template("test_sweep_pulse")
        template2 = loader.load_template("test_sweep_pulse")

        # Should be same object (from cache)
        assert template1 is template2
        assert len(loader._cache) > 0

    def test_load_template_cache_with_params(self, loader: TemplateLoader):
        """Test caching respects different parameters."""
        template1 = loader.load_template("test_sweep_pulse", params={"intensity": "SMOOTH"})
        template2 = loader.load_template("test_sweep_pulse", params={"intensity": "DRAMATIC"})

        # Should be different objects (different params)
        assert template1 is not template2
        assert template1.steps[0].movement_params["intensity"] == "SMOOTH"
        assert template2.steps[0].movement_params["intensity"] == "DRAMATIC"

    def test_load_template_force_reload(self, loader: TemplateLoader):
        """Test force_reload bypasses cache."""
        template1 = loader.load_template("test_sweep_pulse")
        template2 = loader.load_template("test_sweep_pulse", force_reload=True)

        # Should be different objects (force_reload)
        assert template1 is not template2

    def test_load_template_not_found(self, loader: TemplateLoader):
        """Test loading non-existent template raises error."""
        with pytest.raises(TemplateLoadError, match="not found"):
            loader.load_template("nonexistent_template")

    def test_load_template_invalid_json(self, template_dir: Path):
        """Test loading invalid JSON raises error."""
        # Create temp directory with invalid JSON
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            invalid_template = tmpdir_path / "invalid.json"
            invalid_template.write_text("{invalid json}")

            loader = TemplateLoader(tmpdir_path)
            with pytest.raises(TemplateLoadError, match="Invalid JSON"):
                loader.load_template("invalid")

    def test_load_template_validation_error(self, template_dir: Path):
        """Test loading template with validation errors."""
        # Create temp directory with template missing required field
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            invalid_template = tmpdir_path / "missing_field.json"
            invalid_template.write_text(json.dumps({"template_id": "test"}))  # Missing steps

            loader = TemplateLoader(tmpdir_path)
            with pytest.raises(TemplateValidationError, match="validation failed"):
                loader.load_template("missing_field")

    def test_load_template_invalid_movement_id(self, template_dir: Path):
        """Test loading template with invalid movement ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            invalid_template = tmpdir_path / "invalid_movement.json"

            # Create template with invalid movement_id
            template_data = {
                "template_id": "invalid_movement",
                "name": "Invalid Movement",
                "category": "low_energy",
                "steps": [
                    {
                        "step_id": "step1",
                        "target": "ALL",
                        "timing": {
                            "base_timing": {
                                "mode": "musical",
                                "start_offset_bars": 0.0,
                                "duration_bars": 1.0,
                            }
                        },
                        "movement_id": "nonexistent_movement",
                        "dimmer_id": "hold",
                    }
                ],
            }
            invalid_template.write_text(json.dumps(template_data))

            loader = TemplateLoader(tmpdir_path)
            with pytest.raises(TemplateValidationError, match="Invalid movement_id"):
                loader.load_template("invalid_movement")

    def test_load_all(self, loader: TemplateLoader):
        """Test loading all templates."""
        all_templates = loader.load_all()
        assert isinstance(all_templates, dict)
        assert "test_sweep_pulse" in all_templates
        assert all(isinstance(t, Template) for t in all_templates.values())

    def test_get_template_metadata(self, loader: TemplateLoader):
        """Test getting template metadata without full load."""
        metadata = loader.get_template_metadata("test_sweep_pulse")
        assert metadata["template_id"] == "test_sweep_pulse"
        assert metadata["name"] == "Test Sweep Pulse"
        assert metadata["category"] == "medium_energy"
        assert metadata["step_count"] == 2
        assert "metadata" in metadata

    def test_get_all_metadata(self, loader: TemplateLoader):
        """Test getting all template metadata."""
        all_metadata = loader.get_all_metadata()
        assert isinstance(all_metadata, list)
        assert len(all_metadata) > 0
        assert all("template_id" in m for m in all_metadata)

    def test_clear_cache(self, loader: TemplateLoader):
        """Test clearing template cache."""
        # Load template to populate cache
        loader.load_template("test_sweep_pulse")
        assert len(loader._cache) > 0

        # Clear cache
        loader.clear_cache()
        assert len(loader._cache) == 0

    def test_parameter_substitution_multiple_params(self, template_dir: Path):
        """Test parameter substitution with multiple parameters."""
        # Create template with multiple params
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            template_file = tmpdir_path / "multi_param.json"

            template_data = {
                "template_id": "multi_param",
                "name": "Multi Param",
                "category": "low_energy",
                "steps": [
                    {
                        "step_id": "step1",
                        "target": "ALL",
                        "timing": {
                            "base_timing": {
                                "mode": "musical",
                                "start_offset_bars": 0.0,
                                "duration_bars": 1.0,
                            }
                        },
                        "movement_id": "sweep_lr",
                        "movement_params": {"intensity": "{{intensity}}", "speed": "{{speed}}"},
                        "dimmer_id": "hold",
                    }
                ],
            }
            template_file.write_text(json.dumps(template_data))

            loader = TemplateLoader(tmpdir_path)
            template = loader.load_template(
                "multi_param", params={"intensity": "DRAMATIC", "speed": "FAST"}
            )

            assert template.steps[0].movement_params["intensity"] == "DRAMATIC"
            assert template.steps[0].movement_params["speed"] == "FAST"

    def test_parameter_substitution_missing_param(self, template_dir: Path):
        """Test parameter substitution when param not provided leaves placeholder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            template_file = tmpdir_path / "missing_param.json"

            template_data = {
                "template_id": "missing_param",
                "name": "Missing Param",
                "category": "low_energy",
                "steps": [
                    {
                        "step_id": "step1",
                        "target": "ALL",
                        "timing": {
                            "base_timing": {
                                "mode": "musical",
                                "start_offset_bars": 0.0,
                                "duration_bars": 1.0,
                            }
                        },
                        "movement_id": "sweep_lr",
                        "movement_params": {"intensity": "{{intensity}}"},
                        "dimmer_id": "hold",
                    }
                ],
            }
            template_file.write_text(json.dumps(template_data))

            loader = TemplateLoader(tmpdir_path)
            # Load without providing intensity parameter
            template = loader.load_template("missing_param", params={})

            # Should leave placeholder unchanged
            assert template.steps[0].movement_params["intensity"] == "{{intensity}}"
