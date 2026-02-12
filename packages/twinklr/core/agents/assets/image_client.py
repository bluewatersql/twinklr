"""OpenAI Images API client with retry logic.

Async-first implementation wrapping client.images.generate() with
exponential backoff, error handling, base64 decoding, and SHA-256 hashing.

Supports gpt-image-1.5 (default) which:
- Returns base64 by default (no response_format needed)
- Uses output_format (png/webp/jpeg) instead of response_format
- Only supports sizes: 1024x1024, 1024x1536, 1536x1024, auto
- Generates at API size, then resizes locally if target differs
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
from io import BytesIO
from pathlib import Path

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)
from PIL import Image

from twinklr.core.agents.assets.models import ImageResult
from twinklr.core.sequencer.vocabulary import BackgroundMode

logger = logging.getLogger(__name__)

# Errors worth retrying
_RETRYABLE_ERRORS = (APIConnectionError, APITimeoutError, RateLimitError)

# gpt-image-1.5 supported sizes
_SUPPORTED_SIZES = {"1024x1024", "1024x1536", "1536x1024", "auto"}


def _select_api_size(width: int, height: int) -> str:
    """Select the best API size for the target dimensions.

    gpt-image-1.5 only supports 1024x1024, 1024x1536, 1536x1024, or auto.
    We pick the smallest that covers the target and resize locally afterward.

    Args:
        width: Target width in pixels.
        height: Target height in pixels.

    Returns:
        API size string (e.g., '1024x1024').
    """
    exact = f"{width}x{height}"
    if exact in _SUPPORTED_SIZES:
        return exact

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

    Handles retry logic with async sleep, base64 decoding, local resizing,
    file writing, and SHA-256 hashing. Designed for gpt-image-1.5.

    Args:
        client: AsyncOpenAI client instance.
        model: Image generation model name.
        max_retries: Maximum retry attempts on transient errors.
        retry_delay_s: Initial delay between retries in seconds.
        retry_backoff: Backoff multiplier for retry delays.
    """

    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        model: str = "gpt-image-1.5",
        max_retries: int = 3,
        retry_delay_s: float = 2.0,
        retry_backoff: float = 2.0,
    ) -> None:
        self._client = client
        self._model = model
        self._max_retries = max_retries
        self._retry_delay_s = retry_delay_s
        self._retry_backoff = retry_backoff

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
            RuntimeError: If all retries exhausted or non-retryable error.
        """
        api_size = _select_api_size(width, height)
        bg = background.value

        last_error: Exception | None = None
        delay = self._retry_delay_s

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._client.images.generate(
                    model=self._model,
                    prompt=prompt,
                    n=1,
                    size=api_size,  # type: ignore[call-overload]
                    output_format="png",  # type: ignore[call-overload]
                    background=bg,  # type: ignore[call-overload]
                )

                # gpt-image-1 returns base64 by default in data[0].b64_json
                if not response.data:
                    raise RuntimeError("API returned empty data list")
                b64_data = response.data[0].b64_json
                if not b64_data:
                    raise RuntimeError("API returned empty b64_json")

                raw_bytes = base64.b64decode(b64_data)

                # CPU-bound resize/write — run in thread to avoid blocking
                return await asyncio.to_thread(
                    _process_image_bytes, raw_bytes, width, height, output_path
                )

            except _RETRYABLE_ERRORS as e:
                last_error = e
                logger.warning(
                    "Image generation attempt %d/%d failed (retryable): %s",
                    attempt,
                    self._max_retries,
                    e,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(delay)
                    delay *= self._retry_backoff

            except Exception as e:
                # Non-retryable — fail immediately
                raise RuntimeError(f"Image generation failed (non-retryable): {e}") from e

        raise RuntimeError(
            f"Image generation failed after {self._max_retries} retries: {last_error}"
        )
