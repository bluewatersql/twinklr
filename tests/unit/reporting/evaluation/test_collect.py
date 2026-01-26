"""Tests for checkpoint collection utilities."""

import json

import pytest

from blinkb0t.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from blinkb0t.core.reporting.evaluation.collect import (
    build_run_metadata,
    extract_plan,
    load_checkpoint,
)


class TestLoadCheckpoint:
    """Tests for load_checkpoint function."""

    def test_load_valid_checkpoint(self, tmp_path):
        """Test loading a valid checkpoint file."""
        checkpoint_path = tmp_path / "checkpoint.json"
        checkpoint_data = {"run_id": "abc123", "plan": {"sections": []}}
        checkpoint_path.write_text(json.dumps(checkpoint_data), encoding="utf-8")

        result = load_checkpoint(checkpoint_path)
        assert result["run_id"] == "abc123"
        assert "plan" in result

    def test_load_nonexistent_checkpoint(self, tmp_path):
        """Test loading a nonexistent checkpoint file."""
        checkpoint_path = tmp_path / "missing.json"
        with pytest.raises(FileNotFoundError):
            load_checkpoint(checkpoint_path)

    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON."""
        checkpoint_path = tmp_path / "invalid.json"
        checkpoint_path.write_text("not valid json", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_checkpoint(checkpoint_path)


class TestExtractPlan:
    """Tests for extract_plan function."""

    def test_extract_valid_plan(self):
        """Test extracting a valid plan from checkpoint data."""
        checkpoint_data = {
            "run_id": "test",
            "plan": {
                "sections": [
                    {
                        "section_name": "verse_1",
                        "start_bar": 1,
                        "end_bar": 21,
                        "section_role": "verse",
                        "energy_level": 40,
                        "template_id": "fan_pulse",
                        "preset_id": None,
                        "modifiers": {},
                        "reasoning": "Test",
                        "segments": None,
                    }
                ],
                "overall_strategy": "Test strategy",
            },
        }

        plan = extract_plan(checkpoint_data)
        assert isinstance(plan, ChoreographyPlan)
        assert len(plan.sections) == 1
        assert plan.sections[0].section_name == "verse_1"

    def test_extract_missing_plan(self):
        """Test extracting plan when plan field is missing."""
        checkpoint_data = {"run_id": "test"}
        with pytest.raises(ValueError, match="No 'plan' field"):
            extract_plan(checkpoint_data)

    def test_extract_invalid_plan(self):
        """Test extracting invalid plan data."""
        checkpoint_data = {"plan": {"invalid": "structure"}}
        with pytest.raises(ValueError, match="Failed to validate"):
            extract_plan(checkpoint_data)


class TestBuildRunMetadata:
    """Tests for build_run_metadata function."""

    def test_build_metadata_with_run_id(self, tmp_path):
        """Test building metadata with run ID from checkpoint."""
        checkpoint_path = tmp_path / "test.json"
        checkpoint_data = {"run_id": "abc123"}

        metadata = build_run_metadata(checkpoint_path, checkpoint_data)
        assert metadata.run_id == "abc123"
        assert metadata.checkpoint_path == checkpoint_path
        assert metadata.engine_version  # Should have some value

    def test_build_metadata_without_run_id(self, tmp_path):
        """Test building metadata when run_id is missing."""
        checkpoint_path = tmp_path / "test.json"
        checkpoint_data = {}

        metadata = build_run_metadata(checkpoint_path, checkpoint_data)
        # When run_id is missing, it uses the filename stem
        assert metadata.run_id == "test"

    def test_metadata_includes_timestamp(self, tmp_path):
        """Test that metadata includes timestamp."""
        checkpoint_path = tmp_path / "test.json"
        checkpoint_data = {"run_id": "test"}

        metadata = build_run_metadata(checkpoint_path, checkpoint_data)
        assert metadata.timestamp  # Should be ISO 8601 format
        assert "T" in metadata.timestamp  # ISO format includes 'T'

    def test_metadata_git_sha(self, tmp_path):
        """Test git SHA handling."""
        checkpoint_path = tmp_path / "test.json"
        checkpoint_data = {"run_id": "test"}

        metadata = build_run_metadata(checkpoint_path, checkpoint_data)
        # git_sha may be None if not in a git repo or git not available
        # Just verify the field exists
        assert hasattr(metadata, "git_sha")


class TestIntegration:
    """Integration tests for collector workflow."""

    def test_full_checkpoint_loading_workflow(self, tmp_path):
        """Test complete workflow: load → extract → metadata."""
        # Create a realistic checkpoint
        checkpoint_path = tmp_path / "final.json"
        checkpoint_data = {
            "run_id": "test_run",
            "status": "SUCCESS",
            "plan": {
                "sections": [
                    {
                        "section_name": "intro",
                        "start_bar": 1,
                        "end_bar": 8,
                        "section_role": "intro",
                        "energy_level": 30,
                        "template_id": "sweep_lr",
                        "preset_id": "GENTLE",
                        "modifiers": {"width": "narrow"},
                        "reasoning": "Gentle introduction",
                        "segments": None,
                    }
                ],
                "overall_strategy": "Build energy gradually",
            },
        }
        checkpoint_path.write_text(json.dumps(checkpoint_data), encoding="utf-8")

        # Load
        loaded = load_checkpoint(checkpoint_path)
        assert loaded["run_id"] == "test_run"

        # Extract plan
        plan = extract_plan(loaded)
        assert len(plan.sections) == 1
        assert plan.overall_strategy == "Build energy gradually"

        # Build metadata
        metadata = build_run_metadata(checkpoint_path, loaded)
        assert metadata.run_id == "test_run"
        assert metadata.checkpoint_path == checkpoint_path
