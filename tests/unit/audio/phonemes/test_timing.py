"""Unit tests for phoneme timing distribution (Phase 6 Milestone 3).

Tests cover:
- distribute_phonemes_uniform() - uniform distribution
- PhonemeType enum
- Phoneme classification (vowel vs consonant)
"""

from blinkb0t.core.audio.phonemes.timing import (
    PhonemeType,
    classify_phoneme,
    distribute_phonemes_uniform,
)


class TestPhonemeType:
    """Test PhonemeType enum."""

    def test_enum_values(self):
        """PhonemeType should have expected values."""
        assert hasattr(PhonemeType, "VOWEL")
        assert hasattr(PhonemeType, "CONSONANT")
        assert hasattr(PhonemeType, "SILENCE")

    def test_string_values(self):
        """Enum values should be strings."""
        assert isinstance(PhonemeType.VOWEL.value, str)
        assert isinstance(PhonemeType.CONSONANT.value, str)
        assert isinstance(PhonemeType.SILENCE.value, str)


class TestClassifyPhoneme:
    """Test phoneme classification."""

    def test_vowels(self):
        """Vowels should be classified as VOWEL."""
        vowels = [
            "AA",
            "AE",
            "AH",
            "AO",
            "AW",
            "AY",
            "EH",
            "ER",
            "EY",
            "IH",
            "IY",
            "OW",
            "OY",
            "UH",
            "UW",
        ]

        for vowel in vowels:
            assert classify_phoneme(vowel) == PhonemeType.VOWEL, f"{vowel} should be VOWEL"

    def test_consonants(self):
        """Consonants should be classified as CONSONANT."""
        consonants = [
            "B",
            "CH",
            "D",
            "DH",
            "F",
            "G",
            "HH",
            "JH",
            "K",
            "L",
            "M",
            "N",
            "NG",
            "P",
            "R",
            "S",
            "SH",
            "T",
            "TH",
            "V",
            "W",
            "Y",
            "Z",
            "ZH",
        ]

        for consonant in consonants:
            assert classify_phoneme(consonant) == PhonemeType.CONSONANT, (
                f"{consonant} should be CONSONANT"
            )

    def test_unknown_phoneme(self):
        """Unknown phoneme should default to CONSONANT."""
        assert classify_phoneme("UNKNOWN") == PhonemeType.CONSONANT
        assert classify_phoneme("XYZ") == PhonemeType.CONSONANT

    def test_case_insensitive(self):
        """Classification should be case-insensitive."""
        assert classify_phoneme("aa") == PhonemeType.VOWEL
        assert classify_phoneme("AA") == PhonemeType.VOWEL
        assert classify_phoneme("Aa") == PhonemeType.VOWEL

    def test_empty_string(self):
        """Empty string should default to CONSONANT."""
        assert classify_phoneme("") == PhonemeType.CONSONANT


class TestDistributePhonemesUniform:
    """Test uniform phoneme distribution."""

    def test_distribute_single_phoneme(self):
        """Single phoneme should span entire word window."""
        phonemes = ["HH"]
        start_ms = 0
        end_ms = 100

        result = distribute_phonemes_uniform(phonemes, start_ms, end_ms)

        assert len(result) == 1
        assert result[0] == ("HH", 0, 100)

    def test_distribute_multiple_phonemes(self):
        """Multiple phonemes should divide window equally."""
        phonemes = ["HH", "EH", "L", "OW"]
        start_ms = 0
        end_ms = 400

        result = distribute_phonemes_uniform(phonemes, start_ms, end_ms)

        assert len(result) == 4
        # Each phoneme gets 100ms
        assert result[0] == ("HH", 0, 100)
        assert result[1] == ("EH", 100, 200)
        assert result[2] == ("L", 200, 300)
        assert result[3] == ("OW", 300, 400)

    def test_distribute_non_zero_start(self):
        """Distribution should work with non-zero start time."""
        phonemes = ["HH", "EH"]
        start_ms = 1000
        end_ms = 1200

        result = distribute_phonemes_uniform(phonemes, start_ms, end_ms)

        assert len(result) == 2
        assert result[0] == ("HH", 1000, 1100)
        assert result[1] == ("EH", 1100, 1200)

    def test_distribute_fractional_division(self):
        """Should handle fractional divisions correctly."""
        phonemes = ["A", "B", "C"]
        start_ms = 0
        end_ms = 100

        result = distribute_phonemes_uniform(phonemes, start_ms, end_ms)

        assert len(result) == 3
        # Each phoneme gets ~33.33ms, rounded appropriately
        assert result[0][0] == "A"
        assert result[0][1] == 0
        assert result[0][2] <= 34  # ~33.33ms

        assert result[2][0] == "C"
        assert result[2][2] == 100  # Last phoneme ends at word end

    def test_empty_phonemes(self):
        """Empty phonemes list should return empty list."""
        result = distribute_phonemes_uniform([], 0, 100)

        assert result == []

    def test_zero_duration(self):
        """Zero duration should return phonemes with zero-length spans."""
        phonemes = ["HH", "EH"]
        start_ms = 100
        end_ms = 100

        result = distribute_phonemes_uniform(phonemes, start_ms, end_ms)

        assert len(result) == 2
        # All phonemes at same time
        assert result[0] == ("HH", 100, 100)
        assert result[1] == ("EH", 100, 100)

    def test_negative_duration(self):
        """Negative duration should handle gracefully."""
        phonemes = ["HH"]
        start_ms = 100
        end_ms = 50

        result = distribute_phonemes_uniform(phonemes, start_ms, end_ms)

        # Should return empty or handle edge case
        assert isinstance(result, list)

    def test_large_word_window(self):
        """Should handle large word windows."""
        phonemes = ["HH", "EH"]
        start_ms = 0
        end_ms = 10000

        result = distribute_phonemes_uniform(phonemes, start_ms, end_ms)

        assert len(result) == 2
        assert result[0] == ("HH", 0, 5000)
        assert result[1] == ("EH", 5000, 10000)

    def test_many_phonemes(self):
        """Should handle many phonemes."""
        phonemes = ["A"] * 100
        start_ms = 0
        end_ms = 1000

        result = distribute_phonemes_uniform(phonemes, start_ms, end_ms)

        assert len(result) == 100
        # Each phoneme gets 10ms
        assert result[0] == ("A", 0, 10)
        assert result[99][2] == 1000
