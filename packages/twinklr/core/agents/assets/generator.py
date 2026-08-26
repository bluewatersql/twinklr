"""Asset generation orchestrator.

Async-first implementation that routes specs to the appropriate generation
backend (OpenAI API for images, PIL for text), validates results, and
builds catalog entries.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import hashlib
import logging
from pathlib import Path
import re

from PIL import Image

from twinklr.core.agents.assets.catalog import compute_prompt_hash, validate_asset_image
from twinklr.core.agents.assets.image_client import OpenAIImageClient
from twinklr.core.agents.assets.models import (
    AssetCategory,
    AssetSpec,
    AssetStatus,
    CatalogEntry,
)
from twinklr.core.agents.assets.pricing import calculate_image_cost
from twinklr.core.agents.assets.text_renderer import TextRenderer

logger = logging.getLogger(__name__)

# Category → directory structure mapping
_CATEGORY_DIRS: dict[AssetCategory, str] = {
    AssetCategory.IMAGE_TEXTURE: "images/textures",
    AssetCategory.IMAGE_CUTOUT: "images/cutouts",
    AssetCategory.TEXT_BANNER: "text/banners",
}


def build_output_path(spec: AssetSpec, assets_dir: Path) -> Path:
    """Build the output file path for a spec.

    Structure: assets/{category_dir}/{WxH}/{filename}.png

    Args:
        spec: The asset spec.
        assets_dir: Root assets directory.

    Returns:
        Full output path.
    """
    category_dir = _CATEGORY_DIRS[spec.category]
    source = spec.motif_id or spec.spec_id
    for identifier in (spec.spec_id, spec.motif_id):
        if identifier is not None and (
            Path(identifier).is_absolute()
            or "/" in identifier
            or "\\" in identifier
            or ".." in identifier
        ):
            raise ValueError(f"Unsafe asset identifier {identifier!r}")
    slug = re.sub(r"[^a-z0-9_-]+", "_", source.lower()).strip("_-") or "asset"
    identity = hashlib.sha256(spec.spec_id.encode("utf-8")).hexdigest()[:12]
    filename = f"{slug}-{identity}"

    if spec.category.is_image():
        # Sub-organize by dimensions
        size_dir = f"{spec.width}x{spec.height}"
        output = assets_dir / category_dir / size_dir / f"{filename}.png"
    else:
        output = assets_dir / category_dir / f"{filename}.png"
    if not output.resolve().is_relative_to(assets_dir.resolve()):
        raise ValueError(f"Unsafe asset identifier {source!r}")
    return output


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
    output_path = build_output_path(spec, assets_dir)
    relative_path = output_path.relative_to(assets_dir).as_posix()
    prompt_hash = compute_prompt_hash(spec)
    now = datetime.now(UTC).isoformat()

    try:
        if output_path.is_file():
            is_valid, validation_error = await asyncio.to_thread(
                validate_asset_image, output_path, spec
            )
            if not is_valid:
                return _make_failed_entry(
                    spec,
                    Path(relative_path),
                    now,
                    prompt_hash,
                    source_plan_id,
                    generation_model="existing-file",
                    error=validation_error or "Existing image validation failed",
                )
            content = output_path.read_bytes()
            return CatalogEntry(
                asset_id=spec.spec_id,
                spec=spec,
                file_path=relative_path,
                content_hash=hashlib.sha256(content).hexdigest(),
                status=AssetStatus.CACHED,
                width=spec.width,
                height=spec.height,
                has_alpha=False,
                file_size_bytes=len(content),
                created_at=now,
                source_plan_id=source_plan_id,
                generation_model="existing-file",
                prompt_hash=prompt_hash,
            )
        if spec.category.is_image():
            entry = await _generate_image(
                spec,
                output_path,
                image_client,
                now=now,
                prompt_hash=prompt_hash,
                source_plan_id=source_plan_id,
            )
            return entry.model_copy(update={"file_path": relative_path})
        elif spec.category.is_text():
            entry = await _generate_text(
                spec,
                output_path,
                text_renderer,
                now=now,
                prompt_hash=prompt_hash,
                source_plan_id=source_plan_id,
            )
            return entry.model_copy(update={"file_path": relative_path})
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
            Path(relative_path),
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
    _is_valid, error = await asyncio.to_thread(validate_asset_image, output_path, spec)

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
            generation_model=image_client.model,
            error=error or "Validation failed",
        )

    image_cost = (
        calculate_image_cost(result.usage, model=image_client.model)
        if result.usage is not None
        else None
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
        generation_model=image_client.model,
        prompt_hash=prompt_hash,
        image_usage=result.usage,
        image_cost=image_cost,
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
