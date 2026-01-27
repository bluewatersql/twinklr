"""Fingerprinting utilities for cache keys.

Provides stable input hashing for deterministic cache keys.
"""

import hashlib
import json
from typing import Any


def compute_fingerprint(
    step_id: str,
    step_version: str,
    inputs: dict[str, Any],
) -> str:
    """
    Compute stable fingerprint from step identity and inputs.

    Uses canonical JSON encoding (sorted keys, compact separators)
    to ensure stable hashing across processes and runs.

    Args:
        step_id: Step identifier
        step_version: Step version
        inputs: Input dictionary (only values that affect output)

    Returns:
        SHA256 hex digest (64 chars)

    Example:
        >>> compute_fingerprint(
        ...     "audio.features",
        ...     "1",
        ...     {"audio_sha256": "abc123", "sr": 22050}
        ... )
        'a7b3c...'
    """
    payload = {
        "step_id": step_id,
        "step_version": step_version,
        "inputs": inputs,
    }

    # Canonical JSON: sorted keys, compact separators
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    # SHA256 hash
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
