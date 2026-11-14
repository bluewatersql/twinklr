"""Unit tests for TwinklrSession provider dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from pydantic import SecretStr
import pytest

from tests.golden.harness import RIGS, build_fixture_group
from twinklr.core.agents.providers.factory import create_llm_provider
from twinklr.core.config.loader import load_full_config, load_job_config
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.config.render_policy import UnsupportedRenderModeError
from twinklr.core.session import TwinklrSession


def _make_app_config(provider: str = "openai") -> AppConfig:
    return AppConfig.model_validate(
        {
            "llm_provider": provider,
            "llm_api_key": "test-key",
            "llm_base_url": "https://example.local/v1",
            "logging": {"level": "INFO", "format": "json"},
        }
    )


def _make_job_config() -> JobConfig:
    return JobConfig.model_validate(
        {
            "agent": {
                "max_iterations": 1,
                "plan_agent": {"model": "gpt-5.2"},
                "validate_agent": {"model": "gpt-5.2"},
                "judge_agent": {"model": "gpt-5.2"},
                "llm_logging": {"enabled": False},
                "agent_cache": {"enabled": False},
            }
        }
    )


def test_llm_provider_dispatches_from_app_config() -> None:
    """Session should construct provider via configured llm_provider."""
    app_config = _make_app_config("openai")
    job_config = _make_job_config()

    with patch("twinklr.core.session.create_llm_provider") as mock_provider_factory:
        session = TwinklrSession(app_config=app_config, job_config=job_config, session_id="s1")
        _ = session.llm_provider

    mock_provider_factory.assert_called_once()


@pytest.mark.parametrize(
    ("config_path", "payload", "expected"),
    (
        ("app.llm_api_key", {"llm_api_key": "changed-key"}, ("api_key", "changed-key")),
        (
            "app.llm_base_url",
            {"llm_base_url": "https://changed.local/v1"},
            ("base_url", "https://changed.local/v1"),
        ),
    ),
    ids=("app.llm_api_key", "app.llm_base_url"),
)
def test_provider_field_changes_constructor_request(
    config_path: str, payload: dict[str, str], expected: tuple[str, str]
) -> None:
    config = AppConfig.model_validate({**_make_app_config().model_dump(mode="python"), **payload})
    with patch("twinklr.core.agents.providers.factory.OpenAIProvider") as constructor:
        create_llm_provider(config, "session")

    assert constructor.call_args.kwargs[expected[0]] == expected[1], config_path


def test_provider_selection_changes_constructor_branch() -> None:
    config = _make_app_config().model_copy(
        update={"llm_provider": "anthropic", "llm_api_key": SecretStr("sk-ant-test")}
    )
    with patch("twinklr.core.agents.providers.anthropic.AnthropicProvider") as constructor:
        create_llm_provider(config, "session")

    constructor.assert_called_once()


def test_llm_provider_unknown_value_raises() -> None:
    """Unknown provider config should fail with a clear error."""
    app_config = _make_app_config("unknown_provider")
    job_config = _make_job_config()
    session = TwinklrSession(app_config=app_config, job_config=job_config, session_id="s1")

    with pytest.raises(ValueError) as exc_info:
        _ = session.llm_provider

    assert "Unknown LLM provider" in str(exc_info.value)


def test_llm_logging_sanitize_reaches_logger_factory() -> None:
    """The job's sanitization policy must configure the shipped session logger."""
    job_config = JobConfig.model_validate(
        {"agent": {"llm_logging": {"enabled": True, "sanitize": False}}}
    )

    with patch("twinklr.core.session.create_llm_logger") as logger_factory:
        session = TwinklrSession(
            app_config=_make_app_config(), job_config=job_config, session_id="s1"
        )
        _ = session.llm_logger

    assert logger_factory.call_args.kwargs["sanitize"] is False


def test_session_id_strategy_random_default(tmp_path: Path) -> None:
    """Session defaults to random UUID strategy when explicit ID absent."""
    app_config_path = tmp_path / "config.json"
    job_config_path = tmp_path / "job_config.json"
    app_config_path.write_text(_make_app_config().model_dump_json(), encoding="utf-8")
    job_config_path.write_text(_make_job_config().model_dump_json(), encoding="utf-8")

    session = TwinklrSession(app_config=app_config_path, job_config=job_config_path)

    assert session.session_id


def _write_job_dir(directory: Path, job: dict) -> None:
    (directory / "job_config.json").write_text(json.dumps(job), encoding="utf-8")
    (directory / "config.json").write_text(
        json.dumps({"llm_provider": "openai", "llm_api_key": "test-key"}), encoding="utf-8"
    )


_PHYSICAL_JOB = {"schema_version": "3.1", "moving_heads": {"mode": "physical_v2"}}


def test_session_loads_physical_job_file_like_the_loader(tmp_path: Path) -> None:
    """A session resolves no fixtures, so a physical job file loads exactly as
    `load_job_config` and `JobConfig.load_or_default` load it; the fixture
    prerequisites are refused where the fixtures load, before any analysis."""
    _write_job_dir(tmp_path, _PHYSICAL_JOB)
    path = tmp_path / "job_config.json"

    expected = load_job_config(path)
    assert expected.moving_heads.mode == "physical_v2"
    assert JobConfig.load_or_default(path) == expected
    assert TwinklrSession.from_directory(tmp_path).job_config == expected
    assert TwinklrSession(app_config=_make_app_config(), job_config=path).job_config == expected
    (tmp_path / "fixture_config.json").write_text(
        build_fixture_group(RIGS["mh4_minimal"]).model_dump_json(), encoding="utf-8"
    )
    with pytest.raises(UnsupportedRenderModeError, match="MH1: physical_profile is missing"):
        load_full_config(path)


def test_session_default_job_path_loads_physical_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The implicit ./job_config.json goes through the same loader."""
    _write_job_dir(tmp_path, _PHYSICAL_JOB)
    monkeypatch.chdir(tmp_path)

    session = TwinklrSession(app_config=_make_app_config(), job_config=None)
    assert session.job_config == load_job_config(tmp_path / "job_config.json")


def test_session_loads_legacy_job_file_and_accepts_instances(tmp_path: Path) -> None:
    """Legacy files load unchanged; a physical JobConfig instance passed in code is not refused."""
    _write_job_dir(tmp_path, {"schema_version": "3.1", "moving_heads": {"mode": "legacy_v1"}})
    session = TwinklrSession.from_directory(tmp_path)
    assert session.job_config.moving_heads.mode == "legacy_v1"

    physical = JobConfig.model_validate(_PHYSICAL_JOB)
    session = TwinklrSession(app_config=_make_app_config(), job_config=physical)
    assert session.job_config is physical
