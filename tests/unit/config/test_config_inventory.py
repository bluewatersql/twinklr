"""Behavioral accountability for Twinklr's public configuration surface."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import cast, get_args

from pydantic import BaseModel, ValidationError
import pytest

from tests.config_effects_registry import CONFIG_EFFECTS, ConfigDispositionKind
from twinklr.core.audio.energy.profiling import _get_profile_parameters
from twinklr.core.audio.structure.models import SectioningPreset
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.sequencer.models.enum import QuantizeMode, TimingMode
from twinklr.core.sequencer.models.template import (
    BaseTiming,
    Color,
    Dimmer,
    Geometry,
    Gobo,
    Movement,
    PhaseOffset,
    RepeatContract,
    Shutter,
    TemplateDoc,
    TemplateStep,
)

REMOVED_CONFIG_PATHS = (
    "app.audio_processing.cache_enabled",
    "app.output_dir",
    "app.planning",
    "job.include_notes_track",
    "job.debug",
    "job.assumptions",
    "job.agent.enforce_token_budget",
    "job.agent.token_budget",
    "job.agent.token_buffer_pct",
    "job.agent.vision_judge_agent",
    "job.agent.recipe_generation_agent",
    "job.pose_config",
    "job.planner_features",
    "job.output_dir",
    "job.project_name",
    "app.audio_processing.enhancements.metadata_merge_policy_version",
    "app.audio_processing.enhancements.metadata_min_confidence_warn",
    "app.audio_processing.enhancements.http_circuit_breaker_threshold",
    "app.audio_processing.enhancements.http_circuit_breaker_timeout_s",
    "app.audio_processing.enhancements.phoneme_enable_g2p_fallback",
    "fixture.base_config.dmx_universe",
    "fixture.base_config.channel_count",
    "fixture.base_config.capabilities",
    "fixture.base_config.movement_speed",
    "fixture.fixtures.dmx_start_address",
    "fixture.fixtures.config.dmx_universe",
    "fixture.fixtures.config.dmx_start_address",
    "fixture.fixtures.config.channel_count",
    "fixture.fixtures.config.capabilities",
    "fixture.fixtures.config.movement_speed",
    "fixture.base_config.dmx_mapping.pan_channel.config",
    "fixture.fixtures.config.dmx_mapping.pan_channel.config",
    "fixture.base_config.orientation.tilt_up_dmx",
    "fixture.base_config.orientation.tilt_above_horizon_deg",
    "fixture.base_config.orientation.resting_position",
    "fixture.fixtures.config.orientation.tilt_up_dmx",
    "fixture.fixtures.config.orientation.tilt_above_horizon_deg",
    "fixture.fixtures.config.orientation.resting_position",
    "fixture.base_config.limits.avoid_backward",
    "fixture.fixtures.config.limits.avoid_backward",
    "fixture.fixtures.config.position.pan_offset_deg",
    "fixture.fixtures.config.position.tilt_offset_deg",
    "fixture.fixtures.position.pan_offset_deg",
    "fixture.fixtures.position.tilt_offset_deg",
    "template.template.steps.entry_transition",
    "template.template.steps.exit_transition",
    "template.template.steps.priority",
    "template.template.steps.blend_mode",
    "template.template.steps.timing.phase_offset.group",
    "template.template.steps.timing.phase_offset.distribution",
    "template.template.steps.movement.amplitude_override",
    "template.template.steps.movement.frequency_override",
    "template.template.steps.movement.center_offset_override",
    "template.template.steps.geometry.aim_zone",
    "template.template.steps.color.params",
    "template.template.steps.shutter.params",
    "template.template.steps.gobo.params",
    "template.template.roles",
    "template.template.repeat.repeatable",
    "template.template.steps.dimmer.cycles",
    "job.timeline_tracks.sections",
)


def _nested_model(annotation: object) -> type[BaseModel] | None:
    candidates = (annotation, *get_args(annotation))
    for candidate in candidates:
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            return candidate
    return None


def _nested_models(annotation: object) -> tuple[type[BaseModel], ...]:
    found: list[type[BaseModel]] = []

    def visit(candidate: object) -> None:
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            found.append(cast("type[BaseModel]", candidate))
        for argument in get_args(candidate):
            visit(argument)

    visit(annotation)
    return tuple(found)


def _declares_path(path: str) -> bool:
    root, *parts = path.split(".")
    model: type[BaseModel] = {
        "app": AppConfig,
        "job": JobConfig,
        "fixture": FixtureGroup,
        "template": TemplateDoc,
    }[root]
    for index, part in enumerate(parts):
        field = model.model_fields.get(part)
        if field is None:
            return False
        if index == len(parts) - 1:
            return True
        nested = _nested_model(field.annotation)
        if nested is None:
            return False
        model = cast("type[BaseModel]", nested)
    return False


@pytest.mark.parametrize("config_path", REMOVED_CONFIG_PATHS)
def test_removed_config_path_is_absent_from_public_schema(config_path: str) -> None:
    """Deleted knobs cannot remain silently accepted as declared public fields."""
    assert not _declares_path(config_path), f"dead config path is still declared: {config_path}"


@pytest.mark.parametrize(
    ("payload", "retired_key"),
    (
        (
            {
                "group_id": "heads",
                "base_config": {
                    "dmx_universe": 2,
                    "dmx_mapping": {"pan_channel": 1, "tilt_channel": 2, "dimmer_channel": 3},
                },
            },
            "dmx_universe",
        ),
        (
            {
                "group_id": "heads",
                "base_config": {
                    "capabilities": {"has_prism": True},
                    "dmx_mapping": {"pan_channel": 1, "tilt_channel": 2, "dimmer_channel": 3},
                },
            },
            "capabilities",
        ),
        (
            {
                "group_id": "heads",
                "fixtures": [
                    {
                        "fixture_id": "MH1",
                        "dmx_start_address": 17,
                        "xlights_model_name": "Dmx MH1",
                    }
                ],
            },
            "dmx_start_address",
        ),
        (
            {
                "group_id": "heads",
                "base_config": {
                    "dmx_mapping": {
                        "pan_channel": {"channel": 1, "config": {"channel_min": 10}},
                        "tilt_channel": 2,
                        "dimmer_channel": 3,
                    }
                },
            },
            "config",
        ),
        (
            {
                "group_id": "heads",
                "base_config": {
                    "orientation": {"tilt_up_dmx": 112},
                    "dmx_mapping": {"pan_channel": 1, "tilt_channel": 2, "dimmer_channel": 3},
                },
            },
            "tilt_up_dmx",
        ),
        (
            {
                "group_id": "heads",
                "fixtures": [
                    {
                        "fixture_id": "MH1",
                        "xlights_model_name": "Dmx MH1",
                        "position": {"position_index": 1, "pan_offset_deg": 10.0},
                    }
                ],
            },
            "pan_offset_deg",
        ),
    ),
)
def test_retired_fixture_config_fails_loudly_with_migration_message(
    payload: dict[str, object], retired_key: str
) -> None:
    with pytest.raises(ValidationError, match=rf"{retired_key}.*removed|removed.*{retired_key}"):
        FixtureGroup.model_validate(payload)


@pytest.mark.parametrize(
    ("model", "payload", "retired_key"),
    (
        (PhaseOffset, {"group": "ALL"}, "group"),
        (TemplateStep, {"priority": 1}, "priority"),
        (Movement, {"amplitude_override": 0.5}, "amplitude_override"),
        (Geometry, {"aim_zone": "SKY"}, "aim_zone"),
        (Color, {"preset": "WHITE", "params": {"probe": 1}}, "params"),
        (Shutter, {"pattern": "OPEN", "params": {"probe": 1}}, "params"),
        (Gobo, {"pattern": "OPEN", "params": {"probe": 1}}, "params"),
        (TemplateDoc, {"template": {"roles": ["OUTER_LEFT"]}}, "roles"),
        (RepeatContract, {"repeatable": False}, "repeatable"),
        (Dimmer, {"cycles": 2.0}, "cycles"),
    ),
)
def test_retired_template_config_fails_loudly_with_migration_message(
    model: type[BaseModel], payload: dict[str, object], retired_key: str
) -> None:
    with pytest.raises(ValidationError, match=rf"{retired_key}.*removed|removed.*{retired_key}"):
        model.model_validate(payload)


@pytest.mark.parametrize(
    ("model", "payload", "retired_key"),
    (
        (AppConfig, {"planning": {"enabled": True}}, "planning"),
        (AppConfig, {"output_dir": "artifacts"}, "output_dir"),
        (
            AppConfig,
            {"audio_processing": {"cache_enabled": False}},
            "cache_enabled",
        ),
        (JobConfig, {"include_notes_track": True}, "include_notes_track"),
        (JobConfig, {"debug": True}, "debug"),
        (JobConfig, {"assumptions": {"beats_per_bar": 3}}, "assumptions"),
        (JobConfig, {"pose_config": {"poses": {}}}, "pose_config"),
        (JobConfig, {"planner_features": {"enabled": True}}, "planner_features"),
        (JobConfig, {"output_dir": "artifacts"}, "output_dir"),
        (JobConfig, {"project_name": "probe"}, "project_name"),
        (
            JobConfig,
            {"agent": {"enforce_token_budget": True}},
            "enforce_token_budget",
        ),
        (JobConfig, {"agent": {"token_budget": 1234}}, "token_budget"),
        (
            JobConfig,
            {"agent": {"token_buffer_pct": 0.25}},
            "token_buffer_pct",
        ),
        (
            JobConfig,
            {"agent": {"vision_judge_agent": {"model": "probe"}}},
            "vision_judge_agent",
        ),
        (
            JobConfig,
            {"agent": {"recipe_generation_agent": {"model": "probe"}}},
            "recipe_generation_agent",
        ),
        (JobConfig, {"timeline_tracks": {"sections": False}}, "sections"),
        (
            AppConfig,
            {"audio_processing": {"enhancements": {"phoneme_enable_g2p_fallback": False}}},
            "phoneme_enable_g2p_fallback",
        ),
        *(
            (
                AppConfig,
                {"audio_processing": {"enhancements": {retired_key: 1}}},
                retired_key,
            )
            for retired_key in (
                "metadata_merge_policy_version",
                "metadata_min_confidence_warn",
                "http_circuit_breaker_threshold",
                "http_circuit_breaker_timeout_s",
            )
        ),
    ),
)
def test_retired_app_and_job_config_fails_loudly_without_forbidding_future_keys(
    model: type[BaseModel], payload: dict[str, object], retired_key: str
) -> None:
    with pytest.raises(ValidationError, match=rf"{retired_key}.*removed|removed.*{retired_key}"):
        model.model_validate(payload)


def test_unrelated_future_app_and_job_keys_remain_forward_compatible() -> None:
    assert AppConfig.model_validate({"future_extension": {"enabled": True}}) == AppConfig()
    assert JobConfig.model_validate({"future_extension": {"enabled": True}}) == JobConfig()


def test_fixed_policy_config_paths_are_invariant() -> None:
    """Fixed cost/schema policies reject every alternate value exposed by their types."""
    with pytest.raises(ValidationError):
        JobConfig(schema_version="future")

    for field, value in (
        ("max_image_requests_per_run", 2),
        ("estimated_image_usd_per_request", 0.21),
        ("image_quality", "high"),
    ):
        with pytest.raises(ValidationError):
            JobConfig(assets={field: value})  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        BaseTiming(
            mode=TimingMode.ABSOLUTE_MS,
            quantize_type=QuantizeMode.DOWNBEAT,
            start_offset_bars=0,
            duration_bars=1,
        )
    with pytest.raises(ValidationError):
        BaseTiming(
            mode=TimingMode.MUSICAL,
            quantize_type=QuantizeMode.ANY_BEAT,
            start_offset_bars=0,
            duration_bars=1,
        )


def test_retired_analysis_parameters_are_absent() -> None:
    assert "context_weights" not in SectioningPreset.model_fields
    assert "gradient_percentile" not in _get_profile_parameters(
        "moderate", energy_cv=0.5, gradient_std=0.1
    )


EXTERNAL_CONFIG_ROOTS: dict[str, type[BaseModel]] = {
    "app": AppConfig,
    "job": JobConfig,
    "fixture": FixtureGroup,
    "template": TemplateDoc,
}


def _enumerate_config_paths(
    roots: dict[str, type[BaseModel]] = EXTERNAL_CONFIG_ROOTS,
) -> set[str]:
    """Enumerate canonical full paths without collapsing repeated nested models."""
    paths: set[str] = set()

    def walk(prefix: str, model: type[BaseModel], ancestors: tuple[type[BaseModel], ...]) -> None:
        if model in ancestors:
            return
        for field_name, field in model.model_fields.items():
            path = f"{prefix}.{field_name}"
            paths.add(path)
            nested_models = _nested_models(field.annotation)
            for nested in nested_models:
                nested_path = f"{path}[{nested.__name__}]" if len(nested_models) > 1 else path
                walk(nested_path, nested, (*ancestors, model))

    for prefix, model in roots.items():
        walk(prefix, model, ())
    return paths


def test_every_external_config_path_has_an_accountable_disposition() -> None:
    declared = _enumerate_config_paths()
    registered = {
        path
        for path, disposition in CONFIG_EFFECTS.items()
        if disposition.kind is not ConfigDispositionKind.REMOVED
    }
    assert registered == declared, (
        f"unregistered={sorted(declared - registered)}; stale={sorted(registered - declared)}"
    )


def test_union_alternatives_have_distinct_type_qualified_paths() -> None:
    """A set-backed inventory must not collapse same-named fields across union branches."""
    declared = _enumerate_config_paths()

    assert "fixture.fixtures[FixtureInstance].fixture_id" in declared
    assert "fixture.fixtures[SimplifiedFixtureInstance].fixture_id" in declared
    assert "fixture.fixtures[FixtureInstance].xlights_model_name" in declared
    assert "fixture.fixtures[SimplifiedFixtureInstance].xlights_model_name" in declared
    assert "fixture.fixtures[FixtureInstance].config" in declared
    assert "fixture.fixtures[SimplifiedFixtureInstance].config_overrides" in declared
    assert "fixture.fixtures.fixture_id" not in declared


def test_removed_registry_paths_are_absent_and_handed_to_p4_t6() -> None:
    declared = _enumerate_config_paths()
    for path, disposition in CONFIG_EFFECTS.items():
        if disposition.kind is ConfigDispositionKind.REMOVED:
            assert path not in declared
            assert "P4-T6" in disposition.note


def test_registered_effect_and_invariant_nodeids_collect() -> None:
    """Registry references are real pytest nodes, not unchecked documentation strings."""
    nodeids = sorted(
        {
            disposition.test_nodeid
            for disposition in CONFIG_EFFECTS.values()
            if disposition.kind is not ConfigDispositionKind.REMOVED
            and disposition.test_nodeid is not None
        }
    )
    repo_root = Path(__file__).parents[3]
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-cov", *nodeids],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_unregistered_added_field_is_reported_by_canonical_path() -> None:
    """Permanent dummy proof for the CI backstop required by P4-T5."""

    class JobConfigWithUnregisteredField(JobConfig):
        unregistered_probe: bool = False

    declared = _enumerate_config_paths(
        {**EXTERNAL_CONFIG_ROOTS, "job": JobConfigWithUnregisteredField}
    )
    registered = {
        path
        for path, disposition in CONFIG_EFFECTS.items()
        if disposition.kind is not ConfigDispositionKind.REMOVED
    }
    assert declared - registered == {"job.unregistered_probe"}
