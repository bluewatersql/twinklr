"""Tests for metadata merge policy (Phase 3).

Testing the deterministic scoring and merging algorithms.
"""

from twinklr.core.audio.models.metadata import (
    EmbeddedMetadata,
    MetadataCandidate,
    ResolvedMBIDs,
)


class TestTextNormalization:
    """Test text normalization for similarity comparison."""

    def test_normalize_text_remove_punctuation(self):
        """normalize_text removes punctuation."""
        from twinklr.core.audio.metadata.merge import normalize_text

        assert normalize_text("hello, world!") == "hello world"
        assert normalize_text("test-song (remix)") == "testsong remix"
        assert normalize_text("it's a song") == "its a song"

    def test_token_jaccard_none_handling(self):
        """token_jaccard handles None values."""
        from twinklr.core.audio.metadata.merge import token_jaccard

        assert token_jaccard(None, None) == 0.0  # Both missing (no information)
        assert token_jaccard("hello", None) == 0.0
        assert token_jaccard(None, "hello") == 0.0

    def test_is_generic_title(self):
        """is_generic_title detects generic titles."""
        from twinklr.core.audio.metadata.merge import is_generic_title

        assert is_generic_title("track 1")
        assert is_generic_title("Track 12")
        assert is_generic_title("audio 5")
        assert is_generic_title("AUDIO 123")

    def test_is_generic_title_not_generic(self):
        """is_generic_title returns False for non-generic titles."""
        from twinklr.core.audio.metadata.merge import is_generic_title

        assert not is_generic_title("Real Song Title")
        assert not is_generic_title("Track of the Century")  # Contains "track" but not pattern
        assert not is_generic_title("My Track")

    def test_is_generic_artist(self):
        """is_generic_artist detects generic artists."""
        from twinklr.core.audio.metadata.merge import is_generic_artist

        assert is_generic_artist("unknown")
        assert is_generic_artist("Unknown")
        assert is_generic_artist("UNKNOWN")
        assert is_generic_artist("unknown artist")
        assert is_generic_artist("Unknown Artist")

    def test_score_candidate_perfect_match(self):
        """Perfect candidate match with MusicBrainz."""
        from twinklr.core.audio.metadata.merge import MergeConfig, score_candidate

        embedded = EmbeddedMetadata(
            title="Test Song",
            artist="Test Artist",
        )

        candidate = MetadataCandidate(
            provider="musicbrainz",
            provider_id="mb-123",
            score=0.0,  # Not used, will be computed
            title="Test Song",
            artist="Test Artist",
            duration_ms=180000,
            mbids=ResolvedMBIDs(recording_mbid="rec-123"),
        )

        config = MergeConfig()
        score = score_candidate(candidate, embedded=embedded, ref_duration_ms=180000, config=config)

        # Expected score:
        # 0.40 * 1.0 (musicbrainz weight)
        # + 0.20 * 1.0 (title perfect match)
        # + 0.20 * 1.0 (artist perfect match)
        # + 0.15 * 1.0 (duration exact match)
        # + 0.05 * 0.10 (recording_mbid bonus)
        # = 0.40 + 0.20 + 0.20 + 0.15 + 0.005 = 0.955
        expected = 0.40 + 0.20 + 0.20 + 0.15 + 0.005
        assert abs(score - expected) < 0.001

    def test_score_candidate_acoustid_provider(self):
        """AcoustID provider has lower weight."""
        from twinklr.core.audio.metadata.merge import MergeConfig, score_candidate

        embedded = EmbeddedMetadata(title="Test", artist="Artist")
        candidate = MetadataCandidate(
            provider="acoustid",
            provider_id="aid-123",
            score=0.0,
            title="Test",
            artist="Artist",
        )

        config = MergeConfig()
        score = score_candidate(candidate, embedded=embedded, ref_duration_ms=None, config=config)

        # Expected:
        # 0.40 * 0.9 (acoustid weight)
        # + 0.20 * 1.0 (title match)
        # + 0.20 * 1.0 (artist match)
        # + 0.15 * 0.5 (duration missing)
        # + 0 (no stable IDs)
        # = 0.36 + 0.20 + 0.20 + 0.075 = 0.835
        expected = 0.36 + 0.20 + 0.20 + 0.075
        assert abs(score - expected) < 0.001

    def test_score_candidate_with_isrc(self):
        """ISRC adds bonus to score."""
        from twinklr.core.audio.metadata.merge import MergeConfig, score_candidate

        embedded = EmbeddedMetadata()
        candidate = MetadataCandidate(
            provider="musicbrainz",
            provider_id="mb-123",
            score=0.0,
            isrc="US1234567890",
        )

        config = MergeConfig()
        score = score_candidate(candidate, embedded=embedded, ref_duration_ms=None, config=config)

        # Expected:
        # 0.40 * 1.0 (musicbrainz)
        # + 0.20 * 0 (no title)
        # + 0.20 * 0 (no artist)
        # + 0.15 * 0.5 (duration missing)
        # + 0.05 * 0.05 (isrc bonus)
        # = 0.40 + 0 + 0 + 0.075 + 0.0025 = 0.4775
        expected = 0.40 + 0.075 + 0.0025
        assert abs(score - expected) < 0.001

    def test_score_candidate_deterministic(self):
        """Same inputs produce same score (deterministic)."""
        from twinklr.core.audio.metadata.merge import MergeConfig, score_candidate

        embedded = EmbeddedMetadata(title="Test", artist="Artist")
        candidate = MetadataCandidate(
            provider="musicbrainz",
            provider_id="mb-123",
            score=0.0,
            title="Test",
            artist="Artist",
        )

        config = MergeConfig()

        # Run multiple times
        score1 = score_candidate(
            candidate, embedded=embedded, ref_duration_ms=180000, config=config
        )
        score2 = score_candidate(
            candidate, embedded=embedded, ref_duration_ms=180000, config=config
        )
        score3 = score_candidate(
            candidate, embedded=embedded, ref_duration_ms=180000, config=config
        )

        assert score1 == score2 == score3


class TestMergeMetadata:
    """Test metadata merge policy."""

    def test_merge_metadata_no_candidates(self):
        """Merge with no candidates returns None if embedded is empty."""
        from twinklr.core.audio.metadata.merge import MergeConfig, merge_metadata

        embedded = EmbeddedMetadata()  # Empty
        candidates = []

        config = MergeConfig()
        resolved = merge_metadata(embedded, candidates, config=config, ref_duration_ms=180000)

        assert resolved is None

    def test_merge_metadata_single_candidate(self):
        """Merge with single candidate."""
        from twinklr.core.audio.metadata.merge import MergeConfig, merge_metadata

        embedded = EmbeddedMetadata(title="Embedded Title", artist="Embedded Artist")
        candidate = MetadataCandidate(
            provider="musicbrainz",
            provider_id="mb-123",
            score=0.92,  # Pre-scored
            title="Provider Title",
            artist="Provider Artist",
            mbids=ResolvedMBIDs(recording_mbid="rec-123"),
        )

        config = MergeConfig()
        resolved = merge_metadata(embedded, [candidate], config=config, ref_duration_ms=None)

        assert resolved is not None
        # IDs always come from best candidate
        assert resolved.mbids.recording_mbid == "rec-123"

    def test_merge_metadata_prefers_embedded_non_generic(self):
        """Merge prefers embedded strings if non-generic."""
        from twinklr.core.audio.metadata.merge import MergeConfig, merge_metadata

        embedded = EmbeddedMetadata(title="Real Song Title", artist="Real Artist")
        candidate = MetadataCandidate(
            provider="musicbrainz",
            provider_id="mb-123",
            score=0.95,  # High score
            title="Provider Title",
            artist="Provider Artist",
        )

        config = MergeConfig()
        resolved = merge_metadata(embedded, [candidate], config=config, ref_duration_ms=None)

        assert resolved is not None
        # Non-generic embedded strings preferred
        assert resolved.title == "Real Song Title"
        assert resolved.artist == "Real Artist"

    def test_merge_metadata_prefers_provider_for_generic_embedded(self):
        """Merge prefers provider strings if embedded is generic."""
        from twinklr.core.audio.metadata.merge import MergeConfig, merge_metadata

        embedded = EmbeddedMetadata(title="track 1", artist="unknown")  # Generic
        candidate = MetadataCandidate(
            provider="musicbrainz",
            provider_id="mb-123",
            score=0.85,
            title="Provider Title",
            artist="Provider Artist",
        )

        config = MergeConfig()
        resolved = merge_metadata(embedded, [candidate], config=config, ref_duration_ms=None)

        assert resolved is not None
        # Provider strings preferred for generic embedded
        assert resolved.title == "Provider Title"
        assert resolved.artist == "Provider Artist"

    def test_merge_metadata_multiple_candidates(self):
        """Merge with multiple candidates selects best."""
        from twinklr.core.audio.metadata.merge import MergeConfig, merge_metadata

        embedded = EmbeddedMetadata(title="Test", artist="Artist")
        candidates = [
            MetadataCandidate(
                provider="acoustid",
                provider_id="aid-1",
                score=0.75,
                title="Candidate 1",
            ),
            MetadataCandidate(
                provider="musicbrainz",
                provider_id="mb-2",
                score=0.92,  # Best score
                title="Candidate 2",
                mbids=ResolvedMBIDs(recording_mbid="rec-best"),
            ),
            MetadataCandidate(
                provider="musicbrainz",
                provider_id="mb-3",
                score=0.88,
                title="Candidate 3",
            ),
        ]

        config = MergeConfig()
        resolved = merge_metadata(embedded, candidates, config=config, ref_duration_ms=None)

        assert resolved is not None
        # Best candidate (score 0.92) selected
        assert resolved.mbids.recording_mbid == "rec-best"

    def test_merge_metadata_deterministic(self):
        """Merge policy is deterministic."""
        from twinklr.core.audio.metadata.merge import MergeConfig, merge_metadata

        embedded = EmbeddedMetadata(title="Test", artist="Artist")
        candidates = [
            MetadataCandidate(provider="acoustid", provider_id="aid-1", score=0.75, title="A"),
            MetadataCandidate(provider="musicbrainz", provider_id="mb-2", score=0.92, title="B"),
        ]

        config = MergeConfig()

        # Run multiple times
        result1 = merge_metadata(embedded, candidates, config=config, ref_duration_ms=180000)
        result2 = merge_metadata(embedded, candidates, config=config, ref_duration_ms=180000)
        result3 = merge_metadata(embedded, candidates, config=config, ref_duration_ms=180000)

        # All results should be identical
        assert result1 == result2 == result3

    def test_merge_metadata_confidence_tracking(self):
        """Merge tracks per-field confidence."""
        from twinklr.core.audio.metadata.merge import MergeConfig, merge_metadata

        embedded = EmbeddedMetadata(title="Real Song", artist="Real Artist")
        candidate = MetadataCandidate(
            provider="musicbrainz",
            provider_id="mb-123",
            score=0.92,
            title="Provider Song",
            artist="Provider Artist",
        )

        config = MergeConfig()
        resolved = merge_metadata(embedded, [candidate], config=config, ref_duration_ms=None)

        assert resolved is not None
        # Should have confidence scores
        assert resolved.confidence > 0.0
        assert resolved.title_confidence > 0.0
        if resolved.artist_confidence is not None:
            assert resolved.artist_confidence > 0.0
