"""Shared utilities for BlinkB0t."""

from blinkb0t.core.utils.json import read_json, write_json
from blinkb0t.core.utils.math import clamp, lerp, normalize

# Note: validation module not imported here to avoid circular import
# Import directly: from blinkb0t.core.utils import validation

__all__ = [
    "read_json",
    "write_json",
    "clamp",
    "normalize",
    "lerp",
]
