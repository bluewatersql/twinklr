"""Tests for context shaping (SongBundle → shaped context)."""


def test_shape_context_basic():
    """Test basic context shaping from SongBundle."""
    from twinklr.core.agents.audio.profile.context import shape_context
    from twinklr.core.audio.models import SongBundle, SongTiming

    bundle = SongBundle(
        schema_version="3.0",
        audio_path="/test/song.mp3",
        recording_id="test_123",
        features={
            "duration_ms": 60000,
            "tempo": {"bpm": 120.0, "confidence": 0.95, "time_signature": "4/4"},
            "key": {"key": "C", "mode": "major", "confidence": 0.85},
            "sections": [
                {"type": "verse", "start_ms": 0, "end_ms": 30000, "confidence": 0.9},
                {"type": "chorus", "start_ms": 30000, "end_ms": 60000, "confidence": 0.9},
            ],
            "energy": {
                "overall": 0.7,
                "curve": [{"t_ms": i * 1000, "energy": 0.7} for i in range(60)],
                "peaks": [{"start_ms": 25000, "end_ms": 30000, "energy": 0.9}],
            },
        },
        timing=SongTiming(sr=22050, hop_length=512, duration_s=60.0, duration_ms=60000),
    )

    context = shape_context(bundle)

    # Verify structure
    assert "audio_path" in context
    assert "duration_ms" in context
    assert "tempo" in context
    assert "key" in context
    assert "sections" in context
    assert "energy" in context
    assert "lyrics" in context

    # Verify values
    assert context["duration_ms"] == 60000
    assert context["tempo"]["bpm"] == 120.0
    assert context["key"]["key"] == "C"
    assert len(context["sections"]) == 2


def test_shape_context_energy_compression():
    """Test energy curve is compressed per-section."""
    from twinklr.core.agents.audio.profile.context import shape_context
    from twinklr.core.audio.models import SongBundle, SongTiming

    # Create bundle with large energy curve
    bundle = SongBundle(
        schema_version="3.0",
        audio_path="/test/song.mp3",
        recording_id="test_123",
        features={
            "duration_ms": 60000,
            "tempo": {"bpm": 120.0, "confidence": 0.95},
            "sections": [
                {"type": "verse", "start_ms": 0, "end_ms": 30000},
                {"type": "chorus", "start_ms": 30000, "end_ms": 60000},
            ],
            "energy": {
                "overall": 0.7,
                "curve": [{"t_ms": i * 100, "energy": 0.5 + (i % 10) * 0.05} for i in range(600)],
            },
        },
        timing=SongTiming(sr=22050, hop_length=512, duration_s=60.0, duration_ms=60000),
    )

    context = shape_context(bundle)

    # Energy should have per-section profiles
    assert "section_profiles" in context["energy"]
    profiles = context["energy"]["section_profiles"]

    # Should have 2 profiles (one per section)
    assert len(profiles) == 2

    # Each profile should have compressed curve
    for profile in profiles:
        assert "section_id" in profile
        assert "energy_curve" in profile
        # Curve should be compressed (3-15 points per spec)
        assert 3 <= len(profile["energy_curve"]) <= 15


def test_shape_context_lyrics_metadata_only():
    """Test lyrics are metadata-only (no full text)."""
    from twinklr.core.agents.audio.profile.context import shape_context
    from twinklr.core.audio.models import LyricsBundle, LyricsSource, SongBundle, SongTiming
    from twinklr.core.audio.models.enums import StageStatus

    bundle = SongBundle(
        schema_version="3.0",
        audio_path="/test/song.mp3",
        recording_id="test_123",
        features={"duration_ms": 60000, "sections": []},
        timing=SongTiming(sr=22050, hop_length=512, duration_s=60.0, duration_ms=60000),
        lyrics=LyricsBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.OK,
            text="This is a long song with many lyrics...",
            words=[],  # Word-level timing
            source=LyricsSource(
                kind="LOOKUP_SYNCED",
                provider="lrclib",
                confidence=0.95,
            ),
        ),
    )

    context = shape_context(bundle)

    # Lyrics should be metadata only
    assert context["lyrics"]["has_plain_lyrics"] is True
    assert context["lyrics"]["lyric_confidence"] == 0.95
    assert context["lyrics"]["has_timed_words"] is False  # No word-level timing in this test

    # Should NOT include full text
    assert "text" not in context["lyrics"]
    assert "words" not in context["lyrics"]


def test_shape_context_no_lyrics():
    """Test context shaping when no lyrics available."""
    from twinklr.core.agents.audio.profile.context import shape_context
    from twinklr.core.audio.models import SongBundle, SongTiming

    bundle = SongBundle(
        schema_version="3.0",
        audio_path="/test/song.mp3",
        recording_id="test_123",
        features={"duration_ms": 60000, "sections": []},
        timing=SongTiming(sr=22050, hop_length=512, duration_s=60.0, duration_ms=60000),
        lyrics=None,
    )

    context = shape_context(bundle)

    # Lyrics should indicate unavailable
    assert context["lyrics"]["has_plain_lyrics"] is False
    assert context["lyrics"]["has_timed_words"] is False
    assert context["lyrics"]["lyric_confidence"] == 0.0


def test_shape_context_returns_dict():
    """Test shape_context returns a dictionary."""
    from twinklr.core.agents.audio.profile.context import shape_context
    from twinklr.core.audio.models import SongBundle, SongTiming

    bundle = SongBundle(
        schema_version="3.0",
        audio_path="/test/song.mp3",
        recording_id="test_123",
        features={"duration_ms": 60000, "sections": []},
        timing=SongTiming(sr=22050, hop_length=512, duration_s=60.0, duration_ms=60000),
    )

    context = shape_context(bundle)

    assert isinstance(context, dict)


def test_compress_section_curve():
    """Test section curve compression preserves shape."""
    from twinklr.core.agents.audio.profile.context import compress_section_curve

    # Create curve with 100 points
    curve = [{"t_ms": i * 100, "energy": 0.5 + 0.3 * (i / 100)} for i in range(100)]

    compressed = compress_section_curve(curve, points_per_section=8)

    # Should compress to ~8 points
    assert 3 <= len(compressed) <= 10  # Allow some flexibility

    # Should preserve first and last
    assert compressed[0]["t_ms"] == curve[0]["t_ms"]
    assert compressed[-1]["t_ms"] == curve[-1]["t_ms"]

    # Should be monotonically increasing in time
    timestamps = [p["t_ms"] for p in compressed]
    assert timestamps == sorted(timestamps)


def test_compress_section_curve_short():
    """Test compression handles curves shorter than target."""
    from twinklr.core.agents.audio.profile.context import compress_section_curve

    # Curve with only 5 points
    curve = [{"t_ms": i * 1000, "energy": 0.5} for i in range(5)]

    compressed = compress_section_curve(curve, points_per_section=8)

    # Should return original (already short enough)
    assert len(compressed) == 5
    assert compressed == curve


def test_identify_characteristics():
    """Test energy characteristic identification."""
    from twinklr.core.agents.audio.profile.context import identify_characteristics

    # Building curve (increasing)
    building_curve = [{"t_ms": i * 1000, "energy": 0.3 + i * 0.1} for i in range(5)]
    chars = identify_characteristics(building_curve)
    assert "building" in chars

    # Sustained curve (flat)
    sustained_curve = [{"t_ms": i * 1000, "energy": 0.7} for i in range(5)]
    chars = identify_characteristics(sustained_curve)
    assert "sustained" in chars

    # Peak curve (high energy)
    peak_curve = [{"t_ms": i * 1000, "energy": 0.9} for i in range(5)]
    chars = identify_characteristics(peak_curve)
    assert "peak" in chars


def test_shape_context_token_reduction():
    """Test context shaping achieves significant token reduction."""
    import json

    from twinklr.core.agents.audio.profile.context import shape_context
    from twinklr.core.audio.models import SongBundle, SongTiming

    # Create bundle with large energy curve (simulating real data)
    bundle = SongBundle(
        schema_version="3.0",
        audio_path="/test/song.mp3",
        recording_id="test_123",
        features={
            "duration_ms": 180000,  # 3 minutes
            "tempo": {"bpm": 120.0, "confidence": 0.95, "time_signature": "4/4"},
            "key": {"key": "C", "mode": "major", "confidence": 0.85},
            "sections": [
                {"type": "intro", "start_ms": 0, "end_ms": 15000},
                {"type": "verse", "start_ms": 15000, "end_ms": 45000},
                {"type": "chorus", "start_ms": 45000, "end_ms": 75000},
                {"type": "verse", "start_ms": 75000, "end_ms": 105000},
                {"type": "chorus", "start_ms": 105000, "end_ms": 135000},
                {"type": "bridge", "start_ms": 135000, "end_ms": 150000},
                {"type": "chorus", "start_ms": 150000, "end_ms": 180000},
            ],
            "energy": {
                "overall": 0.7,
                # Large curve: 1800 points (one per 100ms)
                "curve": [
                    {"t_ms": i * 100, "energy": 0.5 + (i % 100) * 0.005} for i in range(1800)
                ],
                "peaks": [
                    {"start_ms": 40000, "end_ms": 45000, "energy": 0.9},
                    {"start_ms": 70000, "end_ms": 75000, "energy": 0.9},
                ],
            },
        },
        timing=SongTiming(sr=22050, hop_length=512, duration_s=180.0, duration_ms=180000),
    )

    # Get original size
    original_size = len(json.dumps(bundle.features))

    # Shape context
    context = shape_context(bundle)
    shaped_size = len(json.dumps(context))

    # Should achieve significant reduction (at least 5x)
    reduction_factor = original_size / shaped_size
    assert reduction_factor >= 5.0, (
        f"Only achieved {reduction_factor:.1f}x reduction (expected ≥5x)"
    )
