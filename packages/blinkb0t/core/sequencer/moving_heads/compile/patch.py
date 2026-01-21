"""Patch Data Structures for template compilation.

This module provides immutable deep merge operations for applying
patches (presets, modifiers) to templates. Includes provenance
tracking for debugging patch application chains.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PatchResult(BaseModel):
    """Result of a patch operation with provenance tracking.

    Stores the merged data along with a list of sources that
    contributed to the final result. Useful for debugging.

    Attributes:
        data: The merged dictionary data.
        provenance: List of source identifiers in application order.

    Example:
        >>> result = PatchResult(
        ...     data={"a": 1},
        ...     provenance=["template:fan_pulse", "preset:CHILL"],
        ... )
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    data: dict[str, Any] = Field(...)
    provenance: list[str] = Field(default_factory=list)


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge patch into base, returning a new dict.

    This is an immutable operation - neither base nor patch is modified.
    Nested dicts are merged recursively; all other values (including lists)
    are replaced by the patch value.

    Args:
        base: The base dictionary to merge into.
        patch: The patch dictionary to apply.

    Returns:
        A new dictionary with patch applied to base.

    Example:
        >>> base = {"a": {"b": 1, "c": 2}}
        >>> patch = {"a": {"c": 99}}
        >>> deep_merge(base, patch)
        {'a': {'b': 1, 'c': 99}}
    """
    result: dict[str, Any] = {}

    # Start with all keys from base
    for key, base_value in base.items():
        if key in patch:
            patch_value = patch[key]
            # If both are dicts, merge recursively
            if isinstance(base_value, dict) and isinstance(patch_value, dict):
                result[key] = deep_merge(base_value, patch_value)
            else:
                # Otherwise, patch value wins
                result[key] = _deep_copy_value(patch_value)
        else:
            # Key not in patch, keep base value
            result[key] = _deep_copy_value(base_value)

    # Add keys from patch that aren't in base
    for key, patch_value in patch.items():
        if key not in base:
            result[key] = _deep_copy_value(patch_value)

    return result


def _deep_copy_value(value: Any) -> Any:
    """Create a deep copy of a value.

    Handles dicts, lists, and scalar values.
    """
    if isinstance(value, dict):
        return {k: _deep_copy_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_deep_copy_value(item) for item in value]
    else:
        # Scalar values (int, float, str, bool, None) are immutable
        return value


def merge_with_provenance(
    base: PatchResult,
    patch: dict[str, Any],
    source: str,
) -> PatchResult:
    """Merge patch into base with provenance tracking.

    Args:
        base: The base PatchResult to merge into.
        patch: The patch dictionary to apply.
        source: Identifier for the patch source (e.g., "preset:CHILL").

    Returns:
        New PatchResult with merged data and updated provenance.

    Example:
        >>> base = PatchResult(data={"a": 1}, provenance=["template"])
        >>> result = merge_with_provenance(base, {"b": 2}, "preset:X")
        >>> result.provenance
        ['template', 'preset:X']
    """
    merged_data = deep_merge(base.data, patch)
    new_provenance = list(base.provenance) + [source]

    return PatchResult(data=merged_data, provenance=new_provenance)
