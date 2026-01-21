"""Tests for channel and DMX enums.

Tests ChannelName and BlendMode enum types.
All 5 test cases per implementation plan Task 0.3.
"""

import json

from pydantic import BaseModel, ValidationError
import pytest

from blinkb0t.core.sequencer.moving_heads.models.channel import BlendMode, ChannelName


class TestChannelName:
    """Tests for ChannelName enum."""

    def test_enum_values_are_strings(self) -> None:
        """Test enum values are strings."""
        assert isinstance(ChannelName.PAN.value, str)
        assert isinstance(ChannelName.TILT.value, str)
        assert isinstance(ChannelName.DIMMER.value, str)

        assert ChannelName.PAN.value == "PAN"
        assert ChannelName.TILT.value == "TILT"
        assert ChannelName.DIMMER.value == "DIMMER"

    def test_enum_serialization_to_json(self) -> None:
        """Test enum serializes to JSON as string value."""
        # ChannelName is a str Enum, so json.dumps should work directly
        assert json.dumps(ChannelName.PAN.value) == '"PAN"'

    def test_enum_deserialization_from_json(self) -> None:
        """Test enum deserializes from JSON string."""
        value = json.loads('"TILT"')
        assert ChannelName(value) == ChannelName.TILT


class TestBlendMode:
    """Tests for BlendMode enum."""

    def test_enum_values_are_strings(self) -> None:
        """Test enum values are strings."""
        assert isinstance(BlendMode.OVERRIDE.value, str)
        assert isinstance(BlendMode.ADD.value, str)

        assert BlendMode.OVERRIDE.value == "OVERRIDE"
        assert BlendMode.ADD.value == "ADD"


class TestEnumInPydanticModel:
    """Tests for enums in Pydantic models."""

    def test_enum_in_pydantic_model_field(self) -> None:
        """Test enum works correctly in Pydantic model field."""

        class TestModel(BaseModel):
            channel: ChannelName
            blend: BlendMode

        model = TestModel(channel=ChannelName.PAN, blend=BlendMode.OVERRIDE)
        assert model.channel == ChannelName.PAN
        assert model.blend == BlendMode.OVERRIDE

        # Test with string values (automatic coercion)
        model2 = TestModel(channel="TILT", blend="ADD")  # type: ignore[arg-type]
        assert model2.channel == ChannelName.TILT
        assert model2.blend == BlendMode.ADD

    def test_unknown_enum_value_raises_error(self) -> None:
        """Test unknown enum value raises error in Pydantic model."""

        class TestModel(BaseModel):
            channel: ChannelName

        with pytest.raises(ValidationError) as exc_info:
            TestModel(channel="UNKNOWN_CHANNEL")  # type: ignore[arg-type]

        assert "channel" in str(exc_info.value).lower()


class TestJsonRoundtrip:
    """Tests for JSON serialization roundtrip."""

    def test_pydantic_model_json_roundtrip(self) -> None:
        """Test Pydantic model with enums serializes/deserializes correctly."""

        class TestModel(BaseModel):
            channel: ChannelName
            blend: BlendMode

        original = TestModel(channel=ChannelName.DIMMER, blend=BlendMode.ADD)
        json_str = original.model_dump_json()
        restored = TestModel.model_validate_json(json_str)

        assert restored.channel == original.channel
        assert restored.blend == original.blend

        # Verify JSON structure
        parsed = json.loads(json_str)
        assert parsed["channel"] == "DIMMER"
        assert parsed["blend"] == "ADD"
