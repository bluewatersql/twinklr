"""Utility functions for audio processing."""

from __future__ import annotations

from typing import Any

import numpy as np


def normalize_to_0_1(arr: np.ndarray) -> np.ndarray:
    """Normalize array to [0, 1] range.

    Args:
        arr: Input array

    Returns:
        Normalized array in [0, 1] range
    """
    arr = np.asarray(arr, dtype=np.float32)
    if arr.size == 0:
        return arr
    mn = float(arr.min())
    mx = float(arr.max())
    if mx - mn < 1e-9:
        return np.zeros_like(arr, dtype=np.float32)
    return (arr - mn) / (mx - mn)


def frames_to_time(frames: np.ndarray, *, sr: int, hop_length: int) -> np.ndarray:
    """Convert frame indices to time in seconds.

    Args:
        frames: Frame indices
        sr: Sample rate
        hop_length: Hop length

    Returns:
        Times in seconds
    """
    import librosa

    result: np.ndarray = librosa.frames_to_time(frames, sr=sr, hop_length=hop_length).astype(
        np.float32
    )
    return result


def time_to_frames(times_s: np.ndarray, *, sr: int, hop_length: int, n_frames: int) -> np.ndarray:
    """Convert times to frame indices, clipped to valid range.

    Args:
        times_s: Times in seconds
        sr: Sample rate
        hop_length: Hop length
        n_frames: Total number of frames

    Returns:
        Frame indices clipped to [0, n_frames-1]
    """
    import librosa

    f: np.ndarray = librosa.time_to_frames(times_s, sr=sr, hop_length=hop_length).astype(int)
    result: np.ndarray = np.clip(f, 0, max(0, n_frames - 1))
    return result


def as_float_list(x: np.ndarray, ndigits: int = 3) -> list[float]:
    """Convert array to rounded float list for JSON serialization.

    Args:
        x: Input array
        ndigits: Number of decimal places

    Returns:
        List of rounded floats
    """
    return [float(v) for v in np.round(np.asarray(x, dtype=np.float32), ndigits).tolist()]


def safe_divide(a: np.ndarray, b: np.ndarray, default: float = 0.0) -> np.ndarray:
    """Element-wise division with safety for zero denominators.

    Args:
        a: Numerator array
        b: Denominator array
        default: Default value for division by zero

    Returns:
        Result of a/b with zeros replaced by default
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(np.abs(b) > 1e-9, a / b, default)
    return np.asarray(result, dtype=np.float32)


def align_to_length(arr: np.ndarray, target_len: int) -> np.ndarray:
    """Align array to target length by truncating or padding.

    Args:
        arr: Input array
        target_len: Target length

    Returns:
        Array with length == target_len
    """
    if len(arr) == target_len:
        return arr
    elif len(arr) > target_len:
        return arr[:target_len]
    else:
        # Pad with edge values
        return np.pad(arr, (0, target_len - len(arr)), mode="edge").astype(arr.dtype)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First vector
        b: Second vector

    Returns:
        Cosine similarity in [0, 1]
    """
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def to_simple_dict(bundle: Any) -> dict[str, Any]:
    """Extract v2.3 features dict from SongBundle (backward compatibility).

    This utility enables gradual migration by providing backward compatibility
    with code expecting the old v2.3 dict format. The v2.3 dict is preserved
    in SongBundle.features field.

    Args:
        bundle: SongBundle instance

    Returns:
        v2.3 features dict (from bundle.features)

    Example:
        bundle = analyzer.analyze("song.mp3")  # Returns SongBundle
        features_dict = to_simple_dict(bundle)  # Extract v2.3 dict
        tempo = features_dict["tempo_bpm"]

    TODO: Technical debt - Remove after agent pipeline migrated to use SongBundle directly.
    """
    # Simply return the features dict from the bundle
    # The features field contains the complete v2.3 dict
    return bundle.features


__all__ = [
    "normalize_to_0_1",
    "frames_to_time",
    "time_to_frames",
    "as_float_list",
    "safe_divide",
    "align_to_length",
    "cosine_similarity",
    "to_simple_dict",
]
