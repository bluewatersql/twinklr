"""Tests for asset catalog persistence and reuse checking."""

from __future__ import annotations

from pathlib import Path

from twinklr.core.agents.assets.catalog import (
    check_reuse,
    compute_prompt_hash,
    load_catalog,
    save_catalog,
)
from twinklr.core.agents.assets.models import (
    AssetCatalog,
    AssetCategory,
    AssetSpec,
    AssetStatus,
    CatalogEntry,
)
from twinklr.core.sequencer.vocabulary import BackgroundMode


def _make_spec(
    prompt: str = "A sparkle pattern",
    text_content: str | None = None,
    width: int = 256,
    height: int = 256,
) -> AssetSpec:
    return AssetSpec(
        spec_id="test_spec",
        category=AssetCategory.IMAGE_TEXTURE,
        theme_id="theme.holiday.traditional",
        section_ids=["s1"],
        background=BackgroundMode.OPAQUE,
        width=width,
        height=height,
        prompt=prompt,
        text_content=text_content,
    )


def _make_entry(
    asset_id: str = "test_asset",
    prompt_hash: str = "hash_abc",
    file_path: str = "images/textures/256x256/sparkles.png",
) -> CatalogEntry:
    return CatalogEntry(
        asset_id=asset_id,
        spec=_make_spec(),
        file_path=file_path,
        content_hash="sha256_content",
        status=AssetStatus.CREATED,
        width=256,
        height=256,
        has_alpha=False,
        file_size_bytes=1024,
        created_at="2026-02-10T12:00:00Z",
        source_plan_id="plan_001",
        generation_model="gpt-image-1.5",
        prompt_hash=prompt_hash,
    )


class TestComputePromptHash:
    def test_deterministic(self) -> None:
        spec = _make_spec(prompt="Hello world")
        h1 = compute_prompt_hash(spec)
        h2 = compute_prompt_hash(spec)
        assert h1 == h2

    def test_different_prompts_different_hash(self) -> None:
        s1 = _make_spec(prompt="Sparkle pattern A")
        s2 = _make_spec(prompt="Sparkle pattern B")
        assert compute_prompt_hash(s1) != compute_prompt_hash(s2)

    def test_different_dimensions_different_hash(self) -> None:
        s1 = _make_spec(width=256, height=256)
        s2 = _make_spec(width=512, height=512)
        assert compute_prompt_hash(s1) != compute_prompt_hash(s2)

    def test_text_content_used_when_no_prompt(self) -> None:
        spec = _make_spec(prompt=None, text_content="Song Title")  # type: ignore[arg-type]
        h = compute_prompt_hash(spec)
        assert len(h) == 64  # SHA-256 hex length


class TestLoadSaveCatalog:
    def test_load_missing_file(self, tmp_path: Path) -> None:
        catalog = load_catalog(tmp_path / "nonexistent.json")
        assert len(catalog.entries) == 0
        assert catalog.catalog_id == "default"

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "assets" / "asset_catalog.json"
        entry = _make_entry()
        catalog = AssetCatalog(catalog_id="test_cat", entries=[entry])

        save_catalog(catalog, path)
        assert path.exists()

        loaded = load_catalog(path)
        assert loaded.catalog_id == "test_cat"
        assert len(loaded.entries) == 1
        assert loaded.entries[0].asset_id == "test_asset"

    def test_load_corrupt_file_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not valid json {{{")
        catalog = load_catalog(path)
        assert len(catalog.entries) == 0

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "deep" / "nested" / "catalog.json"
        catalog = AssetCatalog(catalog_id="test")
        save_catalog(catalog, path)
        assert path.exists()


class TestCheckReuse:
    def test_cache_miss(self) -> None:
        catalog = AssetCatalog(catalog_id="test")
        spec = _make_spec(prompt="New prompt")
        assert check_reuse(catalog, spec) is None

    def test_cache_hit_with_valid_file(self, tmp_path: Path) -> None:
        spec = _make_spec(prompt="Cached prompt")
        prompt_hash = compute_prompt_hash(spec)

        # Create a real file on disk
        file_path = tmp_path / "sparkles.png"
        file_path.write_bytes(b"fake png data")

        entry = _make_entry(
            prompt_hash=prompt_hash,
            file_path=str(file_path),
        )
        catalog = AssetCatalog(catalog_id="test", entries=[entry])

        result = check_reuse(catalog, spec)
        assert result is not None
        assert result.asset_id == "test_asset"

    def test_cache_hit_with_missing_file(self, tmp_path: Path) -> None:
        spec = _make_spec(prompt="Cached prompt")
        prompt_hash = compute_prompt_hash(spec)

        entry = _make_entry(
            prompt_hash=prompt_hash,
            file_path=str(tmp_path / "missing.png"),
        )
        catalog = AssetCatalog(catalog_id="test", entries=[entry])

        result = check_reuse(catalog, spec)
        assert result is None
