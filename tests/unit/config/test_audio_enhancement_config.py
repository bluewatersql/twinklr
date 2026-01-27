"""Tests for AudioEnhancementConfig (v3.0 features).

Following TDD for Phase 0 - Dependencies and Configuration.
"""

from pydantic import ValidationError
import pytest

from blinkb0t.core.config.models import AudioEnhancementConfig, AudioProcessingConfig


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

    def test_lyrics_pipeline_defaults(self):
        """Lyrics pipeline has reasonable defaults."""
        config = AudioEnhancementConfig()

        assert config.lyrics_require_timed is False
        assert config.lyrics_min_coverage == 0.80
        assert config.lyrics_language == "en"

    def test_whisperx_defaults(self):
        """WhisperX has sensible defaults for CPU usage."""
        config = AudioEnhancementConfig()

        assert config.whisperx_model == "base"
        assert config.whisperx_device == "cpu"
        assert config.whisperx_batch_size == 16
        assert config.whisperx_return_char_alignments is False

    def test_phoneme_defaults(self):
        """Phoneme generation has sensible defaults."""
        config = AudioEnhancementConfig()

        assert config.phoneme_enable_g2p_fallback is True
        assert config.phoneme_min_duration_ms == 30
        assert config.phoneme_vowel_weight == 2.0
        assert config.phoneme_consonant_weight == 1.0

    def test_viseme_smoothing_defaults(self):
        """Viseme smoothing has decor-friendly defaults."""
        config = AudioEnhancementConfig()

        assert config.viseme_min_hold_ms == 50
        assert config.viseme_min_burst_ms == 40
        assert config.viseme_boundary_soften_ms == 15
        assert config.viseme_mapping_version == "1.0"

    def test_provider_defaults(self):
        """Provider configuration has safe defaults."""
        config = AudioEnhancementConfig()

        assert config.acoustid_api_key is None  # Loaded from env
        assert config.musicbrainz_rate_limit_rps == 1.0
        assert config.musicbrainz_timeout_s == 10.0

    def test_http_client_defaults(self):
        """HTTP client has sensible defaults."""
        config = AudioEnhancementConfig()

        assert config.http_max_retries == 3
        assert config.http_timeout_s == 30.0
        assert config.http_circuit_breaker_threshold == 5
        assert config.http_circuit_breaker_timeout_s == 60.0

    def test_metadata_merge_defaults(self):
        """Metadata merge policy has defaults."""
        config = AudioEnhancementConfig()

        assert config.metadata_merge_policy_version == "1.0"
        assert config.metadata_min_confidence_warn == 0.55


class TestAudioEnhancementConfigValidation:
    """Test validation rules for AudioEnhancementConfig."""

    def test_lyrics_min_coverage_range(self):
        """Lyrics min coverage must be between 0 and 1."""
        # Valid range
        AudioEnhancementConfig(lyrics_min_coverage=0.0)
        AudioEnhancementConfig(lyrics_min_coverage=1.0)
        AudioEnhancementConfig(lyrics_min_coverage=0.5)

        # Invalid range
        with pytest.raises(ValidationError):
            AudioEnhancementConfig(lyrics_min_coverage=-0.1)
        with pytest.raises(ValidationError):
            AudioEnhancementConfig(lyrics_min_coverage=1.1)

    def test_phoneme_min_duration_positive(self):
        """Phoneme min duration must be positive."""
        AudioEnhancementConfig(phoneme_min_duration_ms=10)
        AudioEnhancementConfig(phoneme_min_duration_ms=100)

        with pytest.raises(ValidationError):
            AudioEnhancementConfig(phoneme_min_duration_ms=0)
        with pytest.raises(ValidationError):
            AudioEnhancementConfig(phoneme_min_duration_ms=-10)

    def test_phoneme_weights_positive(self):
        """Phoneme weights must be positive."""
        AudioEnhancementConfig(phoneme_vowel_weight=1.0, phoneme_consonant_weight=1.0)

        with pytest.raises(ValidationError):
            AudioEnhancementConfig(phoneme_vowel_weight=0.0)
        with pytest.raises(ValidationError):
            AudioEnhancementConfig(phoneme_consonant_weight=0.0)

    def test_musicbrainz_rate_limit_range(self):
        """MusicBrainz rate limit must be reasonable."""
        AudioEnhancementConfig(musicbrainz_rate_limit_rps=0.1)
        AudioEnhancementConfig(musicbrainz_rate_limit_rps=10.0)

        with pytest.raises(ValidationError):
            AudioEnhancementConfig(musicbrainz_rate_limit_rps=0.0)
        with pytest.raises(ValidationError):
            AudioEnhancementConfig(musicbrainz_rate_limit_rps=11.0)

    def test_metadata_min_confidence_range(self):
        """Metadata min confidence must be between 0 and 1."""
        AudioEnhancementConfig(metadata_min_confidence_warn=0.0)
        AudioEnhancementConfig(metadata_min_confidence_warn=1.0)

        with pytest.raises(ValidationError):
            AudioEnhancementConfig(metadata_min_confidence_warn=-0.1)
        with pytest.raises(ValidationError):
            AudioEnhancementConfig(metadata_min_confidence_warn=1.1)


class TestAudioEnhancementConfigScenarios:
    """Test common configuration scenarios."""

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

    def test_audio_processing_includes_enhancements(self):
        """AudioProcessingConfig should include enhancements field."""
        config = AudioProcessingConfig()

        assert hasattr(config, "enhancements")
        assert isinstance(config.enhancements, AudioEnhancementConfig)

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

    def test_audio_processing_enhancements_defaults(self):
        """AudioProcessingConfig uses enhancement defaults."""
        config = AudioProcessingConfig()

        # Should have default enhancement config
        assert config.enhancements.enable_metadata is True
        assert config.enhancements.enable_acoustid is False


class TestConfigurationLoading:
    """Test loading configuration from dict (simulates JSON loading)."""

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
