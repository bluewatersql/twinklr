"""Tests for AudioProfile agent models."""

from datetime import datetime

from pydantic import ValidationError
import pytest


def test_severity_enum():
    """Test Severity enum values."""
    from twinklr.core.agents.audio.profile.models import Severity

    assert Severity.INFO == "INFO"
    assert Severity.WARN == "WARN"
    assert Severity.ERROR == "ERROR"
    assert list(Severity) == [Severity.INFO, Severity.WARN, Severity.ERROR]


def test_issue_model_valid():
    """Test Issue model with valid data."""
    from twinklr.core.agents.audio.profile.models import Issue, Severity

    issue = Issue(
        severity=Severity.WARN,
        code="LOW_CONFIDENCE",
        message="Section timing has low confidence",
        path="$.structure.sections[0]",
        hint="Consider reviewing section boundaries",
    )

    assert issue.severity == Severity.WARN
    assert issue.code == "LOW_CONFIDENCE"
    assert issue.message == "Section timing has low confidence"
    assert issue.path == "$.structure.sections[0]"
    assert issue.hint == "Consider reviewing section boundaries"


def test_issue_model_minimal():
    """Test Issue model with minimal required fields."""
    from twinklr.core.agents.audio.profile.models import Issue, Severity

    issue = Issue(severity=Severity.INFO, code="TEST_CODE", message="Test message")

    assert issue.severity == Severity.INFO
    assert issue.code == "TEST_CODE"
    assert issue.message == "Test message"
    assert issue.path is None
    assert issue.hint is None


def test_issue_model_frozen():
    """Test Issue model is frozen (immutable)."""
    from twinklr.core.agents.audio.profile.models import Issue, Severity

    issue = Issue(severity=Severity.INFO, code="TEST", message="Test")

    with pytest.raises(ValidationError):
        issue.severity = Severity.ERROR


def test_issue_model_extra_forbid():
    """Test Issue model forbids extra fields."""
    from twinklr.core.agents.audio.profile.models import Issue, Severity

    with pytest.raises(ValidationError) as exc_info:
        Issue(severity=Severity.INFO, code="TEST", message="Test", extra_field="not allowed")

    assert "extra_field" in str(exc_info.value).lower()


def test_provenance_model_valid():
    """Test Provenance model with valid data."""
    from twinklr.core.agents.audio.profile.models import Provenance

    prov = Provenance(
        provider_id="openai",
        model_id="gpt-5.2",
        prompt_pack="audio_profile.v2",
        prompt_pack_version="1.0.0",
        framework_version="2.0.0",
        seed=42,
        temperature=0.2,
    )

    assert prov.provider_id == "openai"
    assert prov.model_id == "gpt-5.2"
    assert prov.prompt_pack == "audio_profile.v2"
    assert prov.prompt_pack_version == "1.0.0"
    assert prov.framework_version == "2.0.0"
    assert prov.seed == 42
    assert prov.temperature == 0.2
    assert isinstance(prov.created_at, str)
    # Verify it's an ISO format timestamp
    datetime.fromisoformat(prov.created_at.replace("Z", "+00:00"))


def test_provenance_model_auto_timestamp():
    """Test Provenance model auto-generates timestamp."""
    from twinklr.core.agents.audio.profile.models import Provenance

    prov = Provenance(
        provider_id="openai",
        model_id="gpt-5.2",
        prompt_pack="audio_profile.v2",
        prompt_pack_version="1.0.0",
        framework_version="2.0.0",
        temperature=0.2,
    )

    assert prov.created_at is not None
    assert isinstance(prov.created_at, str)
    # Should be able to parse as ISO timestamp
    datetime.fromisoformat(prov.created_at.replace("Z", "+00:00"))


def test_provenance_model_optional_seed():
    """Test Provenance model with no seed."""
    from twinklr.core.agents.audio.profile.models import Provenance

    prov = Provenance(
        provider_id="openai",
        model_id="gpt-5.2",
        prompt_pack="audio_profile.v2",
        prompt_pack_version="1.0.0",
        framework_version="2.0.0",
        temperature=0.2,
    )

    assert prov.seed is None


def test_provenance_model_frozen():
    """Test Provenance model is frozen (immutable)."""
    from twinklr.core.agents.audio.profile.models import Provenance

    prov = Provenance(
        provider_id="openai",
        model_id="gpt-5.2",
        prompt_pack="audio_profile.v2",
        prompt_pack_version="1.0.0",
        framework_version="2.0.0",
        temperature=0.2,
    )

    with pytest.raises(ValidationError):
        prov.provider_id = "anthropic"


def test_provenance_model_extra_forbid():
    """Test Provenance model forbids extra fields."""
    from twinklr.core.agents.audio.profile.models import Provenance

    with pytest.raises(ValidationError) as exc_info:
        Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="audio_profile.v2",
            prompt_pack_version="1.0.0",
            framework_version="2.0.0",
            temperature=0.2,
            extra_field="not allowed",
        )

    assert "extra_field" in str(exc_info.value).lower()


def test_audio_profile_model_defaults():
    """Test AudioProfileModel has proper defaults."""
    from twinklr.core.agents.audio.profile.models import (
        AudioProfileModel,
    )

    # Create minimal model (will need placeholders for required nested models)
    # For now, we'll test this fails appropriately
    with pytest.raises(ValidationError) as exc_info:
        AudioProfileModel()

    # Should fail due to missing required nested models
    error_str = str(exc_info.value).lower()
    assert any(
        field in error_str
        for field in ["song_identity", "structure", "energy", "lyric", "creative", "planner"]
    )


def test_audio_profile_model_excludes_framework_schema_version():
    """Framework metadata does not belong in the structured response."""
    from twinklr.core.agents.audio.profile.models import AudioProfileModel

    assert "schema_version" not in AudioProfileModel.model_fields


def test_audio_profile_model_excludes_framework_agent_id():
    """Agent identity is framework-owned rather than model-generated."""
    from twinklr.core.agents.audio.profile.models import AudioProfileModel

    assert "agent_id" not in AudioProfileModel.model_fields


def test_audio_profile_model_warnings_are_schema_required():
    """Warnings are required by the strict response schema."""
    from twinklr.core.agents.audio.profile.models import AudioProfileModel

    field = AudioProfileModel.model_fields["warnings"]
    assert field.is_required()


def test_audio_profile_model_config():
    """Test AudioProfileModel has correct config."""
    from twinklr.core.agents.audio.profile.models import AudioProfileModel

    config = AudioProfileModel.model_config
    assert config["extra"] == "forbid"
    assert config["validate_assignment"] is True
    assert config["frozen"] is False
