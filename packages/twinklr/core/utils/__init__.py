"""Shared utilities for Twinklr."""

from twinklr.core.utils.json import read_json, write_json
from twinklr.core.utils.math import clamp, lerp, normalize

# Note: validation module not imported here to avoid circular import
# Import directly: from twinklr.core.utils import validation

__all__ = [
    "clamp",
    "lerp",
    "normalize",
    "read_json",
    "write_json",
]
