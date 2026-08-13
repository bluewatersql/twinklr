"""Lyrics resolution must follow the pipeline's own declared source order.

The analyzer used to run metadata and lyrics concurrently, handing the first
lyrics pass ``metadata_bundle=None``. The lyrics pipeline gates LRCLib and
Genius on having an artist/title, so those two — its highest-priority sources —
were structurally skipped; with WhisperX on, ASR resolved the bundle non-SKIPPED
and suppressed the metadata-aware retry entirely, and with WhisperX off the
whole extraction ran twice (P2-M1).
"""

from __future__ import annotations

from typing import Any

import pytest

from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.audio.models import LyricsBundle, MetadataBundle
from twinklr.core.audio.models.enums import StageStatus
from twinklr.core.audio.models.lyrics import LyricsSource, LyricsSourceKind
from twinklr.core.audio.models.metadata import EmbeddedMetadata, ResolvedMetadata
from twinklr.core.config.models import AppConfig, AudioEnhancementConfig, JobConfig


class RecordingLyricsPipeline:
    """Lyrics pipeline double that records the artist/title it was given.

    Mirrors the real pipeline's gating: providers are consulted only when an
    artist or title is present; otherwise it falls back to ASR (WhisperX).
    """

    def __init__(self, *, whisperx_enabled: bool) -> None:
        self.whisperx_enabled = whisperx_enabled
        self.calls: list[dict[str, Any]] = []
        self.providers_consulted: list[str] = []

    async def resolve(
        self,
        *,
        audio_path: str,
        duration_ms: int,
        artist: str | None = None,
        title: str | None = None,
        vocal_segments: list[dict[str, float]] | None = None,
    ) -> LyricsBundle:
        self.calls.append({"artist": artist, "title": title})

        if artist or title:
            self.providers_consulted.append("lrclib")
            return LyricsBundle(
                schema_version="1.0.0",
                stage_status=StageStatus.OK,
                text="synced lyrics",
                source=LyricsSource(
                    kind=LyricsSourceKind.LOOKUP_SYNCED, provider="lrclib", confidence=0.8
                ),
            )

        if self.whisperx_enabled:
            self.providers_consulted.append("whisperx")
            return LyricsBundle(
                schema_version="1.0.0",
                stage_status=StageStatus.OK,
                text="asr transcript",
                source=LyricsSource(
                    kind=LyricsSourceKind.WHISPERX_TRANSCRIBE, provider="whisperx", confidence=0.8
                ),
            )

        return LyricsBundle(schema_version="1.0.0", stage_status=StageStatus.SKIPPED)


class StubMetadataPipeline:
    """Metadata pipeline double resolving a known artist/title."""

    def __init__(self) -> None:
        self.calls = 0

    async def extract(
        self, audio_path: str, embedded_metadata: EmbeddedMetadata | None = None
    ) -> MetadataBundle:
        self.calls += 1
        return MetadataBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.OK,
            embedded=EmbeddedMetadata(),
            resolved=ResolvedMetadata(
                confidence=0.9,
                artist="Resolved Artist",
                title="Resolved Title",
                title_confidence=0.9,
            ),
        )


@pytest.fixture
def app_config(tmp_path):
    config = AppConfig()
    config.audio_processing.enhancements = AudioEnhancementConfig(
        enable_metadata=True,
        enable_lyrics=True,
        enable_acoustid=False,
        enable_musicbrainz=False,
    )
    config.cache_dir = str(tmp_path / "cache")
    return config


@pytest.fixture
def features() -> dict[str, Any]:
    return {"sr": 22050, "hop_length": 512, "duration_s": 180.0, "vocals": []}


async def test_lyrics_consults_authoritative_providers_when_metadata_resolves(app_config, features):
    """With WhisperX on, LRCLib is still consulted because metadata went first.

    Before the fix the first pass received metadata=None, ASR answered, and the
    retry never fired — LRCLib was never asked.
    """
    analyzer = AudioAnalyzer(app_config, JobConfig())
    lyrics = RecordingLyricsPipeline(whisperx_enabled=True)
    analyzer.metadata_pipeline = StubMetadataPipeline()
    analyzer.lyrics_pipeline = lyrics

    bundle = await analyzer._build_song_bundle("/test/audio.mp3", features, EmbeddedMetadata())

    assert lyrics.providers_consulted == ["lrclib"]
    assert "whisperx" not in lyrics.providers_consulted
    assert lyrics.calls == [{"artist": "Resolved Artist", "title": "Resolved Title"}]
    assert bundle.lyrics.source.kind == LyricsSourceKind.LOOKUP_SYNCED


async def test_lyrics_resolved_once_when_whisperx_disabled(app_config, features):
    """Lyrics extraction runs exactly once per analyze (was twice)."""
    analyzer = AudioAnalyzer(app_config, JobConfig())
    lyrics = RecordingLyricsPipeline(whisperx_enabled=False)
    analyzer.metadata_pipeline = StubMetadataPipeline()
    analyzer.lyrics_pipeline = lyrics

    await analyzer._build_song_bundle("/test/audio.mp3", features, EmbeddedMetadata())

    assert len(lyrics.calls) == 1


async def test_lyrics_never_sees_none_metadata(app_config, features):
    """No pass is made with metadata withheld, whatever the outcome."""
    analyzer = AudioAnalyzer(app_config, JobConfig())
    lyrics = RecordingLyricsPipeline(whisperx_enabled=True)
    analyzer.metadata_pipeline = StubMetadataPipeline()
    analyzer.lyrics_pipeline = lyrics

    await analyzer._build_song_bundle("/test/audio.mp3", features, EmbeddedMetadata())

    assert all(call["artist"] or call["title"] for call in lyrics.calls)


async def test_embedded_tags_reach_lyrics_when_metadata_pipeline_disabled(app_config, features):
    """Embedded artist/title still route to LRCLib with metadata lookup off."""
    analyzer = AudioAnalyzer(app_config, JobConfig())
    lyrics = RecordingLyricsPipeline(whisperx_enabled=True)
    analyzer.metadata_pipeline = None
    analyzer.lyrics_pipeline = lyrics

    embedded = EmbeddedMetadata(artist="Tagged Artist", title="Tagged Title")
    await analyzer._build_song_bundle("/test/audio.mp3", features, embedded)

    assert lyrics.calls == [{"artist": "Tagged Artist", "title": "Tagged Title"}]
    assert lyrics.providers_consulted == ["lrclib"]
