"""Audio enhancement transports follow the analyzer's async lifecycle."""

from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.audio.enhancement_factory import EnhancementServiceFactory
from twinklr.core.config.models import AppConfig, JobConfig


async def test_audio_analyzer_context_closes_factory_http_clients() -> None:
    config = AppConfig(
        audio_processing={
            "enhancements": {
                "enable_metadata": False,
                "enable_lyrics": True,
                "enable_lyrics_lookup": True,
                "enable_whisperx": False,
            }
        }
    )
    factory = EnhancementServiceFactory()

    async with AudioAnalyzer(config, JobConfig(), service_factory=factory) as analyzer:
        assert analyzer.lyrics_pipeline is not None
        client = analyzer.lyrics_pipeline.providers["lrclib"].http_client
        assert client._client.is_closed is False

    assert client._client.is_closed is True
