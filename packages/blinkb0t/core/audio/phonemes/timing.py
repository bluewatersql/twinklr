"""Phoneme timing distribution (Phase 6).

Functions for distributing word time windows across phonemes.

Functions:
    distribute_phonemes_uniform: Distribute word window uniformly across phonemes
    classify_phoneme: Classify phoneme as VOWEL or CONSONANT

Example:
    >>> phonemes = ["HH", "EH", "L", "OW"]
    >>> result = distribute_phonemes_uniform(phonemes, start_ms=0, end_ms=400)
    >>> result
    [('HH', 0, 100), ('EH', 100, 200), ('L', 200, 300), ('OW', 300, 400)]
"""

from enum import Enum


class PhonemeType(str, Enum):
    """Phoneme type classification.

    Values:
        VOWEL: Vowel phoneme
        CONSONANT: Consonant phoneme
        SILENCE: Silence/pause
    """

    VOWEL = "vowel"
    CONSONANT = "consonant"
    SILENCE = "silence"


# ARPAbet vowels
_VOWELS = {
    "AA", "AE", "AH", "AO", "AW", "AY",
    "EH", "ER", "EY",
    "IH", "IY",
    "OW", "OY",
    "UH", "UW",
}


def classify_phoneme(phoneme: str) -> PhonemeType:
    """Classify phoneme as VOWEL or CONSONANT.

    Uses ARPAbet phoneme set for classification.

    Args:
        phoneme: Phoneme text (e.g., "AH", "HH", "L")

    Returns:
        PhonemeType (VOWEL or CONSONANT)

    Example:
        >>> classify_phoneme("AH")
        <PhonemeType.VOWEL: 'vowel'>
        >>> classify_phoneme("HH")
        <PhonemeType.CONSONANT: 'consonant'>
    """
    # Normalize to uppercase
    phoneme_upper = phoneme.upper()

    # Check if vowel
    if phoneme_upper in _VOWELS:
        return PhonemeType.VOWEL

    # Default to consonant
    return PhonemeType.CONSONANT


def distribute_phonemes_uniform(
    phonemes: list[str],
    start_ms: int,
    end_ms: int,
) -> list[tuple[str, int, int]]:
    """Distribute word time window uniformly across phonemes.

    Each phoneme gets an equal portion of the word's duration.

    Args:
        phonemes: List of phonemes for the word
        start_ms: Word start time in milliseconds
        end_ms: Word end time in milliseconds

    Returns:
        List of (phoneme, start_ms, end_ms) tuples

    Example:
        >>> distribute_phonemes_uniform(["HH", "EH"], 0, 200)
        [('HH', 0, 100), ('EH', 100, 200)]
    """
    if not phonemes:
        return []

    duration_ms = end_ms - start_ms

    # Handle zero or negative duration
    if duration_ms <= 0:
        # All phonemes at start time with zero duration
        return [(p, start_ms, start_ms) for p in phonemes]

    # Calculate duration per phoneme
    duration_per_phoneme = duration_ms / len(phonemes)

    result: list[tuple[str, int, int]] = []
    current_time = start_ms

    for i, phoneme in enumerate(phonemes):
        # Calculate phoneme end time
        if i == len(phonemes) - 1:
            # Last phoneme: ensure it ends exactly at word end
            phoneme_end = end_ms
        else:
            # Round to nearest millisecond
            phoneme_end = int(current_time + duration_per_phoneme)

        result.append((phoneme, int(current_time), phoneme_end))
        current_time = phoneme_end

    return result
