"""Math utilities for common operations."""

from __future__ import annotations

import math
from typing import TypeVar

import numpy as np

Number = TypeVar("Number", int, float, np.number)


def trunc_to(x: float, decimals: int) -> float:
    p = 10**decimals
    return float(math.trunc(x * p) / p)  # truncates toward 0 (no rounding)


def clamp(value: Number, min_val: Number, max_val: Number) -> Number:
    """Clamp value to range [min_val, max_val].

    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))


def normalize(arr: np.ndarray, min_val: float = 0.0, max_val: float = 1.0) -> np.ndarray:
    """Normalize array to range [min_val, max_val].

    Args:
        arr: Input array
        min_val: Target minimum value
        max_val: Target maximum value

    Returns:
        Normalized array
    """
    arr_min = arr.min()
    arr_max = arr.max()

    if arr_max - arr_min < 1e-9:
        return np.full_like(arr, min_val)

    normalized = (arr - arr_min) / (arr_max - arr_min)
    result: np.ndarray = normalized * (max_val - min_val) + min_val
    return result


def lerp(a: Number, b: Number, t: float) -> float:
    """Linear interpolation between a and b.

    Args:
        a: Start value
        b: End value
        t: Interpolation factor [0, 1]

    Returns:
        Interpolated value
    """
    return float(a) + (float(b) - float(a)) * t
