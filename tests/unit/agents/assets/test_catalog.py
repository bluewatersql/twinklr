"""Tests for asset catalog persistence and reuse checking."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PIL import Image
import pytest

from twinklr.core.agents.assets.catalog import (
    check_reuse,
    check_reuse_by_spec_id,
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

    def test_load_corrupt_file_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not valid json {{{")
        with pytest.raises(ValueError, match="asset catalog"):
            load_catalog(path)

    def test_unexpected_catalog_reader_failure_propagates(self, tmp_path: Path) -> None:
        path = tmp_path / "catalog.json"
        path.write_text("{}", encoding="utf-8")
        with (
            patch.object(Path, "read_text", side_effect=RuntimeError("programmer bug")),
            pytest.raises(RuntimeError, match="programmer bug"),
        ):
            load_catalog(path)

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "deep" / "nested" / "catalog.json"
        catalog = AssetCatalog(catalog_id="test")
        save_catalog(catalog, path)
        assert path.exists()


class TestCheckReuse:
    @pytest.mark.parametrize("lookup", ["prompt", "spec_id"])
    @pytest.mark.parametrize("invalid_kind", ["fake", "corrupt", "zero", "jpeg", "wrong-size"])
    def test_cached_image_must_be_valid_png_with_expected_dimensions(
        self,
        tmp_path: Path,
        lookup: str,
        invalid_kind: str,
    ) -> None:
        spec = _make_spec(prompt="Scoped prompt")
        path = tmp_path / "cached.png"
        if invalid_kind == "fake":
            path.write_bytes(b"paid image")
        elif invalid_kind == "corrupt":
            path.write_bytes(b"\x89PNG\r\n\x1a\ntruncated")
        elif invalid_kind == "zero":
            path.write_bytes(b"")
        elif invalid_kind == "jpeg":
            Image.new("RGB", (256, 256)).save(path, format="JPEG")
        else:
            Image.new("RGB", (128, 256)).save(path, format="PNG")
        entry = _make_entry(prompt_hash=compute_prompt_hash(spec), file_path="cached.png")
        catalog = AssetCatalog(catalog_id="test", entries=[entry])

        with pytest.raises(ValueError, match="Cached image validation failed"):
            if lookup == "prompt":
                check_reuse(catalog, spec, assets_dir=tmp_path, source_plan_id="plan_001")
            else:
                check_reuse_by_spec_id(
                    catalog, spec, assets_dir=tmp_path, source_plan_id="plan_001"
                )

    def test_prompt_hash_reuse_is_scoped_to_source_plan(self, tmp_path: Path) -> None:
        spec = _make_spec(prompt="Same enriched image prompt")
        prompt_hash = compute_prompt_hash(spec)
        relative_a = "images/textures/256x256/song-a.png"
        relative_b = "images/textures/256x256/song-b.png"
        for relative in (relative_a, relative_b):
            output = tmp_path / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (256, 256)).save(output, format="PNG")
        song_a = _make_entry(asset_id="song-a:asset", prompt_hash=prompt_hash, file_path=relative_a)
        song_a.source_plan_id = "song-a"
        song_b = _make_entry(asset_id="song-b:asset", prompt_hash=prompt_hash, file_path=relative_b)
        song_b.source_plan_id = "song-b"
        catalog = AssetCatalog(catalog_id="test", entries=[song_a, song_b])

        hit = check_reuse(catalog, spec, assets_dir=tmp_path, source_plan_id="song-b")

        assert hit is not None
        assert hit.asset_id == "song-b:asset"
        assert check_reuse(catalog, spec, assets_dir=tmp_path, source_plan_id="song-c") is None

    @pytest.mark.parametrize("file_path", ["/tmp/outside.png", "../outside.png"])
    @pytest.mark.parametrize("lookup", ["prompt", "spec_id"])
    def test_reuse_rejects_unsafe_catalog_paths(
        self,
        tmp_path: Path,
        file_path: str,
        lookup: str,
    ) -> None:
        spec = _make_spec(prompt="Scoped prompt")
        entry = _make_entry(prompt_hash=compute_prompt_hash(spec), file_path=file_path)
        catalog = AssetCatalog(catalog_id="test", entries=[entry])

        with pytest.raises(ValueError, match="catalog file_path"):
            if lookup == "prompt":
                check_reuse(catalog, spec, assets_dir=tmp_path, source_plan_id="plan_001")
            else:
                check_reuse_by_spec_id(
                    catalog, spec, assets_dir=tmp_path, source_plan_id="plan_001"
                )

    @pytest.mark.parametrize("lookup", ["prompt", "spec_id"])
    def test_reuse_rejects_symlink_escape(self, tmp_path: Path, lookup: str) -> None:
        root = tmp_path / "assets"
        outside = tmp_path / "outside"
        root.mkdir()
        outside.mkdir()
        (outside / "paid.png").write_bytes(b"paid")
        (root / "escape").symlink_to(outside, target_is_directory=True)
        spec = _make_spec(prompt="Scoped prompt")
        entry = _make_entry(prompt_hash=compute_prompt_hash(spec), file_path="escape/paid.png")
        catalog = AssetCatalog(catalog_id="test", entries=[entry])

        with pytest.raises(ValueError, match="escapes assets root"):
            if lookup == "prompt":
                check_reuse(catalog, spec, assets_dir=root, source_plan_id="plan_001")
            else:
                check_reuse_by_spec_id(catalog, spec, assets_dir=root, source_plan_id="plan_001")

    def test_cache_miss(self) -> None:
        catalog = AssetCatalog(catalog_id="test")
        spec = _make_spec(prompt="New prompt")
        assert check_reuse(catalog, spec, assets_dir=Path.cwd(), source_plan_id="plan_001") is None

    def test_cache_hit_with_valid_file(self, tmp_path: Path) -> None:
        spec = _make_spec(prompt="Cached prompt")
        prompt_hash = compute_prompt_hash(spec)

        # Create a real file on disk
        file_path = tmp_path / "sparkles.png"
        Image.new("RGB", (256, 256)).save(file_path, format="PNG")

        entry = _make_entry(
            prompt_hash=prompt_hash,
            file_path="sparkles.png",
        )
        catalog = AssetCatalog(catalog_id="test", entries=[entry])

        result = check_reuse(catalog, spec, assets_dir=tmp_path, source_plan_id="plan_001")
        assert result is not None
        assert result.asset_id == "test_asset"

    def test_cache_hit_with_missing_file(self, tmp_path: Path) -> None:
        spec = _make_spec(prompt="Cached prompt")
        prompt_hash = compute_prompt_hash(spec)

        entry = _make_entry(
            prompt_hash=prompt_hash,
            file_path="missing.png",
        )
        catalog = AssetCatalog(catalog_id="test", entries=[entry])

        result = check_reuse(catalog, spec, assets_dir=tmp_path, source_plan_id="plan_001")
        assert result is None


class TestCheckReuseBySpecId:
    """Tests for spec_id-based reuse (pre-enrichment image cache check)."""

    def test_cache_hit_by_spec_id(self, tmp_path: Path) -> None:
        """Image spec with matching spec_id + dimensions reuses existing entry."""
        from twinklr.core.agents.assets.catalog import check_reuse_by_spec_id

        file_path = tmp_path / "sparkles.png"
        Image.new("RGB", (256, 256)).save(file_path, format="PNG")

        entry = _make_entry(file_path="sparkles.png")
        catalog = AssetCatalog(catalog_id="test", entries=[entry])

        # New spec with same spec_id but different/no prompt (pre-enrichment)
        spec = AssetSpec(
            spec_id="test_spec",
            category=AssetCategory.IMAGE_TEXTURE,
            theme_id="theme.holiday.traditional",
            section_ids=["s1"],
            background=BackgroundMode.OPAQUE,
            width=256,
            height=256,
        )

        result = check_reuse_by_spec_id(
            catalog, spec, assets_dir=tmp_path, source_plan_id="plan_001"
        )
        assert result is not None
        assert result.asset_id == "test_asset"

    def test_cache_miss_different_spec_id(self, tmp_path: Path) -> None:
        """Different spec_id does not match."""
        from twinklr.core.agents.assets.catalog import check_reuse_by_spec_id

        file_path = tmp_path / "sparkles.png"
        Image.new("RGB", (256, 256)).save(file_path, format="PNG")

        entry = _make_entry(file_path="sparkles.png")
        catalog = AssetCatalog(catalog_id="test", entries=[entry])

        spec = AssetSpec(
            spec_id="different_spec",
            category=AssetCategory.IMAGE_TEXTURE,
            theme_id="theme.holiday.traditional",
            section_ids=["s1"],
            background=BackgroundMode.OPAQUE,
            width=256,
            height=256,
        )

        result = check_reuse_by_spec_id(
            catalog, spec, assets_dir=tmp_path, source_plan_id="plan_001"
        )
        assert result is None

    def test_cache_miss_different_dimensions(self, tmp_path: Path) -> None:
        """Same spec_id but different dimensions does not match."""
        from twinklr.core.agents.assets.catalog import check_reuse_by_spec_id

        file_path = tmp_path / "sparkles.png"
        Image.new("RGB", (256, 256)).save(file_path, format="PNG")

        entry = _make_entry(file_path="sparkles.png")
        catalog = AssetCatalog(catalog_id="test", entries=[entry])

        spec = AssetSpec(
            spec_id="test_spec",
            category=AssetCategory.IMAGE_TEXTURE,
            theme_id="theme.holiday.traditional",
            section_ids=["s1"],
            background=BackgroundMode.OPAQUE,
            width=512,
            height=512,
        )

        result = check_reuse_by_spec_id(
            catalog, spec, assets_dir=tmp_path, source_plan_id="plan_001"
        )
        assert result is None

    def test_cache_miss_file_deleted(self, tmp_path: Path) -> None:
        """Matching spec_id but file no longer on disk returns None."""
        from twinklr.core.agents.assets.catalog import check_reuse_by_spec_id

        entry = _make_entry(file_path="deleted.png")
        catalog = AssetCatalog(catalog_id="test", entries=[entry])

        spec = AssetSpec(
            spec_id="test_spec",
            category=AssetCategory.IMAGE_TEXTURE,
            theme_id="theme.holiday.traditional",
            section_ids=["s1"],
            background=BackgroundMode.OPAQUE,
            width=256,
            height=256,
        )

        result = check_reuse_by_spec_id(
            catalog, spec, assets_dir=tmp_path, source_plan_id="plan_001"
        )
        assert result is None

    def test_cache_miss_failed_entry(self, tmp_path: Path) -> None:
        """Failed entries are not reused even with matching spec_id."""
        from twinklr.core.agents.assets.catalog import check_reuse_by_spec_id

        file_path = tmp_path / "sparkles.png"
        file_path.write_bytes(b"fake png data")

        entry = CatalogEntry(
            asset_id="test_asset",
            spec=_make_spec(),
            file_path="sparkles.png",
            content_hash="sha256_content",
            status=AssetStatus.FAILED,
            width=256,
            height=256,
            has_alpha=False,
            file_size_bytes=0,
            created_at="2026-02-10T12:00:00Z",
            source_plan_id="plan_001",
            generation_model="gpt-image-1.5",
            prompt_hash="hash_abc",
        )
        catalog = AssetCatalog(catalog_id="test", entries=[entry])

        spec = AssetSpec(
            spec_id="test_spec",
            category=AssetCategory.IMAGE_TEXTURE,
            theme_id="theme.holiday.traditional",
            section_ids=["s1"],
            background=BackgroundMode.OPAQUE,
            width=256,
            height=256,
        )

        result = check_reuse_by_spec_id(
            catalog, spec, assets_dir=tmp_path, source_plan_id="plan_001"
        )
        assert result is None
