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
