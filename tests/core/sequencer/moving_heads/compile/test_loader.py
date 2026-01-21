"""Tests for Template Loader.

Tests loading templates from JSON files and validating them.
"""

import json
from pathlib import Path

import pytest

from blinkb0t.core.sequencer.moving_heads.compile.loader import (
    TemplateLoader,
    TemplateLoadError,
    TemplateNotFoundError,
)
from blinkb0t.core.sequencer.moving_heads.models.template import (
    TemplateDoc,
    TemplatePreset,
)

# =============================================================================
# Test Fixtures (Sample Template Data)
# =============================================================================


def get_minimal_template_dict() -> dict:
    """Get a minimal valid template dict for testing."""
    return {
        "template": {
            "template_id": "test_template",
            "version": 1,
            "name": "Test Template",
            "category": "test",
            "roles": ["FRONT_LEFT", "FRONT_RIGHT"],
            "groups": {"all": ["FRONT_LEFT", "FRONT_RIGHT"]},
            "repeat": {
                "repeatable": True,
                "mode": "PING_PONG",
                "cycle_bars": 4.0,
                "loop_step_ids": ["main"],
                "remainder_policy": "HOLD_LAST_POSE",
            },
            "defaults": {"intensity": "SMOOTH"},
            "steps": [
                {
                    "step_id": "main",
                    "target": "all",
                    "timing": {
                        "base_timing": {
                            "start_offset_bars": 0.0,
                            "duration_bars": 4.0,
                        },
                        "phase_offset": {
                            "mode": "NONE",
                        },
                    },
                    "geometry": {
                        "geometry_id": "ROLE_POSE",
                        "pan_pose_by_role": {
                            "FRONT_LEFT": "LEFT",
                            "FRONT_RIGHT": "RIGHT",
                        },
                        "tilt_pose": "CROWD",
                    },
                    "movement": {
                        "movement_id": "SWEEP_LR",
                        "intensity": "SMOOTH",
                        "cycles": 1.0,
                    },
                    "dimmer": {
                        "dimmer_id": "PULSE",
                        "intensity": "SMOOTH",
                        "min_norm": 0.0,
                        "max_norm": 1.0,
                        "cycles": 2.0,
                    },
                }
            ],
        },
        "presets": [
            {
                "preset_id": "CHILL",
                "name": "Chill",
                "defaults": {"intensity": "SLOW"},
                "step_patches": {},
            },
            {
                "preset_id": "ENERGETIC",
                "name": "Energetic",
                "defaults": {"intensity": "FAST"},
                "step_patches": {
                    "main": {
                        "movement": {"cycles": 4.0},
                        "dimmer": {"max_norm": 0.8},
                    }
                },
            },
        ],
    }


def get_second_template_dict() -> dict:
    """Get a second template dict for multi-template tests."""
    data = get_minimal_template_dict()
    data["template"]["template_id"] = "second_template"
    data["template"]["name"] = "Second Template"
    data["presets"] = []
    return data


# =============================================================================
# Tests for TemplateLoader Basic Operations
# =============================================================================


class TestTemplateLoaderBasic:
    """Tests for basic TemplateLoader operations."""

    def test_load_from_dict(self) -> None:
        """Test loading a template from a dict."""
        loader = TemplateLoader()
        data = get_minimal_template_dict()

        loader.load_from_dict(data)

        assert loader.has("test_template")

    def test_get_template_doc(self) -> None:
        """Test getting a template doc by ID."""
        loader = TemplateLoader()
        data = get_minimal_template_dict()
        loader.load_from_dict(data)

        doc = loader.get("test_template")

        assert isinstance(doc, TemplateDoc)
        assert doc.template.template_id == "test_template"

    def test_get_nonexistent_template_raises(self) -> None:
        """Test getting a nonexistent template raises error."""
        loader = TemplateLoader()

        with pytest.raises(TemplateNotFoundError) as exc_info:
            loader.get("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_has_returns_false_for_nonexistent(self) -> None:
        """Test has returns False for nonexistent template."""
        loader = TemplateLoader()

        assert not loader.has("nonexistent")

    def test_list_templates(self) -> None:
        """Test listing all loaded templates."""
        loader = TemplateLoader()
        loader.load_from_dict(get_minimal_template_dict())
        loader.load_from_dict(get_second_template_dict())

        template_ids = loader.list_templates()

        assert "test_template" in template_ids
        assert "second_template" in template_ids

    def test_load_overwrites_existing(self) -> None:
        """Test loading a template with same ID overwrites existing."""
        loader = TemplateLoader()
        data1 = get_minimal_template_dict()
        data1["template"]["name"] = "First Version"
        loader.load_from_dict(data1)

        data2 = get_minimal_template_dict()
        data2["template"]["name"] = "Second Version"
        loader.load_from_dict(data2)

        doc = loader.get("test_template")
        assert doc.template.name == "Second Version"


# =============================================================================
# Tests for File Loading
# =============================================================================


class TestTemplateLoaderFiles:
    """Tests for loading templates from files."""

    def test_load_from_file(self, tmp_path: Path) -> None:
        """Test loading a template from a JSON file."""
        loader = TemplateLoader()
        file_path = tmp_path / "template.json"
        file_path.write_text(json.dumps(get_minimal_template_dict()))

        loader.load_from_file(file_path)

        assert loader.has("test_template")

    def test_load_from_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Test loading from nonexistent file raises error."""
        loader = TemplateLoader()
        file_path = tmp_path / "nonexistent.json"

        with pytest.raises(TemplateLoadError) as exc_info:
            loader.load_from_file(file_path)

        assert "not found" in str(exc_info.value).lower()

    def test_load_from_invalid_json_raises(self, tmp_path: Path) -> None:
        """Test loading invalid JSON raises error."""
        loader = TemplateLoader()
        file_path = tmp_path / "invalid.json"
        file_path.write_text("not valid json {{{")

        with pytest.raises(TemplateLoadError) as exc_info:
            loader.load_from_file(file_path)

        assert "json" in str(exc_info.value).lower()

    def test_load_from_invalid_schema_raises(self, tmp_path: Path) -> None:
        """Test loading JSON with invalid schema raises error."""
        loader = TemplateLoader()
        file_path = tmp_path / "invalid_schema.json"
        file_path.write_text(json.dumps({"invalid": "schema"}))

        with pytest.raises(TemplateLoadError) as exc_info:
            loader.load_from_file(file_path)

        assert "validation" in str(exc_info.value).lower()

    def test_load_directory(self, tmp_path: Path) -> None:
        """Test loading all templates from a directory."""
        loader = TemplateLoader()

        # Create two template files
        file1 = tmp_path / "template1.json"
        file1.write_text(json.dumps(get_minimal_template_dict()))

        file2 = tmp_path / "template2.json"
        file2.write_text(json.dumps(get_second_template_dict()))

        # Also create a non-JSON file that should be ignored
        (tmp_path / "readme.txt").write_text("This should be ignored")

        loader.load_directory(tmp_path)

        assert loader.has("test_template")
        assert loader.has("second_template")
        assert len(loader.list_templates()) == 2

    def test_load_directory_recursive(self, tmp_path: Path) -> None:
        """Test loading templates from subdirectories."""
        loader = TemplateLoader()

        # Create nested structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        file1 = tmp_path / "template1.json"
        file1.write_text(json.dumps(get_minimal_template_dict()))

        file2 = subdir / "template2.json"
        file2.write_text(json.dumps(get_second_template_dict()))

        loader.load_directory(tmp_path, recursive=True)

        assert loader.has("test_template")
        assert loader.has("second_template")


# =============================================================================
# Tests for Preset Operations
# =============================================================================


class TestTemplateLoaderPresets:
    """Tests for preset-related operations."""

    def test_get_presets(self) -> None:
        """Test getting presets for a template."""
        loader = TemplateLoader()
        loader.load_from_dict(get_minimal_template_dict())

        presets = loader.get_presets("test_template")

        assert len(presets) == 2
        preset_ids = [p.preset_id for p in presets]
        assert "CHILL" in preset_ids
        assert "ENERGETIC" in preset_ids

    def test_get_preset_by_id(self) -> None:
        """Test getting a specific preset by ID."""
        loader = TemplateLoader()
        loader.load_from_dict(get_minimal_template_dict())

        preset = loader.get_preset("test_template", "CHILL")

        assert isinstance(preset, TemplatePreset)
        assert preset.preset_id == "CHILL"

    def test_get_nonexistent_preset_raises(self) -> None:
        """Test getting nonexistent preset raises error."""
        loader = TemplateLoader()
        loader.load_from_dict(get_minimal_template_dict())

        with pytest.raises(TemplateNotFoundError) as exc_info:
            loader.get_preset("test_template", "NONEXISTENT")

        assert "preset" in str(exc_info.value).lower()

    def test_get_with_preset_applied(self) -> None:
        """Test getting a template with a preset applied."""
        loader = TemplateLoader()
        loader.load_from_dict(get_minimal_template_dict())

        template = loader.get_with_preset("test_template", "ENERGETIC")

        # Check preset was applied
        assert template.steps[0].movement.cycles == 4.0
        assert template.steps[0].dimmer.max_norm == 0.8

    def test_get_with_preset_preserves_original(self) -> None:
        """Test getting with preset doesn't modify original."""
        loader = TemplateLoader()
        loader.load_from_dict(get_minimal_template_dict())

        # Get with preset
        loader.get_with_preset("test_template", "ENERGETIC")

        # Original should be unchanged
        doc = loader.get("test_template")
        assert doc.template.steps[0].movement.cycles == 1.0


# =============================================================================
# Tests for Template Validation
# =============================================================================


class TestTemplateLoaderValidation:
    """Tests for template validation during loading."""

    def test_invalid_step_target_rejected(self, tmp_path: Path) -> None:
        """Test template with invalid step target is rejected."""
        data = get_minimal_template_dict()
        data["template"]["steps"][0]["target"] = "nonexistent_group"

        loader = TemplateLoader()
        with pytest.raises(TemplateLoadError):
            loader.load_from_dict(data)

    def test_invalid_loop_step_rejected(self, tmp_path: Path) -> None:
        """Test template with invalid loop_step_ids is rejected."""
        data = get_minimal_template_dict()
        data["template"]["repeat"]["loop_step_ids"] = ["nonexistent_step"]

        loader = TemplateLoader()
        with pytest.raises(TemplateLoadError):
            loader.load_from_dict(data)
