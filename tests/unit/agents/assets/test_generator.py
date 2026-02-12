"""Tests for async asset generation orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from twinklr.core.agents.assets.generator import (
    _build_output_path,
    generate_asset,
)
from twinklr.core.agents.assets.models import (
    AssetCategory,
    AssetSpec,
    AssetStatus,
    ImageResult,
)
from twinklr.core.agents.assets.text_renderer import TextRenderer
from twinklr.core.sequencer.vocabulary import BackgroundMode


def _make_image_spec(
    motif_id: str = "sparkles",
    category: AssetCategory = AssetCategory.IMAGE_TEXTURE,
    prompt: str | None = "A sparkle pattern",
) -> AssetSpec:
    return AssetSpec(
        spec_id=f"asset_{category.value}_{motif_id}",
        category=category,
        motif_id=motif_id,
        theme_id="theme.holiday.traditional",
        section_ids=["s1"],
        background=BackgroundMode.OPAQUE,
        prompt=prompt,
    )


def _make_text_spec(text_content: str = "Song Title") -> AssetSpec:
    return AssetSpec(
        spec_id="asset_text_banner_song_title",
        category=AssetCategory.TEXT_BANNER,
        theme_id="theme.holiday.traditional",
        section_ids=["s1"],
        background=BackgroundMode.TRANSPARENT,
        text_content=text_content,
        width=512,
        height=128,
    )


def _make_mock_image_client(
    result: ImageResult | None = None,
    side_effect: Exception | None = None,
) -> MagicMock:
    """Build a mock async image client."""
    mock_client = MagicMock()
    mock_client._model = "test-model"
    mock_client.generate = AsyncMock()
    if side_effect:
        mock_client.generate.side_effect = side_effect
    elif result:
        mock_client.generate.return_value = result
    return mock_client


class TestBuildOutputPath:
    def test_image_texture_path(self, tmp_path: Path) -> None:
        spec = _make_image_spec()
        path = _build_output_path(spec, tmp_path)
        assert "images/textures/1024x1024/sparkles.png" in str(path)

    def test_image_cutout_path(self, tmp_path: Path) -> None:
        spec = _make_image_spec(category=AssetCategory.IMAGE_CUTOUT)
        path = _build_output_path(spec, tmp_path)
        assert "images/cutouts/1024x1024/sparkles.png" in str(path)

    def test_text_banner_path(self, tmp_path: Path) -> None:
        spec = _make_text_spec()
        path = _build_output_path(spec, tmp_path)
        # Text specs use spec_id as filename (motif_id is None)
        assert "text/banners/" in str(path)
        assert path.suffix == ".png"


class TestGenerateAsset:
    @pytest.mark.asyncio
    async def test_image_with_mock_client(self, tmp_path: Path) -> None:
        spec = _make_image_spec()

        output_path = tmp_path / "images" / "textures" / "1024x1024" / "sparkles.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create a real image file so validation passes
        from PIL import Image

        img = Image.new("RGB", (1024, 1024), "red")
        img.save(str(output_path))

        mock_client = _make_mock_image_client(
            result=ImageResult(
                file_path=str(output_path),
                content_hash="sha256_abc",
                file_size_bytes=4096,
                width=1024,
                height=1024,
            )
        )

        entry = await generate_asset(
            spec, tmp_path, image_client=mock_client, source_plan_id="plan_1"
        )

        assert entry.status == AssetStatus.CREATED
        assert entry.generation_model == "test-model"
        assert entry.source_plan_id == "plan_1"

    @pytest.mark.asyncio
    async def test_text_with_renderer(self, tmp_path: Path) -> None:
        spec = _make_text_spec()
        renderer = TextRenderer()

        entry = await generate_asset(
            spec, tmp_path, text_renderer=renderer, source_plan_id="plan_1"
        )

        assert entry.status == AssetStatus.CREATED
        assert entry.generation_model == "pil"
        assert entry.has_alpha is True

    @pytest.mark.asyncio
    async def test_image_without_prompt_fails(self, tmp_path: Path) -> None:
        spec = _make_image_spec(prompt=None)
        mock_client = _make_mock_image_client()

        entry = await generate_asset(spec, tmp_path, image_client=mock_client)
        assert entry.status == AssetStatus.FAILED
        assert "No prompt" in (entry.error or "")

    @pytest.mark.asyncio
    async def test_image_without_client_fails(self, tmp_path: Path) -> None:
        spec = _make_image_spec()

        entry = await generate_asset(spec, tmp_path, image_client=None)
        assert entry.status == AssetStatus.FAILED
        assert "No image client" in (entry.error or "")

    @pytest.mark.asyncio
    async def test_text_without_content_fails(self, tmp_path: Path) -> None:
        spec = AssetSpec(
            spec_id="empty_text",
            category=AssetCategory.TEXT_BANNER,
            theme_id="theme.holiday.traditional",
            section_ids=["s1"],
            background=BackgroundMode.TRANSPARENT,
        )
        renderer = TextRenderer()
        entry = await generate_asset(spec, tmp_path, text_renderer=renderer)
        assert entry.status == AssetStatus.FAILED
        assert "No text_content" in (entry.error or "")

    @pytest.mark.asyncio
    async def test_text_without_renderer_fails(self, tmp_path: Path) -> None:
        spec = _make_text_spec()
        entry = await generate_asset(spec, tmp_path, text_renderer=None)
        assert entry.status == AssetStatus.FAILED
        assert "No text renderer" in (entry.error or "")

    @pytest.mark.asyncio
    async def test_exception_caught_as_failed(self, tmp_path: Path) -> None:
        spec = _make_image_spec()
        mock_client = _make_mock_image_client(side_effect=RuntimeError("API exploded"))

        entry = await generate_asset(spec, tmp_path, image_client=mock_client)
        assert entry.status == AssetStatus.FAILED
        assert "API exploded" in (entry.error or "")
