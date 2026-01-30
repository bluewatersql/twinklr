"""Diarization functions for speaker attribution (Phase 5).

Functions:
    suggest_diarization: Heuristic to suggest when diarization would be useful
    assign_speakers: Assign speakers to words based on segment overlap

Example:
    >>> suggested, confidence, reasons = suggest_diarization(
    ...     "(male) hello (female) world", None
    ... )
    >>> suggested
    True
    >>> confidence >= 0.85
    True
"""

import logging
import re
from typing import Protocol

from blinkb0t.core.audio.lyrics.diarization_models import (
    DiarizationConfig,
    DiarizationResult,
    SpeakerSegment,
)
from blinkb0t.core.audio.models.lyrics import LyricWord

logger = logging.getLogger(__name__)


def suggest_diarization(
    lyrics_text: str | None,
    words: list[LyricWord] | None,
    *,
    config: DiarizationConfig | None = None,
) -> tuple[bool, float, list[str]]:
    """Suggest whether diarization would be useful based on lyrics text markers.

    Detects markers in lyrics that indicate multiple speakers:
    - (male), (female) - gender markers
    - [duet], [chorus] - section markers
    - A:, B:, 1:, 2: - speaker prefixes

    Args:
        lyrics_text: Lyrics text to analyze (None = no suggestion)
        words: Word-level timing (optional, not used currently)
        config: Diarization configuration (for thresholds)

    Returns:
        Tuple of (suggested, confidence, reasons):
        - suggested: Whether diarization is suggested (confidence >= threshold)
        - confidence: Confidence score (0.0-1.0)
        - reasons: List of reasons for suggestion

    Example:
        >>> suggested, conf, reasons = suggest_diarization("(male) hello\\n(female) world", None)
        >>> suggested
        True
        >>> conf >= 0.90  # Multiple markers
        True
        >>> len(reasons)
        2
    """
    if not lyrics_text:
        return False, 0.0, []

    if config is None:
        config = DiarizationConfig()

    reasons: list[str] = []
    markers_found = 0

    # Convert to lowercase for case-insensitive matching
    text_lower = lyrics_text.lower()

    # Gender markers
    if "(male)" in text_lower:
        reasons.append("Found gender marker: (male)")
        markers_found += 1
    if "(female)" in text_lower:
        reasons.append("Found gender marker: (female)")
        markers_found += 1

    # Section markers
    if "[duet]" in text_lower:
        reasons.append("Found section marker: [duet]")
        markers_found += 1
    if "[chorus]" in text_lower:
        reasons.append("Found section marker: [chorus]")
        markers_found += 1

    # Speaker prefixes (A:, B:, 1:, 2:, etc at start of line)
    speaker_prefix_pattern = r"^[A-Z12]:\s"
    if re.search(speaker_prefix_pattern, lyrics_text, re.MULTILINE):
        reasons.append("Found speaker prefixes: A:, B:, etc.")
        markers_found += 1

    # No markers found
    if markers_found == 0:
        return False, 0.0, []

    # Compute confidence based on number of markers
    # Base confidence: 0.85 for 1 marker, up to 0.95 for multiple
    if markers_found == 1:
        confidence = 0.85
    elif markers_found == 2:
        confidence = 0.90
    else:
        confidence = 0.95

    # Check if confidence meets threshold
    suggested = confidence >= config.suggest_threshold

    return suggested, confidence, reasons


def assign_speakers(
    words: list[LyricWord],
    segments: list[SpeakerSegment],
    *,
    min_overlap_pct: float = 0.3,
) -> list[LyricWord]:
    """Assign speakers to words based on speaker segment overlap.

    Each word is assigned to the speaker whose segment has the highest overlap
    with the word's time range, provided the overlap is >= min_overlap_pct.

    Args:
        words: List of words to assign speakers to
        segments: List of speaker segments
        min_overlap_pct: Minimum overlap required (0.0-1.0, default 0.3 = 30%)

    Returns:
        New list of words with speaker field updated

    Example:
        >>> words = [LyricWord(text="hello", start_ms=0, end_ms=500)]
        >>> segments = [SpeakerSegment(speaker="SPEAKER_01", start_ms=0, end_ms=1000, confidence=0.95)]
        >>> assigned = assign_speakers(words, segments)
        >>> assigned[0].speaker
        'SPEAKER_01'
    """
    if not words:
        return []

    if not segments:
        # No segments: all speakers = None
        return [
            LyricWord(
                text=w.text,
                start_ms=w.start_ms,
                end_ms=w.end_ms,
                speaker=None,
            )
            for w in words
        ]

    assigned_words: list[LyricWord] = []

    for word in words:
        word_duration = word.end_ms - word.start_ms

        # Find best overlapping segment
        best_speaker = None
        best_overlap = 0.0

        for segment in segments:
            # Compute overlap
            overlap_start = max(word.start_ms, segment.start_ms)
            overlap_end = min(word.end_ms, segment.end_ms)
            overlap_ms = max(0, overlap_end - overlap_start)

            if overlap_ms > 0 and word_duration > 0:
                overlap_pct = overlap_ms / word_duration

                if overlap_pct >= min_overlap_pct and overlap_pct > best_overlap:
                    best_speaker = segment.speaker
                    best_overlap = overlap_pct

        # Create new word with assigned speaker
        assigned_words.append(
            LyricWord(
                text=word.text,
                start_ms=word.start_ms,
                end_ms=word.end_ms,
                speaker=best_speaker,
            )
        )

    return assigned_words


class DiarizationService(Protocol):
    """Protocol for diarization service operations.

    Defines the interface for speaker diarization.
    Implementations can be real (using pyannote-audio) or mock (for testing).
    """

    def diarize(self, audio_path: str, *, config: DiarizationConfig) -> DiarizationResult:
        """Perform speaker diarization on audio.

        Args:
            audio_path: Path to audio file
            config: Diarization configuration

        Returns:
            DiarizationResult with speaker segments

        Raises:
            ImportError: If pyannote-audio not installed
            FileNotFoundError: If audio file not found
            RuntimeError: If diarization fails
        """
        ...
