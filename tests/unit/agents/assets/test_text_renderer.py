"""Tests for PIL text renderer."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from twinklr.core.agents.assets.models import AssetCategory, AssetSpec
from twinklr.core.agents.assets.text_renderer import TextRenderer
from twinklr.core.sequencer.vocabulary import BackgroundMode


def _make_text_spec(
    text_content: str = "Rudolph the Red-Nosed Reindeer",
    width: int = 512,
    height: int = 128,
) -> AssetSpec:
    return AssetSpec(
        spec_id="text_banner_song_title",
        category=AssetCategory.TEXT_BANNER,
        theme_id="theme.holiday.traditional",
        section_ids=["intro_1"],
        background=BackgroundMode.TRANSPARENT,
        width=width,
        height=height,
        text_content=text_content,
    )


class TestTextRenderer:
    def test_renders_png(self, tmp_path: Path) -> None:
        renderer = TextRenderer()
        spec = _make_text_spec()
        output = tmp_path / "banner.png"
        result = renderer.render(spec, output)

        assert output.exists()
        assert result.width == 512
        assert result.height == 128
        assert result.file_size_bytes > 0
        assert len(result.content_hash) == 64

    def test_creates_rgba_image(self, tmp_path: Path) -> None:
        renderer = TextRenderer()
        spec = _make_text_spec()
        output = tmp_path / "banner.png"
        renderer.render(spec, output)

        img = Image.open(output)
        assert img.mode == "RGBA"
        assert img.size == (512, 128)

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        renderer = TextRenderer()
        spec = _make_text_spec()
        output = tmp_path / "deep" / "nested" / "banner.png"
        renderer.render(spec, output)
        assert output.exists()

    def test_custom_text_color(self, tmp_path: Path) -> None:
        renderer = TextRenderer()
        spec = _make_text_spec()
        output = tmp_path / "banner.png"
        result = renderer.render(spec, output, text_color=(255, 0, 0, 255))
        assert result.file_size_bytes > 0

    def test_no_text_content_raises(self, tmp_path: Path) -> None:
        renderer = TextRenderer()
        spec = AssetSpec(
            spec_id="empty_text",
            category=AssetCategory.TEXT_BANNER,
            theme_id="theme.holiday.traditional",
            section_ids=["s1"],
            background=BackgroundMode.TRANSPARENT,
        )
        output = tmp_path / "banner.png"
        with pytest.raises(ValueError, match="no text_content"):
            renderer.render(spec, output)

    def test_small_canvas(self, tmp_path: Path) -> None:
        """Text should still render even on very small canvas."""
        renderer = TextRenderer()
        spec = _make_text_spec(width=64, height=32)
        output = tmp_path / "small.png"
        result = renderer.render(spec, output)
        assert result.width == 64
        assert result.height == 32

    def test_with_custom_font(self, tmp_path: Path) -> None:
        """With a nonexistent font path, falls back to default."""
        renderer = TextRenderer(font_path=Path("/nonexistent/font.ttf"))
        spec = _make_text_spec()
        output = tmp_path / "banner.png"
        result = renderer.render(spec, output)
        assert result.file_size_bytes > 0
