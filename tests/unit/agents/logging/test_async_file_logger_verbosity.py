"""Tests for SEC-08: AsyncFileLogger prompt logging verbosity.

Verifies that:
- DEBUG level logs only prompt metadata (length, model, token count) — never full content
- TRACE level (5) logs full prompt content
- System prompts are never logged at DEBUG or higher
- The log_full_prompts flag enables content at DEBUG when explicitly set
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from twinklr.core.agents.logging.async_file_logger import TRACE, AsyncFileLogger
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.session import TwinklrSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_logger(tmp_path: Path, log_level: str = "standard") -> AsyncFileLogger:
    return AsyncFileLogger(
        output_dir=tmp_path,
        run_id="test_run",
        session_id="sess",
        log_level=log_level,
        format="json",
        sanitize=False,
    )


_PROMPTS = {
    "system": "You are a lighting sequencer. Keep this secret.",
    "user": "Plan the chorus section with energetic lights.",
    "developer": "Focus on high-energy patterns.",
}

_CONTEXT: dict = {"section_id": "chorus_1", "energy": 0.9}


async def _session_log_snapshot(
    tmp_path: Path, name: str, logging_payload: dict[str, object]
) -> tuple[tuple[str, ...], str]:
    log_path = tmp_path / name
    payload = {"enabled": True, "log_path": str(log_path), "format": "json"}
    payload.update(logging_payload)
    job = JobConfig.model_validate({"agent": {"llm_logging": payload}})
    session = TwinklrSession(app_config=AppConfig(), job_config=job, session_id=f"session-{name}")
    logger = session.llm_logger
    call_id = await logger.start_call_async(
        agent_name="probe",
        agent_mode="plan",
        iteration=1,
        model="probe-model",
        temperature=0.2,
        prompts={"user": "contact secret@example.com"},
        context={"secret": "secret@example.com"},
    )
    await logger.complete_call_async(
        call_id,
        raw_response={"secret": "secret@example.com"},
        validated_response=None,
        validation_errors=[],
        tokens_used=1,
        prompt_tokens=1,
        completion_tokens=0,
        duration_seconds=0.1,
        success=True,
        repair_attempts=0,
    )
    files = tuple(sorted(path.name for path in log_path.rglob("*.*")))
    text = "\n".join(path.read_text() for path in log_path.rglob("*.*"))
    return files, text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config_path", "changed_payload"),
    (
        ("job.agent.llm_logging", {"enabled": False}),
        ("job.agent.llm_logging.enabled", {"enabled": False}),
        ("job.agent.llm_logging.log_path", {"log_path": "__replace__"}),
        ("job.agent.llm_logging.log_level", {"log_level": "full"}),
        ("job.agent.llm_logging.format", {"format": "yaml"}),
        ("job.agent.llm_logging.sanitize", {"sanitize": False}),
    ),
    ids=(
        "job.agent.llm_logging",
        "job.agent.llm_logging.enabled",
        "job.agent.llm_logging.log_path",
        "job.agent.llm_logging.log_level",
        "job.agent.llm_logging.format",
        "job.agent.llm_logging.sanitize",
    ),
)
async def test_llm_logging_field_changes_actual_session_log_output(
    tmp_path: Path, config_path: str, changed_payload: dict[str, object]
) -> None:
    """Each logging knob changes a completed call's real file output."""
    baseline = await _session_log_snapshot(tmp_path, "baseline", {})
    if changed_payload.get("log_path") == "__replace__":
        changed_payload = {"log_path": str(tmp_path / "explicit-log-root")}
    changed = await _session_log_snapshot(tmp_path, "changed", changed_payload)

    assert changed != baseline, config_path
    if config_path == "job.agent.llm_logging.log_path":
        assert (tmp_path / "explicit-log-root").is_dir()
    elif config_path == "job.agent.llm_logging.log_level":
        assert '"context_full"' in changed[1]
        assert '"context_full"' not in baseline[1]
    elif config_path == "job.agent.llm_logging.format":
        assert any(name.endswith(".yaml") for name in changed[0])
    elif config_path == "job.agent.llm_logging.sanitize":
        assert "secret@example.com" in changed[1]
        assert "secret@example.com" not in baseline[1]


# ---------------------------------------------------------------------------
# TRACE constant
# ---------------------------------------------------------------------------


def test_trace_level_is_5() -> None:
    """TRACE level must be 5 (below DEBUG=10)."""
    assert TRACE == 5


def test_trace_level_name_registered() -> None:
    """TRACE level name must be registered with the logging module."""
    assert logging.getLevelName(TRACE) == "TRACE"


# ---------------------------------------------------------------------------
# DEBUG level: metadata only, no prompt content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_call_debug_logs_no_system_prompt_content(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """System prompt content must never appear in DEBUG or higher logs."""
    file_logger = _make_logger(tmp_path)

    with caplog.at_level(logging.DEBUG, logger="twinklr.core.agents.logging.async_file_logger"):
        await file_logger.start_call_async(
            agent_name="test_agent",
            agent_mode="plan",
            iteration=1,
            model="gpt-5.2",
            temperature=0.7,
            prompts=_PROMPTS,
            context=_CONTEXT,
        )

    for record in caplog.records:
        if record.levelno >= logging.DEBUG:
            msg = record.getMessage()
            assert "Keep this secret" not in msg, (
                "System prompt content must not appear in DEBUG logs"
            )
            assert "Plan the chorus section" not in msg, (
                "User prompt content must not appear in DEBUG logs"
            )
            assert "Focus on high-energy patterns" not in msg, (
                "Developer prompt content must not appear in DEBUG logs"
            )


@pytest.mark.asyncio
async def test_start_call_debug_logs_length_metadata(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """DEBUG logs should include prompt length / token / model metadata."""
    file_logger = _make_logger(tmp_path)

    with caplog.at_level(logging.DEBUG, logger="twinklr.core.agents.logging.async_file_logger"):
        await file_logger.start_call_async(
            agent_name="test_agent",
            agent_mode="plan",
            iteration=2,
            model="gpt-5.2",
            temperature=0.7,
            prompts=_PROMPTS,
            context=_CONTEXT,
        )

    debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert debug_records, "Expected at least one DEBUG-level log record from start_call_async"
    all_debug_text = " ".join(r.getMessage() for r in debug_records)
    # Model name or length/token references should be present
    has_metadata = (
        "gpt-5.2" in all_debug_text
        or "chars" in all_debug_text
        or "tokens" in all_debug_text
        or "len=" in all_debug_text
    )
    assert has_metadata, (
        f"DEBUG logs should include model/length/token metadata, got: {all_debug_text!r}"
    )


# ---------------------------------------------------------------------------
# TRACE level: full prompt content visible
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_call_trace_logs_full_prompt(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """At TRACE level, full prompt content must appear in logs."""
    file_logger = _make_logger(tmp_path)

    with caplog.at_level(TRACE, logger="twinklr.core.agents.logging.async_file_logger"):
        await file_logger.start_call_async(
            agent_name="test_agent",
            agent_mode="plan",
            iteration=1,
            model="gpt-5.2",
            temperature=0.7,
            prompts=_PROMPTS,
            context=_CONTEXT,
        )

    trace_records = [r for r in caplog.records if r.levelno == TRACE]
    assert trace_records, "Expected at least one TRACE-level log record"

    all_trace_text = " ".join(r.getMessage() for r in trace_records)
    has_content = (
        "Plan the chorus section" in all_trace_text
        or "Focus on high-energy patterns" in all_trace_text
        or "Keep this secret" in all_trace_text
    )
    assert has_content, "TRACE logs must contain full prompt content"


# ---------------------------------------------------------------------------
# log_full_prompts flag: enables content at DEBUG
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_full_prompts_flag_enables_content_at_debug(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """When log_full_prompts=True, full content appears at DEBUG level."""
    file_logger = AsyncFileLogger(
        output_dir=tmp_path,
        run_id="test_run_flag",
        session_id="sess",
        log_level="standard",
        format="json",
        sanitize=False,
        log_full_prompts=True,
    )

    with caplog.at_level(logging.DEBUG, logger="twinklr.core.agents.logging.async_file_logger"):
        await file_logger.start_call_async(
            agent_name="test_agent",
            agent_mode="plan",
            iteration=0,
            model="gpt-5.2",
            temperature=0.7,
            prompts=_PROMPTS,
            context=_CONTEXT,
        )

    all_text = " ".join(r.getMessage() for r in caplog.records)
    has_content = (
        "Plan the chorus section" in all_text or "Focus on high-energy patterns" in all_text
    )
    assert has_content, "With log_full_prompts=True, prompt content should appear in DEBUG logs"
