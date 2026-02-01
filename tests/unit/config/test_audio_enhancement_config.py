"""Tests for AudioEnhancementConfig (v3.0 features).

Following TDD for Phase 0 - Dependencies and Configuration.
"""

from twinklr.core.config.models import AudioEnhancementConfig, AudioProcessingConfig


class TestAudioEnhancementConfigDefaults:
    """Test default values for AudioEnhancementConfig."""

    def test_all_defaults_valid(self):
        """Default configuration should be valid."""
        config = AudioEnhancementConfig()

        # Feature flags default to embedded-only mode (no network)
        assert config.enable_metadata is True
        assert config.enable_lyrics is True
        assert config.enable_phonemes is True

        # Network features disabled by default
        assert config.enable_acoustid is False
        assert config.enable_musicbrainz is False
        assert config.enable_lyrics_lookup is False
        assert config.enable_whisperx is False
        assert config.enable_diarization is False

    def test_embedded_only_mode(self):
        """Embedded-only mode (no network, no ML)."""
        config = AudioEnhancementConfig(
            enable_metadata=True,
            enable_lyrics=True,
            enable_phonemes=True,
            enable_acoustid=False,
            enable_musicbrainz=False,
            enable_lyrics_lookup=False,
            enable_whisperx=False,
            enable_diarization=False,
        )

        assert config.enable_metadata is True
        assert config.enable_acoustid is False
        assert config.enable_whisperx is False

    def test_full_network_mode(self):
        """Full network mode with all providers enabled."""
        config = AudioEnhancementConfig(
            enable_metadata=True,
            enable_lyrics=True,
            enable_phonemes=True,
            enable_acoustid=True,
            enable_musicbrainz=True,
            enable_lyrics_lookup=True,
            acoustid_api_key="test_key_123",
        )

        assert config.enable_acoustid is True
        assert config.enable_musicbrainz is True
        assert config.enable_lyrics_lookup is True
        assert config.acoustid_api_key == "test_key_123"

    def test_whisperx_with_gpu(self):
        """WhisperX configuration for GPU acceleration."""
        config = AudioEnhancementConfig(
            enable_whisperx=True,
            whisperx_device="cuda",
            whisperx_model="large",
            whisperx_batch_size=32,
        )

        assert config.whisperx_device == "cuda"
        assert config.whisperx_model == "large"
        assert config.whisperx_batch_size == 32

    def test_all_features_disabled(self):
        """All v3.0 features can be disabled."""
        config = AudioEnhancementConfig(
            enable_metadata=False,
            enable_lyrics=False,
            enable_phonemes=False,
        )

        assert config.enable_metadata is False
        assert config.enable_lyrics is False
        assert config.enable_phonemes is False


class TestAudioProcessingConfigWithEnhancements:
    """Test AudioProcessingConfig with nested enhancements."""

    def test_audio_processing_with_custom_enhancements(self):
        """Can customize enhancements in AudioProcessingConfig."""
        config = AudioProcessingConfig(
            hop_length=512,
            enhancements=AudioEnhancementConfig(
                enable_acoustid=True,
                acoustid_api_key="test_key",
            ),
        )

        assert config.hop_length == 512
        assert config.enhancements.enable_acoustid is True
        assert config.enhancements.acoustid_api_key == "test_key"

    def test_load_from_dict_with_enhancements(self):
        """Load AudioProcessingConfig from dict with enhancements."""
        data = {
            "hop_length": 512,
            "frame_length": 2048,
            "cache_enabled": True,
            "enhancements": {
                "enable_metadata": True,
                "enable_lyrics": True,
                "enable_acoustid": True,
                "acoustid_api_key": "test_key",
                "whisperx_model": "small",
            },
        }

        config = AudioProcessingConfig.model_validate(data)

        assert config.hop_length == 512
        assert config.enhancements.enable_acoustid is True
        assert config.enhancements.acoustid_api_key == "test_key"
        assert config.enhancements.whisperx_model == "small"

    def test_load_from_dict_without_enhancements(self):
        """Load AudioProcessingConfig without enhancements (uses defaults)."""
        data = {
            "hop_length": 512,
            "frame_length": 2048,
        }

        config = AudioProcessingConfig.model_validate(data)

        # Should use default enhancements
        assert config.enhancements.enable_metadata is True
        assert config.enhancements.enable_acoustid is False

    def test_forward_compatibility_unknown_fields_ignored(self):
        """Unknown fields in enhancements should be ignored (forward compat)."""
        data = {
            "hop_length": 512,
            "enhancements": {
                "enable_metadata": True,
                "future_feature_v4": True,  # Future field
                "another_unknown": "value",
            },
        }

        # Should not raise error (extra="ignore" in model config)
        config = AudioProcessingConfig.model_validate(data)
        assert config.enhancements.enable_metadata is True
