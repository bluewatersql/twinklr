"""Tests for enhanced config loader with YAML support.

Following TDD: These tests are written BEFORE implementation.
They should FAIL initially (RED phase).
"""

import json
from pathlib import Path

import pytest
import yaml

# Import config module directly
import blinkb0t.core.config.loader as config_loader


@pytest.fixture
def sample_config_data():
    """Sample configuration data for testing."""
    return {
        "openai_api_key": "sk-test123",
        "logging": {"level": "INFO", "format": "%(message)s"},
        "audio_processing": {"sample_rate": 22050, "hop_length": 512},
        "cache_dir": "data/cache",
    }


def test_detect_format_json():
    """Test format detection for JSON files."""
    assert config_loader.detect_format("config.json") == "json"
    assert config_loader.detect_format(Path("config.json")) == "json"


def test_detect_format_yaml():
    """Test format detection for YAML files."""
    assert config_loader.detect_format("config.yaml") == "yaml"
    assert config_loader.detect_format("config.yml") == "yaml"
    assert config_loader.detect_format(Path("config.yaml")) == "yaml"
    assert config_loader.detect_format(Path("config.yml")) == "yaml"


def test_detect_format_invalid():
    """Test format detection for invalid extensions."""
    with pytest.raises(ValueError) as exc_info:
        config_loader.detect_format("config.txt")

    assert "Unsupported config format" in str(exc_info.value)


def test_load_config_json(tmp_path, sample_config_data):
    """Test loading JSON config."""
    config_file = tmp_path / "config.json"
    with Path.open(config_file, "w") as f:
        json.dump(sample_config_data, f)

    config = config_loader.load_config(config_file)

    assert config["openai_api_key"] == "sk-test123"
    assert config["logging"]["level"] == "INFO"
    assert config["cache_dir"] == "data/cache"


def test_load_config_yaml(tmp_path, sample_config_data):
    """Test loading YAML config."""
    config_file = tmp_path / "config.yaml"
    with Path.open(config_file, "w") as f:
        yaml.dump(sample_config_data, f)

    config = config_loader.load_config(config_file)

    assert config["openai_api_key"] == "sk-test123"
    assert config["logging"]["level"] == "INFO"
    assert config["cache_dir"] == "data/cache"


def test_load_config_yml_extension(tmp_path, sample_config_data):
    """Test loading YAML config with .yml extension."""
    config_file = tmp_path / "config.yml"
    with Path.open(config_file, "w") as f:
        yaml.dump(sample_config_data, f)

    config = config_loader.load_config(config_file)

    assert config["openai_api_key"] == "sk-test123"


def test_load_config_file_not_found():
    """Test loading non-existent config file."""
    with pytest.raises(FileNotFoundError):
        config_loader.load_config("nonexistent.json")


def test_load_config_invalid_json(tmp_path):
    """Test loading invalid JSON."""
    config_file = tmp_path / "invalid.json"
    config_file.write_text("{ invalid json }")

    with pytest.raises(ValueError) as exc_info:
        config_loader.load_config(config_file)

    assert "Invalid JSON" in str(exc_info.value)


def test_load_config_invalid_yaml(tmp_path):
    """Test loading invalid YAML."""
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("invalid: yaml: content: [")

    with pytest.raises(ValueError) as exc_info:
        config_loader.load_config(config_file)

    assert "Invalid YAML" in str(exc_info.value)


def test_load_config_yaml_with_comments(tmp_path):
    """Test loading YAML with comments (YAML-specific feature)."""
    config_file = tmp_path / "config.yaml"
    yaml_content = """
# Application configuration
openai_api_key: sk-test123

# Logging settings
logging:
  level: INFO  # Can be DEBUG, INFO, WARNING, ERROR
  format: "%(message)s"

# Audio processing
audio_processing:
  sample_rate: 22050
  hop_length: 512
"""
    config_file.write_text(yaml_content)

    config = config_loader.load_config(config_file)

    assert config["openai_api_key"] == "sk-test123"
    assert config["logging"]["level"] == "INFO"


def test_load_config_empty_yaml(tmp_path):
    """Test loading empty YAML file."""
    config_file = tmp_path / "empty.yaml"
    config_file.write_text("")

    config = config_loader.load_config(config_file)

    # Empty YAML should return empty dict
    assert config == {}


def test_load_config_yaml_multiline_strings(tmp_path):
    """Test YAML-specific multiline string support."""
    config_file = tmp_path / "config.yaml"
    yaml_content = """
description: |
  This is a multiline
  description that spans
  multiple lines.
value: 123
"""
    config_file.write_text(yaml_content)

    config = config_loader.load_config(config_file)

    assert "This is a multiline" in config["description"]
    assert "multiple lines" in config["description"]
    assert config["value"] == 123


def test_load_config_autodetect_format(tmp_path, sample_config_data):
    """Test that format is auto-detected from extension."""
    # Create both JSON and YAML files
    json_file = tmp_path / "config.json"
    yaml_file = tmp_path / "config.yaml"

    with Path.open(json_file, "w") as f:
        json.dump(sample_config_data, f)

    with Path.open(yaml_file, "w") as f:
        yaml.dump(sample_config_data, f)

    # Both should load correctly with auto-detection
    json_config = config_loader.load_config(json_file)
    yaml_config = config_loader.load_config(yaml_file)

    assert json_config == yaml_config
    assert json_config["openai_api_key"] == "sk-test123"
