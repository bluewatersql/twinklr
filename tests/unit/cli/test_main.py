"""Unit tests for CLI path resolution helpers."""

from __future__ import annotations

from pathlib import Path

from twinklr.cli.main import _resolve_fixture_config_path


def test_resolve_fixture_config_path_relative_to_job_config_dir() -> None:
    """Relative fixture path resolves against job config directory."""
    job_config_path = Path("/tmp/project/job_config.json")
    resolved = _resolve_fixture_config_path(job_config_path, "configs/fixtures.json")
    assert resolved == Path("/tmp/project/configs/fixtures.json")


def test_resolve_fixture_config_path_keeps_absolute_path() -> None:
    """Absolute fixture path is preserved."""
    job_config_path = Path("/tmp/project/job_config.json")
    fixture_path = Path("/etc/twinklr/fixtures.json")
    resolved = _resolve_fixture_config_path(job_config_path, str(fixture_path))
    assert resolved == fixture_path
