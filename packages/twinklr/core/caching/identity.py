"""Deterministic cache identity derivation.

The agent cache is addressed by ``<cache_root>/<domain>/<session_id>/...``, so a
random session ID makes every run write into a subtree no later run can reach.
These helpers derive a session ID from job *inputs* — audio content and the
configs — so an identical re-run addresses the same subtree and reuses work.

Only content is hashed, never paths: hashing the audio path would make the ID
depend on where the file happens to live.
"""

from __future__ import annotations

from collections.abc import Iterable
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_CHUNK_BYTES = 1024 * 1024

SESSION_ID_LENGTH = 16
"""Hex characters kept from the derived digest (64 bits of collision space)."""

ENVIRONMENT_CONFIG_KEYS = ("project_root", "output_dir", "llm_api_key")
"""Top-level config keys describing *where* a run happens rather than what it
produces. Excluded from the derived ID so relocating a checkout or rotating a
key does not orphan the cache."""


def hash_file_content(path: Path | str) -> str:
    """Return the SHA256 of a file's bytes, read in chunks.

    Args:
        path: File to hash

    Returns:
        Hex digest of the file's content

    Raises:
        FileNotFoundError: If the file does not exist
    """
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def config_fingerprint(
    *configs: BaseModel | dict[str, Any] | None,
    exclude: Iterable[str] = (),
) -> str:
    """Return a stable hash over one or more configuration objects.

    Pydantic models are dumped in JSON mode so secrets serialize to their masked
    form rather than an unstable object repr. Keys are sorted so dict ordering
    cannot perturb the result.

    Args:
        *configs: Config models or plain dicts (``None`` entries are skipped)
        exclude: Top-level keys dropped from every config before hashing

    Returns:
        Hex digest over the canonical encoding of all configs
    """
    excluded = set(exclude)
    payload: list[Any] = []
    for config in configs:
        if config is None:
            continue
        dumped = config.model_dump(mode="json") if isinstance(config, BaseModel) else dict(config)
        payload.append({k: v for k, v in dumped.items() if k not in excluded})

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_session_id(
    *,
    audio_path: Path | str,
    configs: tuple[BaseModel | dict[str, Any] | None, ...] = (),
    prefix: str = "sess",
) -> str:
    """Derive a deterministic session ID from job inputs.

    The same audio content and the same configuration always produce the same
    ID, in this process or any other; changing either changes it.

    Keys in :data:`ENVIRONMENT_CONFIG_KEYS` are excluded, so moving the checkout
    or rotating an API key does not orphan previously cached work.

    Args:
        audio_path: Audio file whose *content* identifies the job
        configs: Configuration objects that affect the job's outputs
        prefix: Human-readable prefix kept on the returned ID

    Returns:
        Session ID of the form ``<prefix>_<hex>``

    Raises:
        FileNotFoundError: If the audio file does not exist
    """
    digest = hashlib.sha256()
    digest.update(hash_file_content(audio_path).encode("utf-8"))
    digest.update(b"\x00")
    digest.update(config_fingerprint(*configs, exclude=ENVIRONMENT_CONFIG_KEYS).encode("utf-8"))

    return f"{prefix}_{digest.hexdigest()[:SESSION_ID_LENGTH]}"
