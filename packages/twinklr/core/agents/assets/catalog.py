"""Asset catalog persistence and reuse checking.

Handles loading, saving, and querying the persistent asset catalog.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from twinklr.core.agents.assets.models import AssetCatalog, AssetSpec, CatalogEntry

logger = logging.getLogger(__name__)


def compute_prompt_hash(spec: AssetSpec) -> str:
    """Compute a deterministic hash for cache matching.

    Hash is based on the generation prompt + dimensions + background mode.
    Used for exact-match reuse across runs.

    Args:
        spec: The asset spec (must have prompt set for image specs,
              or text_content for text specs).

    Returns:
        SHA-256 hex digest.
    """
    parts = [
        spec.prompt or spec.text_content or "",
        spec.negative_prompt or "",
        str(spec.width),
        str(spec.height),
        spec.background.value,
    ]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode()).hexdigest()


def load_catalog(catalog_path: Path) -> AssetCatalog:
    """Load an existing catalog from disk, or return an empty one.

    Args:
        catalog_path: Path to asset_catalog.json.

    Returns:
        AssetCatalog (existing or new empty).
    """
    if catalog_path.exists():
        try:
            data = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog = AssetCatalog.model_validate(data)
            logger.debug(
                "Loaded catalog with %d entries from %s",
                len(catalog.entries),
                catalog_path,
            )
            return catalog
        except Exception:
            logger.warning(
                "Failed to load catalog from %s, starting fresh",
                catalog_path,
                exc_info=True,
            )

    return AssetCatalog(catalog_id="default")


def save_catalog(catalog: AssetCatalog, catalog_path: Path) -> None:
    """Save catalog to disk as JSON.

    Args:
        catalog: The catalog to persist.
        catalog_path: Path to write asset_catalog.json.
    """
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    data = catalog.model_dump(mode="json")
    catalog_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.debug(
        "Saved catalog with %d entries to %s",
        len(catalog.entries),
        catalog_path,
    )


def check_reuse(catalog: AssetCatalog, spec: AssetSpec) -> CatalogEntry | None:
    """Check if an existing catalog entry can be reused for this spec.

    Uses prompt_hash for exact-match caching.

    Args:
        catalog: The existing catalog.
        spec: The spec to check (must have prompt or text_content set).

    Returns:
        Existing CatalogEntry if reusable, None otherwise.
    """
    prompt_hash = compute_prompt_hash(spec)
    entry = catalog.find_by_prompt_hash(prompt_hash)
    if entry is None:
        return None

    # Verify file still exists on disk
    file_path = Path(entry.file_path)
    if not file_path.exists():
        logger.debug(
            "Cache hit for %s but file missing: %s",
            spec.spec_id,
            entry.file_path,
        )
        return None

    logger.debug("Cache hit for %s → %s", spec.spec_id, entry.asset_id)
    return entry
