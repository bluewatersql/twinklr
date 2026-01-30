"""Tests for AudioProfile agent fixtures."""

from tests.fixtures.audio_profile import load_need_a_favor_bundle
from twinklr.core.audio.models import SongBundle


def test_load_need_a_favor_bundle():
    """Test that Need A Favor fixture loads successfully."""
    bundle = load_need_a_favor_bundle()
    assert isinstance(bundle, SongBundle)


def test_need_a_favor_bundle_has_expected_properties():
    """Test that Need A Favor fixture has expected properties."""
    bundle = load_need_a_favor_bundle()

    # Basic properties
    assert bundle.audio_path.endswith("Need A Favor.mp3")
    assert bundle.recording_id is not None

    # Timing
    assert bundle.timing.duration_ms > 0
    assert 190000 < bundle.timing.duration_ms < 200000  # ~197s

    # Features
    assert bundle.features is not None


def test_need_a_favor_bundle_has_tempo():
    """Test that Need A Favor fixture has tempo data."""
    bundle = load_need_a_favor_bundle()
    assert "tempo_bpm" in bundle.features
    assert 150 < bundle.features["tempo_bpm"] < 160  # ~156 BPM


def test_need_a_favor_bundle_has_sections():
    """Test that Need A Favor fixture has section data."""
    bundle = load_need_a_favor_bundle()
    assert "structure" in bundle.features
    assert bundle.features["structure"] is not None


def test_need_a_favor_bundle_has_energy():
    """Test that Need A Favor fixture has energy data."""
    bundle = load_need_a_favor_bundle()
    assert "energy" in bundle.features
    assert bundle.features["energy"] is not None
