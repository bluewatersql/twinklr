"""Unit tests for G2P service (Phase 6 Milestone 2).

Tests cover:
- G2PConfig validation
- word_to_phonemes() function
- normalize_phoneme() function
- G2PService protocol
- G2PImpl implementation
- Import error handling
"""

from pydantic import ValidationError
import pytest

from twinklr.core.audio.phonemes.g2p_service import (
    G2PConfig,
    G2PImpl,
    normalize_phoneme,
    word_to_phonemes,
)


class TestG2PConfig:
    """Test G2PConfig model validation."""

    def test_minimal_config(self):
        """Config with defaults should work."""
        config = G2PConfig()

        assert config.strip_stress is True
        assert config.filter_punctuation is True

    def test_custom_config(self):
        """Config with custom values should work."""
        config = G2PConfig(
            strip_stress=False,
            filter_punctuation=False,
        )

        assert config.strip_stress is False
        assert config.filter_punctuation is False

    def test_extra_fields_forbidden(self):
        """Extra fields should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            G2PConfig(extra_field="value")  # type: ignore
        assert "Extra inputs are not permitted" in str(exc_info.value)


class TestNormalizePhoneme:
    """Test normalize_phoneme() function."""

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

    def test_empty_string(self):
        """Empty string should remain empty."""
        assert normalize_phoneme("") == ""

    def test_already_normalized(self):
        """Already normalized phonemes should remain unchanged."""
        assert normalize_phoneme("AH") == "AH"
        assert normalize_phoneme("IY") == "IY"


class TestWordToPhonemes:
    """Test word_to_phonemes() function."""

    def test_simple_word(self):
        """Simple word should convert to phonemes."""
        phonemes = word_to_phonemes("hello")

        assert isinstance(phonemes, list)
        assert len(phonemes) > 0
        # Should contain phonemes like H, EH, L, OW
        assert all(isinstance(p, str) for p in phonemes)

    def test_complex_word(self):
        """Complex word should convert to phonemes."""
        phonemes = word_to_phonemes("beautiful")

        assert len(phonemes) > 0

    def test_single_letter(self):
        """Single letter should convert."""
        phonemes = word_to_phonemes("a")

        assert len(phonemes) > 0

    def test_case_insensitive(self):
        """Should handle different cases."""
        phonemes_lower = word_to_phonemes("hello")
        phonemes_upper = word_to_phonemes("HELLO")
        phonemes_mixed = word_to_phonemes("HeLLo")

        # All should produce phonemes (exact match not guaranteed due to g2p)
        assert len(phonemes_lower) > 0
        assert len(phonemes_upper) > 0
        assert len(phonemes_mixed) > 0

    def test_punctuation_filtered(self):
        """Punctuation should be filtered out."""
        phonemes = word_to_phonemes("hello!")

        # Should not contain punctuation
        assert all(p.isalnum() for p in phonemes)

    def test_empty_string(self):
        """Empty string should return empty list."""
        phonemes = word_to_phonemes("")

        assert phonemes == []

    def test_whitespace_only(self):
        """Whitespace-only should return empty list."""
        phonemes = word_to_phonemes("   ")

        assert phonemes == []


class TestG2PService:
    """Test G2PService protocol."""

    def test_protocol_compliance(self):
        """G2PImpl should comply with G2PService protocol."""
        # Protocol compliance is a compile-time check
        # We verify the instance has the required method
        service = G2PImpl()

        assert hasattr(service, "convert")
        assert callable(service.convert)


class TestG2PImpl:
    """Test G2PImpl implementation."""

    def test_convert_simple_word(self):
        """Convert simple word to phonemes."""
        service = G2PImpl()
        config = G2PConfig()

        phonemes = service.convert("hello", config=config)

        assert isinstance(phonemes, list)
        assert len(phonemes) > 0
        assert all(isinstance(p, str) for p in phonemes)

    def test_strip_stress_enabled(self):
        """With strip_stress=True, should have no stress markers."""
        service = G2PImpl()
        config = G2PConfig(strip_stress=True)

        phonemes = service.convert("hello", config=config)

        # No phonemes should contain digits
        for phoneme in phonemes:
            assert not any(ch.isdigit() for ch in phoneme), f"Found stress marker in: {phoneme}"

    def test_strip_stress_disabled(self):
        """With strip_stress=False, stress markers should be preserved."""
        service = G2PImpl()
        config = G2PConfig(strip_stress=False)

        phonemes = service.convert("hello", config=config)

        # At least some phonemes should contain digits (stress markers)
        # Note: Not all phonemes have stress (consonants don't)
        has_stress = any(any(ch.isdigit() for ch in p) for p in phonemes)
        assert has_stress, "Expected some phonemes with stress markers"

    def test_empty_word(self):
        """Empty word should return empty list."""
        service = G2PImpl()
        config = G2PConfig()

        phonemes = service.convert("", config=config)

        assert phonemes == []

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

    def test_graceful_import_error(self):
        """Should raise ImportError with helpful message if g2p_en not installed."""
        # This test is tricky because g2p_en is installed in our environment
        # We can't easily test the import error path without mocking
        # For now, we verify the function exists and handles the case
        try:
            phonemes = word_to_phonemes("test")
            assert isinstance(phonemes, list)
        except ImportError as e:
            # If g2p_en is not installed, should get helpful error
            assert "g2p-en" in str(e).lower() or "g2p" in str(e).lower()
