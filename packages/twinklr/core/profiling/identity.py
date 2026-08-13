"""Content-derived identity helpers for profiling artifacts.

Identity keys written by the profiling pipeline are derived from the content
they describe, never from randomness: re-ingesting an unchanged archive must
produce byte-identical primary keys so the feature store's
``INSERT OR REPLACE`` upserts replace rows instead of accumulating duplicates.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
import uuid

# Namespace for effect-event identity. Computed once; changing it invalidates
# every previously written effect_event_id.
EFFECT_EVENT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "twinklr.profiling.effect_event")


def canonical_json(data: dict[str, Any]) -> str:
    """Serialize a mapping to a stable, compact JSON string."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_digest(data: dict[str, Any]) -> str:
    """Return the SHA-256 hex digest of *data*'s canonical JSON form."""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def content_uuid5(namespace: uuid.UUID, key: str) -> str:
    """Return a deterministic UUID5 string for *key* within *namespace*."""
    return str(uuid.uuid5(namespace, key))
