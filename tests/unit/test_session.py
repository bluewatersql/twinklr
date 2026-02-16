"""Unit tests for TwinklrSession provider dispatch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from twinklr.core.config.models import AppConfig, JobConfig
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


def test_llm_provider_unknown_value_raises() -> None:
    """Unknown provider config should fail with a clear error."""
    app_config = _make_app_config("unknown_provider")
    job_config = _make_job_config()
    session = TwinklrSession(app_config=app_config, job_config=job_config, session_id="s1")

    with pytest.raises(ValueError) as exc_info:
        _ = session.llm_provider

    assert "Unknown LLM provider" in str(exc_info.value)


def test_session_id_strategy_random_default(tmp_path: Path) -> None:
    """Session defaults to random UUID strategy when explicit ID absent."""
    app_config_path = tmp_path / "config.json"
    job_config_path = tmp_path / "job_config.json"
    app_config_path.write_text(_make_app_config().model_dump_json(), encoding="utf-8")
    job_config_path.write_text(_make_job_config().model_dump_json(), encoding="utf-8")

    session = TwinklrSession(app_config=app_config_path, job_config=job_config_path)

    assert session.session_id
