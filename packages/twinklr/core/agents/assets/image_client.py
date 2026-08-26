"""Single-attempt OpenAI Images API client for the guarded asset path.

Async-first implementation wrapping the provider image capability with no ambiguous
paid-response retry, plus error handling, local resizing, and SHA-256 hashing.

Supports the configured OpenAI Images API model which:
- Returns base64 by default (no response_format needed)
- Uses output_format (png/webp/jpeg) instead of response_format
- Only supports sizes: 1024x1024, 1024x1536, 1536x1024, auto
- Generates at API size, then resizes locally if target differs
"""

from __future__ import annotations

import asyncio
import hashlib
from io import BytesIO
import logging
from pathlib import Path
from typing import Literal, cast

from openai import (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
)
from PIL import Image

from twinklr.core.agents.assets.models import ImageGenerationUsage as CatalogImageUsage
from twinklr.core.agents.assets.models import ImageResult
from twinklr.core.agents.providers.base import ImageBackground, ImageSize, LLMProvider
from twinklr.core.config.models import AgentOrchestrationConfig
from twinklr.core.sequencer.vocabulary import BackgroundMode

logger = logging.getLogger(__name__)

# Errors worth retrying
_RETRYABLE_ERRORS = (APIConnectionError, APITimeoutError, RateLimitError)

# OpenAI Images API supported sizes
_SUPPORTED_SIZES = {"1024x1024", "1024x1536", "1536x1024", "auto"}


def _select_api_size(width: int, height: int) -> ImageSize:
    """Select the best API size for the target dimensions.

    The configured OpenAI Images API model supports 1024x1024, 1024x1536,
    1536x1024, or auto.
    We pick the smallest that covers the target and resize locally afterward.

    Args:
        width: Target width in pixels.
        height: Target height in pixels.

    Returns:
        API size string (e.g., '1024x1024').
    """
    exact = f"{width}x{height}"
    if exact in _SUPPORTED_SIZES:
        return cast("ImageSize", exact)

    # Pick smallest supported size that covers the target
    if width <= 1024 and height <= 1024:
        return "1024x1024"
    elif width <= 1024 and height <= 1536:
        return "1024x1536"
    elif width <= 1536 and height <= 1024:
        return "1536x1024"
    else:
        return "auto"


def _process_image_bytes(
    raw_bytes: bytes,
    width: int,
    height: int,
    output_path: Path,
) -> ImageResult:
    """Decode, resize, hash, and write image bytes to disk.

    Pure CPU work — no I/O to external services. Safe to run in a thread
    or inline after an async API call.

    Args:
        raw_bytes: Raw PNG bytes from base64 decoding.
        width: Target width in pixels.
        height: Target height in pixels.
        output_path: Path to write the final PNG.

    Returns:
        ImageResult with file metadata.
    """
    image_bytes = raw_bytes

    # Resize if target differs from API size
    img: Image.Image = Image.open(BytesIO(image_bytes))
    if img.size != (width, height):
        logger.debug("Resizing from %s to %dx%d", img.size, width, height)
        img = img.resize((width, height), Image.Resampling.LANCZOS)

        # Re-encode to PNG
        buf = BytesIO()
        img.save(buf, "PNG")
        image_bytes = buf.getvalue()

    content_hash = hashlib.sha256(image_bytes).hexdigest()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_bytes)

    return ImageResult(
        file_path=str(output_path),
        content_hash=content_hash,
        file_size_bytes=len(image_bytes),
        width=width,
        height=height,
    )


class OpenAIImageClient:
    """Async-first client for generating images via the OpenAI Images API.

    Allows exactly one provider attempt, then handles local resizing, file writing,
    and SHA-256 hashing.

    Args:
        client: AsyncOpenAI client instance.
        model: Image generation model name.
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        model: str | None = None,
        quality: Literal["low", "medium", "high"] = "low",
    ) -> None:
        self._provider = provider
        self._model = model or AgentOrchestrationConfig().image_model
        self._quality = quality

    @property
    def model(self) -> str:
        """Configured image model used for provenance."""
        return self._model

    async def generate(
        self,
        prompt: str,
        output_path: Path,
        width: int = 256,
        height: int = 256,
        background: BackgroundMode = BackgroundMode.TRANSPARENT,
    ) -> ImageResult:
        """Generate an image and save to disk.

        Generates at the nearest supported API size, then resizes locally
        to the target dimensions if they differ.

        Args:
            prompt: Image generation prompt.
            output_path: Path to write the generated PNG.
            width: Target image width in pixels.
            height: Target image height in pixels.
            background: Background mode (transparent or opaque).

        Returns:
            ImageResult with file path, content hash, and dimensions.

        Raises:
            RuntimeError: If the single provider attempt fails.
        """
        api_size = _select_api_size(width, height)
        bg = cast("ImageBackground", background.value)

        try:
            response = await self._provider.generate_image_async(
                model=self._model,
                prompt=prompt,
                size=api_size,
                quality=self._quality,
                output_format="png",
                background=bg,
            )
        except _RETRYABLE_ERRORS as error:
            raise RuntimeError(
                f"Image generation failed after one provider attempt: {error}"
            ) from error
        except Exception as error:
            raise RuntimeError(f"Image generation failed (non-retryable): {error}") from error

        try:
            result = await asyncio.to_thread(
                _process_image_bytes, response.image_bytes, width, height, output_path
            )
        except (OSError, ValueError) as error:
            raise RuntimeError(f"Image generation failed (non-retryable): {error}") from error
        usage = response.usage
        return result.model_copy(
            update={
                "usage": (
                    CatalogImageUsage(
                        input_tokens=usage.input_tokens,
                        input_text_tokens=usage.input_text_tokens,
                        input_image_tokens=usage.input_image_tokens,
                        output_tokens=usage.output_tokens,
                        output_text_tokens=usage.output_text_tokens,
                        output_image_tokens=usage.output_image_tokens,
                        total_tokens=usage.total_tokens,
                    )
                    if usage is not None
                    else None
                )
            }
        )
