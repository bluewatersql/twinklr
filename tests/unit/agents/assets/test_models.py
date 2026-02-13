"""Tests for asset creation pipeline models.

Covers: AssetCategory, AssetStatus, AssetSpec, EnrichedPrompt,
ImageResult, CatalogEntry, AssetCatalog.
"""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from twinklr.core.agents.assets.models import (
    AssetCatalog,
    AssetCategory,
    AssetSpec,
    AssetStatus,
    CatalogEntry,
    EnrichedPrompt,
    ImageResult,
)
from twinklr.core.sequencer.vocabulary import BackgroundMode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(
    *,
    spec_id: str = "asset_image_texture_sparkles",
    category: AssetCategory = AssetCategory.IMAGE_TEXTURE,
    motif_id: str | None = "sparkles",
    theme_id: str = "theme.holiday.traditional",
    section_ids: list[str] | None = None,
    target_roles: list[str] | None = None,
    background: BackgroundMode = BackgroundMode.OPAQUE,
    **kwargs: object,
) -> AssetSpec:
    return AssetSpec(
        spec_id=spec_id,
        category=category,
        motif_id=motif_id,
        theme_id=theme_id,
        section_ids=section_ids or ["intro_1"],
        target_roles=target_roles or ["MEGA_TREE"],
        background=background,
        **kwargs,  # type: ignore[arg-type]
    )


def _make_entry(
    *,
    asset_id: str = "asset_image_texture_sparkles",
    status: AssetStatus = AssetStatus.CREATED,
    prompt_hash: str = "abc123",
    **kwargs: object,
) -> CatalogEntry:
    spec = _make_spec()
    return CatalogEntry(
        asset_id=asset_id,
        spec=spec,
        file_path="images/textures/1024x1024/sparkles.png",
        content_hash="sha256_abc",
        status=status,
        width=1024,
        height=1024,
        has_alpha=False,
        file_size_bytes=1024,
        created_at="2026-02-10T12:00:00Z",
        source_plan_id="plan_001",
        generation_model="gpt-image-1.5",
        prompt_hash=prompt_hash,
        **kwargs,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# AssetCategory
# ---------------------------------------------------------------------------


class TestAssetCategory:
    def test_image_categories(self) -> None:
        assert AssetCategory.IMAGE_TEXTURE.value == "image_texture"
        assert AssetCategory.IMAGE_CUTOUT.value == "image_cutout"
        assert AssetCategory.IMAGE_PLATE.value == "image_plate"

    def test_text_categories(self) -> None:
        assert AssetCategory.TEXT_BANNER.value == "text_banner"
        assert AssetCategory.TEXT_LYRIC.value == "text_lyric"

    def test_shader_category(self) -> None:
        assert AssetCategory.SHADER.value == "shader"

    def test_is_image(self) -> None:
        assert AssetCategory.IMAGE_TEXTURE.is_image()
        assert AssetCategory.IMAGE_CUTOUT.is_image()
        assert AssetCategory.IMAGE_PLATE.is_image()
        assert not AssetCategory.TEXT_BANNER.is_image()
        assert not AssetCategory.TEXT_LYRIC.is_image()
        assert not AssetCategory.SHADER.is_image()

    def test_is_text(self) -> None:
        assert AssetCategory.TEXT_BANNER.is_text()
        assert AssetCategory.TEXT_LYRIC.is_text()
        assert not AssetCategory.IMAGE_TEXTURE.is_text()
        assert not AssetCategory.SHADER.is_text()


# ---------------------------------------------------------------------------
# AssetStatus
# ---------------------------------------------------------------------------


class TestAssetStatus:
    def test_values(self) -> None:
        assert AssetStatus.CREATED.value == "created"
        assert AssetStatus.CACHED.value == "cached"
        assert AssetStatus.FAILED.value == "failed"


# ---------------------------------------------------------------------------
# AssetSpec
# ---------------------------------------------------------------------------


class TestAssetSpec:
    def test_minimal_valid(self) -> None:
        spec = _make_spec()
        assert spec.spec_id == "asset_image_texture_sparkles"
        assert spec.category == AssetCategory.IMAGE_TEXTURE
        assert spec.motif_id == "sparkles"
        assert spec.format == "png"
        assert spec.width == 1024
        assert spec.height == 1024

    def test_defaults(self) -> None:
        spec = _make_spec()
        assert spec.prompt is None
        assert spec.negative_prompt is None
        assert spec.text_content is None
        assert spec.text_timing_ms is None
        assert spec.token_budget is None
        assert spec.matched_template_id is None
        assert spec.scene_context == []
        assert spec.style_tags == []
        assert spec.content_tags == []

    def test_text_spec_fields(self) -> None:
        spec = _make_spec(
            spec_id="text_banner_song_title",
            category=AssetCategory.TEXT_BANNER,
            motif_id=None,
            text_content="Rudolph the Red-Nosed Reindeer",
            text_timing_ms=0,
            background=BackgroundMode.TRANSPARENT,
        )
        assert spec.text_content == "Rudolph the Red-Nosed Reindeer"
        assert spec.text_timing_ms == 0
        assert spec.motif_id is None

    def test_enriched_spec(self) -> None:
        spec = _make_spec(
            prompt="A festive sparkle pattern...",
            negative_prompt="text, logos, watermarks",
        )
        assert spec.prompt == "A festive sparkle pattern..."
        assert spec.negative_prompt == "text, logos, watermarks"

    def test_empty_spec_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_spec(spec_id="")

    def test_empty_theme_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_spec(theme_id="")

    def test_empty_section_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssetSpec(
                spec_id="test",
                category=AssetCategory.IMAGE_TEXTURE,
                theme_id="theme.holiday.traditional",
                section_ids=[],
                background=BackgroundMode.OPAQUE,
            )

    def test_zero_dimensions_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_spec(width=0)
        with pytest.raises(ValidationError):
            _make_spec(height=0)

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_spec(bogus_field="nope")

    def test_scene_context(self) -> None:
        spec = _make_spec(
            scene_context=["Traditional Christmas feel", "Lyrics: Rudolph's glowing nose"],
        )
        assert len(spec.scene_context) == 2


# ---------------------------------------------------------------------------
# EnrichedPrompt
# ---------------------------------------------------------------------------


class TestEnrichedPrompt:
    def test_valid(self) -> None:
        ep = EnrichedPrompt(
            prompt="A festive Christmas sparkle pattern with bold shapes.",
            negative_prompt="text, logos, watermarks",
        )
        assert len(ep.prompt) > 20
        assert "text" in ep.negative_prompt

    def test_short_prompt_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EnrichedPrompt(prompt="too short", negative_prompt="text, logos")

    def test_short_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EnrichedPrompt(
                prompt="A festive Christmas sparkle pattern with bold shapes.",
                negative_prompt="x",
            )


# ---------------------------------------------------------------------------
# ImageResult
# ---------------------------------------------------------------------------


class TestImageResult:
    def test_valid(self) -> None:
        result = ImageResult(
            file_path="images/textures/1024x1024/sparkles.png",
            content_hash="sha256_abc",
            file_size_bytes=4096,
            width=1024,
            height=1024,
        )
        assert result.file_path == "images/textures/1024x1024/sparkles.png"
        assert result.content_hash == "sha256_abc"

    def test_zero_size_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ImageResult(
                file_path="x.png",
                content_hash="abc",
                file_size_bytes=0,
                width=256,
                height=256,
            )


# ---------------------------------------------------------------------------
# CatalogEntry
# ---------------------------------------------------------------------------


class TestCatalogEntry:
    def test_valid(self) -> None:
        entry = _make_entry()
        assert entry.asset_id == "asset_image_texture_sparkles"
        assert entry.status == AssetStatus.CREATED
        assert entry.error is None
        assert entry.embedding is None

    def test_failed_entry_with_error(self) -> None:
        entry = _make_entry(
            status=AssetStatus.FAILED,
            error="API rate limit exceeded",
        )
        assert entry.status == AssetStatus.FAILED
        assert entry.error == "API rate limit exceeded"

    def test_cached_entry(self) -> None:
        entry = _make_entry(status=AssetStatus.CACHED)
        assert entry.status == AssetStatus.CACHED


# ---------------------------------------------------------------------------
# AssetCatalog
# ---------------------------------------------------------------------------


class TestAssetCatalog:
    def test_empty_catalog(self) -> None:
        catalog = AssetCatalog(catalog_id="cat_001")
        assert catalog.entries == []
        assert catalog.total_created == 0
        assert catalog.total_cached == 0
        assert catalog.total_failed == 0

    def test_get_existing(self) -> None:
        entry = _make_entry()
        catalog = AssetCatalog(catalog_id="cat_001", entries=[entry])
        found = catalog.get("asset_image_texture_sparkles")
        assert found is not None
        assert found.asset_id == "asset_image_texture_sparkles"

    def test_get_missing(self) -> None:
        catalog = AssetCatalog(catalog_id="cat_001")
        assert catalog.get("nonexistent") is None

    def test_find_by_motif(self) -> None:
        e1 = _make_entry(asset_id="e1", prompt_hash="h1")
        e2 = _make_entry(asset_id="e2", prompt_hash="h2")
        catalog = AssetCatalog(catalog_id="cat_001", entries=[e1, e2])
        results = catalog.find_by_motif("sparkles")
        assert len(results) == 2

    def test_find_by_prompt_hash(self) -> None:
        entry = _make_entry(prompt_hash="exact_match_hash")
        catalog = AssetCatalog(catalog_id="cat_001", entries=[entry])
        found = catalog.find_by_prompt_hash("exact_match_hash")
        assert found is not None
        assert found.asset_id == "asset_image_texture_sparkles"

    def test_find_by_prompt_hash_miss(self) -> None:
        entry = _make_entry(prompt_hash="abc")
        catalog = AssetCatalog(catalog_id="cat_001", entries=[entry])
        assert catalog.find_by_prompt_hash("different_hash") is None

    def test_successful_entries(self) -> None:
        e1 = _make_entry(asset_id="ok", status=AssetStatus.CREATED, prompt_hash="h1")
        e2 = _make_entry(asset_id="fail", status=AssetStatus.FAILED, prompt_hash="h2")
        e3 = _make_entry(asset_id="cached", status=AssetStatus.CACHED, prompt_hash="h3")
        catalog = AssetCatalog(catalog_id="cat_001", entries=[e1, e2, e3])
        successful = catalog.successful_entries()
        assert len(successful) == 2
        ids = {e.asset_id for e in successful}
        assert ids == {"ok", "cached"}

    def test_summary_counts(self) -> None:
        e1 = _make_entry(asset_id="a1", status=AssetStatus.CREATED, prompt_hash="h1")
        e2 = _make_entry(asset_id="a2", status=AssetStatus.CACHED, prompt_hash="h2")
        e3 = _make_entry(asset_id="a3", status=AssetStatus.FAILED, prompt_hash="h3")
        catalog = AssetCatalog(catalog_id="cat_001", entries=[e1, e2, e3])
        assert catalog.total_created == 1
        assert catalog.total_cached == 1
        assert catalog.total_failed == 1

    def test_merge(self) -> None:
        """Merge adds new entries and updates existing ones by asset_id."""
        e1 = _make_entry(asset_id="a1", prompt_hash="h1")
        catalog = AssetCatalog(catalog_id="cat_001", entries=[e1])

        e2 = _make_entry(asset_id="a2", prompt_hash="h2")
        e1_updated = _make_entry(asset_id="a1", status=AssetStatus.CACHED, prompt_hash="h1")

        catalog.merge([e1_updated, e2])
        assert len(catalog.entries) == 2
        found = catalog.get("a1")
        assert found is not None
        assert found.status == AssetStatus.CACHED

    def test_build_index_excludes_failed(self) -> None:
        """build_index returns only successful entries keyed by asset_id."""
        e1 = _make_entry(asset_id="ok", status=AssetStatus.CREATED, prompt_hash="h1")
        e2 = _make_entry(asset_id="fail", status=AssetStatus.FAILED, prompt_hash="h2")
        e3 = _make_entry(asset_id="cached", status=AssetStatus.CACHED, prompt_hash="h3")
        catalog = AssetCatalog(catalog_id="cat_idx", entries=[e1, e2, e3])

        index = catalog.build_index()
        assert len(index) == 2
        assert "ok" in index
        assert "cached" in index
        assert "fail" not in index
        assert index["ok"].asset_id == "ok"

    def test_build_index_empty_catalog(self) -> None:
        """build_index on empty catalog returns empty dict."""
        catalog = AssetCatalog(catalog_id="empty", entries=[])
        assert catalog.build_index() == {}
