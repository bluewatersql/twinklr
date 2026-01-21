"""Tests for Patch Data Structures.

Tests immutable deep merge and provenance tracking.
"""

from pydantic import ValidationError
import pytest

from blinkb0t.core.sequencer.moving_heads.compile.patch import (
    PatchResult,
    deep_merge,
    merge_with_provenance,
)


class TestDeepMerge:
    """Tests for deep_merge function."""

    def test_merge_empty_dicts(self) -> None:
        """Test merging empty dicts."""
        result = deep_merge({}, {})
        assert result == {}

    def test_merge_disjoint_keys(self) -> None:
        """Test merging dicts with disjoint keys."""
        base = {"a": 1, "b": 2}
        patch = {"c": 3, "d": 4}
        result = deep_merge(base, patch)

        assert result == {"a": 1, "b": 2, "c": 3, "d": 4}

    def test_patch_overwrites_base(self) -> None:
        """Test patch values overwrite base values."""
        base = {"a": 1, "b": 2}
        patch = {"b": 99}
        result = deep_merge(base, patch)

        assert result == {"a": 1, "b": 99}

    def test_nested_merge(self) -> None:
        """Test nested dict merge."""
        base = {
            "outer": {
                "inner1": 1,
                "inner2": 2,
            }
        }
        patch = {
            "outer": {
                "inner2": 99,
                "inner3": 3,
            }
        }
        result = deep_merge(base, patch)

        assert result == {
            "outer": {
                "inner1": 1,
                "inner2": 99,
                "inner3": 3,
            }
        }

    def test_deeply_nested_merge(self) -> None:
        """Test deeply nested merge (3+ levels)."""
        base = {
            "level1": {
                "level2": {
                    "level3": {
                        "a": 1,
                        "b": 2,
                    }
                }
            }
        }
        patch = {
            "level1": {
                "level2": {
                    "level3": {
                        "b": 99,
                        "c": 3,
                    }
                }
            }
        }
        result = deep_merge(base, patch)

        assert result["level1"]["level2"]["level3"] == {"a": 1, "b": 99, "c": 3}

    def test_patch_replaces_non_dict_with_dict(self) -> None:
        """Test patch can replace scalar with dict."""
        base = {"a": 1}
        patch = {"a": {"nested": "value"}}
        result = deep_merge(base, patch)

        assert result == {"a": {"nested": "value"}}

    def test_patch_replaces_dict_with_scalar(self) -> None:
        """Test patch can replace dict with scalar."""
        base = {"a": {"nested": "value"}}
        patch = {"a": 1}
        result = deep_merge(base, patch)

        assert result == {"a": 1}

    def test_original_not_modified(self) -> None:
        """Test original dicts are not modified (immutable)."""
        base = {"a": {"b": 1}}
        patch = {"a": {"c": 2}}

        result = deep_merge(base, patch)

        # Originals unchanged
        assert base == {"a": {"b": 1}}
        assert patch == {"a": {"c": 2}}
        # Result is new
        assert result == {"a": {"b": 1, "c": 2}}

    def test_list_values_replaced_not_merged(self) -> None:
        """Test list values are replaced, not merged."""
        base = {"items": [1, 2, 3]}
        patch = {"items": [4, 5]}
        result = deep_merge(base, patch)

        assert result == {"items": [4, 5]}

    def test_none_values_preserved(self) -> None:
        """Test None values in patch are preserved."""
        base = {"a": 1, "b": 2}
        patch = {"a": None}
        result = deep_merge(base, patch)

        assert result == {"a": None, "b": 2}


class TestPatchResult:
    """Tests for PatchResult model."""

    def test_patch_result_creation(self) -> None:
        """Test PatchResult can be created."""
        result = PatchResult(
            data={"a": 1},
            provenance=["base"],
        )
        assert result.data == {"a": 1}
        assert result.provenance == ["base"]

    def test_patch_result_is_immutable(self) -> None:
        """Test PatchResult is immutable."""
        result = PatchResult(data={"a": 1}, provenance=["base"])
        with pytest.raises(ValidationError):
            result.data = {"b": 2}  # type: ignore[misc]


class TestMergeWithProvenance:
    """Tests for merge_with_provenance function."""

    def test_merge_tracks_provenance(self) -> None:
        """Test merge tracks provenance chain."""
        base = PatchResult(data={"a": 1}, provenance=["template:fan_pulse"])
        patch = {"b": 2}

        result = merge_with_provenance(base, patch, source="preset:CHILL")

        assert result.data == {"a": 1, "b": 2}
        assert "template:fan_pulse" in result.provenance
        assert "preset:CHILL" in result.provenance

    def test_provenance_order_preserved(self) -> None:
        """Test provenance order is preserved."""
        base = PatchResult(data={}, provenance=["step1"])
        result1 = merge_with_provenance(base, {"a": 1}, source="step2")
        result2 = merge_with_provenance(result1, {"b": 2}, source="step3")

        assert result2.provenance == ["step1", "step2", "step3"]

    def test_merge_with_empty_patch(self) -> None:
        """Test merge with empty patch still records provenance."""
        base = PatchResult(data={"a": 1}, provenance=["base"])
        result = merge_with_provenance(base, {}, source="empty_patch")

        assert result.data == {"a": 1}
        assert "empty_patch" in result.provenance


class TestDeepMergeEdgeCases:
    """Tests for edge cases."""

    def test_merge_with_empty_base(self) -> None:
        """Test merge with empty base."""
        result = deep_merge({}, {"a": 1})
        assert result == {"a": 1}

    def test_merge_with_empty_patch(self) -> None:
        """Test merge with empty patch."""
        result = deep_merge({"a": 1}, {})
        assert result == {"a": 1}

    def test_merge_preserves_types(self) -> None:
        """Test merge preserves value types."""
        base = {
            "int_val": 1,
            "float_val": 1.5,
            "str_val": "hello",
            "bool_val": True,
            "list_val": [1, 2],
            "dict_val": {"nested": "dict"},
        }
        patch = {"new_val": "added"}
        result = deep_merge(base, patch)

        assert isinstance(result["int_val"], int)
        assert isinstance(result["float_val"], float)
        assert isinstance(result["str_val"], str)
        assert isinstance(result["bool_val"], bool)
        assert isinstance(result["list_val"], list)
        assert isinstance(result["dict_val"], dict)
