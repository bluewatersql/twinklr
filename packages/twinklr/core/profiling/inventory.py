"""Asset/shader inventory derivation from package manifest."""

from __future__ import annotations

from pathlib import Path

from twinklr.core.profiling.models.enums import FileKind
from twinklr.core.profiling.models.pack import PackageManifest
from twinklr.core.profiling.models.profile import AssetInventory

_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


def _asset_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in _AUDIO_EXTS:
        return "audio"
    if ext in _VIDEO_EXTS:
        return "video"
    if ext in _IMAGE_EXTS:
        return "image"
    return "other"


def build_asset_inventory(manifest: PackageManifest) -> AssetInventory:
    """Build typed asset/shader inventory from manifest file entries."""
    assets: list[dict[str, str]] = []
    shaders: list[dict[str, str]] = []

    for file_entry in manifest.files:
        if file_entry.kind is FileKind.ASSET:
            assets.append(
                {
                    "file_id": file_entry.file_id,
                    "filename": file_entry.filename,
                    "asset_type": _asset_type(file_entry.filename),
                }
            )
        elif file_entry.kind is FileKind.SHADER:
            shaders.append(
                {
                    "file_id": file_entry.file_id,
                    "filename": file_entry.filename,
                    "shader_type": Path(file_entry.filename).suffix.lower(),
                }
            )

    return AssetInventory(assets=tuple(assets), shaders=tuple(shaders))
