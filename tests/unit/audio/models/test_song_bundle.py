"""Tests for SongBundle and related models (Phase 1).

Following TDD for Phase 1 - Scaffolding and Backward Compatibility.
"""

from pydantic import ValidationError
import pytest

from twinklr.core.audio.models import (
    SongBundle,
    SongTiming,
)
from twinklr.core.audio.models.enums import StageStatus


class TestSongTiming:
    """Test SongTiming model."""

    def test_minimal_valid(self):
        """Minimal SongTiming with all required fields."""
        timing = SongTiming(
            sr=22050,
            hop_length=512,
            duration_s=180.5,
            duration_ms=180500,
        )

        assert timing.sr == 22050
        assert timing.hop_length == 512
        assert timing.duration_s == 180.5
        assert timing.duration_ms == 180500

    def test_validation_positive_values(self):
        """All numeric fields must be positive."""
        with pytest.raises(ValidationError):
            SongTiming(sr=0, hop_length=512, duration_s=10.0, duration_ms=10000)

        with pytest.raises(ValidationError):
            SongTiming(sr=22050, hop_length=0, duration_s=10.0, duration_ms=10000)

        with pytest.raises(ValidationError):
            SongTiming(sr=22050, hop_length=512, duration_s=-1.0, duration_ms=10000)


class TestSongBundleMinimal:
    """Test SongBundle with minimal/features-only configuration."""

    def test_features_only_bundle(self):
        """SongBundle with just features (all enhancements disabled)."""
        features_dict = {
            "schema_version": "2.3",
            "tempo_bpm": 120.0,
            "beats_s": [0.5, 1.0, 1.5],
            "bars": [[0.5, 1]],
        }

        bundle = SongBundle(
            schema_version="3.0",
            audio_path="/path/to/song.mp3",
            recording_id="test_audio_rec_123",
            features=features_dict,
            timing=SongTiming(sr=22050, hop_length=512, duration_s=3.0, duration_ms=3000),
            metadata=None,
            lyrics=None,
            phonemes=None,
        )

        assert bundle.schema_version == "3.0"
        assert bundle.audio_path == "/path/to/song.mp3"
        assert bundle.recording_id == "test_audio_rec_123"
        assert bundle.features == features_dict
        assert bundle.features["schema_version"] == "2.3"
        assert bundle.timing.sr == 22050
        assert bundle.metadata is None
        assert bundle.lyrics is None
        assert bundle.phonemes is None
        assert bundle.warnings == []
        assert bundle.provenance == {}

    def test_default_warnings_and_provenance(self):
        """Warnings and provenance have default empty values."""
        bundle = SongBundle(
            schema_version="3.0",
            audio_path="/path/to/song.mp3",
            recording_id="rec_123",
            features={"schema_version": "2.3"},
            timing=SongTiming(sr=22050, hop_length=512, duration_s=1.0, duration_ms=1000),
        )

        assert bundle.warnings == []
        assert bundle.provenance == {}

    def test_can_add_warnings(self):
        """Can add warnings to bundle."""
        bundle = SongBundle(
            schema_version="3.0",
            audio_path="/path/to/song.mp3",
            recording_id="rec_123",
            features={"schema_version": "2.3"},
            timing=SongTiming(sr=22050, hop_length=512, duration_s=1.0, duration_ms=1000),
            warnings=["Low confidence metadata", "Lyrics not found"],
        )

        assert len(bundle.warnings) == 2
        assert "Low confidence metadata" in bundle.warnings

    def test_can_add_provenance(self):
        """Can add provenance to bundle."""
        bundle = SongBundle(
            schema_version="3.0",
            audio_path="/path/to/song.mp3",
            recording_id="rec_123",
            features={"schema_version": "2.3"},
            timing=SongTiming(sr=22050, hop_length=512, duration_s=1.0, duration_ms=1000),
            provenance={"analyzer_version": "3.0", "processed_at": "2026-01-27T00:00:00Z"},
        )

        assert bundle.provenance["analyzer_version"] == "3.0"


class TestSongBundleValidation:
    """Test SongBundle validation rules."""

    def test_schema_version_required(self):
        """schema_version must be present."""
        with pytest.raises(ValidationError):
            SongBundle(
                audio_path="/path/to/song.mp3",
                recording_id="rec_123",
                features={"schema_version": "2.3"},
                timing=SongTiming(sr=22050, hop_length=512, duration_s=1.0, duration_ms=1000),
            )

    def test_audio_path_required(self):
        """audio_path must be present."""
        with pytest.raises(ValidationError):
            SongBundle(
                schema_version="3.0",
                recording_id="rec_123",
                features={"schema_version": "2.3"},
                timing=SongTiming(sr=22050, hop_length=512, duration_s=1.0, duration_ms=1000),
            )

    def test_features_dict_required(self):
        """features dict must be present."""
        with pytest.raises(ValidationError):
            SongBundle(
                schema_version="3.0",
                audio_path="/path/to/song.mp3",
                recording_id="rec_123",
                timing=SongTiming(sr=22050, hop_length=512, duration_s=1.0, duration_ms=1000),
            )

    def test_timing_required(self):
        """timing must be present."""
        with pytest.raises(ValidationError):
            SongBundle(
                schema_version="3.0",
                audio_path="/path/to/song.mp3",
                recording_id="rec_123",
                features={"schema_version": "2.3"},
            )


class TestSongBundleSerialization:
    """Test SongBundle serialization/deserialization."""

    def test_dict_round_trip(self):
        """Bundle can be serialized to dict and back."""
        original = SongBundle(
            schema_version="3.0",
            audio_path="/path/to/song.mp3",
            recording_id="rec_123",
            features={"schema_version": "2.3", "tempo_bpm": 120.0},
            timing=SongTiming(sr=22050, hop_length=512, duration_s=3.0, duration_ms=3000),
        )

        # Serialize to dict
        data = original.model_dump()

        # Deserialize from dict
        restored = SongBundle.model_validate(data)

        assert restored.schema_version == original.schema_version
        assert restored.audio_path == original.audio_path
        assert restored.features == original.features
        assert restored.timing.sr == original.timing.sr

    def test_json_round_trip(self):
        """Bundle can be serialized to JSON and back."""
        original = SongBundle(
            schema_version="3.0",
            audio_path="/path/to/song.mp3",
            recording_id="rec_123",
            features={"schema_version": "2.3", "tempo_bpm": 120.0},
            timing=SongTiming(sr=22050, hop_length=512, duration_s=3.0, duration_ms=3000),
        )

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize from JSON
        restored = SongBundle.model_validate_json(json_str)

        assert restored.schema_version == original.schema_version
        assert restored.audio_path == original.audio_path
        assert restored.features == original.features


class TestStageStatus:
    """Test StageStatus enum."""

    def test_all_values_available(self):
        """All expected status values are available."""
        assert StageStatus.OK == "OK"
        assert StageStatus.SKIPPED == "SKIPPED"
        assert StageStatus.FAILED == "FAILED"

    def test_can_use_in_models(self):
        """StageStatus can be used in Pydantic models."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            status: StageStatus

        model = TestModel(status=StageStatus.OK)
        assert model.status == StageStatus.OK

        model2 = TestModel(status="SKIPPED")
        assert model2.status == StageStatus.SKIPPED
