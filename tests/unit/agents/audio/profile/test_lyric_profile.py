"""Tests for LyricProfile model."""

from pydantic import ValidationError
import pytest


def test_lyric_profile_valid_full():
    """Test LyricProfile with all fields."""
    from twinklr.core.agents.audio.profile.models import LyricProfile

    profile = LyricProfile(
        has_plain_lyrics=True,
        has_timed_words=True,
        has_phonemes=True,
        lyric_confidence=0.95,
        phoneme_confidence=0.90,
        notes=["High quality lyrics", "Accurate phoneme timing"],
    )

    assert profile.has_plain_lyrics is True
    assert profile.has_timed_words is True
    assert profile.has_phonemes is True
    assert profile.lyric_confidence == 0.95
    assert profile.phoneme_confidence == 0.90
    assert len(profile.notes) == 2


def test_lyric_profile_minimal():
    """Test LyricProfile with minimal fields."""
    from twinklr.core.agents.audio.profile.models import LyricProfile

    profile = LyricProfile(
        has_plain_lyrics=False,
        has_timed_words=False,
        has_phonemes=False,
        lyric_confidence=0.0,
        phoneme_confidence=0.0,
    )

    assert profile.has_plain_lyrics is False
    assert profile.has_timed_words is False
    assert profile.has_phonemes is False
    assert profile.lyric_confidence == 0.0
    assert profile.phoneme_confidence == 0.0
    assert profile.notes == []


def test_lyric_profile_lyric_confidence_validation():
    """Test LyricProfile lyric_confidence must be in [0, 1]."""
    from twinklr.core.agents.audio.profile.models import LyricProfile

    # Valid
    LyricProfile(
        has_plain_lyrics=True,
        has_timed_words=False,
        has_phonemes=False,
        lyric_confidence=0.0,
        phoneme_confidence=0.0,
    )
    LyricProfile(
        has_plain_lyrics=True,
        has_timed_words=False,
        has_phonemes=False,
        lyric_confidence=1.0,
        phoneme_confidence=0.0,
    )

    # Invalid: < 0
    with pytest.raises(ValidationError):
        LyricProfile(
            has_plain_lyrics=True,
            has_timed_words=False,
            has_phonemes=False,
            lyric_confidence=-0.1,
            phoneme_confidence=0.0,
        )

    # Invalid: > 1
    with pytest.raises(ValidationError):
        LyricProfile(
            has_plain_lyrics=True,
            has_timed_words=False,
            has_phonemes=False,
            lyric_confidence=1.1,
            phoneme_confidence=0.0,
        )


def test_lyric_profile_phoneme_confidence_validation():
    """Test LyricProfile phoneme_confidence must be in [0, 1]."""
    from twinklr.core.agents.audio.profile.models import LyricProfile

    # Valid
    LyricProfile(
        has_plain_lyrics=False,
        has_timed_words=False,
        has_phonemes=True,
        lyric_confidence=0.0,
        phoneme_confidence=0.0,
    )
    LyricProfile(
        has_plain_lyrics=False,
        has_timed_words=False,
        has_phonemes=True,
        lyric_confidence=0.0,
        phoneme_confidence=1.0,
    )

    # Invalid: < 0
    with pytest.raises(ValidationError):
        LyricProfile(
            has_plain_lyrics=False,
            has_timed_words=False,
            has_phonemes=True,
            lyric_confidence=0.0,
            phoneme_confidence=-0.1,
        )

    # Invalid: > 1
    with pytest.raises(ValidationError):
        LyricProfile(
            has_plain_lyrics=False,
            has_timed_words=False,
            has_phonemes=True,
            lyric_confidence=0.0,
            phoneme_confidence=1.1,
        )


def test_lyric_profile_notes_optional():
    """Test LyricProfile notes field is optional."""
    from twinklr.core.agents.audio.profile.models import LyricProfile

    # Without notes
    profile1 = LyricProfile(
        has_plain_lyrics=True,
        has_timed_words=False,
        has_phonemes=False,
        lyric_confidence=0.8,
        phoneme_confidence=0.0,
    )
    assert profile1.notes == []

    # With notes
    profile2 = LyricProfile(
        has_plain_lyrics=True,
        has_timed_words=False,
        has_phonemes=False,
        lyric_confidence=0.8,
        phoneme_confidence=0.0,
        notes=["Some lyrics detected"],
    )
    assert len(profile2.notes) == 1


def test_lyric_profile_not_frozen():
    """Test LyricProfile is mutable."""
    from twinklr.core.agents.audio.profile.models import LyricProfile

    profile = LyricProfile(
        has_plain_lyrics=True,
        has_timed_words=False,
        has_phonemes=False,
        lyric_confidence=0.8,
        phoneme_confidence=0.0,
    )

    # Should be able to modify
    profile.lyric_confidence = 0.9
    assert profile.lyric_confidence == 0.9


def test_lyric_profile_extra_forbid():
    """Test LyricProfile forbids extra fields."""
    from twinklr.core.agents.audio.profile.models import LyricProfile

    with pytest.raises(ValidationError) as exc_info:
        LyricProfile(
            has_plain_lyrics=True,
            has_timed_words=False,
            has_phonemes=False,
            lyric_confidence=0.8,
            phoneme_confidence=0.0,
            extra="not allowed",
        )

    assert "extra" in str(exc_info.value).lower()


def test_lyric_profile_no_lyrics():
    """Test LyricProfile when no lyrics available."""
    from twinklr.core.agents.audio.profile.models import LyricProfile

    profile = LyricProfile(
        has_plain_lyrics=False,
        has_timed_words=False,
        has_phonemes=False,
        lyric_confidence=0.0,
        phoneme_confidence=0.0,
        notes=["Instrumental track"],
    )

    assert not profile.has_plain_lyrics
    assert not profile.has_timed_words
    assert not profile.has_phonemes
    assert profile.lyric_confidence == 0.0
    assert "Instrumental" in profile.notes[0]
