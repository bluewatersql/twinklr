"""Tests for SEC-09: SecretStr usage for API keys in config models."""

from __future__ import annotations

import os
from unittest.mock import patch

from pydantic import SecretStr

from twinklr.core.config.models import AppConfig, AudioEnhancementConfig


class TestSecretStrApiKeys:
    """Verify API keys use SecretStr for protection."""

    def test_llm_api_key_is_secretstr(self) -> None:
        """llm_api_key field must be SecretStr type."""
        config = AppConfig()
        assert isinstance(config.llm_api_key, SecretStr)

    def test_acoustid_api_key_is_secretstr(self) -> None:
        """acoustid_api_key field must accept SecretStr."""
        config = AudioEnhancementConfig(acoustid_api_key=SecretStr("test-key"))
        assert isinstance(config.acoustid_api_key, SecretStr)
        assert config.acoustid_api_key.get_secret_value() == "test-key"

    def test_genius_access_token_is_secretstr(self) -> None:
        """genius_access_token field must accept SecretStr."""
        config = AudioEnhancementConfig(genius_access_token=SecretStr("genius-key"))
        assert isinstance(config.genius_access_token, SecretStr)
        assert config.genius_access_token.get_secret_value() == "genius-key"

    def test_secretstr_not_leaked_in_repr(self) -> None:
        """SecretStr values must not appear in repr/str output."""
        config = AudioEnhancementConfig(acoustid_api_key=SecretStr("super-secret-key"))
        repr_str = repr(config)
        assert "super-secret-key" not in repr_str

    def test_secretstr_not_leaked_in_dict(self) -> None:
        """SecretStr values must not appear in model_dump by default."""
        config = AudioEnhancementConfig(acoustid_api_key=SecretStr("secret-123"))
        dumped = config.model_dump()
        # SecretStr should be serialized as '**********' or similar
        assert dumped["acoustid_api_key"] != "secret-123"

    def test_default_none_api_keys(self) -> None:
        """API keys should default to None when not provided."""
        config = AudioEnhancementConfig()
        assert config.acoustid_api_key is None
        assert config.genius_access_token is None

    @patch.dict(os.environ, {"OPENAI_API_KEY": "env-test-key"}, clear=False)
    def test_llm_api_key_from_env(self) -> None:
        """llm_api_key should load from OPENAI_API_KEY env var."""
        config = AppConfig()
        assert config.llm_api_key.get_secret_value() == "env-test-key"
