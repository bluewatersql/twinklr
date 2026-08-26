"""Asset catalog persistence and reuse checking.

Handles loading, saving, and querying the persistent asset catalog.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile

from PIL import Image
from pydantic import ValidationError

from twinklr.core.agents.assets.models import AssetCatalog, AssetSpec, CatalogEntry

logger = logging.getLogger(__name__)


def validate_asset_image(file_path: Path, spec: AssetSpec) -> tuple[bool, str | None]:
    """Validate that an existing asset is a non-empty PNG of the requested dimensions."""
    try:
        if file_path.stat().st_size == 0:
            return False, "Existing image is empty"
        with Image.open(file_path) as image:
            image_format = image.format
            width, height = image.size
            image.load()
    except (OSError, ValueError) as error:
        return False, f"Image validation failed: {error}"
    if image_format != "PNG":
        return False, f"Image type mismatch: expected PNG, got {image_format or 'unknown'}"
    if width != spec.width or height != spec.height:
        return False, (
            f"Dimension mismatch: expected {spec.width}x{spec.height}, got {width}x{height}"
        )
    return True, None


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
    if not catalog_path.exists():
        logger.info("Asset catalog absent at %s; starting a new catalog", catalog_path)
        return AssetCatalog(catalog_id="default")
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog = AssetCatalog.model_validate(data)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as error:
        raise ValueError(f"Could not read asset catalog {catalog_path}: {error}") from error
    logger.debug("Loaded catalog with %d entries from %s", len(catalog.entries), catalog_path)
    return catalog


def save_catalog(catalog: AssetCatalog, catalog_path: Path) -> None:
    """Save catalog to disk as JSON.

    Args:
        catalog: The catalog to persist.
        catalog_path: Path to write asset_catalog.json.
    """
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    data = catalog.model_dump(mode="json")
    payload = json.dumps(data, indent=2)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=catalog_path.parent,
            prefix=f".{catalog_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(catalog_path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
    logger.debug(
        "Saved catalog with %d entries to %s",
        len(catalog.entries),
        catalog_path,
    )


def check_reuse(
    catalog: AssetCatalog,
    spec: AssetSpec,
    *,
    assets_dir: Path,
    source_plan_id: str,
) -> CatalogEntry | None:
    """Check if an existing catalog entry can be reused for this spec.

    Uses prompt_hash for exact-match caching.

    Args:
        catalog: The existing catalog.
        spec: The spec to check (must have prompt or text_content set).
        assets_dir: Root used to resolve and contain the stored relative path.
        source_plan_id: Plan/song identity that owns the reusable entry.

    Returns:
        Existing CatalogEntry if reusable, None otherwise.
    """
    prompt_hash = compute_prompt_hash(spec)
    entry = catalog.find_by_prompt_hash(prompt_hash, source_plan_id)
    if entry is None:
        return None

    # Missing files are cache misses; present but invalid paid outputs are loud.
    file_path = _resolve_catalog_path(entry, assets_dir)
    if not file_path.exists():
        logger.debug(
            "Cache hit for %s but file missing: %s",
            spec.spec_id,
            entry.file_path,
        )
        return None
    valid, error = validate_asset_image(file_path, spec)
    if not valid:
        raise ValueError(f"Cached image validation failed for {entry.file_path!r}: {error}")

    logger.debug("Cache hit for %s → %s", spec.spec_id, entry.asset_id)
    return entry


def check_reuse_by_spec_id(
    catalog: AssetCatalog,
    spec: AssetSpec,
    *,
    assets_dir: Path,
    source_plan_id: str,
) -> CatalogEntry | None:
    """Check reuse by deterministic spec_id + dimensions (pre-enrichment).

    Image specs don't have a prompt before LLM enrichment, and enrichment
    is non-deterministic. This function matches by the stable identity
    (spec_id derived from motif_id + category) so existing assets can be
    reused without re-running enrichment.

    Args:
        catalog: The existing catalog.
        spec: The spec to check (prompt may not be set yet).
        assets_dir: Root used to resolve and contain the stored relative path.
        source_plan_id: Plan/song identity that owns the reusable entry.

    Returns:
        Existing CatalogEntry if reusable, None otherwise.
    """
    entry = next(
        (
            candidate
            for candidate in catalog.entries
            if candidate.spec.spec_id == spec.spec_id
            and candidate.spec.width == spec.width
            and candidate.spec.height == spec.height
            and candidate.source_plan_id == source_plan_id
            and candidate.status.value != "failed"
        ),
        None,
    )
    if entry is None:
        return None

    # Missing files are cache misses; present but invalid paid outputs are loud.
    file_path = _resolve_catalog_path(entry, assets_dir)
    if not file_path.exists():
        logger.debug(
            "Spec-id cache hit for %s but file missing: %s",
            spec.spec_id,
            entry.file_path,
        )
        return None
    valid, error = validate_asset_image(file_path, spec)
    if not valid:
        raise ValueError(f"Cached image validation failed for {entry.file_path!r}: {error}")

    logger.debug("Spec-id cache hit for %s → %s", spec.spec_id, entry.asset_id)
    return entry


def _resolve_catalog_path(entry: CatalogEntry, assets_dir: Path) -> Path:
    """Resolve one catalog path while rejecting legacy unsafe path forms."""
    relative = Path(entry.file_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe catalog file_path {entry.file_path!r}")
    root = assets_dir.resolve()
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Catalog file_path escapes assets root: {entry.file_path!r}")
    return resolved
