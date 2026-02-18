"""Unit tests for asset inventory builder."""

from __future__ import annotations

from twinklr.core.profiling.inventory import build_asset_inventory
from twinklr.core.profiling.models.enums import FileKind
from twinklr.core.profiling.models.pack import FileEntry, PackageManifest


def test_build_asset_inventory_classifies_assets_and_shaders() -> None:
    manifest = PackageManifest(
        package_id="pkg",
        zip_sha256="sha",
        source_extensions=frozenset({".zip"}),
        files=(
            FileEntry(
                file_id="1",
                filename="song.mp3",
                ext=".mp3",
                size=1,
                sha256="a",
                kind=FileKind.ASSET,
            ),
            FileEntry(
                file_id="2",
                filename="effect.fs",
                ext=".fs",
                size=1,
                sha256="b",
                kind=FileKind.SHADER,
            ),
        ),
        sequence_file_id=None,
        rgb_effects_file_id=None,
    )

    inventory = build_asset_inventory(manifest)
    assert len(inventory.assets) == 1
    assert inventory.assets[0]["asset_type"] == "audio"
    assert len(inventory.shaders) == 1
    assert inventory.shaders[0]["shader_type"] == ".fs"


def test_build_asset_inventory_empty_sections() -> None:
    manifest = PackageManifest(
        package_id="pkg",
        zip_sha256="sha",
        source_extensions=frozenset({".zip"}),
        files=(),
        sequence_file_id=None,
        rgb_effects_file_id=None,
    )
    inventory = build_asset_inventory(manifest)
    assert inventory.assets == ()
    assert inventory.shaders == ()
