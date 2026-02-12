"""Unit tests for phoneme timing distribution (Phase 6 Milestone 3).

Tests cover:
- distribute_phonemes_uniform() - uniform distribution
- distribute_word_window_to_phonemes() - weighted distribution (spec)
- PhonemeType enum
- Phoneme classification (vowel vs consonant)
"""

from twinklr.core.audio.phonemes.timing import (
    PhonemeType,
    classify_phoneme,
    distribute_phonemes_uniform,
    distribute_word_window_to_phonemes,
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

    def test_case_insensitive(self):
        """Classification should be case-insensitive."""
        assert classify_phoneme("aa") == PhonemeType.VOWEL
        assert classify_phoneme("AA") == PhonemeType.VOWEL
        assert classify_phoneme("Aa") == PhonemeType.VOWEL

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


class TestDistributeWordWindowToPhonemes:
    """Test weighted phoneme distribution per spec."""

    def test_vowels_get_more_time(self):
        """Vowels should get proportionally more time than consonants."""
        # HH=consonant, EH=vowel, L=consonant, OW=vowel
        result = distribute_word_window_to_phonemes(
            word_start_ms=0,
            word_end_ms=600,
            phonemes=["HH", "EH", "L", "OW"],
            vowel_weight=2.0,
            consonant_weight=1.0,
        )

        assert len(result) == 4
        # Weights: 1 + 2 + 1 + 2 = 6, duration=600
        # HH gets 100ms, EH gets 200ms, L gets 100ms, OW gets 200ms
        hh_dur = result[0][2] - result[0][1]
        eh_dur = result[1][2] - result[1][1]
        l_dur = result[2][2] - result[2][1]
        ow_dur = result[3][2] - result[3][1]

        assert eh_dur > hh_dur, "Vowel EH should get more time than consonant HH"
        assert ow_dur > l_dur, "Vowel OW should get more time than consonant L"
        assert result[-1][2] == 600, "Final end must equal word_end_ms"

    def test_monotonic_windows(self):
        """Phoneme windows should be monotonically increasing with no gaps."""
        result = distribute_word_window_to_phonemes(
            word_start_ms=1000,
            word_end_ms=1500,
            phonemes=["B", "AE", "T"],
            vowel_weight=2.0,
            consonant_weight=1.0,
        )

        assert result[0][1] == 1000, "First phoneme starts at word_start_ms"
        for i in range(1, len(result)):
            assert result[i][1] == result[i - 1][2], "No gaps between phonemes"
        assert result[-1][2] == 1500, "Last phoneme ends at word_end_ms"

    def test_short_word_collapses_to_single(self):
        """Words shorter than min_phoneme_ms should collapse to single span."""
        result = distribute_word_window_to_phonemes(
            word_start_ms=0,
            word_end_ms=50,
            phonemes=["HH", "EH", "L", "OW"],
            min_phoneme_ms=80,
            vowel_weight=2.0,
            consonant_weight=1.0,
        )

        # Duration 50ms < 80ms min → collapse
        assert len(result) == 1
        assert result[0] == ("HH", 0, 50)

    def test_empty_phonemes(self):
        """Empty phoneme list should return empty."""
        result = distribute_word_window_to_phonemes(
            word_start_ms=0,
            word_end_ms=500,
            phonemes=[],
            vowel_weight=2.0,
            consonant_weight=1.0,
        )

        assert result == []

    def test_single_phoneme(self):
        """Single phoneme should span entire word window."""
        result = distribute_word_window_to_phonemes(
            word_start_ms=100,
            word_end_ms=300,
            phonemes=["AH"],
            vowel_weight=2.0,
            consonant_weight=1.0,
        )

        assert len(result) == 1
        assert result[0] == ("AH", 100, 300)

    def test_leftover_goes_to_earliest(self):
        """Leftover ms from floor division should go to earliest phonemes."""
        # 3 consonants at weight 1.0 each, 100ms total
        # floor(100/3) = 33ms each, 1ms leftover
        result = distribute_word_window_to_phonemes(
            word_start_ms=0,
            word_end_ms=100,
            phonemes=["B", "D", "G"],
            vowel_weight=2.0,
            consonant_weight=1.0,
        )

        assert len(result) == 3
        total_dur = sum(r[2] - r[1] for r in result)
        assert total_dur == 100, "Total must equal word duration"
        assert result[-1][2] == 100, "Final end must equal word_end_ms"
        # First phoneme gets the leftover
        first_dur = result[0][2] - result[0][1]
        last_dur = result[2][2] - result[2][1]
        assert first_dur >= last_dur

    def test_equal_weights_like_uniform(self):
        """Equal weights should produce near-uniform distribution."""
        result = distribute_word_window_to_phonemes(
            word_start_ms=0,
            word_end_ms=400,
            phonemes=["B", "D", "G", "K"],
            vowel_weight=1.0,
            consonant_weight=1.0,
        )

        assert len(result) == 4
        for _i, (_phoneme, start, end) in enumerate(result):
            dur = end - start
            assert dur == 100, f"With equal weights, each should get 100ms, got {dur}"
