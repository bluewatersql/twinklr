"""PIL/Pillow text renderer for text_banner and text_lyric assets.

Renders text as transparent PNG with LED-friendly styling.
No OpenAI API calls — purely local rendering.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from twinklr.core.agents.assets.models import AssetSpec, ImageResult

logger = logging.getLogger(__name__)

# Default text color (white) if no palette available
_DEFAULT_TEXT_COLOR = (255, 255, 255, 255)

# Minimum font size to attempt
_MIN_FONT_SIZE = 12

# Padding ratio (fraction of canvas dimension)
_PADDING_RATIO = 0.1


class TextRenderer:
    """Renders text assets as transparent PNGs using PIL/Pillow.

    Uses auto-sizing to fit text within canvas dimensions with padding.
    Falls back to PIL's default font if no custom font is available.

    Args:
        font_path: Optional path to a .ttf font file. If None, uses PIL default.
    """

    def __init__(self, font_path: Path | None = None) -> None:
        self._font_path = font_path

    def render(
        self,
        spec: AssetSpec,
        output_path: Path,
        text_color: tuple[int, int, int, int] | None = None,
    ) -> ImageResult:
        """Render a text spec to a transparent PNG.

        Args:
            spec: AssetSpec with text_content set.
            output_path: Path to write the generated PNG.
            text_color: RGBA tuple for text color. Defaults to white.

        Returns:
            ImageResult with file path, content hash, and dimensions.

        Raises:
            ValueError: If spec has no text_content.
        """
        if not spec.text_content:
            raise ValueError(f"Spec {spec.spec_id} has no text_content")

        color = text_color or _DEFAULT_TEXT_COLOR
        width = spec.width
        height = spec.height
        text = spec.text_content

        # Create transparent RGBA canvas
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Calculate available area with padding
        pad_x = int(width * _PADDING_RATIO)
        pad_y = int(height * _PADDING_RATIO)
        max_text_width = width - 2 * pad_x
        max_text_height = height - 2 * pad_y

        # Auto-size font
        font = self._auto_size_font(draw, text, max_text_width, max_text_height)

        # Get text bounding box for centering
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # Center text on canvas
        x = (width - text_w) // 2
        y = (height - text_h) // 2

        # Draw text
        draw.text((x, y), text, fill=color, font=font)

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(output_path), "PNG")

        # Hash
        file_bytes = output_path.read_bytes()
        content_hash = hashlib.sha256(file_bytes).hexdigest()

        return ImageResult(
            file_path=str(output_path),
            content_hash=content_hash,
            file_size_bytes=len(file_bytes),
            width=width,
            height=height,
        )

    def _auto_size_font(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        max_width: int,
        max_height: int,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Find the largest font size that fits text within bounds.

        Args:
            draw: ImageDraw instance for measuring.
            text: Text to measure.
            max_width: Maximum text width in pixels.
            max_height: Maximum text height in pixels.

        Returns:
            PIL font at the best size.
        """
        if self._font_path and self._font_path.exists():
            # Binary search for best font size
            lo, hi = _MIN_FONT_SIZE, max(max_height, 200)
            best_font = ImageFont.truetype(str(self._font_path), _MIN_FONT_SIZE)

            while lo <= hi:
                mid = (lo + hi) // 2
                font = ImageFont.truetype(str(self._font_path), mid)
                bbox = draw.textbbox((0, 0), text, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]

                if text_w <= max_width and text_h <= max_height:
                    best_font = font
                    lo = mid + 1
                else:
                    hi = mid - 1

            return best_font
        else:
            # Fallback to PIL default font
            logger.debug("No custom font available, using PIL default")
            return ImageFont.load_default()
