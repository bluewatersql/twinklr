"""Tests for lyrics provider models (Phase 4).

Testing LyricsQuery and LyricsCandidate models.
"""

from twinklr.core.audio.lyrics.providers.models import LyricsCandidate, LyricsQuery


class TestLyricsQuery:
    """Test LyricsQuery model."""

    def test_minimal_query(self):
        """Query with minimal fields."""
        query = LyricsQuery()

        assert query.artist is None
        assert query.title is None
        assert query.album is None
        assert query.duration_ms is None
        assert query.ids == {}

    def test_query_with_metadata(self):
        """Query with artist and title."""
        query = LyricsQuery(
            artist="Test Artist",
            title="Test Song",
        )

        assert query.artist == "Test Artist"
        assert query.title == "Test Song"

    def test_query_with_all_fields(self):
        """Query with all fields."""
        query = LyricsQuery(
            artist="Test Artist",
            title="Test Song",
            album="Test Album",
            duration_ms=180000,
            ids={"musicbrainz": "abc123", "spotify": "xyz789"},
        )

        assert query.artist == "Test Artist"
        assert query.title == "Test Song"
        assert query.album == "Test Album"
        assert query.duration_ms == 180000
        assert query.ids["musicbrainz"] == "abc123"


class TestLyricsCandidate:
    """Test LyricsCandidate model."""

    def test_minimal_candidate(self):
        """Candidate with minimal fields."""
        candidate = LyricsCandidate(
            provider="test_provider",
            kind="PLAIN",
            text="Test lyrics",
        )

        assert candidate.provider == "test_provider"
        assert candidate.kind == "PLAIN"
        assert candidate.text == "Test lyrics"
        assert candidate.provider_id is None
        assert candidate.lrc is None
        assert candidate.confidence == 0.5
        assert candidate.attribution == {}
        assert candidate.warnings == []

    def test_synced_candidate(self):
        """Candidate with synced lyrics (LRC)."""
        candidate = LyricsCandidate(
            provider="lrclib",
            provider_id="12345",
            kind="SYNCED",
            text="Test lyrics\nLine 2",
            lrc="[00:12.00]Test lyrics\n[00:15.00]Line 2",
            confidence=0.85,
        )

        assert candidate.kind == "SYNCED"
        assert candidate.lrc is not None
        assert "[00:12.00]" in candidate.lrc
        assert candidate.confidence == 0.85

    def test_plain_candidate(self):
        """Candidate with plain lyrics."""
        candidate = LyricsCandidate(
            provider="genius",
            kind="PLAIN",
            text="Test lyrics\nLine 2\nLine 3",
            confidence=0.75,
        )

        assert candidate.kind == "PLAIN"
        assert candidate.lrc is None

    def test_candidate_with_attribution(self):
        """Candidate with attribution metadata."""
        candidate = LyricsCandidate(
            provider="test_provider",
            kind="PLAIN",
            text="Test lyrics",
            attribution={
                "source_url": "https://example.com",
                "license": "CC BY-SA",
            },
        )

        assert "source_url" in candidate.attribution
        assert candidate.attribution["license"] == "CC BY-SA"

    def test_candidate_with_warnings(self):
        """Candidate with warnings."""
        candidate = LyricsCandidate(
            provider="test_provider",
            kind="PLAIN",
            text="Test lyrics",
            warnings=["Low confidence match", "Partial lyrics"],
        )

        assert len(candidate.warnings) == 2
        assert "Low confidence match" in candidate.warnings
