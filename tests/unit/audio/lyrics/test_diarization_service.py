"""Unit tests for diarization service and functions (Phase 5 Milestone 3).

Tests cover:
- suggest_diarization() heuristic function
- assign_speakers() function
- DiarizationService protocol
- Marker detection
- Speaker assignment logic
"""


from blinkb0t.core.audio.lyrics.diarization import (
    assign_speakers,
    suggest_diarization,
)
from blinkb0t.core.audio.lyrics.diarization_models import (
    DiarizationConfig,
    SpeakerSegment,
)
from blinkb0t.core.audio.models.lyrics import LyricWord


class TestSuggestDiarization:
    """Test diarization suggestion heuristic."""

    def test_no_markers_no_suggestion(self):
        """Lyrics without markers should not suggest diarization."""
        lyrics_text = "hello world this is a song with no speaker markers"
        words = [LyricWord(text="hello", start_ms=0, end_ms=500)]

        suggested, confidence, reasons = suggest_diarization(lyrics_text, words)

        assert not suggested
        assert confidence == 0.0
        assert len(reasons) == 0

    def test_male_marker_suggests_diarization(self):
        """Lyrics with (male) marker should suggest diarization."""
        lyrics_text = "(male) hello world"
        words = [LyricWord(text="hello", start_ms=0, end_ms=500)]

        suggested, confidence, reasons = suggest_diarization(lyrics_text, words)

        assert suggested
        assert confidence >= 0.85  # Above default threshold
        assert any("(male)" in r for r in reasons)

    def test_female_marker_suggests_diarization(self):
        """Lyrics with (female) marker should suggest diarization."""
        lyrics_text = "(female) goodbye world"
        words = None

        suggested, confidence, reasons = suggest_diarization(lyrics_text, words)

        assert suggested
        assert confidence >= 0.85
        assert any("(female)" in r for r in reasons)

    def test_duet_marker_suggests_diarization(self):
        """Lyrics with [duet] marker should suggest diarization."""
        lyrics_text = "[duet] singing together"
        words = None

        suggested, confidence, reasons = suggest_diarization(lyrics_text, words)

        assert suggested
        assert confidence >= 0.85
        assert any("[duet]" in r for r in reasons)

    def test_speaker_prefix_suggests_diarization(self):
        """Lyrics with A: B: prefixes should suggest diarization."""
        lyrics_text = "A: hello\nB: world"
        words = None

        suggested, confidence, reasons = suggest_diarization(lyrics_text, words)

        assert suggested
        assert confidence >= 0.85
        assert any("A:" in r or "B:" in r for r in reasons)

    def test_multiple_markers_higher_confidence(self):
        """Multiple markers should increase confidence."""
        lyrics_text = "(male) A: hello\n(female) B: world"
        words = None

        suggested, _confidence, reasons = suggest_diarization(lyrics_text, words)

        assert suggested
        assert _confidence >= 0.90  # Multiple markers = higher confidence
        assert len(reasons) >= 2

    def test_case_insensitive_markers(self):
        """Markers should be detected case-insensitively."""
        lyrics_text = "(MALE) HELLO (Female) world"
        words = None

        suggested, _confidence, reasons = suggest_diarization(lyrics_text, words)

        assert suggested
        assert len(reasons) >= 1

    def test_custom_threshold(self):
        """Custom threshold should affect suggestion."""
        lyrics_text = "(male) hello"
        words = None
        config = DiarizationConfig(suggest_threshold=0.95)

        suggested, confidence, reasons = suggest_diarization(
            lyrics_text, words, config=config
        )

        # Confidence is 0.85-0.90, below 0.95 threshold
        assert not suggested  # Not suggested (below threshold)
        assert confidence > 0.0  # But confidence is > 0
        assert len(reasons) > 0  # Reasons still returned

    def test_none_text_no_suggestion(self):
        """None text should not suggest diarization."""
        suggested, confidence, reasons = suggest_diarization(None, None)

        assert not suggested
        assert confidence == 0.0
        assert len(reasons) == 0

    def test_empty_text_no_suggestion(self):
        """Empty text should not suggest diarization."""
        suggested, confidence, _reasons = suggest_diarization("", None)

        assert not suggested
        assert confidence == 0.0


class TestAssignSpeakers:
    """Test speaker assignment to words."""

    def test_assign_single_speaker(self):
        """Words in single speaker segment should get that speaker."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),
            LyricWord(text="world", start_ms=500, end_ms=1000),
        ]

        segments = [
            SpeakerSegment(speaker="SPEAKER_01", start_ms=0, end_ms=1000, confidence=0.95)
        ]

        assigned_words = assign_speakers(words, segments)

        assert len(assigned_words) == 2
        assert assigned_words[0].speaker == "SPEAKER_01"
        assert assigned_words[1].speaker == "SPEAKER_01"

    def test_assign_multiple_speakers(self):
        """Words should be assigned to appropriate speakers by overlap."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),  # SPEAKER_01
            LyricWord(text="world", start_ms=5000, end_ms=5500),  # SPEAKER_02
        ]

        segments = [
            SpeakerSegment(speaker="SPEAKER_01", start_ms=0, end_ms=2000, confidence=0.95),
            SpeakerSegment(speaker="SPEAKER_02", start_ms=4000, end_ms=6000, confidence=0.92),
        ]

        assigned_words = assign_speakers(words, segments)

        assert assigned_words[0].speaker == "SPEAKER_01"
        assert assigned_words[1].speaker == "SPEAKER_02"

    def test_no_overlap_no_speaker(self):
        """Words with no sufficient overlap should have None speaker."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=100),  # Too short overlap
        ]

        segments = [
            SpeakerSegment(speaker="SPEAKER_01", start_ms=90, end_ms=2000, confidence=0.95)
        ]

        # Word duration = 100ms, overlap with segment = 10ms (10%)
        # Below 30% threshold, so no speaker assigned
        assigned_words = assign_speakers(words, segments)

        assert assigned_words[0].speaker is None

    def test_overlap_threshold_enforced(self):
        """Speaker assignment requires >= 30% overlap by default."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=1000),
        ]

        # Segment overlaps 250ms out of 1000ms = 25% (below threshold)
        segments = [
            SpeakerSegment(speaker="SPEAKER_01", start_ms=750, end_ms=2000, confidence=0.95)
        ]

        assigned_words = assign_speakers(words, segments)
        assert assigned_words[0].speaker is None

        # Segment overlaps 400ms out of 1000ms = 40% (above threshold)
        segments = [
            SpeakerSegment(speaker="SPEAKER_01", start_ms=600, end_ms=2000, confidence=0.95)
        ]

        assigned_words = assign_speakers(words, segments)
        assert assigned_words[0].speaker == "SPEAKER_01"

    def test_custom_overlap_threshold(self):
        """Custom overlap threshold should be respected."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=1000),
        ]

        # 25% overlap
        segments = [
            SpeakerSegment(speaker="SPEAKER_01", start_ms=750, end_ms=2000, confidence=0.95)
        ]

        # Default 30% threshold: no speaker
        assigned_words = assign_speakers(words, segments, min_overlap_pct=0.3)
        assert assigned_words[0].speaker is None

        # Lower threshold 20%: speaker assigned
        assigned_words = assign_speakers(words, segments, min_overlap_pct=0.2)
        assert assigned_words[0].speaker == "SPEAKER_01"

    def test_best_overlap_wins(self):
        """Word should be assigned to speaker with highest overlap."""
        words = [
            LyricWord(text="hello", start_ms=500, end_ms=1500),  # 1000ms duration
        ]

        segments = [
            # SPEAKER_01 overlaps 500ms (50%)
            SpeakerSegment(speaker="SPEAKER_01", start_ms=0, end_ms=1000, confidence=0.95),
            # SPEAKER_02 overlaps 750ms (75%) - BEST
            SpeakerSegment(speaker="SPEAKER_02", start_ms=750, end_ms=2000, confidence=0.92),
        ]

        assigned_words = assign_speakers(words, segments)
        assert assigned_words[0].speaker == "SPEAKER_02"  # Best overlap

    def test_empty_words(self):
        """Empty words list should return empty list."""
        segments = [
            SpeakerSegment(speaker="SPEAKER_01", start_ms=0, end_ms=1000, confidence=0.95)
        ]

        assigned_words = assign_speakers([], segments)
        assert len(assigned_words) == 0

    def test_empty_segments(self):
        """Empty segments should leave all speakers as None."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),
        ]

        assigned_words = assign_speakers(words, [])
        assert assigned_words[0].speaker is None

    def test_preserves_other_fields(self):
        """Speaker assignment should preserve other word fields."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500, speaker="OLD_SPEAKER"),
        ]

        segments = [
            SpeakerSegment(speaker="NEW_SPEAKER", start_ms=0, end_ms=1000, confidence=0.95)
        ]

        assigned_words = assign_speakers(words, segments)

        assert assigned_words[0].text == "hello"
        assert assigned_words[0].start_ms == 0
        assert assigned_words[0].end_ms == 500
        assert assigned_words[0].speaker == "NEW_SPEAKER"  # Updated
