"""Tests for JSON utility functions."""

from __future__ import annotations

import pytest

from blinkb0t.core.utils.json import read_json, write_json


@pytest.fixture
def temp_json_file(tmp_path):
    """Create a temporary JSON file path."""
    return tmp_path / "test.json"


def test_write_and_read_json(temp_json_file):
    """Test writing and reading JSON files."""
    data = {
        "string": "value",
        "number": 42,
        "float": 3.14,
        "bool": True,
        "list": [1, 2, 3],
        "nested": {"key": "value"},
    }

    # Write JSON
    write_json(temp_json_file, data)

    # Read JSON
    result = read_json(temp_json_file)

    assert result == data


def test_write_json_creates_parent_dirs(tmp_path):
    """Test that write_json creates parent directories."""
    nested_path = tmp_path / "subdir" / "nested" / "test.json"
    data = {"test": "value"}

    # Parent directories don't exist yet
    assert not nested_path.parent.exists()

    # Write JSON should create them
    write_json(nested_path, data)

    # Parent directories should now exist
    assert nested_path.parent.exists()
    assert nested_path.exists()

    # And data should be readable
    result = read_json(nested_path)
    assert result == data


def test_write_json_with_string_path(temp_json_file):
    """Test write_json with string path."""
    data = {"test": "value"}

    # Pass path as string
    write_json(str(temp_json_file), data)

    # Should be readable
    result = read_json(str(temp_json_file))
    assert result == data


def test_read_json_with_string_path(temp_json_file):
    """Test read_json with string path."""
    data = {"test": "value"}

    write_json(temp_json_file, data)

    # Read with string path
    result = read_json(str(temp_json_file))
    assert result == data


def test_write_json_with_none_values(temp_json_file):
    """Test writing JSON with None values."""
    data = {
        "key1": "value",
        "key2": None,
        "key3": {"nested": None},
    }

    write_json(temp_json_file, data)
    result = read_json(temp_json_file)

    assert result == data


def test_write_json_with_empty_collections(temp_json_file):
    """Test writing JSON with empty collections."""
    data = {
        "empty_list": [],
        "empty_dict": {},
        "empty_string": "",
    }

    write_json(temp_json_file, data)
    result = read_json(temp_json_file)

    assert result == data


def test_read_json_file_not_found(tmp_path):
    """Test reading non-existent JSON file."""
    non_existent = tmp_path / "does_not_exist.json"

    with pytest.raises(FileNotFoundError):
        read_json(non_existent)


def test_read_json_invalid_json(temp_json_file):
    """Test reading invalid JSON."""
    import json

    # Write invalid JSON
    temp_json_file.write_text("{ invalid json }")

    with pytest.raises(json.JSONDecodeError):
        read_json(temp_json_file)


def test_write_json_pretty_formatting(temp_json_file):
    """Test that JSON is written with pretty formatting."""
    data = {"key1": "value1", "key2": {"nested": "value2"}}

    write_json(temp_json_file, data)

    # Read raw text
    text = temp_json_file.read_text()

    # Should have indentation (pretty formatting)
    assert "\n" in text
    assert "  " in text  # Indentation


def test_write_json_unicode(temp_json_file):
    """Test writing JSON with unicode characters."""
    data = {
        "emoji": "🎵🎶",
        "chinese": "你好",
        "arabic": "مرحبا",
    }

    write_json(temp_json_file, data)
    result = read_json(temp_json_file)

    assert result == data
