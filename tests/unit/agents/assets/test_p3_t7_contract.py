"""P3-T7 safety contracts at the assets package's public seams."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from PIL import Image
from pydantic import ValidationError
import pytest

from twinklr.core.agents.assets.catalog import check_reuse_by_spec_id, load_catalog, save_catalog
from twinklr.core.agents.assets.generator import build_output_path
from twinklr.core.agents.assets.models import (
    AssetCatalog,
    AssetCategory,
    AssetSpec,
    AssetStatus,
    CatalogEntry,
)
from twinklr.core.config.models import AssetGenerationConfig, JobConfig
from twinklr.core.sequencer.planning.group_plan import (
    GroupPlanSet,
    NarrativeAssetDirective,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.vocabulary import BackgroundMode


def _spec(spec_id: str = "song-a:image_texture:sparkles") -> AssetSpec:
    return AssetSpec(
        spec_id=spec_id,
        category=AssetCategory.IMAGE_TEXTURE,
        motif_id="sparkles",
        theme_id="theme.holiday.traditional",
        section_ids=["intro"],
        background=BackgroundMode.OPAQUE,
    )


def _entry(spec: AssetSpec, file_path: str) -> CatalogEntry:
    return CatalogEntry(
        asset_id=spec.spec_id,
        spec=spec,
        file_path=file_path,
        content_hash="abc",
        status=AssetStatus.CREATED,
        width=spec.width,
        height=spec.height,
        file_size_bytes=1,
        created_at="2026-08-26T00:00:00Z",
        source_plan_id="song-a",
        generation_model="gpt-image-2",
        prompt_hash="def",
    )


def test_asset_generation_defaults_are_off_and_capped() -> None:
    config = AssetGenerationConfig()
    assert config.enabled is False
    assert config.dry_run is False
    assert config.max_image_requests_per_run == 1
    assert config.estimated_image_usd_per_request == pytest.approx(0.20)
    assert not hasattr(config, "max_images_per_run")
    assert not hasattr(config, "max_estimated_image_usd_per_run")
    assert JobConfig().assets == config
    with pytest.raises(ValidationError):
        AssetGenerationConfig(estimated_image_usd_per_request=0.05)
    with pytest.raises(ValidationError):
        AssetGenerationConfig(image_quality="high")  # type: ignore[arg-type]


def test_corrupt_catalog_is_loud(tmp_path: Path) -> None:
    path = tmp_path / "asset_catalog.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="asset catalog"):
        load_catalog(path)


def test_atomic_save_failure_preserves_previous_catalog(tmp_path: Path) -> None:
    path = tmp_path / "asset_catalog.json"
    save_catalog(AssetCatalog(catalog_id="original"), path)
    with (
        patch.object(Path, "replace", side_effect=OSError("simulated crash")),
        pytest.raises(OSError, match="simulated crash"),
    ):
        save_catalog(AssetCatalog(catalog_id="replacement"), path)
    assert load_catalog(path).catalog_id == "original"


def test_relative_catalog_paths_survive_root_move(tmp_path: Path) -> None:
    first_root = tmp_path / "first" / "assets"
    relative = Path("images/textures/1024x1024/sparkles.png")
    first_file = first_root / relative
    first_file.parent.mkdir(parents=True)
    Image.new("RGB", (1024, 1024)).save(first_file, format="PNG")
    spec = _spec()
    catalog = AssetCatalog(catalog_id="cat", entries=[_entry(spec, relative.as_posix())])
    assert (
        check_reuse_by_spec_id(catalog, spec, assets_dir=first_root, source_plan_id="song-a")
        is not None
    )

    second_root = tmp_path / "second" / "assets"
    second_file = second_root / relative
    second_file.parent.mkdir(parents=True)
    Image.new("RGB", (1024, 1024)).save(second_file, format="PNG")
    assert (
        check_reuse_by_spec_id(catalog, spec, assets_dir=second_root, source_plan_id="song-a")
        is not None
    )


def test_output_path_rejects_traversal_and_resists_slug_collisions(tmp_path: Path) -> None:
    traversal = _spec("../../../../etc/cron.d/x")
    with pytest.raises(ValueError, match=r"\.\./\.\./\.\./\.\./etc/cron\.d/x"):
        build_output_path(traversal, tmp_path)

    first = build_output_path(_spec("song-a:image_texture:Snow Glow"), tmp_path)
    second = build_output_path(_spec("song-a:image_texture:snow-glow"), tmp_path)
    assert first != second
    assert first.is_relative_to(tmp_path)
    assert second.is_relative_to(tmp_path)


def test_group_plan_narrative_assets_have_a_hard_bound() -> None:
    directive = NarrativeAssetDirective(
        directive_id="snow",
        subject="falling snow",
        category="image_texture",
        visual_description="Large bright snowflakes against a dark field",
        story_context="The quiet opening of the song",
    )
    section = SectionCoordinationPlan.model_construct(
        section_id="intro",
        theme=ThemeRef(theme_id="theme.holiday.traditional", scope="SECTION"),
        motif_ids=[],
        palette=PaletteRef(palette_id="core.christmas_traditional"),
        lane_plans=[],
        narrative_assets=[directive] * 5,
    )
    with pytest.raises(ValidationError):
        GroupPlanSet(
            plan_set_id="song-a",
            section_plans=[section],
            narrative_assets=[directive] * 5,
        )


def test_group_plan_schema_builds_in_a_clean_process() -> None:
    script = (
        "from twinklr.core.sequencer.planning.group_plan import GroupPlanSet; "
        "print(GroupPlanSet.model_json_schema()['title'])"
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "GroupPlanSet"


def test_catalog_json_stores_only_relative_paths(tmp_path: Path) -> None:
    root = tmp_path / "assets"
    spec = _spec()
    payload = AssetCatalog(catalog_id="cat", entries=[_entry(spec, "images/a.png")]).model_dump(
        mode="json"
    )
    assert json.dumps(payload).find(str(root)) == -1


def test_catalog_has_no_unscoped_spec_id_reuse_api() -> None:
    assert not hasattr(AssetCatalog, "find_by_spec_id")
