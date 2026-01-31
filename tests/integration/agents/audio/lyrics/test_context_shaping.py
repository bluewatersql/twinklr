"""Integration tests for lyrics context shaping with real SongBundle."""

from tests.fixtures.audio_profile import load_need_a_favor_bundle
from twinklr.core.agents.audio.lyrics import context


def test_shape_lyrics_context_with_lyrics():
    """Test lyrics context shaping with real SongBundle."""
    bundle = load_need_a_favor_bundle()

    # Check if bundle has lyrics
    if bundle.lyrics is None or bundle.lyrics.text is None:
        import pytest

        pytest.skip("Bundle does not have lyrics")

    shaped = context.shape_lyrics_context(bundle)

    # Verify shaped context structure
    assert isinstance(shaped, dict)
    assert shaped["has_lyrics"] is True
    assert "text" in shaped
    assert "words" in shaped
    assert "phrases" in shaped
    assert "sections" in shaped
    assert "quality" in shaped
    assert "duration_ms" in shaped


def test_shaped_lyrics_context_has_correct_duration():
    """Test that shaped lyrics context preserves duration."""
    bundle = load_need_a_favor_bundle()

    if bundle.lyrics is None or bundle.lyrics.text is None:
        import pytest

        pytest.skip("Bundle does not have lyrics")

    shaped = context.shape_lyrics_context(bundle)

    assert shaped["duration_ms"] == bundle.timing.duration_ms
    assert 190000 < shaped["duration_ms"] < 200000  # ~197s


def test_shaped_lyrics_context_includes_words():
    """Test that shaped context includes word timing."""
    bundle = load_need_a_favor_bundle()

    if bundle.lyrics is None or bundle.lyrics.text is None:
        import pytest

        pytest.skip("Bundle does not have lyrics")

    shaped = context.shape_lyrics_context(bundle)

    assert "words" in shaped
    assert isinstance(shaped["words"], list)

    # Each word should have text, start_ms, end_ms
    if shaped["words"]:
        word = shaped["words"][0]
        assert "text" in word
        assert "start_ms" in word
        assert "end_ms" in word


def test_shaped_lyrics_context_includes_phrases():
    """Test that shaped context includes phrase timing."""
    bundle = load_need_a_favor_bundle()

    if bundle.lyrics is None or bundle.lyrics.text is None:
        import pytest

        pytest.skip("Bundle does not have lyrics")

    shaped = context.shape_lyrics_context(bundle)

    assert "phrases" in shaped
    assert isinstance(shaped["phrases"], list)

    # Each phrase should have text, start_ms, end_ms
    if shaped["phrases"]:
        phrase = shaped["phrases"][0]
        assert "text" in phrase
        assert "start_ms" in phrase
        assert "end_ms" in phrase


def test_shaped_lyrics_context_includes_sections():
    """Test that shaped context includes song structure sections."""
    bundle = load_need_a_favor_bundle()

    if bundle.lyrics is None or bundle.lyrics.text is None:
        import pytest

        pytest.skip("Bundle does not have lyrics")

    shaped = context.shape_lyrics_context(bundle)

    assert "sections" in shaped
    assert isinstance(shaped["sections"], list)

    # Each section should have section_id, name, start_ms, end_ms
    if shaped["sections"]:
        section = shaped["sections"][0]
        assert "section_id" in section
        assert "name" in section
        assert "start_ms" in section
        assert "end_ms" in section


def test_shaped_lyrics_context_includes_quality():
    """Test that shaped context includes quality metrics."""
    bundle = load_need_a_favor_bundle()

    if bundle.lyrics is None or bundle.lyrics.text is None:
        import pytest

        pytest.skip("Bundle does not have lyrics")

    shaped = context.shape_lyrics_context(bundle)

    assert "quality" in shaped
    assert isinstance(shaped["quality"], dict)
    assert "coverage_pct" in shaped["quality"]
    assert "source_confidence" in shaped["quality"]


def test_shaped_lyrics_context_handles_no_lyrics():
    """Test that context shaping handles missing lyrics gracefully."""
    from twinklr.core.audio.models import SongBundle, SongTiming

    # Create bundle without lyrics
    bundle = SongBundle(
        schema_version="3.0",
        audio_path="/fake/path.mp3",
        recording_id="test-no-lyrics",
        timing=SongTiming(sr=44100, hop_length=512, duration_s=180.0, duration_ms=180000),
        lyrics=None,
        features={},
    )

    shaped = context.shape_lyrics_context(bundle)

    assert shaped["has_lyrics"] is False
    assert "reason" in shaped
    assert shaped["reason"] == "No lyrics available"


def test_shaped_lyrics_context_is_compact():
    """Test that shaped context is reasonably sized."""
    import json

    bundle = load_need_a_favor_bundle()

    if bundle.lyrics is None or bundle.lyrics.text is None:
        import pytest

        pytest.skip("Bundle does not have lyrics")

    shaped = context.shape_lyrics_context(bundle)

    # Context should be under 100KB (even with full lyrics)
    shaped_size = len(json.dumps(shaped))
    assert shaped_size < 100_000, f"Context is {shaped_size} bytes (expected < 100KB)"
