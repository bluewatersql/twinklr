"""Phoneme pipeline entry point (Phase 6).

Wires G2P → weighted distribution → viseme mapping → smoothing → confidence
into a single build_phoneme_bundle() function that produces a PhonemeBundle.

Functions:
    build_phoneme_bundle: Build complete PhonemeBundle from timed words.

Example:
    >>> from twinklr.core.audio.models.lyrics import LyricWord
    >>> words = [LyricWord(text="hello", start_ms=0, end_ms=500)]
    >>> bundle = build_phoneme_bundle(duration_ms=1000, words=words, mapping_version="1.0")
    >>> len(bundle.phonemes) > 0
    True
"""

import logging

from twinklr.core.audio.models.lyrics import LyricWord
from twinklr.core.audio.models.phonemes import (
    Phoneme,
    PhonemeBundle,
    PhonemeSource,
    VisemeEvent,
)
from twinklr.core.audio.phonemes.g2p_service import G2PConfig, word_to_phonemes
from twinklr.core.audio.phonemes.smooth import smooth_visemes
from twinklr.core.audio.phonemes.timing import (
    classify_phoneme,
    distribute_word_window_to_phonemes,
)
from twinklr.core.audio.phonemes.viseme_mapping import phoneme_to_viseme

logger = logging.getLogger(__name__)


def build_phoneme_bundle(
    *,
    duration_ms: int,
    words: list[LyricWord],
    mapping_version: str,
    enable_g2p_en: bool = True,
    min_phoneme_ms: int = 30,
    vowel_weight: float = 2.0,
    consonant_weight: float = 1.0,
    min_hold_ms: int = 50,
    min_burst_ms: int = 40,
    boundary_soften_ms: int = 15,
) -> PhonemeBundle:
    """Build complete PhonemeBundle from timed lyric words.

    Pipeline stages:
    1. G2P: Convert each word to ARPAbet phonemes via g2p_en.
    2. Distribute: Assign weighted timing windows to phonemes within each word.
    3. Viseme map: Map each timed phoneme to a viseme code.
    4. Smooth: Apply coalesce, min-hold, burst merge, boundary soften.
    5. Confidence: Compute overall confidence from G2P source, OOV rate,
       burst merge count, and viseme coverage.

    Args:
        duration_ms: Total song duration in milliseconds.
        words: List of LyricWord with text, start_ms, end_ms.
        mapping_version: Viseme mapping version string.
        enable_g2p_en: Whether to use g2p_en for conversion.
        min_phoneme_ms: Minimum phoneme duration; words shorter collapse.
        vowel_weight: Relative weight for vowel duration.
        consonant_weight: Relative weight for consonant duration.
        min_hold_ms: Minimum viseme hold duration in ms.
        min_burst_ms: Minimum burst duration before merging in ms.
        boundary_soften_ms: Boundary softening window in ms.

    Returns:
        PhonemeBundle with phonemes, visemes, confidence, and stats.
    """
    if not words:
        return PhonemeBundle(
            phonemes=[],
            visemes=[],
            source=PhonemeSource.G2P,
            confidence=0.0,
            oov_rate=0.0,
            coverage_pct=0.0,
            burst_merge_count=0,
            metadata={"word_count": 0, "mapping_version": mapping_version},
        )

    g2p_config = G2PConfig(strip_stress=False, filter_punctuation=True)

    all_phonemes: list[Phoneme] = []
    raw_viseme_events: list[VisemeEvent] = []
    oov_count = 0
    total_words = len(words)

    for word in words:
        # Skip words with no text
        text = word.text.strip()
        if not text:
            continue

        # Stage 1: G2P conversion
        try:
            phoneme_list = word_to_phonemes(text, config=g2p_config)
        except Exception:
            logger.debug(f"G2P failed for word '{text}', skipping")
            oov_count += 1
            continue

        if not phoneme_list:
            oov_count += 1
            continue

        # Stage 2: Weighted timing distribution
        timed = distribute_word_window_to_phonemes(
            word_start_ms=word.start_ms,
            word_end_ms=word.end_ms,
            phonemes=phoneme_list,
            min_phoneme_ms=min_phoneme_ms,
            vowel_weight=vowel_weight,
            consonant_weight=consonant_weight,
        )

        # Build Phoneme objects and viseme events
        for phoneme_text, start_ms, end_ms in timed:
            ptype = classify_phoneme(phoneme_text)
            all_phonemes.append(
                Phoneme(
                    text=phoneme_text,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    phoneme_type=ptype.value,
                )
            )

            # Stage 3: Viseme mapping
            viseme_code = phoneme_to_viseme(phoneme_text)
            raw_viseme_events.append(
                VisemeEvent(
                    viseme=viseme_code,
                    start_ms=start_ms,
                    end_ms=end_ms,
                )
            )

    # Stage 4: Smoothing
    smoothed_visemes, burst_merge_count = smooth_visemes(
        raw_viseme_events,
        min_hold_ms=min_hold_ms,
        min_burst_ms=min_burst_ms,
        boundary_soften_ms=boundary_soften_ms,
        duration_ms=duration_ms,
    )

    # Stage 5: Confidence and stats
    oov_rate = oov_count / total_words if total_words > 0 else 0.0
    coverage_pct = _compute_coverage(smoothed_visemes, duration_ms)
    confidence = _compute_confidence(
        oov_rate=oov_rate,
        burst_merge_count=burst_merge_count,
        coverage_pct=coverage_pct,
    )

    return PhonemeBundle(
        phonemes=all_phonemes,
        visemes=smoothed_visemes,
        source=PhonemeSource.G2P,
        confidence=confidence,
        oov_rate=oov_rate,
        coverage_pct=coverage_pct,
        burst_merge_count=burst_merge_count,
        metadata={
            "word_count": total_words,
            "phoneme_count": len(all_phonemes),
            "viseme_count": len(smoothed_visemes),
            "mapping_version": mapping_version,
        },
    )


def _compute_coverage(visemes: list[VisemeEvent], duration_ms: int) -> float:
    """Compute viseme coverage as fraction of song duration.

    Args:
        visemes: Smoothed viseme events.
        duration_ms: Total song duration in milliseconds.

    Returns:
        Coverage fraction (0-1).
    """
    if not visemes or duration_ms <= 0:
        return 0.0

    total_viseme_span = sum(v.end_ms - v.start_ms for v in visemes)
    return min(1.0, total_viseme_span / duration_ms)


def _compute_confidence(
    *,
    oov_rate: float,
    burst_merge_count: int,
    coverage_pct: float,
    base_confidence: float = 0.85,
    g2p_factor: float = 0.9,
) -> float:
    """Compute overall confidence per spec.

    Base confidence * G2P factor, then penalties:
    - -0.10 if oov_rate > 0.15
    - -0.10 if burst_merge_count > 30
    - -0.10 if coverage < 0.50

    Args:
        oov_rate: Out-of-vocabulary rate.
        burst_merge_count: Number of burst merges.
        coverage_pct: Viseme coverage of song duration.
        base_confidence: Base confidence (default 0.85).
        g2p_factor: G2P source factor (G2P_EN=0.9, CMUDICT=1.0).

    Returns:
        Confidence clamped to [0, 1].
    """
    confidence = base_confidence * g2p_factor

    if oov_rate > 0.15:
        confidence -= 0.10
    if burst_merge_count > 30:
        confidence -= 0.10
    if coverage_pct < 0.50:
        confidence -= 0.10

    return max(0.0, min(1.0, confidence))
