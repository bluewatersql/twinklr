"""Tests for SongIdentity model."""

from pydantic import ValidationError
import pytest


def test_song_identity_full():
    """Test SongIdentity with all fields."""
    from twinklr.core.agents.audio.profile.models import SongIdentity

    identity = SongIdentity(
        title="Test Song",
        artist="Test Artist",
        duration_ms=180000,  # 3 minutes
        bpm=120.0,
        key="C major",
        time_signature="4/4",
    )

    assert identity.title == "Test Song"
    assert identity.artist == "Test Artist"
    assert identity.duration_ms == 180000
    assert identity.bpm == 120.0
    assert identity.key == "C major"
    assert identity.time_signature == "4/4"


def test_song_identity_minimal():
    """Test SongIdentity with only required fields."""
    from twinklr.core.agents.audio.profile.models import SongIdentity

    identity = SongIdentity(duration_ms=180000)

    assert identity.title is None
    assert identity.artist is None
    assert identity.duration_ms == 180000
    assert identity.bpm is None
    assert identity.key is None
    assert identity.time_signature is None


def test_song_identity_duration_validation_too_short():
    """Test SongIdentity rejects duration < 1 second."""
    from twinklr.core.agents.audio.profile.models import SongIdentity

    with pytest.raises(ValidationError) as exc_info:
        SongIdentity(duration_ms=500)  # 0.5 seconds

    assert "duration too short" in str(exc_info.value).lower()


def test_song_identity_duration_validation_too_long():
    """Test SongIdentity rejects duration > 30 minutes."""
    from twinklr.core.agents.audio.profile.models import SongIdentity

    with pytest.raises(ValidationError) as exc_info:
        SongIdentity(duration_ms=1900000)  # 31.67 minutes

    assert "duration too long" in str(exc_info.value).lower()


def test_song_identity_duration_validation_valid_bounds():
    """Test SongIdentity accepts valid duration boundaries."""
    from twinklr.core.agents.audio.profile.models import SongIdentity

    # 1 second (minimum)
    identity1 = SongIdentity(duration_ms=1000)
    assert identity1.duration_ms == 1000

    # 30 minutes (maximum)
    identity2 = SongIdentity(duration_ms=1800000)
    assert identity2.duration_ms == 1800000


def test_song_identity_duration_must_be_positive():
    """Test SongIdentity duration must be > 0."""
    from twinklr.core.agents.audio.profile.models import SongIdentity

    with pytest.raises(ValidationError):
        SongIdentity(duration_ms=0)

    with pytest.raises(ValidationError):
        SongIdentity(duration_ms=-1000)


def test_song_identity_bpm_validation():
    """Test SongIdentity BPM validation."""
    from twinklr.core.agents.audio.profile.models import SongIdentity

    # Valid BPM
    identity = SongIdentity(duration_ms=180000, bpm=120.0)
    assert identity.bpm == 120.0

    # BPM must be > 0
    with pytest.raises(ValidationError):
        SongIdentity(duration_ms=180000, bpm=0)

    with pytest.raises(ValidationError):
        SongIdentity(duration_ms=180000, bpm=-60)

    # BPM must be < 300
    with pytest.raises(ValidationError):
        SongIdentity(duration_ms=180000, bpm=300)

    with pytest.raises(ValidationError):
        SongIdentity(duration_ms=180000, bpm=350)


def test_song_identity_bpm_boundaries():
    """Test SongIdentity BPM boundary values."""
    from twinklr.core.agents.audio.profile.models import SongIdentity

    # Just above 0
    identity1 = SongIdentity(duration_ms=180000, bpm=0.1)
    assert identity1.bpm == 0.1

    # Just below 300
    identity2 = SongIdentity(duration_ms=180000, bpm=299.9)
    assert identity2.bpm == 299.9


def test_song_identity_extra_forbid():
    """Test SongIdentity forbids extra fields."""
    from twinklr.core.agents.audio.profile.models import SongIdentity

    with pytest.raises(ValidationError) as exc_info:
        SongIdentity(duration_ms=180000, extra_field="not allowed")

    assert "extra_field" in str(exc_info.value).lower()


def test_song_identity_not_frozen():
    """Test SongIdentity is mutable (not frozen)."""
    from twinklr.core.agents.audio.profile.models import SongIdentity

    identity = SongIdentity(duration_ms=180000, title="Original")

    # Should be able to modify
    identity.title = "Modified"
    assert identity.title == "Modified"


def test_song_identity_common_keys():
    """Test SongIdentity with common musical keys."""
    from twinklr.core.agents.audio.profile.models import SongIdentity

    keys = [
        "C major",
        "A minor",
        "G major",
        "E minor",
        "D major",
        "B minor",
        "F# major",
        "Eb minor",
    ]

    for key in keys:
        identity = SongIdentity(duration_ms=180000, key=key)
        assert identity.key == key


def test_song_identity_common_time_signatures():
    """Test SongIdentity with common time signatures."""
    from twinklr.core.agents.audio.profile.models import SongIdentity

    signatures = ["4/4", "3/4", "6/8", "2/4", "5/4", "7/8", "12/8"]

    for sig in signatures:
        identity = SongIdentity(duration_ms=180000, time_signature=sig)
        assert identity.time_signature == sig
