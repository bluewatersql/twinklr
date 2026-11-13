"""Compatibility boundary for the versioned moving-head render policy."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
import pytest
import yaml

from tests.golden.harness import RIGS, build_beat_grid, build_fixture_group, build_plan
from twinklr.core.config.loader import load_full_config, load_job_config
from twinklr.core.config.models import JobConfig
from twinklr.core.config.render_policy import preflight_render_policy
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    UnsupportedRenderModeError,
)


def test_omitted_policy_retains_legacy() -> None:
    """A job written before the policy existed loads unchanged onto the legacy renderer."""
    assert JobConfig().schema_version == "3.0"
    assert JobConfig().moving_heads.mode == "legacy_v1"
    assert JobConfig.model_validate({"schema_version": "3.0"}) == JobConfig()


def test_physical_mode_requires_schema_31() -> None:
    """Physical mode is admissible only in a job that declares schema 3.1."""
    with pytest.raises(ValidationError, match=r"3\.1"):
        JobConfig.model_validate({"schema_version": "3.0", "moving_heads": {"mode": "physical_v2"}})
    with pytest.raises(ValidationError, match=r"3\.1"):
        JobConfig.model_validate({"moving_heads": {"mode": "physical_v2"}})

    job = JobConfig.model_validate({"schema_version": "3.1", "moving_heads": {"mode": "legacy_v1"}})
    assert (job.schema_version, job.moving_heads.mode) == ("3.1", "legacy_v1")


def test_unknown_policy_option_is_rejected() -> None:
    """An option this code does not know is rejected, not ignored into a legacy render."""
    with pytest.raises(ValidationError):
        JobConfig.model_validate(
            {"schema_version": "3.1", "moving_heads": {"mode": "legacy_v1", "probe": 1}}
        )


def test_unimplemented_physical_mode_is_rejected(tmp_path: Path) -> None:
    """Requesting the unbuilt physical renderer fails before any output, never falls back."""
    job = JobConfig.model_validate(
        {"schema_version": "3.1", "moving_heads": {"mode": "physical_v2"}}
    )

    with pytest.raises(UnsupportedRenderModeError, match="physical_v2"):
        RenderingPipeline(
            choreography_plan=build_plan(),
            beat_grid=build_beat_grid(),
            fixture_group=build_fixture_group(RIGS["mh4_minimal"]),
            job_config=job,
            output_path=tmp_path / "out.xsq",
        )

    assert list(tmp_path.iterdir()) == []


def _write_job(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "job_config.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


_PHYSICAL_JOB = {"schema_version": "3.1", "moving_heads": {"mode": "physical_v2"}}


def test_loading_physical_job_is_rejected_before_execution(tmp_path: Path) -> None:
    """A physical job fails at load, naming the mode and the remedy, before any planning."""
    path = _write_job(tmp_path, _PHYSICAL_JOB)

    with pytest.raises(UnsupportedRenderModeError, match=r"physical_v2.*legacy_v1"):
        load_job_config(path)
    with pytest.raises(UnsupportedRenderModeError, match=r"physical_v2.*legacy_v1"):
        load_full_config(path)


def test_physical_job_model_still_validates() -> None:
    """The model accepts a physical job in code; only loading it for execution refuses."""
    job = JobConfig.model_validate(_PHYSICAL_JOB)
    assert job.moving_heads.mode == "physical_v2"
    with pytest.raises(UnsupportedRenderModeError, match="physical_v2"):
        preflight_render_policy(job)


def test_legacy_and_omitted_policy_load_unchanged(tmp_path: Path) -> None:
    """Legacy and policy-omitted jobs load exactly as the model validates them."""
    omitted = {"schema_version": "3.0"}
    legacy = {"schema_version": "3.1", "moving_heads": {"mode": "legacy_v1"}}
    for document in (omitted, legacy):
        path = _write_job(tmp_path, document)
        assert load_job_config(path) == JobConfig.model_validate(document)
