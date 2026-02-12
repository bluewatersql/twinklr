"""Asset generation orchestrator.

Async-first implementation that routes specs to the appropriate generation
backend (OpenAI API for images, PIL for text), validates results, and
builds catalog entries.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from twinklr.core.agents.assets.catalog import compute_prompt_hash
from twinklr.core.agents.assets.image_client import OpenAIImageClient
from twinklr.core.agents.assets.models import (
    AssetCategory,
    AssetSpec,
    AssetStatus,
    CatalogEntry,
)
from twinklr.core.agents.assets.text_renderer import TextRenderer

logger = logging.getLogger(__name__)

# Category → directory structure mapping
_CATEGORY_DIRS: dict[AssetCategory, str] = {
    AssetCategory.IMAGE_TEXTURE: "images/textures",
    AssetCategory.IMAGE_CUTOUT: "images/cutouts",
    AssetCategory.IMAGE_PLATE: "images/plates",
    AssetCategory.TEXT_BANNER: "text/banners",
    AssetCategory.TEXT_LYRIC: "text/lyrics",
    AssetCategory.SHADER: "shaders",
}


def _build_output_path(spec: AssetSpec, assets_dir: Path) -> Path:
    """Build the output file path for a spec.

    Structure: assets/{category_dir}/{WxH}/{filename}.png

    Args:
        spec: The asset spec.
        assets_dir: Root assets directory.

    Returns:
        Full output path.
    """
    category_dir = _CATEGORY_DIRS.get(spec.category, "other")
    filename = spec.motif_id or spec.spec_id
    # Sanitize filename
    filename = filename.replace(" ", "_").lower()

    if spec.category.is_image():
        # Sub-organize by dimensions
        size_dir = f"{spec.width}x{spec.height}"
        return assets_dir / category_dir / size_dir / f"{filename}.png"
    else:
        return assets_dir / category_dir / f"{filename}.png"


def _validate_image(file_path: Path, spec: AssetSpec) -> tuple[bool, str | None]:
    """Validate a generated image with PIL.

    Checks dimensions and alpha channel presence.

    Args:
        file_path: Path to the generated image.
        spec: The spec for expected properties.

    Returns:
        (is_valid, error_message_or_none)
    """
    try:
        img = Image.open(file_path)
        w, h = img.size

        if w != spec.width or h != spec.height:
            return False, (f"Dimension mismatch: expected {spec.width}x{spec.height}, got {w}x{h}")

        return True, None

    except Exception as e:
        return False, f"Image validation failed: {e}"


def _make_failed_entry(
    spec: AssetSpec,
    output_path: Path,
    now: str,
    prompt_hash: str,
    source_plan_id: str,
    generation_model: str,
    error: str,
) -> CatalogEntry:
    """Build a CatalogEntry for a failed generation."""
    return CatalogEntry(
        asset_id=spec.spec_id,
        spec=spec,
        file_path=str(output_path),
        content_hash="",
        status=AssetStatus.FAILED,
        width=spec.width,
        height=spec.height,
        has_alpha=False,
        file_size_bytes=0,
        created_at=now,
        source_plan_id=source_plan_id,
        generation_model=generation_model,
        prompt_hash=prompt_hash,
        error=error,
    )


async def generate_asset(
    spec: AssetSpec,
    assets_dir: Path,
    *,
    image_client: OpenAIImageClient | None = None,
    text_renderer: TextRenderer | None = None,
    source_plan_id: str = "",
) -> CatalogEntry:
    """Generate a single asset and return a catalog entry.

    Routes to the appropriate backend based on spec category.
    Image generation uses the async OpenAI client. Text generation
    wraps the sync PIL renderer in asyncio.to_thread().

    Args:
        spec: The enriched AssetSpec (prompt or text_content set).
        assets_dir: Root assets directory.
        image_client: Async OpenAI image client (required for image specs).
        text_renderer: PIL text renderer (required for text specs).
        source_plan_id: GroupPlanSet ID for provenance.

    Returns:
        CatalogEntry with generation result.
    """
    output_path = _build_output_path(spec, assets_dir)
    prompt_hash = compute_prompt_hash(spec)
    now = datetime.now(timezone.utc).isoformat()

    try:
        if spec.category.is_image():
            return await _generate_image(
                spec,
                output_path,
                image_client,
                now=now,
                prompt_hash=prompt_hash,
                source_plan_id=source_plan_id,
            )
        elif spec.category.is_text():
            return await _generate_text(
                spec,
                output_path,
                text_renderer,
                now=now,
                prompt_hash=prompt_hash,
                source_plan_id=source_plan_id,
            )
        else:
            return _make_failed_entry(
                spec,
                output_path,
                now,
                prompt_hash,
                source_plan_id,
                generation_model="none",
                error=f"Unsupported category: {spec.category.value}",
            )

    except Exception as e:
        logger.error("Asset generation failed for %s: %s", spec.spec_id, e)
        return _make_failed_entry(
            spec,
            output_path,
            now,
            prompt_hash,
            source_plan_id,
            generation_model="unknown",
            error=str(e),
        )


async def _generate_image(
    spec: AssetSpec,
    output_path: Path,
    image_client: OpenAIImageClient | None,
    *,
    now: str,
    prompt_hash: str,
    source_plan_id: str,
) -> CatalogEntry:
    """Generate an image via async OpenAI Images API."""
    if not spec.prompt:
        return _make_failed_entry(
            spec,
            output_path,
            now,
            prompt_hash,
            source_plan_id,
            generation_model="none",
            error="No prompt set on image spec",
        )

    if image_client is None:
        return _make_failed_entry(
            spec,
            output_path,
            now,
            prompt_hash,
            source_plan_id,
            generation_model="none",
            error="No image client provided",
        )

    result = await image_client.generate(
        prompt=spec.prompt,
        output_path=output_path,
        width=spec.width,
        height=spec.height,
        background=spec.background,
    )

    # Validate (CPU-bound PIL work — run in thread)
    _is_valid, error = await asyncio.to_thread(_validate_image, output_path, spec)

    # Detect alpha
    try:
        img = Image.open(output_path)
        has_alpha = img.mode == "RGBA"
    except Exception:
        has_alpha = False

    if not _is_valid:
        return _make_failed_entry(
            spec,
            output_path,
            now,
            prompt_hash,
            source_plan_id,
            generation_model=image_client._model,
            error=error or "Validation failed",
        )

    return CatalogEntry(
        asset_id=spec.spec_id,
        spec=spec,
        file_path=str(output_path),
        content_hash=result.content_hash,
        status=AssetStatus.CREATED,
        width=spec.width,
        height=spec.height,
        has_alpha=has_alpha,
        file_size_bytes=result.file_size_bytes,
        created_at=now,
        source_plan_id=source_plan_id,
        generation_model=image_client._model,
        prompt_hash=prompt_hash,
    )


async def _generate_text(
    spec: AssetSpec,
    output_path: Path,
    text_renderer: TextRenderer | None,
    *,
    now: str,
    prompt_hash: str,
    source_plan_id: str,
) -> CatalogEntry:
    """Generate a text asset via PIL (sync PIL wrapped in asyncio.to_thread)."""
    if not spec.text_content:
        return _make_failed_entry(
            spec,
            output_path,
            now,
            prompt_hash,
            source_plan_id,
            generation_model="pil",
            error="No text_content set on text spec",
        )

    if text_renderer is None:
        return _make_failed_entry(
            spec,
            output_path,
            now,
            prompt_hash,
            source_plan_id,
            generation_model="pil",
            error="No text renderer provided",
        )

    # PIL is CPU-bound — run in thread to avoid blocking the event loop
    result = await asyncio.to_thread(text_renderer.render, spec, output_path)

    return CatalogEntry(
        asset_id=spec.spec_id,
        spec=spec,
        file_path=str(output_path),
        content_hash=result.content_hash,
        status=AssetStatus.CREATED,
        width=spec.width,
        height=spec.height,
        has_alpha=True,  # Text is always RGBA
        file_size_bytes=result.file_size_bytes,
        created_at=now,
        source_plan_id=source_plan_id,
        generation_model="pil",
        prompt_hash=prompt_hash,
    )
