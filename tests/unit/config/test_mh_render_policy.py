"""Compatibility boundary for the versioned moving-head render policy."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
import pytest
import yaml

from tests.golden.harness import RIGS, build_beat_grid, build_fixture_group, build_plan
from tests.support.mh_physical import PHYSICAL_INITIAL_STATE, physical_job, physical_rig
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


def test_physical_mode_without_profiles_is_rejected(tmp_path: Path) -> None:
    """Physical mode on a rig without physical profiles fails with diagnostics naming
    each fixture and the missing item, before any output; legacy mode renders it."""
    rig = build_fixture_group(RIGS["mh4_minimal"])
    job = JobConfig.model_validate(
        {"schema_version": "3.1", "moving_heads": {"mode": "physical_v2"}}
    )

    with pytest.raises(UnsupportedRenderModeError, match="physical_v2") as raised:
        RenderingPipeline(
            choreography_plan=build_plan(),
            beat_grid=build_beat_grid(),
            fixture_group=rig,
            job_config=job,
            output_path=tmp_path / "out.xsq",
        )

    for fixture_id in ("MH1", "MH2", "MH3", "MH4"):
        assert f"{fixture_id}: physical_profile is missing" in str(raised.value)
    assert list(tmp_path.iterdir()) == []
    RenderingPipeline(
        choreography_plan=build_plan(),
        beat_grid=build_beat_grid(),
        fixture_group=rig,
        job_config=JobConfig(),
        output_path=tmp_path / "out.xsq",
    )


def _write_job(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "job_config.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


_PHYSICAL_JOB = {"schema_version": "3.1", "moving_heads": {"mode": "physical_v2"}}


def test_loading_physical_job_without_profiles_is_rejected_before_execution(
    tmp_path: Path,
) -> None:
    """The job alone loads; loading it with its fixtures fails, naming each fixture and
    the missing item, before any analysis or planning."""
    path = _write_job(tmp_path, {**_PHYSICAL_JOB, "fixture_config_path": "fixtures.json"})
    (tmp_path / "fixtures.json").write_text(
        build_fixture_group(RIGS["mh4_minimal"]).model_dump_json(), encoding="utf-8"
    )

    assert load_job_config(path).moving_heads.mode == "physical_v2"
    with pytest.raises(
        UnsupportedRenderModeError, match=r"physical_v2.*MH1: physical_profile is missing"
    ):
        load_full_config(path)

    (tmp_path / "fixtures.json").write_text(physical_rig().model_dump_json(), encoding="utf-8")
    with pytest.raises(UnsupportedRenderModeError, match=r"MH1: .*initial state is unknown"):
        load_full_config(path)

    initial = {"MH1": PHYSICAL_INITIAL_STATE, "MH2": PHYSICAL_INITIAL_STATE}
    path = _write_job(
        tmp_path,
        {
            "schema_version": "3.1",
            "fixture_config_path": "fixtures.json",
            "moving_heads": {"mode": "physical_v2", "initial_states": initial},
        },
    )
    job, fixtures = load_full_config(path)
    assert job.moving_heads.mode == "physical_v2"
    assert [f.fixture_id for f in fixtures.expand_fixtures()] == ["MH1", "MH2"]


def test_physical_preflight_names_each_unusable_initial_state() -> None:
    """An unsettled, contradictory or stray initial state is refused at preflight; the
    transaction pass would fail it whenever the first cue is."""
    unsettled = {**PHYSICAL_INITIAL_STATE, "settled": False}
    contradictory = {
        **PHYSICAL_INITIAL_STATE,
        "dimmer": 1.0,
        "discrete_states": {**PHYSICAL_INITIAL_STATE["discrete_states"], "shutter": "open"},
    }
    job = physical_job(
        initial_states={"MH1": unsettled, "MH2": contradictory, "MH9": PHYSICAL_INITIAL_STATE}
    )

    with pytest.raises(UnsupportedRenderModeError) as raised:
        preflight_render_policy(job, physical_rig())

    message = str(raised.value)
    assert "MH1: moving_heads.initial_states['MH1']: initial state is not settled" in message
    assert "MH2: moving_heads.initial_states['MH2']: initial state claims dark=True" in message
    assert "moving_heads.initial_states['MH9'] names no fixture of the rig" in message
    preflight_render_policy(physical_job(), physical_rig())


def test_physical_job_model_still_validates() -> None:
    """The model accepts a physical job in code; with no fixtures known, the preflight
    has nothing to refuse until the fixtures are checked."""
    job = JobConfig.model_validate(_PHYSICAL_JOB)
    assert job.moving_heads.mode == "physical_v2"
    preflight_render_policy(job)
    with pytest.raises(UnsupportedRenderModeError, match="physical_profile is missing"):
        preflight_render_policy(job, build_fixture_group(RIGS["mh4_minimal"]))


def test_legacy_and_omitted_policy_load_unchanged(tmp_path: Path) -> None:
    """Legacy and policy-omitted jobs load exactly as the model validates them."""
    omitted = {"schema_version": "3.0"}
    legacy = {"schema_version": "3.1", "moving_heads": {"mode": "legacy_v1"}}
    for document in (omitted, legacy):
        path = _write_job(tmp_path, document)
        assert load_job_config(path) == JobConfig.model_validate(document)
