"""Tests for channel specification system (Component 1)."""

from __future__ import annotations

import pytest

from blinkb0t.core.config.models import ChannelDefaults
from blinkb0t.core.domains.sequencing.channels.resolver import ChannelResolver
from blinkb0t.core.domains.sequencing.channels.validation import BasicChannelValidator
from blinkb0t.core.domains.sequencing.models.channels import (
    ChannelSpecification,
    ResolvedChannels,
)


class TestChannelDefaults:
    """Test ChannelDefaults model."""

    def test_default_values(self):
        """Test default channel values."""
        defaults = ChannelDefaults()
        assert defaults.shutter == "open"
        assert defaults.color == "white"
        assert defaults.gobo == "open"

    def test_custom_values(self):
        """Test custom channel values."""
        defaults = ChannelDefaults(shutter="closed", color="blue", gobo="stars")
        assert defaults.shutter == "closed"
        assert defaults.color == "blue"
        assert defaults.gobo == "stars"

    def test_immutable(self):
        """Test defaults are immutable."""
        from pydantic import ValidationError

        defaults = ChannelDefaults()
        with pytest.raises(ValidationError):  # Frozen model
            defaults.shutter = "closed"  # type: ignore

    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):  # Pydantic validation error
            ChannelDefaults(shutter="open", invalid_field="value")  # type: ignore

    def test_json_serialization(self):
        """Test JSON serialization."""
        defaults = ChannelDefaults(shutter="strobe_fast", color="red", gobo="stars")
        data = defaults.model_dump()
        assert data == {"shutter": "strobe_fast", "color": "red", "gobo": "stars"}

    def test_json_deserialization(self):
        """Test JSON deserialization."""
        data = {"shutter": "strobe_fast", "color": "red", "gobo": "stars"}
        defaults = ChannelDefaults.model_validate(data)
        assert defaults.shutter == "strobe_fast"
        assert defaults.color == "red"
        assert defaults.gobo == "stars"


class TestChannelSpecification:
    """Test ChannelSpecification model."""

    def test_all_none(self):
        """Test specification with no overrides."""
        spec = ChannelSpecification()
        assert spec.shutter is None
        assert spec.color is None
        assert spec.gobo is None

    def test_partial_overrides(self):
        """Test specification with partial overrides."""
        spec = ChannelSpecification(shutter="strobe_fast", gobo="stars")
        assert spec.shutter == "strobe_fast"
        assert spec.color is None
        assert spec.gobo == "stars"

    def test_all_overrides(self):
        """Test specification with all overrides."""
        spec = ChannelSpecification(shutter="strobe_fast", color="red", gobo="stars")
        assert spec.shutter == "strobe_fast"
        assert spec.color == "red"
        assert spec.gobo == "stars"

    def test_has_override(self):
        """Test has_override method."""
        spec = ChannelSpecification(shutter="strobe_fast")
        assert spec.has_override("shutter") is True
        assert spec.has_override("color") is False
        assert spec.has_override("gobo") is False

    def test_get_overrides(self):
        """Test get_overrides method."""
        spec = ChannelSpecification(shutter="strobe_fast", gobo="stars")
        overrides = spec.get_overrides()
        assert overrides == {"shutter": "strobe_fast", "gobo": "stars"}

    def test_get_overrides_empty(self):
        """Test get_overrides with no overrides."""
        spec = ChannelSpecification()
        overrides = spec.get_overrides()
        assert overrides == {}

    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):  # Pydantic validation error
            ChannelSpecification(shutter="open", invalid_field="value")  # type: ignore

    def test_json_serialization(self):
        """Test JSON serialization."""
        spec = ChannelSpecification(shutter="strobe_fast", gobo="stars")
        data = spec.model_dump()
        assert data == {"shutter": "strobe_fast", "color": None, "gobo": "stars"}

    def test_json_deserialization(self):
        """Test JSON deserialization."""
        data = {"shutter": "strobe_fast", "color": None, "gobo": "stars"}
        spec = ChannelSpecification.model_validate(data)
        assert spec.shutter == "strobe_fast"
        assert spec.color is None
        assert spec.gobo == "stars"


class TestResolvedChannels:
    """Test ResolvedChannels model."""

    def test_valid_creation(self):
        """Test creating valid resolved channels."""
        resolved = ResolvedChannels(shutter="open", color="white", gobo="open")
        assert resolved.shutter == "open"
        assert resolved.color == "white"
        assert resolved.gobo == "open"

    def test_immutable(self):
        """Test resolved channels are immutable."""
        from dataclasses import FrozenInstanceError

        resolved = ResolvedChannels(shutter="open", color="white", gobo="open")
        with pytest.raises(FrozenInstanceError):  # Frozen dataclass
            resolved.shutter = "closed"  # type: ignore

    def test_empty_shutter_raises(self):
        """Test empty shutter value raises error."""
        with pytest.raises(ValueError, match="must be non-empty string"):
            ResolvedChannels(shutter="", color="white", gobo="open")

    def test_empty_color_raises(self):
        """Test empty color value raises error."""
        with pytest.raises(ValueError, match="must be non-empty string"):
            ResolvedChannels(shutter="open", color="", gobo="open")

    def test_empty_gobo_raises(self):
        """Test empty gobo value raises error."""
        with pytest.raises(ValueError, match="must be non-empty string"):
            ResolvedChannels(shutter="open", color="white", gobo="")

    def test_non_string_shutter_raises(self):
        """Test non-string shutter value raises error."""
        with pytest.raises(ValueError, match="must be non-empty string"):
            ResolvedChannels(shutter=123, color="white", gobo="open")  # type: ignore

    def test_equality(self):
        """Test equality comparison."""
        r1 = ResolvedChannels(shutter="open", color="white", gobo="open")
        r2 = ResolvedChannels(shutter="open", color="white", gobo="open")
        r3 = ResolvedChannels(shutter="closed", color="white", gobo="open")

        assert r1 == r2
        assert r1 != r3


class TestBasicChannelValidator:
    """Test BasicChannelValidator."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return BasicChannelValidator()

    def test_valid_combination(self, validator):
        """Test valid channel combination."""
        resolved = ResolvedChannels(shutter="open", color="blue", gobo="stars")
        is_valid, errors = validator.validate(resolved)
        assert is_valid is True
        assert errors == []

    def test_all_valid_shutters(self, validator):
        """Test all valid shutter values."""
        valid_shutters = [
            "open",
            "closed",
            "strobe_fast",
            "strobe_medium",
            "strobe_slow",
            "pulse",
        ]
        for shutter in valid_shutters:
            resolved = ResolvedChannels(shutter=shutter, color="white", gobo="open")
            is_valid, _ = validator.validate(resolved)
            assert is_valid is True, f"Shutter '{shutter}' should be valid"

    def test_all_valid_colors(self, validator):
        """Test all valid color values."""
        valid_colors = [
            "red",
            "blue",
            "green",
            "yellow",
            "magenta",
            "cyan",
            "orange",
            "purple",
            "amber",
            "lime",
            "white",
            "warm_white",
            "cool_white",
            "uv",
        ]
        for color in valid_colors:
            resolved = ResolvedChannels(shutter="open", color=color, gobo="open")
            is_valid, _ = validator.validate(resolved)
            assert is_valid is True, f"Color '{color}' should be valid"

    def test_all_valid_gobos(self, validator):
        """Test all valid gobo values."""
        valid_gobos = [
            "open",
            "circles",
            "triangles",
            "stars",
            "diamonds",
            "clouds",
            "prism",
            "shatter",
            "dots",
            "flame",
            "water",
            "foliage",
            "abstract",
        ]
        for gobo in valid_gobos:
            resolved = ResolvedChannels(shutter="open", color="white", gobo=gobo)
            is_valid, _ = validator.validate(resolved)
            assert is_valid is True, f"Gobo '{gobo}' should be valid"

    def test_invalid_shutter(self, validator):
        """Test invalid shutter value."""
        resolved = ResolvedChannels(shutter="invalid_value", color="blue", gobo="open")
        is_valid, errors = validator.validate(resolved)
        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid shutter value" in errors[0]
        assert "invalid_value" in errors[0]

    def test_invalid_color(self, validator):
        """Test invalid color value."""
        resolved = ResolvedChannels(shutter="open", color="invalid_color", gobo="open")
        is_valid, errors = validator.validate(resolved)
        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid color value" in errors[0]
        assert "invalid_color" in errors[0]

    def test_invalid_gobo(self, validator):
        """Test invalid gobo value."""
        resolved = ResolvedChannels(shutter="open", color="white", gobo="invalid_gobo")
        is_valid, errors = validator.validate(resolved)
        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid gobo value" in errors[0]
        assert "invalid_gobo" in errors[0]

    def test_multiple_invalid_values(self, validator):
        """Test multiple invalid values."""
        resolved = ResolvedChannels(shutter="bad_shutter", color="bad_color", gobo="bad_gobo")
        is_valid, errors = validator.validate(resolved)
        assert is_valid is False
        assert len(errors) == 3
        assert any("shutter" in err.lower() for err in errors)
        assert any("color" in err.lower() for err in errors)
        assert any("gobo" in err.lower() for err in errors)

    def test_incompatible_closed_shutter_with_gobo(self, validator):
        """Test incompatible: closed shutter with non-open gobo."""
        resolved = ResolvedChannels(shutter="closed", color="white", gobo="stars")
        is_valid, errors = validator.validate(resolved)
        assert is_valid is False
        assert any("Incompatible" in err for err in errors)
        assert any("closed shutter" in err for err in errors)

    def test_closed_shutter_with_open_gobo_valid(self, validator):
        """Test closed shutter with open gobo is valid."""
        resolved = ResolvedChannels(shutter="closed", color="white", gobo="open")
        is_valid, _ = validator.validate(resolved)
        assert is_valid is True


class TestChannelResolver:
    """Test ChannelResolver."""

    @pytest.fixture
    def resolver(self):
        """Create resolver instance."""
        validator = BasicChannelValidator()
        return ChannelResolver(validator)

    @pytest.fixture
    def defaults(self):
        """Create default channel defaults."""
        return ChannelDefaults(shutter="open", color="white", gobo="open")

    def test_no_overrides(self, resolver, defaults):
        """Test resolution with no overrides."""
        spec = ChannelSpecification()
        resolved = resolver.resolve(defaults, spec)

        assert resolved.shutter == "open"
        assert resolved.color == "white"
        assert resolved.gobo == "open"

    def test_partial_overrides(self, resolver, defaults):
        """Test resolution with partial overrides."""
        spec = ChannelSpecification(shutter="strobe_fast", gobo="stars")
        resolved = resolver.resolve(defaults, spec)

        assert resolved.shutter == "strobe_fast"  # Override
        assert resolved.color == "white"  # Inherited
        assert resolved.gobo == "stars"  # Override

    def test_all_overrides(self, resolver, defaults):
        """Test resolution with all overrides."""
        spec = ChannelSpecification(shutter="strobe_fast", color="red", gobo="stars")
        resolved = resolver.resolve(defaults, spec)

        assert resolved.shutter == "strobe_fast"
        assert resolved.color == "red"
        assert resolved.gobo == "stars"

    def test_shutter_only_override(self, resolver, defaults):
        """Test override shutter only."""
        spec = ChannelSpecification(shutter="pulse")
        resolved = resolver.resolve(defaults, spec)

        assert resolved.shutter == "pulse"
        assert resolved.color == "white"
        assert resolved.gobo == "open"

    def test_color_only_override(self, resolver, defaults):
        """Test override color only."""
        spec = ChannelSpecification(color="blue")
        resolved = resolver.resolve(defaults, spec)

        assert resolved.shutter == "open"
        assert resolved.color == "blue"
        assert resolved.gobo == "open"

    def test_gobo_only_override(self, resolver, defaults):
        """Test override gobo only."""
        spec = ChannelSpecification(gobo="clouds")
        resolved = resolver.resolve(defaults, spec)

        assert resolved.shutter == "open"
        assert resolved.color == "white"
        assert resolved.gobo == "clouds"

    def test_invalid_combination_raises(self, resolver, defaults):
        """Test invalid combination raises ValueError."""
        spec = ChannelSpecification(shutter="invalid_value")

        with pytest.raises(ValueError, match="Invalid channel combination"):
            resolver.resolve(defaults, spec)

    def test_error_message_includes_details(self, resolver, defaults):
        """Test error message includes resolved values."""
        spec = ChannelSpecification(shutter="invalid_value")

        with pytest.raises(ValueError) as exc_info:
            resolver.resolve(defaults, spec)

        error_msg = str(exc_info.value)
        assert "shutter=invalid_value" in error_msg
        assert "color=white" in error_msg
        assert "gobo=open" in error_msg

    def test_fallback_on_error(self, resolver, defaults):
        """Test fallback resolver returns defaults on error."""
        spec = ChannelSpecification(shutter="invalid_value")

        resolved = resolver.resolve_with_fallback(defaults, spec)

        # Should fall back to defaults
        assert resolved.shutter == "open"
        assert resolved.color == "white"
        assert resolved.gobo == "open"

    def test_fallback_on_incompatible_combination(self, resolver, defaults):
        """Test fallback on incompatible combination."""
        spec = ChannelSpecification(shutter="closed", gobo="stars")

        resolved = resolver.resolve_with_fallback(defaults, spec)

        # Should fall back to defaults
        assert resolved.shutter == "open"
        assert resolved.color == "white"
        assert resolved.gobo == "open"

    def test_fallback_succeeds_on_valid_spec(self, resolver, defaults):
        """Test fallback returns resolved values when valid."""
        spec = ChannelSpecification(shutter="strobe_fast", color="red")

        resolved = resolver.resolve_with_fallback(defaults, spec)

        # Should use resolved values (not fallback)
        assert resolved.shutter == "strobe_fast"
        assert resolved.color == "red"
        assert resolved.gobo == "open"

    def test_multiple_sections(self, resolver):
        """Test resolving multiple sections with different overrides."""
        defaults = ChannelDefaults(shutter="open", color="white", gobo="open")

        sections = [
            ChannelSpecification(color="blue"),
            ChannelSpecification(color="purple", gobo="clouds"),
            ChannelSpecification(shutter="strobe_fast", color="red", gobo="stars"),
        ]

        results = [resolver.resolve(defaults, spec) for spec in sections]

        # Section 1: blue color only
        assert results[0].shutter == "open"
        assert results[0].color == "blue"
        assert results[0].gobo == "open"

        # Section 2: purple + clouds
        assert results[1].shutter == "open"
        assert results[1].color == "purple"
        assert results[1].gobo == "clouds"

        # Section 3: all overrides
        assert results[2].shutter == "strobe_fast"
        assert results[2].color == "red"
        assert results[2].gobo == "stars"

    def test_custom_defaults(self, resolver):
        """Test resolution with custom job defaults."""
        defaults = ChannelDefaults(shutter="pulse", color="blue", gobo="clouds")

        spec = ChannelSpecification(color="red")
        resolved = resolver.resolve(defaults, spec)

        assert resolved.shutter == "pulse"  # Custom default
        assert resolved.color == "red"  # Override
        assert resolved.gobo == "clouds"  # Custom default
