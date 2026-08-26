"""Factory for creating audio enhancement services (metadata, lyrics, phonemes).

Centralizes HTTP client and provider initialization for dependency injection.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from twinklr.core.api.audio.acoustid import AcoustIDClient
from twinklr.core.api.audio.musicbrainz import MusicBrainzClient
from twinklr.core.api.audio.rate_limit import AsyncRateLimiter
from twinklr.core.api.http import AsyncApiClient, HttpClientConfig
from twinklr.core.api.http.retry import RetryPolicy
from twinklr.core.audio.lyrics.pipeline import LyricsPipeline, LyricsPipelineConfig
from twinklr.core.audio.lyrics.providers.genius import GeniusClient
from twinklr.core.audio.lyrics.providers.lrclib import LRCLibClient
from twinklr.core.audio.lyrics.whisperx_models import WhisperXConfig
from twinklr.core.audio.metadata.pipeline import MetadataPipeline, PipelineConfig
from twinklr.core.config.models import AppConfig

logger = logging.getLogger(__name__)


class EnhancementServiceFactory:
    """Factory for creating audio enhancement services with proper DI.

    Centralizes:
    - HTTP client creation
    - Provider initialization (AcoustID, MusicBrainz, Genius, LRCLib)
    - Pipeline assembly (MetadataPipeline, LyricsPipeline)
    - WhisperX service initialization

    Example:
        factory = EnhancementServiceFactory()
        metadata_pipeline = factory.create_metadata_pipeline(app_config)
        lyrics_pipeline = factory.create_lyrics_pipeline(app_config)
    """

    def __init__(self) -> None:
        self._http_clients: list[AsyncApiClient] = []

    def _create_http_client(self, config: AppConfig, *, base_url: str) -> AsyncApiClient:
        enhancements = config.audio_processing.enhancements
        client = AsyncApiClient(
            config=HttpClientConfig(
                base_url=base_url,
                timeout=httpx.Timeout(enhancements.http_timeout_s),
            ),
            retry_policy=RetryPolicy(max_attempts=enhancements.http_max_retries + 1),
        )
        self._http_clients.append(client)
        return client

    async def aclose(self) -> None:
        """Close every transport pool created by this factory."""
        clients, self._http_clients = self._http_clients, []
        for client in clients:
            await client.aclose()

    def create_metadata_pipeline(self, config: AppConfig) -> MetadataPipeline | None:
        """Create configured metadata pipeline if enabled.

        Args:
            config: Application configuration

        Returns:
            MetadataPipeline if enabled, None otherwise
        """
        if not config.audio_processing.enhancements.enable_metadata:
            return None

        # Initialize API clients if needed
        acoustid_client = None
        musicbrainz_client = None

        if (
            config.audio_processing.enhancements.enable_acoustid
            or config.audio_processing.enhancements.enable_musicbrainz
        ):
            # Create async HTTP client for API calls
            http_client = self._create_http_client(config, base_url="http://localhost")

            # Initialize AcoustID client if enabled
            if config.audio_processing.enhancements.enable_acoustid:
                acoustid_api_key = config.audio_processing.enhancements.acoustid_api_key
                if acoustid_api_key:
                    acoustid_client = AcoustIDClient(
                        api_key=acoustid_api_key.get_secret_value(),
                        http_client=http_client,
                    )
                else:
                    logger.warning("AcoustID enabled but no API key provided (ACOUSTID_API_KEY)")

            # Initialize MusicBrainz client if enabled
            if config.audio_processing.enhancements.enable_musicbrainz:
                user_agent = "Twinklr/4.0 (https://github.com/twinklr)"
                musicbrainz_client = MusicBrainzClient(
                    http_client=http_client,
                    user_agent=user_agent,
                    rate_limiter=AsyncRateLimiter(
                        rate_per_second=(
                            config.audio_processing.enhancements.musicbrainz_rate_limit_rps
                        )
                    ),
                    timeout_s=config.audio_processing.enhancements.musicbrainz_timeout_s,
                )

        # Create pipeline config
        pipeline_config = PipelineConfig(
            enable_acoustid=config.audio_processing.enhancements.enable_acoustid,
            enable_musicbrainz=config.audio_processing.enhancements.enable_musicbrainz,
        )

        # Create pipeline
        return MetadataPipeline(
            config=pipeline_config,
            acoustid_client=acoustid_client,
            musicbrainz_client=musicbrainz_client,
        )

    def create_lyrics_pipeline(self, config: AppConfig) -> LyricsPipeline | None:
        """Create configured lyrics pipeline if enabled.

        Args:
            config: Application configuration

        Returns:
            LyricsPipeline if enabled, None otherwise
        """
        if not config.audio_processing.enhancements.enable_lyrics:
            return None

        # Initialize provider clients if enabled
        providers: dict[str, Any] = {}

        if config.audio_processing.enhancements.enable_lyrics_lookup:
            # Create async HTTP client for API calls
            # Providers use absolute URLs, so base_url is just a placeholder
            http_client = self._create_http_client(
                config,
                base_url="https://api.placeholder.local",
            )

            # LRCLib (always available, no API key needed)
            providers["lrclib"] = LRCLibClient(http_client=http_client)

            # Genius (requires API key)
            genius_token = config.audio_processing.enhancements.genius_access_token
            if genius_token:
                providers["genius"] = GeniusClient(
                    http_client=http_client,
                    access_token=genius_token.get_secret_value(),
                )
            else:
                logger.debug("Genius provider skipped (no GENIUS_ACCESS_TOKEN provided)")

        # Create WhisperX config with language and device settings
        whisperx_config = WhisperXConfig(
            device=config.audio_processing.enhancements.whisperx_device,
            model=config.audio_processing.enhancements.whisperx_model,
            batch_size=config.audio_processing.enhancements.whisperx_batch_size,
            language=config.audio_processing.enhancements.lyrics_language,
            return_char_alignments=config.audio_processing.enhancements.whisperx_return_char_alignments,
        )

        # Create pipeline config
        pipeline_config = LyricsPipelineConfig(
            require_timed_words=config.audio_processing.enhancements.lyrics_require_timed,
            min_coverage_pct=config.audio_processing.enhancements.lyrics_min_coverage,
            whisperx_config=whisperx_config,
        )

        # Initialize WhisperX service if enabled
        whisperx_service = None
        if config.audio_processing.enhancements.enable_whisperx:
            try:
                from twinklr.core.audio.lyrics.whisperx_service import WhisperXImpl

                whisperx_service = WhisperXImpl()
                logger.debug("WhisperX service initialized")
            except ImportError as e:
                logger.warning(
                    f"WhisperX enabled but not installed: {e}. Install with: uv sync --extra ml"
                )

        # Create pipeline
        logger.debug(
            f"Creating lyrics pipeline with {len(providers)} providers: {list(providers.keys())}"
        )
        return LyricsPipeline(
            config=pipeline_config,
            providers=providers,
            whisperx_service=whisperx_service,
        )
