"""Provider-failure warnings must say what kind of failure occurred.

A bare "provider lookup failed" reads identically whether the cause was a
network fault, a bad credential, or a broken response contract — which is how a
100% client failure rate went undiagnosed (the P1-F1 "deception" refinement).
"""

from __future__ import annotations

import pytest

from twinklr.core.api.audio.acoustid import AcoustIDError
from twinklr.core.api.audio.errors import ProviderFailureCategory
from twinklr.core.api.audio.musicbrainz import MusicBrainzError
from twinklr.core.audio.metadata.pipeline import MetadataPipeline, PipelineConfig
from twinklr.core.audio.models.metadata import FingerprintInfo


class FailingAcoustID:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def lookup(self, *, fingerprint: str, duration_s: float):
        raise self.error


class FailingMusicBrainz:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def lookup_recording(self, *, mbid: str):
        raise self.error


@pytest.fixture
def fingerprint() -> FingerprintInfo:
    return FingerprintInfo(
        audio_fingerprint="hash", chromaprint_fingerprint="fp", chromaprint_duration_s=180.0
    )


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        (ProviderFailureCategory.PARSE, "parse"),
        (ProviderFailureCategory.TRANSPORT, "transport"),
        (ProviderFailureCategory.CREDENTIAL, "credential"),
    ],
)
async def test_acoustid_warning_names_the_failure_kind(fingerprint, category, expected):
    pipeline = MetadataPipeline(
        config=PipelineConfig(),
        acoustid_client=FailingAcoustID(AcoustIDError("boom", category=category)),
        musicbrainz_client=None,
    )
    warnings: list[str] = []

    await pipeline._query_acoustid(fingerprint, warnings)

    assert len(warnings) == 1
    assert expected in warnings[0]


async def test_musicbrainz_warning_names_the_failure_kind():
    pipeline = MetadataPipeline(
        config=PipelineConfig(),
        acoustid_client=None,
        musicbrainz_client=FailingMusicBrainz(
            MusicBrainzError("boom", category=ProviderFailureCategory.PARSE)
        ),
    )
    warnings: list[str] = []

    await pipeline._query_musicbrainz("mbid-1", warnings)

    assert len(warnings) == 1
    assert "parse" in warnings[0]


async def test_parse_and_transport_warnings_are_distinguishable(fingerprint):
    """The two failure kinds do not produce interchangeable messages."""
    messages = []
    for category in (ProviderFailureCategory.PARSE, ProviderFailureCategory.TRANSPORT):
        pipeline = MetadataPipeline(
            config=PipelineConfig(),
            acoustid_client=FailingAcoustID(AcoustIDError("boom", category=category)),
            musicbrainz_client=None,
        )
        warnings: list[str] = []
        await pipeline._query_acoustid(fingerprint, warnings)
        messages.append(warnings[0])

    assert messages[0] != messages[1]
