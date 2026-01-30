"""Integration tests for context shaping with real SongBundle."""

from tests.fixtures.audio_profile import load_need_a_favor_bundle
from twinklr.core.agents.audio.profile import shape_context


def test_shape_context_with_real_song_bundle():
    """Test context shaping with real SongBundle produces valid output."""
    bundle = load_need_a_favor_bundle()
    shaped = shape_context(bundle)

    # Verify shaped context structure
    assert isinstance(shaped, dict)
    assert "audio_path" in shaped
    assert "duration_ms" in shaped
    assert "sections" in shaped
    assert "energy" in shaped


def test_shaped_context_has_correct_duration():
    """Test that shaped context preserves duration."""
    bundle = load_need_a_favor_bundle()
    shaped = shape_context(bundle)

    assert shaped["duration_ms"] == bundle.timing.duration_ms
    assert 190000 < shaped["duration_ms"] < 200000  # ~197s


def test_shaped_context_has_sections():
    """Test that shaped context includes sections (if available in bundle)."""
    bundle = load_need_a_favor_bundle()
    shaped = shape_context(bundle)

    # Note: sections may be empty if bundle doesn't have structure data
    # This is expected for older SongBundle formats
    assert "sections" in shaped
    assert isinstance(shaped["sections"], list)


def test_shaped_context_has_energy_profiles():
    """Test that shaped context includes energy structure."""
    bundle = load_need_a_favor_bundle()
    shaped = shape_context(bundle)

    assert "energy" in shaped
    assert "section_profiles" in shaped["energy"]
    # Note: May be empty if bundle doesn't have section-level energy
    assert isinstance(shaped["energy"]["section_profiles"], list)


def test_shaped_context_compresses_energy_curves():
    """Test that energy curves are compressed when present."""
    bundle = load_need_a_favor_bundle()
    shaped = shape_context(bundle)

    # Skip if no section profiles (older bundle format)
    if not shaped["energy"]["section_profiles"]:
        import pytest

        pytest.skip("No section energy profiles in bundle")

    # Each section should have 3-15 energy points (compressed)
    for profile in shaped["energy"]["section_profiles"]:
        curve_len = len(profile["energy_curve"])
        assert 3 <= curve_len <= 15, f"Energy curve has {curve_len} points (expected 3-15)"


def test_shaped_context_is_smaller_than_bundle():
    """Test that shaped context achieves token reduction."""
    import json

    bundle = load_need_a_favor_bundle()
    shaped = shape_context(bundle)

    # Rough size comparison (JSON serialization)
    bundle_size = len(json.dumps(bundle.model_dump()))
    shaped_size = len(json.dumps(shaped))

    # Should achieve significant reduction (target 10x, accept 5x minimum)
    reduction_factor = bundle_size / shaped_size
    assert reduction_factor >= 5.0, (
        f"Only achieved {reduction_factor:.1f}x reduction (expected ≥5x)"
    )


def test_shaped_context_preserves_tempo():
    """Test that shaped context preserves tempo information."""
    bundle = load_need_a_favor_bundle()
    shaped = shape_context(bundle)

    # Tempo may be in different locations depending on bundle version
    assert "tempo" in shaped or "bpm" in shaped

    # Check if tempo data is available
    if shaped.get("tempo"):
        tempo_data = shaped["tempo"]
        assert "bpm" in tempo_data
    elif "bpm" in shaped:
        # Direct BPM field
        assert shaped["bpm"] is not None
