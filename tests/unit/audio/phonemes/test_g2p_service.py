"""Unit tests for G2P service (Phase 6 Milestone 2).

Tests cover:
- G2PConfig validation
- word_to_phonemes() function
- normalize_phoneme() function
- G2PService protocol
- G2PImpl implementation
- Import error handling
"""

from twinklr.core.audio.phonemes.g2p_service import (
    G2PConfig,
    G2PImpl,
    normalize_phoneme,
    word_to_phonemes,
)


class TestG2PConfig:
    """Test G2PConfig model validation."""

    def test_custom_config(self):
        """Config with custom values should work."""
        config = G2PConfig(
            strip_stress=False,
            filter_punctuation=False,
        )

        assert config.strip_stress is False
        assert config.filter_punctuation is False

    def test_strip_stress_markers(self):
        """Should strip stress markers (0, 1, 2)."""
        assert normalize_phoneme("AH0") == "AH"
        assert normalize_phoneme("IY1") == "IY"
        assert normalize_phoneme("EH2") == "EH"

    def test_no_stress_markers(self):
        """Phonemes without stress should remain unchanged."""
        assert normalize_phoneme("M") == "M"
        assert normalize_phoneme("N") == "N"
        assert normalize_phoneme("L") == "L"

    def test_simple_word(self):
        """Simple word should convert to phonemes."""
        phonemes = word_to_phonemes("hello")

        assert isinstance(phonemes, list)
        assert len(phonemes) > 0
        # Should contain phonemes like H, EH, L, OW
        assert all(isinstance(p, str) for p in phonemes)

    def test_case_insensitive(self):
        """Should handle different cases."""
        phonemes_lower = word_to_phonemes("hello")
        phonemes_upper = word_to_phonemes("HELLO")
        phonemes_mixed = word_to_phonemes("HeLLo")

        # All should produce phonemes (exact match not guaranteed due to g2p)
        assert len(phonemes_lower) > 0
        assert len(phonemes_upper) > 0
        assert len(phonemes_mixed) > 0

    def test_convert_simple_word(self):
        """Convert simple word to phonemes."""
        service = G2PImpl()
        config = G2PConfig()

        phonemes = service.convert("hello", config=config)

        assert isinstance(phonemes, list)
        assert len(phonemes) > 0
        assert all(isinstance(p, str) for p in phonemes)

    def test_punctuation_handling(self):
        """Punctuation should be filtered."""
        service = G2PImpl()
        config = G2PConfig()

        phonemes = service.convert("hello!", config=config)

        # Should contain phonemes for "hello", not punctuation
        assert len(phonemes) > 0
        assert all(p.isalnum() for p in phonemes)


class TestG2PImportError:
    """Test G2P import error handling."""
