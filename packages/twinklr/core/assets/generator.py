"""AssetGenerator protocol and PromptBuilder.

Defines the provider interface for AI asset generation and a prompt
builder that enriches narrative directives with palette and technical
constraints for Christmas light show displays.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from twinklr.core.assets.models import AssetRequest, AssetResult


@runtime_checkable
class AssetGenerator(Protocol):
    """Protocol for AI asset generation providers."""

    async def generate(self, request: AssetRequest) -> AssetResult:
        """Generate a single asset."""
        ...

    async def generate_batch(self, requests: list[AssetRequest]) -> list[AssetResult]:
        """Generate multiple assets."""
        ...


class PromptBuilder:
    """Builds enriched prompts for asset generation.

    Enriches a base narrative prompt with palette colors,
    technical constraints, and Christmas light show context.
    """

    _SYSTEM_PREFIX = "Christmas light show visual asset."
    _TECHNICAL_SUFFIX = "High contrast, suitable for LED display projection."

    def build(self, request: AssetRequest) -> str:
        """Build enriched prompt from an AssetRequest.

        Args:
            request: Asset generation request with base prompt and metadata.

        Returns:
            Enriched prompt string ready for the AI provider.
        """
        parts = [self._SYSTEM_PREFIX]
        if request.style_hint:
            parts.append(f"Style: {request.style_hint}.")
        parts.append(request.prompt)
        if request.palette_colors:
            color_str = ", ".join(request.palette_colors)
            parts.append(f"Color palette: {color_str}.")
        parts.append(f"Resolution: {request.width}x{request.height}.")
        parts.append(self._TECHNICAL_SUFFIX)
        return " ".join(parts)
