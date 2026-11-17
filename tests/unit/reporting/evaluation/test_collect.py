"""Tests for checkpoint collection utilities."""

import json

import pytest

from tests.support.moving_heads import plan_section
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.reporting.evaluation.collect import (
    build_run_metadata,
    extract_plan,
    load_checkpoint,
)


class TestLoadCheckpoint:
    """Tests for load_checkpoint function."""

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
        section = plan_section("verse_1", 1, 21, "fan_pulse", section_role="verse", energy_level=40)
        checkpoint_data = {
            "run_id": "test",
            "plan": {
                "sections": [section.model_dump(mode="json")],
                "overall_strategy": "Test strategy",
            },
        }

        plan = extract_plan(checkpoint_data)
        assert isinstance(plan, ChoreographyPlan)
        assert len(plan.sections) == 1
        assert plan.sections[0].section_id == "verse_1"

    def test_an_old_shape_plan_is_refused_by_name_with_the_remedy(self):
        """A checkpoint written before the song-intent contract cannot be read; the
        refusal says so and how to write it again."""
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
                        "modifiers": [],
                        "reasoning": "Test",
                        "segments": None,
                    }
                ],
                "overall_strategy": "Test strategy",
            },
        }

        with pytest.raises(ValueError, match=r"before 2026-11-17.*re-run .*`twinklr run`"):
            extract_plan(checkpoint_data)

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

    def test_full_checkpoint_loading_workflow(self, tmp_path):
        """Test complete workflow: load → extract → metadata."""
        # Create a realistic checkpoint
        checkpoint_path = tmp_path / "final.json"
        checkpoint_data = {
            "run_id": "test_run",
            "status": "SUCCESS",
            "plan": {
                "sections": [
                    plan_section(
                        "intro",
                        1,
                        8,
                        "sweep_lr",
                        "GENTLE",
                        section_role="intro",
                        energy_level=30,
                        reasoning="Gentle introduction",
                    ).model_dump(mode="json")
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
