"""TwinklrSession releases lazily-created network resources on aclose()."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.session import TwinklrSession


def _session() -> TwinklrSession:
    return TwinklrSession(app_config=AppConfig(), job_config=JobConfig())


@pytest.mark.asyncio
async def test_aclose_closes_created_provider_and_audio() -> None:
    session = _session()
    provider = MagicMock()
    provider.aclose = AsyncMock()
    analyzer = MagicMock()
    analyzer.aclose = AsyncMock()
    with (
        patch("twinklr.core.session.create_llm_provider", return_value=provider) as create_provider,
        patch("twinklr.core.session.AudioAnalyzer", return_value=analyzer),
    ):
        _ = session.llm_provider
        _ = session.audio_analyzer
        await session.aclose()

    create_provider.assert_called_once()
    provider.aclose.assert_awaited_once()
    analyzer.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_aclose_is_safe_when_no_services_were_created() -> None:
    session = _session()
    # Neither llm_provider nor audio_analyzer was accessed; aclose must not create them.
    with (
        patch("twinklr.core.session.create_llm_provider") as create_provider,
        patch("twinklr.core.session.AudioAnalyzer") as analyzer_cls,
    ):
        await session.aclose()
    create_provider.assert_not_called()
    analyzer_cls.assert_not_called()


@pytest.mark.asyncio
async def test_async_context_manager_closes_on_exit() -> None:
    provider = MagicMock()
    provider.aclose = AsyncMock()
    with patch("twinklr.core.session.create_llm_provider", return_value=provider):
        async with TwinklrSession(app_config=AppConfig(), job_config=JobConfig()) as session:
            _ = session.llm_provider
    provider.aclose.assert_awaited_once()
