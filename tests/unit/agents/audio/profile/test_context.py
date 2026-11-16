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


def test_shape_context_surfaces_stem_signals_to_planners():
    """Planner substrate retains the three provenance-tagged stem signals."""
    from twinklr.core.agents.audio.profile.context import shape_context
    from twinklr.core.audio.models import SongBundle, SongTiming

    bundle = SongBundle(
        schema_version="3.0",
        audio_path="/test/song.mp3",
        recording_id="test_123",
        features={
            "duration_ms": 10_000,
            "sections": [],
            "stems": {"status": "available", "model_name": "htdemucs"},
            "rhythm": {
                "source": "drum_stem",
                "beat_confidence": 0.92,
                "accent_confidence": 0.88,
            },
            "energy": {"build_drop_source": "bass_stem", "builds": [], "drops": []},
            "vocals_source": "vocal_stem",
            "vocals_statistics": {"vocal_coverage_pct": 0.64},
        },
        timing=SongTiming(sr=22_050, hop_length=512, duration_s=10.0, duration_ms=10_000),
    )

    context = shape_context(bundle)

    assert context["stem_signals"] == {
        "status": "available",
        "model_name": "htdemucs",
        "rhythm_source": "drum_stem",
        "beat_confidence": 0.92,
        "accent_confidence": 0.88,
        "build_drop_source": "bass_stem",
        "vocals_source": "vocal_stem",
        "vocal_presence_pct": 0.64,
    }


def _beat_grid_bundle(*, tempo_octave: dict, downbeat_method: str, rhythm_source: str = "dsp"):
    from twinklr.core.audio.models import SongBundle, SongTiming

    return SongBundle(
        schema_version="3.0",
        audio_path="/test/song.mp3",
        recording_id="test_123",
        features={
            "duration_ms": 10_000,
            "tempo_bpm": tempo_octave.get("chosen_bpm", 120.0),
            "analysis_sources": {
                "rhythm": {"name": rhythm_source, "version": "test"},
                "structure": {"name": "dsp", "version": "test"},
            },
            "time_signature": {
                "time_signature": "4/4",
                "confidence": 0.99,
                "method": "accent_pattern",
                "tempo_octave": tempo_octave,
            },
            "rhythm": {
                "source": "full_mix",
                "beat_confidence": 0.99,
                "accent_confidence": 0.99,
                "downbeat_meta": {"phase": 2, "phase_confidence": 0.0, "method": downbeat_method},
            },
        },
        timing=SongTiming(sr=22_050, hop_length=512, duration_s=10.0, duration_ms=10_000),
    )


def test_shape_context_reports_meter_bar_placement_and_halving():
    from twinklr.core.agents.audio.profile.context import shape_context

    bundle = _beat_grid_bundle(
        tempo_octave={
            "tracker_bpm": 156.6,
            "half_bpm": 78.3,
            "chosen_bpm": 78.3,
            "reason": "halved: backbeat accent two beats from the chord change",
        },
        downbeat_method="fallback",
    )

    context = shape_context(bundle)

    assert context["beat_grid"] == {
        "meter_confidence": 0.99,
        "downbeat_confidence": 0.0,
        "downbeat_method": "fallback",
        "tempo_octave": {
            "tracker_bpm": 156.6,
            "chosen_bpm": 78.3,
            "reason": "halved: backbeat accent two beats from the chord change",
        },
    }


def test_shape_context_omits_the_octave_note_when_the_tracker_tempo_was_kept():
    from twinklr.core.agents.audio.profile.context import shape_context

    bundle = _beat_grid_bundle(
        tempo_octave={
            "tracker_bpm": 129.2,
            "half_bpm": 64.6,
            "chosen_bpm": 129.2,
            "reason": "kept tracker tempo: no significant 4-beat accent and chord phase",
        },
        downbeat_method="harmonic_change",
    )

    context = shape_context(bundle)

    assert context["beat_grid"]["tempo_octave"] is None
    assert context["beat_grid"]["downbeat_method"] == "harmonic_change"


def test_shape_context_beat_grid_only_for_the_dsp_rhythm_source():
    """Other sources report fixed 1.0 confidences that are not permutation shares."""
    from twinklr.core.agents.audio.profile.context import shape_context

    bundle = _beat_grid_bundle(
        tempo_octave={"tracker_bpm": 120.0, "chosen_bpm": 120.0, "reason": "kept"},
        downbeat_method="beat_this",
        rhythm_source="beat_this",
    )

    assert shape_context(bundle)["beat_grid"] is None


def test_shape_context_tolerates_a_partial_octave_record_and_missing_rhythm():
    from twinklr.core.agents.audio.profile.context import shape_context

    partial = _beat_grid_bundle(tempo_octave={"tracker_bpm": 156.6}, downbeat_method="fallback")
    no_rhythm = _beat_grid_bundle(
        tempo_octave={"tracker_bpm": 120.0, "chosen_bpm": 120.0, "reason": "kept"},
        downbeat_method="fallback",
    )
    no_rhythm.features["rhythm"] = None

    assert shape_context(partial)["beat_grid"]["tempo_octave"] is None
    assert shape_context(no_rhythm)["beat_grid"] is None


def test_shape_context_reports_no_tempo_confidence():
    """No source computes a tempo confidence; the profile must not invent one."""
    from twinklr.core.agents.audio.profile.context import shape_context

    bundle = _beat_grid_bundle(
        tempo_octave={"tracker_bpm": 120.0, "chosen_bpm": 120.0, "reason": "kept"},
        downbeat_method="harmonic_change",
    )

    assert "confidence" not in shape_context(bundle)["tempo"]


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
