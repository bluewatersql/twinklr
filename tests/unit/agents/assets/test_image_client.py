"""Tests for async OpenAI Images API client."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from openai import RateLimitError
from PIL import Image
import pytest

from twinklr.core.agents.assets.image_client import (
    OpenAIImageClient,
    _select_api_size,
)


def _make_png_b64(width: int = 1024, height: int = 1024) -> str:
    """Create a valid PNG image and return its base64 encoding."""
    img = Image.new("RGBA", (width, height), (255, 0, 0, 128))
    buf = BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _mock_response(b64_data: str | None = None) -> MagicMock:
    """Create a mock OpenAI image response with valid PNG data."""
    if b64_data is None:
        b64_data = _make_png_b64()
    data_item = MagicMock()
    data_item.b64_json = b64_data
    response = MagicMock()
    response.data = [data_item]
    return response


def _make_async_client(
    response: MagicMock | None = None,
    side_effect: Exception | list | None = None,
) -> MagicMock:
    """Build a mock AsyncOpenAI client with images.generate as AsyncMock."""
    mock_client = MagicMock()
    mock_client.images = MagicMock()
    mock_client.images.generate = AsyncMock()
    if side_effect is not None:
        mock_client.images.generate.side_effect = side_effect
    elif response is not None:
        mock_client.images.generate.return_value = response
    else:
        mock_client.images.generate.return_value = _mock_response()
    return mock_client


class TestSelectApiSize:
    def test_small_image_maps_to_1024(self) -> None:
        assert _select_api_size(256, 256) == "1024x1024"

    def test_exact_supported_size(self) -> None:
        assert _select_api_size(1024, 1024) == "1024x1024"
        assert _select_api_size(1024, 1536) == "1024x1536"
        assert _select_api_size(1536, 1024) == "1536x1024"

    def test_tall_image(self) -> None:
        assert _select_api_size(512, 1200) == "1024x1536"

    def test_wide_image(self) -> None:
        assert _select_api_size(1200, 512) == "1536x1024"

    def test_oversized_uses_auto(self) -> None:
        assert _select_api_size(2048, 2048) == "auto"


class TestOpenAIImageClient:
    @pytest.mark.asyncio
    async def test_generate_success(self, tmp_path: Path) -> None:
        mock_client = _make_async_client()

        client = OpenAIImageClient(mock_client, model="test-model")
        output = tmp_path / "test.png"
        result = await client.generate(
            prompt="A sparkle pattern",
            output_path=output,
            width=256,
            height=256,
        )

        assert result.file_path == str(output)
        assert result.width == 256
        assert result.height == 256
        assert result.file_size_bytes > 0
        assert len(result.content_hash) == 64
        assert output.exists()

        # Verify the saved file is a valid PNG at target size
        saved_img = Image.open(output)
        assert saved_img.size == (256, 256)

    @pytest.mark.asyncio
    async def test_generate_creates_parent_dirs(self, tmp_path: Path) -> None:
        mock_client = _make_async_client()

        client = OpenAIImageClient(mock_client)
        output = tmp_path / "deep" / "nested" / "test.png"
        await client.generate("prompt", output)
        assert output.exists()

    @pytest.mark.asyncio
    async def test_api_called_with_output_format_not_response_format(self, tmp_path: Path) -> None:
        """Verify we use output_format (gpt-image-1), not response_format (DALL-E)."""
        mock_client = _make_async_client()

        client = OpenAIImageClient(mock_client)
        output = tmp_path / "test.png"
        await client.generate("prompt", output)

        call_kwargs = mock_client.images.generate.call_args.kwargs
        assert "output_format" in call_kwargs
        assert call_kwargs["output_format"] == "png"
        assert "response_format" not in call_kwargs

    @pytest.mark.asyncio
    async def test_api_called_with_supported_size(self, tmp_path: Path) -> None:
        """Verify API is called with a supported size, not the target size."""
        mock_client = _make_async_client()

        client = OpenAIImageClient(mock_client)
        output = tmp_path / "test.png"
        await client.generate("prompt", output, width=256, height=256)

        call_kwargs = mock_client.images.generate.call_args.kwargs
        assert call_kwargs["size"] == "1024x1024"

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, tmp_path: Path) -> None:
        # First call fails with rate limit, second succeeds
        rate_err = RateLimitError(
            message="Rate limit",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        mock_client = _make_async_client(side_effect=[rate_err, _mock_response()])

        client = OpenAIImageClient(mock_client, max_retries=2, retry_delay_s=0.01)
        output = tmp_path / "test.png"
        result = await client.generate("prompt", output)
        assert result.file_path == str(output)
        assert mock_client.images.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises(self, tmp_path: Path) -> None:
        rate_err = RateLimitError(
            message="Rate limit",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        mock_client = _make_async_client(side_effect=rate_err)

        client = OpenAIImageClient(mock_client, max_retries=2, retry_delay_s=0.01)
        output = tmp_path / "test.png"
        with pytest.raises(RuntimeError, match="failed after 2 retries"):
            await client.generate("prompt", output)

    @pytest.mark.asyncio
    async def test_non_retryable_error_fails_immediately(self, tmp_path: Path) -> None:
        mock_client = _make_async_client(side_effect=ValueError("Bad request"))

        client = OpenAIImageClient(mock_client, max_retries=3)
        output = tmp_path / "test.png"
        with pytest.raises(RuntimeError, match="non-retryable"):
            await client.generate("prompt", output)
        assert mock_client.images.generate.call_count == 1

    @pytest.mark.asyncio
    async def test_empty_b64_raises(self, tmp_path: Path) -> None:
        mock_client = _make_async_client(response=_mock_response(b64_data=""))

        client = OpenAIImageClient(mock_client)
        output = tmp_path / "test.png"
        with pytest.raises(RuntimeError, match="non-retryable"):
            await client.generate("prompt", output)

    @pytest.mark.asyncio
    async def test_resize_from_api_size_to_target(self, tmp_path: Path) -> None:
        """Verify image is resized from API size to target size."""
        mock_client = _make_async_client(
            response=_mock_response(b64_data=_make_png_b64(1024, 1024))
        )

        client = OpenAIImageClient(mock_client)
        output = tmp_path / "test.png"
        result = await client.generate("prompt", output, width=256, height=256)

        assert result.width == 256
        assert result.height == 256

        saved = Image.open(output)
        assert saved.size == (256, 256)
