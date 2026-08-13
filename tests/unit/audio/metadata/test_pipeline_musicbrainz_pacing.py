"""MusicBrainz lookups must respect the provider's published rate policy.

MusicBrainz allows 1 request/second and no concurrent requests. The pipeline
used to fan MBID lookups out under ``asyncio.gather``; that was dormant only
because AcoustID failed on every call and no MBIDs ever reached it (P2-F13).
"""

from __future__ import annotations

import asyncio

import pytest

from twinklr.core.api.audio.models import AcoustIDRecording, AcoustIDResponse, MusicBrainzRecording
from twinklr.core.audio.metadata.pipeline import MetadataPipeline, PipelineConfig
from twinklr.core.audio.models.metadata import EmbeddedMetadata, FingerprintInfo

MBIDS = ["rec-1", "rec-2", "rec-3"]


class SerializationProbe:
    """MusicBrainz client double that detects overlapping lookups."""

    def __init__(self) -> None:
        self.in_flight = 0
        self.max_in_flight = 0
        self.order: list[str] = []

    async def lookup_recording(self, *, mbid: str) -> MusicBrainzRecording:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        self.order.append(mbid)
        # Yield: an overlapping lookup would be observed here.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.in_flight -= 1
        return MusicBrainzRecording(id=mbid, title=f"Title {mbid}", artists=["A"])


class StubAcoustID:
    """AcoustID client double returning one candidate per MBID."""

    async def lookup(self, *, fingerprint: str, duration_s: float) -> AcoustIDResponse:
        return AcoustIDResponse(
            status="ok",
            results=[
                AcoustIDRecording(id=f"aid-{i}", score=0.9, title="T", recording_mbid=mbid)
                for i, mbid in enumerate(MBIDS)
            ],
        )


@pytest.fixture
def probe() -> SerializationProbe:
    return SerializationProbe()


@pytest.fixture
def pipeline(probe: SerializationProbe) -> MetadataPipeline:
    return MetadataPipeline(
        config=PipelineConfig(enable_acoustid=True, enable_musicbrainz=True),
        acoustid_client=StubAcoustID(),
        musicbrainz_client=probe,
    )


async def test_musicbrainz_lookups_are_sequential(pipeline, probe, monkeypatch):
    """N MBIDs issue one at a time, in order — no fan-out."""
    monkeypatch.setattr(
        MetadataPipeline,
        "_compute_fingerprint",
        lambda self, path, warnings: FingerprintInfo(
            audio_fingerprint="hash",
            chromaprint_fingerprint="fp",
            chromaprint_duration_s=180.0,
        ),
    )

    bundle = await pipeline.extract("/test/audio.mp3", embedded_metadata=EmbeddedMetadata())

    assert probe.max_in_flight == 1, "MusicBrainz lookups must never overlap"
    assert probe.order == MBIDS
    musicbrainz_candidates = [c for c in bundle.candidates if c.provider == "musicbrainz"]
    assert len(musicbrainz_candidates) == len(MBIDS)


def test_pipeline_module_does_not_fan_out_musicbrainz():
    """The gather over MBID tasks is gone from the source."""
    from pathlib import Path

    import twinklr.core.audio.metadata.pipeline as pipeline_module

    source = Path(pipeline_module.__file__).read_text()
    assert "asyncio.gather" not in source
