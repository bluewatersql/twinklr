"""``musicbrainz_rate_limit_rps`` must reach the client that issues requests.

The field was declared and never read: no production code paced anything by it
(P2-F13). These tests pin the wiring so it cannot go dead again.
"""

from __future__ import annotations

import pytest

from twinklr.core.api.audio.rate_limit import AsyncRateLimiter
from twinklr.core.audio.enhancement_factory import EnhancementServiceFactory
from twinklr.core.config.models import AppConfig, AudioEnhancementConfig


@pytest.fixture
def config() -> AppConfig:
    config = AppConfig()
    config.audio_processing.enhancements = AudioEnhancementConfig(
        enable_metadata=True,
        enable_acoustid=False,
        enable_musicbrainz=True,
    )
    return config


def test_rate_limit_config_is_read(config):
    """A non-default rate configures the client's limiter."""
    config.audio_processing.enhancements.musicbrainz_rate_limit_rps = 0.5

    pipeline = EnhancementServiceFactory.create_metadata_pipeline(config)

    limiter = pipeline.musicbrainz_client.rate_limiter
    assert isinstance(limiter, AsyncRateLimiter)
    assert limiter.rate_per_second == 0.5


def test_default_rate_is_the_documented_one_per_second(config):
    """MusicBrainz's published anonymous limit is the default."""
    pipeline = EnhancementServiceFactory.create_metadata_pipeline(config)

    assert pipeline.musicbrainz_client.rate_limiter.rate_per_second == 1.0


def test_musicbrainz_user_agent_is_non_empty(config):
    """MusicBrainz requires an identifying user agent on every request."""
    pipeline = EnhancementServiceFactory.create_metadata_pipeline(config)

    assert pipeline.musicbrainz_client.user_agent
