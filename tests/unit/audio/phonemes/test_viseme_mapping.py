"""Unit tests for viseme mapping (Phase 6 Milestone 4).

Tests cover:
- PHONEME_TO_VISEME mapping
- phoneme_to_viseme() function
- merge_adjacent_visemes() function
- apply_min_hold() function
"""

from twinklr.core.audio.models.phonemes import VisemeEvent
from twinklr.core.audio.phonemes.viseme_mapping import (
    PHONEME_TO_VISEME,
    apply_min_hold,
    merge_adjacent_visemes,
    phoneme_to_viseme,
)


class TestPhonemeToVisemeMapping:
    """Test PHONEME_TO_VISEME mapping."""

    def test_vowel_mappings(self):
        """Vowels should map to appropriate visemes."""
        # Open vowels
        assert PHONEME_TO_VISEME["AA"] in ["A", "O"]
        assert PHONEME_TO_VISEME["AH"] in ["A", "O"]

        # Front vowels
        assert PHONEME_TO_VISEME["IY"] in ["I", "E"]
        assert PHONEME_TO_VISEME["EH"] in ["E", "A"]

        # Rounded vowels
        assert PHONEME_TO_VISEME["OW"] in ["O", "U"]
        assert PHONEME_TO_VISEME["UW"] in ["U", "O"]

    def test_consonant_mappings(self):
        """Consonants should map to appropriate visemes."""
        # Bilabials
        assert PHONEME_TO_VISEME["P"] == "BMP"
        assert PHONEME_TO_VISEME["B"] == "BMP"
        assert PHONEME_TO_VISEME["M"] == "BMP"

        # Labiodentals
        assert PHONEME_TO_VISEME["F"] == "FV"
        assert PHONEME_TO_VISEME["V"] == "FV"

        # Dental
        assert PHONEME_TO_VISEME["TH"] == "TH"
        assert PHONEME_TO_VISEME["DH"] == "TH"

        # Alveolar lateral
        assert PHONEME_TO_VISEME["L"] == "L"


class TestPhonemeToViseme:
    """Test phoneme_to_viseme() function."""

    def test_convert_vowel(self):
        """Vowels should convert to appropriate visemes."""
        assert phoneme_to_viseme("AA") in ["A", "O"]
        assert phoneme_to_viseme("IY") in ["I", "E"]
        assert phoneme_to_viseme("OW") in ["O", "U"]

    def test_convert_consonant(self):
        """Consonants should convert to appropriate visemes."""
        assert phoneme_to_viseme("B") == "BMP"
        assert phoneme_to_viseme("F") == "FV"
        assert phoneme_to_viseme("L") == "L"

    def test_strip_stress_markers(self):
        """Stress markers should be stripped before lookup."""
        assert phoneme_to_viseme("AH0") == phoneme_to_viseme("AH")
        assert phoneme_to_viseme("IY1") == phoneme_to_viseme("IY")
        assert phoneme_to_viseme("EH2") == phoneme_to_viseme("EH")

    def test_merge_identical_adjacent(self):
        """Adjacent identical visemes should merge."""
        events = [
            VisemeEvent(viseme="A", start_ms=0, end_ms=100),
            VisemeEvent(viseme="A", start_ms=100, end_ms=200),
            VisemeEvent(viseme="A", start_ms=200, end_ms=300),
        ]

        result = merge_adjacent_visemes(events)

        assert len(result) == 1
        assert result[0].viseme == "A"
        assert result[0].start_ms == 0
        assert result[0].end_ms == 300

    def test_dont_merge_different_visemes(self):
        """Different visemes should not merge."""
        events = [
            VisemeEvent(viseme="A", start_ms=0, end_ms=100),
            VisemeEvent(viseme="E", start_ms=100, end_ms=200),
            VisemeEvent(viseme="I", start_ms=200, end_ms=300),
        ]

        result = merge_adjacent_visemes(events)

        assert len(result) == 3
        assert result[0].viseme == "A"
        assert result[1].viseme == "E"
        assert result[2].viseme == "I"

    def test_merge_with_small_gap(self):
        """Adjacent visemes with small gap should merge."""
        events = [
            VisemeEvent(viseme="A", start_ms=0, end_ms=100),
            VisemeEvent(viseme="A", start_ms=105, end_ms=200),  # 5ms gap
        ]

        # Default threshold is 20ms
        result = merge_adjacent_visemes(events, max_gap_ms=20)

        assert len(result) == 1
        assert result[0].start_ms == 0
        assert result[0].end_ms == 200

    def test_dont_merge_large_gap(self):
        """Adjacent visemes with large gap should not merge."""
        events = [
            VisemeEvent(viseme="A", start_ms=0, end_ms=100),
            VisemeEvent(viseme="A", start_ms=150, end_ms=200),  # 50ms gap
        ]

        # Max gap is 20ms
        result = merge_adjacent_visemes(events, max_gap_ms=20)

        assert len(result) == 2

    def test_extend_short_events(self):
        """Events shorter than min_hold should be extended."""
        events = [
            VisemeEvent(viseme="A", start_ms=0, end_ms=30),  # 30ms < 50ms
            VisemeEvent(viseme="E", start_ms=30, end_ms=100),  # Long enough
        ]

        result = apply_min_hold(events, min_hold_ms=50)

        # First event extended to 50ms
        assert result[0].end_ms == 50
        # Second event starts later
        assert result[1].start_ms == 50
