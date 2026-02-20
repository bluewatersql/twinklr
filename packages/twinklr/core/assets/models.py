"""Asset generation request/result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class AssetRequest:
    """Request to generate a visual asset."""

    asset_id: str
    prompt: str
    style_hint: str = ""
    palette_colors: list[str] = field(default_factory=list)
    width: int = 512
    height: int = 512
    format: Literal["png", "jpeg"] = "png"


@dataclass(frozen=True)
class AssetResult:
    """Result of asset generation."""

    asset_id: str
    file_path: str
    content_hash: str
    prompt_used: str
    cached: bool = False


@dataclass(frozen=True)
class AssetError:
    """Error from asset generation."""

    asset_id: str
    error: str
    retryable: bool = False
