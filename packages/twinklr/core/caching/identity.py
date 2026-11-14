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

ENVIRONMENT_CONFIG_KEYS = ("project_root", "output_dir", "cache_dir", "llm_api_key")
"""Top-level config keys describing *where* a run happens rather than what it
produces. Excluded from the derived ID so relocating a checkout or rotating a
key does not orphan the cache."""

RENDER_ONLY_CONFIG_KEYS = (
    "moving_heads.initial_states",
    "moving_heads.max_effects",
    "moving_heads.max_xsq_bytes",
)
"""Job keys that change only the moving-head render, never the plan. Excluded from
the derived ID so moving a head's start pose or an output budget does not re-key the
planner's cache. ``moving_heads.mode`` stays in: it changes what the planner is
offered. A legacy job's dump carries none of them, so its ID is unchanged."""


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
        exclude: Keys dropped from every config before hashing; a dotted key such as
            ``"moving_heads.max_effects"`` drops that nested key

    Returns:
        Hex digest over the canonical encoding of all configs
    """
    excluded = set(exclude)
    payload: list[Any] = []
    for config in configs:
        if config is None:
            continue
        dumped = config.model_dump(mode="json") if isinstance(config, BaseModel) else dict(config)
        payload.append(_without(dumped, excluded))

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _without(dumped: dict[str, Any], excluded: set[str]) -> dict[str, Any]:
    """`dumped` without the excluded keys, descending into dicts for dotted keys."""
    kept: dict[str, Any] = {}
    for key, value in dumped.items():
        if key in excluded:
            continue
        nested = {path.split(".", 1)[1] for path in excluded if path.startswith(f"{key}.")}
        kept[key] = _without(value, nested) if nested and isinstance(value, dict) else value
    return kept


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
    or rotating an API key does not orphan previously cached work, and so are the
    render-only keys in :data:`RENDER_ONLY_CONFIG_KEYS`, so they never re-key a plan.

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
    excluded = ENVIRONMENT_CONFIG_KEYS + RENDER_ONLY_CONFIG_KEYS
    digest.update(config_fingerprint(*configs, exclude=excluded).encode("utf-8"))

    return f"{prefix}_{digest.hexdigest()[:SESSION_ID_LENGTH]}"
