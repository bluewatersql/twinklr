"""Unit tests for phoneme models (Phase 6 Milestone 1).

Tests cover:
- Phoneme model validation
- VisemeEvent model validation
- PhonemeBundle structure
- PhonemeSource enum
"""

from pydantic import ValidationError
import pytest

from twinklr.core.audio.models.phonemes import (
    Phoneme,
    PhonemeBundle,
    PhonemeSource,
    VisemeEvent,
)


class TestPhoneme:
    """Test Phoneme model validation."""

    def test_valid_phoneme(self):
        """Valid phoneme with timing should work."""
        phoneme = Phoneme(
            text="AH0",
            start_ms=0,
            end_ms=100,
        )

        assert phoneme.text == "AH0"
        assert phoneme.start_ms == 0
        assert phoneme.end_ms == 100

    def test_phoneme_with_type(self):
        """Phoneme with phoneme_type should work."""
        phoneme = Phoneme(
            text="IY1",
            start_ms=100,
            end_ms=250,
            phoneme_type="VOWEL",
        )

        assert phoneme.phoneme_type == "VOWEL"

    def test_timing_validation(self):
        """Start/end times must be non-negative."""
        # Valid
        phoneme = Phoneme(text="AH0", start_ms=0, end_ms=100)
        assert phoneme.start_ms == 0

        # Invalid start
        with pytest.raises(ValidationError) as exc_info:
            Phoneme(text="AH0", start_ms=-100, end_ms=100)
        assert "greater than or equal to 0" in str(exc_info.value)

        # Invalid end
        with pytest.raises(ValidationError) as exc_info:
            Phoneme(text="AH0", start_ms=0, end_ms=-1)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_text_required(self):
        """Phoneme text is required."""
        with pytest.raises(ValidationError) as exc_info:
            Phoneme(start_ms=0, end_ms=100)  # type: ignore
        assert "Field required" in str(exc_info.value)

    def test_extra_fields_forbidden(self):
        """Extra fields should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Phoneme(
                text="AH0",
                start_ms=0,
                end_ms=100,
                extra_field="value",  # type: ignore
            )
        assert "Extra inputs are not permitted" in str(exc_info.value)


class TestVisemeEvent:
    """Test VisemeEvent model validation."""

    def test_valid_viseme_event(self):
        """Valid viseme event should work."""
        event = VisemeEvent(
            viseme="A",
            start_ms=0,
            end_ms=150,
            confidence=0.8,
        )

        assert event.viseme == "A"
        assert event.start_ms == 0
        assert event.end_ms == 150
        assert event.confidence == 0.8

    def test_viseme_codes(self):
        """Various viseme codes should work."""
        codes = ["A", "E", "I", "O", "U", "BMP", "FV", "TH", "L", "REST"]
        for code in codes:
            event = VisemeEvent(viseme=code, start_ms=0, end_ms=100)
            assert event.viseme == code

    def test_confidence_validation(self):
        """Confidence must be 0-1."""
        # Valid
        event = VisemeEvent(viseme="A", start_ms=0, end_ms=100, confidence=0.5)
        assert event.confidence == 0.5

        # Invalid
        with pytest.raises(ValidationError) as exc_info:
            VisemeEvent(viseme="A", start_ms=0, end_ms=100, confidence=1.5)
        assert "less than or equal to 1" in str(exc_info.value)

    def test_default_confidence(self):
        """Confidence defaults to 1.0."""
        event = VisemeEvent(viseme="A", start_ms=0, end_ms=100)
        assert event.confidence == 1.0

    def test_timing_validation(self):
        """Start/end times must be non-negative."""
        # Valid
        event = VisemeEvent(viseme="A", start_ms=0, end_ms=100)
        assert event.start_ms == 0

        # Invalid
        with pytest.raises(ValidationError) as exc_info:
            VisemeEvent(viseme="A", start_ms=-10, end_ms=100)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_extra_fields_forbidden(self):
        """Extra fields should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VisemeEvent(
                viseme="A",
                start_ms=0,
                end_ms=100,
                extra_field="value",  # type: ignore
            )
        assert "Extra inputs are not permitted" in str(exc_info.value)


class TestPhonemeSource:
    """Test PhonemeSource enum."""

    def test_enum_values(self):
        """PhonemeSource should have expected values."""
        assert hasattr(PhonemeSource, "G2P")
        assert hasattr(PhonemeSource, "CMUDICT")
        assert hasattr(PhonemeSource, "ALLOSAURUS")

    def test_string_values(self):
        """Enum values should be strings."""
        assert isinstance(PhonemeSource.G2P.value, str)
        assert isinstance(PhonemeSource.CMUDICT.value, str)


class TestPhonemeBundle:
    """Test PhonemeBundle model."""

    def test_minimal_bundle(self):
        """Bundle with just phonemes should work."""
        phonemes = [
            Phoneme(text="HH", start_ms=0, end_ms=50),
            Phoneme(text="EH1", start_ms=50, end_ms=150),
            Phoneme(text="L", start_ms=150, end_ms=200),
            Phoneme(text="OW0", start_ms=200, end_ms=300),
        ]

        bundle = PhonemeBundle(
            phonemes=phonemes,
            source=PhonemeSource.G2P,
        )

        assert len(bundle.phonemes) == 4
        assert bundle.source == PhonemeSource.G2P
        assert bundle.visemes == []
        assert bundle.metadata == {}

    def test_bundle_with_visemes(self):
        """Bundle with phonemes and visemes should work."""
        phonemes = [
            Phoneme(text="HH", start_ms=0, end_ms=50),
            Phoneme(text="EH1", start_ms=50, end_ms=150),
        ]
        visemes = [
            VisemeEvent(viseme="H", start_ms=0, end_ms=50, confidence=0.9),
            VisemeEvent(viseme="E", start_ms=50, end_ms=150, confidence=0.9),
        ]

        bundle = PhonemeBundle(
            phonemes=phonemes,
            visemes=visemes,
            source=PhonemeSource.G2P,
        )

        assert len(bundle.phonemes) == 2
        assert len(bundle.visemes) == 2
        assert bundle.visemes[0].viseme == "H"

    def test_bundle_with_metadata(self):
        """Bundle with metadata should work."""
        bundle = PhonemeBundle(
            phonemes=[],
            source=PhonemeSource.G2P,
            metadata={
                "model": "g2p_en",
                "timing_strategy": "uniform",
                "min_hold_ms": 50,
            },
        )

        assert bundle.metadata["model"] == "g2p_en"
        assert bundle.metadata["timing_strategy"] == "uniform"

    def test_empty_phonemes(self):
        """Bundle can have empty phonemes (e.g., no lyrics)."""
        bundle = PhonemeBundle(
            phonemes=[],
            source=PhonemeSource.G2P,
        )

        assert len(bundle.phonemes) == 0

    def test_source_required(self):
        """Source is required."""
        with pytest.raises(ValidationError) as exc_info:
            PhonemeBundle(phonemes=[])  # type: ignore
        assert "Field required" in str(exc_info.value)

    def test_extra_fields_forbidden(self):
        """Extra fields should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PhonemeBundle(
                phonemes=[],
                source=PhonemeSource.G2P,
                extra_field="value",  # type: ignore
            )
        assert "Extra inputs are not permitted" in str(exc_info.value)
