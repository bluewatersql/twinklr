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

    def test_normalize_text_lowercase(self):
        """normalize_text converts to lowercase."""
        from twinklr.core.audio.metadata.merge import normalize_text

        assert normalize_text("Hello WORLD") == "hello world"
        assert normalize_text("Test Song") == "test song"

    def test_normalize_text_strip(self):
        """normalize_text strips whitespace."""
        from twinklr.core.audio.metadata.merge import normalize_text

        assert normalize_text("  hello  ") == "hello"
        assert normalize_text("\t test \n") == "test"

    def test_normalize_text_collapse_whitespace(self):
        """normalize_text collapses multiple spaces."""
        from twinklr.core.audio.metadata.merge import normalize_text

        assert normalize_text("hello    world") == "hello world"
        assert normalize_text("a  b   c") == "a b c"

    def test_normalize_text_remove_punctuation(self):
        """normalize_text removes punctuation."""
        from twinklr.core.audio.metadata.merge import normalize_text

        assert normalize_text("hello, world!") == "hello world"
        assert normalize_text("test-song (remix)") == "testsong remix"
        assert normalize_text("it's a song") == "its a song"

    def test_normalize_text_none(self):
        """normalize_text handles None."""
        from twinklr.core.audio.metadata.merge import normalize_text

        assert normalize_text(None) == ""

    def test_normalize_text_empty(self):
        """normalize_text handles empty string."""
        from twinklr.core.audio.metadata.merge import normalize_text

        assert normalize_text("") == ""


class TestTokenJaccard:
    """Test token Jaccard similarity."""

    def test_token_jaccard_identical(self):
        """Identical strings have similarity 1.0."""
        from twinklr.core.audio.metadata.merge import token_jaccard

        assert token_jaccard("hello world", "hello world") == 1.0
        assert token_jaccard("test", "test") == 1.0

    def test_token_jaccard_no_overlap(self):
        """No overlap has similarity 0.0."""
        from twinklr.core.audio.metadata.merge import token_jaccard

        assert token_jaccard("hello", "world") == 0.0
        assert token_jaccard("foo bar", "baz qux") == 0.0

    def test_token_jaccard_partial_overlap(self):
        """Partial overlap."""
        from twinklr.core.audio.metadata.merge import token_jaccard

        # "hello world" and "hello there" share 1 token (hello)
        # Union: {hello, world, there} = 3 tokens
        # Jaccard: 1/3 = 0.333...
        assert abs(token_jaccard("hello world", "hello there") - 1 / 3) < 0.001

        # "a b c" and "b c d" share 2 tokens (b, c)
        # Union: {a, b, c, d} = 4 tokens
        # Jaccard: 2/4 = 0.5
        assert token_jaccard("a b c", "b c d") == 0.5

    def test_token_jaccard_case_insensitive(self):
        """token_jaccard is case-insensitive (normalized)."""
        from twinklr.core.audio.metadata.merge import token_jaccard

        assert token_jaccard("Hello World", "hello world") == 1.0

    def test_token_jaccard_none_handling(self):
        """token_jaccard handles None values."""
        from twinklr.core.audio.metadata.merge import token_jaccard

        assert token_jaccard(None, None) == 0.0  # Both missing (no information)
        assert token_jaccard("hello", None) == 0.0
        assert token_jaccard(None, "hello") == 0.0

    def test_token_jaccard_empty_strings(self):
        """token_jaccard handles empty strings."""
        from twinklr.core.audio.metadata.merge import token_jaccard

        assert token_jaccard("", "") == 0.0  # Both empty (no information)
        assert token_jaccard("hello", "") == 0.0


class TestDurationSimilarity:
    """Test duration similarity."""

    def test_duration_similarity_exact_match(self):
        """Exact duration match has similarity 1.0."""
        from twinklr.core.audio.metadata.merge import duration_similarity

        assert duration_similarity(180000, 180000) == 1.0
        assert duration_similarity(120500, 120500) == 1.0

    def test_duration_similarity_small_delta(self):
        """Small duration difference has high similarity."""
        from twinklr.core.audio.metadata.merge import duration_similarity

        # 1 second difference (1000ms) on 180s song
        # delta_s = 1
        # sim = 1 - min(1, 6)/6 = 1 - 1/6 = 0.833...
        sim = duration_similarity(180000, 181000)
        assert abs(sim - (1 - 1 / 6)) < 0.001

    def test_duration_similarity_large_delta(self):
        """Large duration difference has low similarity."""
        from twinklr.core.audio.metadata.merge import duration_similarity

        # 10 second difference (10000ms)
        # delta_s = 10
        # sim = 1 - min(10, 6)/6 = 1 - 6/6 = 0
        assert duration_similarity(180000, 190000) == 0.0

    def test_duration_similarity_missing_ref(self):
        """Missing reference duration returns 0.5."""
        from twinklr.core.audio.metadata.merge import duration_similarity

        assert duration_similarity(180000, None) == 0.5
        assert duration_similarity(None, 180000) == 0.5

    def test_duration_similarity_both_missing(self):
        """Both missing returns 0.5 (can't compare)."""
        from twinklr.core.audio.metadata.merge import duration_similarity

        assert duration_similarity(None, None) == 0.5


class TestGenericDetection:
    """Test generic title/artist detection."""

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

    def test_is_generic_title_none(self):
        """is_generic_title handles None."""
        from twinklr.core.audio.metadata.merge import is_generic_title

        assert is_generic_title(None)

    def test_is_generic_artist(self):
        """is_generic_artist detects generic artists."""
        from twinklr.core.audio.metadata.merge import is_generic_artist

        assert is_generic_artist("unknown")
        assert is_generic_artist("Unknown")
        assert is_generic_artist("UNKNOWN")
        assert is_generic_artist("unknown artist")
        assert is_generic_artist("Unknown Artist")

    def test_is_generic_artist_not_generic(self):
        """is_generic_artist returns False for non-generic artists."""
        from twinklr.core.audio.metadata.merge import is_generic_artist

        assert not is_generic_artist("Real Artist Name")
        assert not is_generic_artist("The Unknown Legends")  # Contains "unknown" but not exact

    def test_is_generic_artist_none(self):
        """is_generic_artist handles None."""
        from twinklr.core.audio.metadata.merge import is_generic_artist

        assert is_generic_artist(None)


class TestCandidateScoring:
    """Test candidate scoring algorithm."""

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
