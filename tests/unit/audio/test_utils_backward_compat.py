"""Tests for backward compatibility utilities (Phase 1).

Testing to_simple_dict() which extracts v2.3 dict from SongBundle.
"""

from blinkb0t.core.audio.models import SongBundle, SongTiming
from blinkb0t.core.audio.utils import to_simple_dict


class TestToSimpleDict:
    """Test to_simple_dict() backward compatibility utility."""

    def test_features_only_bundle(self):
        """Extract v2.3 dict from features-only bundle."""
        features_dict = {
            "schema_version": "2.3",
            "tempo_bpm": 120.0,
            "beats_s": [0.5, 1.0, 1.5, 2.0],
            "bars": [[0.5, 1], [1.5, 2]],
            "energy_smooth_1s": [0.5, 0.6, 0.7],
        }

        bundle = SongBundle(
            schema_version="3.0",
            audio_path="/path/to/song.mp3",
            recording_id="rec_123",
            features=features_dict,
            timing=SongTiming(sr=22050, hop_length=512, duration_s=3.0, duration_ms=3000),
        )

        result = to_simple_dict(bundle)

        # Should return the features dict unchanged
        assert result == features_dict
        assert result["schema_version"] == "2.3"
        assert result["tempo_bpm"] == 120.0
        assert result["beats_s"] == [0.5, 1.0, 1.5, 2.0]

    def test_preserves_all_v23_fields(self):
        """All v2.3 fields are preserved."""
        features_dict = {
            "schema_version": "2.3",
            "tempo_bpm": 128.0,
            "time_signature": [4, 4],
            "beats_s": [0.0, 0.5],
            "bars": [[0.0, 1]],
            "downbeats_s": [0.0],
            "energy_smooth_1s": [0.8],
            "spectral_centroid": [1500.0],
            "sections": [{"label": "intro", "start_s": 0.0, "end_s": 8.0}],
            "key": "C",
            "chords": [],
            "transients": [],
        }

        bundle = SongBundle(
            schema_version="3.0",
            audio_path="/path/to/song.mp3",
            recording_id="rec_123",
            features=features_dict,
            timing=SongTiming(sr=22050, hop_length=512, duration_s=2.0, duration_ms=2000),
        )

        result = to_simple_dict(bundle)

        # All fields preserved
        assert result == features_dict
        assert "tempo_bpm" in result
        assert "time_signature" in result
        assert "sections" in result

    def test_ignores_v3_enhancements(self):
        """v3.0 enhancement fields (metadata, lyrics, phonemes) are not included."""
        features_dict = {
            "schema_version": "2.3",
            "tempo_bpm": 120.0,
        }

        bundle = SongBundle(
            schema_version="3.0",
            audio_path="/path/to/song.mp3",
            recording_id="rec_123",
            features=features_dict,
            timing=SongTiming(sr=22050, hop_length=512, duration_s=1.0, duration_ms=1000),
            # These should be ignored in output
            metadata=None,
            lyrics=None,
            phonemes=None,
            warnings=["Some warning"],
            provenance={"version": "3.0"},
        )

        result = to_simple_dict(bundle)

        # Only features dict returned
        assert result == features_dict
        assert "metadata" not in result
        assert "lyrics" not in result
        assert "phonemes" not in result
        assert "warnings" not in result
        assert "provenance" not in result
        assert "schema_version" in result
        assert result["schema_version"] == "2.3"

    def test_empty_features_dict(self):
        """Can handle minimal/empty features dict."""
        features_dict = {"schema_version": "2.3"}

        bundle = SongBundle(
            schema_version="3.0",
            audio_path="/path/to/song.mp3",
            recording_id="rec_123",
            features=features_dict,
            timing=SongTiming(sr=22050, hop_length=512, duration_s=1.0, duration_ms=1000),
        )

        result = to_simple_dict(bundle)

        assert result == features_dict
        assert result["schema_version"] == "2.3"

    def test_features_dict_not_modified(self):
        """Original features dict in bundle is not modified."""
        features_dict = {
            "schema_version": "2.3",
            "tempo_bpm": 120.0,
            "beats_s": [0.0, 0.5],
        }

        bundle = SongBundle(
            schema_version="3.0",
            audio_path="/path/to/song.mp3",
            recording_id="rec_123",
            features=features_dict,
            timing=SongTiming(sr=22050, hop_length=512, duration_s=1.0, duration_ms=1000),
        )

        result = to_simple_dict(bundle)

        # Result should equal original
        assert result == features_dict
        # Original features in bundle unchanged
        assert bundle.features == features_dict
        assert bundle.features["tempo_bpm"] == 120.0

    def test_complex_nested_structures(self):
        """Handles complex nested structures in features dict."""
        features_dict = {
            "schema_version": "2.3",
            "sections": [
                {
                    "label": "intro",
                    "start_s": 0.0,
                    "end_s": 8.0,
                    "confidence": 0.9,
                    "metrics": {"energy": 0.5, "spectral": [100, 200, 300]},
                }
            ],
            "dynamic_features": {
                "bass": [0.1, 0.2, 0.3],
                "mid": [0.4, 0.5, 0.6],
                "high": [0.7, 0.8, 0.9],
            },
        }

        bundle = SongBundle(
            schema_version="3.0",
            audio_path="/path/to/song.mp3",
            recording_id="rec_123",
            features=features_dict,
            timing=SongTiming(sr=22050, hop_length=512, duration_s=8.0, duration_ms=8000),
        )

        result = to_simple_dict(bundle)

        # Complex structures preserved
        assert result == features_dict
        assert result["sections"][0]["metrics"]["spectral"] == [100, 200, 300]
        assert result["dynamic_features"]["mid"] == [0.4, 0.5, 0.6]
