"""The moving-head render policy and the job keys removed with the second renderer."""

from __future__ import annotations

from pathlib import Path
import re

from pydantic import ValidationError
import pytest
import yaml

from tests.support.mh_physical import (
    PHYSICAL_INITIAL_STATE,
    physical_grid,
    physical_job,
    physical_plan,
    physical_rig,
)
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.loader import load_full_config, load_job_config
from twinklr.core.config.models import JobConfig
from twinklr.core.config.render_policy import preflight_render_policy
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    UnsupportedRenderModeError,
)


def _unprofiled_rig() -> FixtureGroup:
    """`physical_rig` without its physical profiles."""
    payload = physical_rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        del fixture["config"]["physical_profile"]
    return FixtureGroup.model_validate(payload)


def test_omitted_schema_version_and_policy_load_as_the_defaults() -> None:
    """A job that names neither the schema version nor a policy loads; 3.1 is the one
    accepted version."""
    assert JobConfig().schema_version == "3.1"
    assert JobConfig.model_validate({}) == JobConfig()
    assert JobConfig.model_validate({"schema_version": "3.1"}) == JobConfig()


@pytest.mark.parametrize(
    ("document", "message"),
    [
        pytest.param(
            {"moving_heads": {"mode": "physical_v2"}},
            r"job field 'moving_heads\.mode' was removed.*Delete the key",
            id="mode-physical",
        ),
        pytest.param(
            {"schema_version": "3.1", "moving_heads": {"mode": "legacy_v1"}},
            r"job field 'moving_heads\.mode' was removed.*Delete the key",
            id="mode-legacy",
        ),
        pytest.param(
            {"schema_version": "3.0"},
            r"job schema_version '3\.0' is no longer accepted.*Set schema_version to '3\.1' or "
            r"delete it",
            id="schema-3.0",
        ),
        pytest.param(
            {"transitions": {"enabled": False}},
            r"job field 'transitions' was removed.*Delete the key",
            id="transitions",
        ),
    ],
)
def test_keys_of_the_removed_renderer_are_refused_by_name(
    tmp_path: Path, document: dict[str, object], message: str
) -> None:
    """A job naming a key the removed renderer read is refused when it loads, naming the
    key and what to do, rather than ignored."""
    with pytest.raises(ValidationError, match=message):
        JobConfig.model_validate(document)
    with pytest.raises(ValidationError, match=message):
        load_job_config(_write_job(tmp_path, document))


def test_an_unsupported_schema_version_is_refused() -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        JobConfig.model_validate({"schema_version": "3.2"})


def test_unknown_policy_option_is_rejected() -> None:
    """An option this code does not know is rejected, not ignored."""
    with pytest.raises(ValidationError):
        JobConfig.model_validate({"moving_heads": {"probe": 1}})


def test_a_rig_without_profiles_is_rejected(tmp_path: Path) -> None:
    """A rig without physical profiles fails with diagnostics naming each fixture and the
    missing item, before any output."""
    with pytest.raises(UnsupportedRenderModeError, match="cannot render this rig") as raised:
        RenderingPipeline(
            choreography_plan=physical_plan(),
            beat_grid=physical_grid(),
            fixture_group=_unprofiled_rig(),
            job_config=physical_job(),
            output_path=tmp_path / "out.xsq",
        )

    for fixture_id in ("MH1", "MH2"):
        assert f"{fixture_id}: physical_profile is missing" in str(raised.value)
    assert list(tmp_path.iterdir()) == []


def _write_job(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "job_config.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_loading_a_job_on_a_rig_without_profiles_is_rejected_before_execution(
    tmp_path: Path,
) -> None:
    """The job alone loads; loading it with its fixtures fails, naming each fixture and
    the missing item, before any analysis or planning."""
    path = _write_job(tmp_path, {"fixture_config_path": "fixtures.json"})
    (tmp_path / "fixtures.json").write_text(_unprofiled_rig().model_dump_json(), encoding="utf-8")

    assert load_job_config(path).fixture_config_path == "fixtures.json"
    with pytest.raises(
        UnsupportedRenderModeError,
        match=r"cannot render this rig.*MH1: physical_profile is missing",
    ):
        load_full_config(path)

    (tmp_path / "fixtures.json").write_text(physical_rig().model_dump_json(), encoding="utf-8")
    with pytest.raises(UnsupportedRenderModeError, match=r"MH1: .*initial state is unknown"):
        load_full_config(path)

    initial = {"MH1": PHYSICAL_INITIAL_STATE, "MH2": PHYSICAL_INITIAL_STATE}
    path = _write_job(
        tmp_path,
        {"fixture_config_path": "fixtures.json", "moving_heads": {"initial_states": initial}},
    )
    job, fixtures = load_full_config(path)
    assert set(job.moving_heads.initial_states) == {"MH1", "MH2"}
    assert [f.fixture_id for f in fixtures.expand_fixtures()] == ["MH1", "MH2"]


def test_preflight_names_each_unusable_initial_state() -> None:
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


def test_refusal_names_each_fixture_what_to_add_and_where_the_example_is() -> None:
    """A rig without profiles is refused naming every fixture, where its profile goes and
    the user guide's minimal example."""
    with pytest.raises(UnsupportedRenderModeError) as raised:
        preflight_render_policy(physical_job(), _unprofiled_rig())

    message = str(raised.value)
    for fixture_id in ("MH1", "MH2"):
        assert (
            f"{fixture_id}: physical_profile is missing; add one to its config, or once as "
            "base_config.physical_profile for identical heads"
        ) in message
    assert message.count("docs/user-guide.md#minimal-physical-profile") == 1


def test_job_model_validates_without_fixtures() -> None:
    """With no fixtures known, the preflight has nothing to refuse until the fixtures are
    checked."""
    job = JobConfig()
    preflight_render_policy(job)
    with pytest.raises(UnsupportedRenderModeError, match="physical_profile is missing"):
        preflight_render_policy(job, _unprofiled_rig())


def _renamed(*names: str) -> FixtureGroup:
    """`physical_rig` with its two heads' xLights model names replaced."""
    payload = physical_rig().model_dump(mode="json")
    for fixture, name in zip(payload["fixtures"], names, strict=True):
        fixture["xlights_model_name"] = name
    return FixtureGroup.model_validate(payload)


@pytest.mark.parametrize(
    ("names", "message"),
    [
        pytest.param(
            ("Dmx MH1", "Dmx MH1"),
            "MH1 and MH2: both map to xLights model 'Dmx MH1'",
            id="shared-model",
        ),
        pytest.param(("Dmx MH1", "  "), "MH2: xlights_model_name is blank", id="blank-model"),
    ],
)
def test_preflight_refuses_unusable_model_names(names: tuple[str, str], message: str) -> None:
    """Frames go to each fixture's own model, so a shared or blank model name is refused
    before planning."""
    with pytest.raises(UnsupportedRenderModeError, match=re.escape(message)):
        preflight_render_policy(physical_job(), _renamed(*names))
