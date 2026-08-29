"""P3-T3 clean-clone display pipeline wiring."""

import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from twinklr.core.agents.audio.stages.analysis import AudioAnalysisStage
from twinklr.core.agents.sequencer.group_planner.stage import GroupPlannerStage
from twinklr.core.config.models import AssetGenerationConfig, JobConfig
from twinklr.core.feature_engineering.loader import FEArtifactBundle
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.display_wiring import (
    default_local_catalog_dir,
    prepare_display_pipeline,
    tracked_catalog_dir,
)
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.templates.group.store import TemplateStore

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[3]
TRACKED_CATALOG = REPO_ROOT / "catalog" / "templates"


def _planner_stage(wiring) -> GroupPlannerStage:
    stage = next(
        definition.stage for definition in wiring.pipeline.stages if definition.id == "groups"
    )
    assert isinstance(stage, GroupPlannerStage)
    return stage


def test_fe_bundle_threaded() -> None:
    bundle = FEArtifactBundle()
    wiring = prepare_display_pipeline(
        layout_path=FIXTURES / "display_layout_a.xml",
        job_config=JobConfig(),
        catalog_dir=TRACKED_CATALOG,
        fe_bundle=bundle,
        song_name="song",
    )

    assert _planner_stage(wiring).fe_bundle is bundle
    assert wiring.recipe_catalog.recipes
    assert wiring.template_catalog.entries


def test_runs_without_fe_bundle(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        wiring = prepare_display_pipeline(
            layout_path=FIXTURES / "display_layout_a.xml",
            job_config=JobConfig(),
            catalog_dir=TRACKED_CATALOG,
            song_name="song",
        )

    assert _planner_stage(wiring).fe_bundle is None
    assert (
        caplog.messages.count("No feature-engineering output supplied; planning without FE context")
        == 1
    )


def test_missing_tracked_catalog_names_expected_path(tmp_path: Path) -> None:
    missing = tmp_path / "tracked" / "templates"
    with pytest.raises(FileNotFoundError, match=str(missing)):
        prepare_display_pipeline(
            layout_path=FIXTURES / "display_layout_a.xml",
            job_config=JobConfig(),
            catalog_dir=missing,
            song_name="song",
        )


def test_optional_local_catalog_overlay(tmp_path: Path) -> None:
    wiring = prepare_display_pipeline(
        layout_path=FIXTURES / "display_layout_a.xml",
        job_config=JobConfig(),
        catalog_dir=TRACKED_CATALOG,
        local_catalog_dir=tmp_path / "absent-local-overlay",
        song_name="song",
    )
    assert wiring.recipe_catalog.recipes


def test_default_catalog_paths_are_clean_clone_safe(tmp_path: Path) -> None:
    assert tracked_catalog_dir() == TRACKED_CATALOG
    assert (tracked_catalog_dir() / "index.json").is_file()
    assert default_local_catalog_dir() == REPO_ROOT / "data" / "templates"
    # Simulate a clean clone: the gitignored `data/templates/` overlay is absent.
    # We must NOT read the developer's real local overlay here, or the recipe count
    # becomes machine-dependent (a populated local library would inflate it).
    absent_local_overlay = tmp_path / "clean-clone-no-local-overlay"
    wiring = prepare_display_pipeline(
        layout_path=FIXTURES / "display_layout_a.xml",
        job_config=JobConfig(),
        catalog_dir=tracked_catalog_dir(),
        local_catalog_dir=absent_local_overlay,
        song_name="song",
    )
    assert len(wiring.recipe_catalog.recipes) == 6


def test_catalog_layers_tracked_local_then_fe_promoted(tmp_path: Path) -> None:
    tracked_store = TemplateStore.from_directory(TRACKED_CATALOG)
    tracked_recipes = {
        recipe.recipe_id: recipe for recipe in RecipeCatalog.from_store(tracked_store).recipes
    }
    assert len(tracked_recipes) == 6
    recipe_id = "gtpl_base_wash_split"
    local = tmp_path / "local"
    (local / "custom").mkdir(parents=True)
    local_recipe = tracked_recipes[recipe_id].model_copy(update={"name": "Local Override"})
    (local / "custom" / "override.json").write_text(
        local_recipe.model_dump_json(indent=2), encoding="utf-8"
    )
    (local / "index.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "recipe_id": recipe_id,
                        "name": "Local Override",
                        "template_type": local_recipe.template_type.value,
                        "visual_intent": local_recipe.visual_intent.value,
                        "file": "custom/override.json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    promoted = local_recipe.model_copy(update={"name": "FE Promoted Override"})
    wiring = prepare_display_pipeline(
        layout_path=FIXTURES / "display_layout_a.xml",
        job_config=JobConfig(),
        catalog_dir=TRACKED_CATALOG,
        local_catalog_dir=local,
        fe_bundle=FEArtifactBundle(recipe_catalog_entries=(promoted,)),
        song_name="song",
    )

    assert len(wiring.recipe_catalog.recipes) == 6
    assert wiring.recipe_catalog.get_recipe(recipe_id).name == "FE Promoted Override"
    planner = _planner_stage(wiring)
    render = next(
        definition.stage
        for definition in wiring.pipeline.stages
        if definition.id == "display_render"
    )
    assert planner.recipe_catalog is wiring.recipe_catalog
    assert render._recipe_catalog is wiring.recipe_catalog


def test_planner_and_renderer_catalog_ids_match_with_new_fe_recipe() -> None:
    tracked = RecipeCatalog.from_store(TemplateStore.from_directory(TRACKED_CATALOG)).recipes
    promoted = tracked[0].model_copy(update={"recipe_id": "fe_brand_new_recipe"})
    wiring = prepare_display_pipeline(
        layout_path=FIXTURES / "display_layout_a.xml",
        job_config=JobConfig(),
        catalog_dir=TRACKED_CATALOG,
        fe_bundle=FEArtifactBundle(recipe_catalog_entries=(promoted,)),
        song_name="song",
    )

    assert {entry.template_id for entry in wiring.template_catalog.entries} == {
        recipe.recipe_id for recipe in wiring.recipe_catalog.recipes
    }


def test_duplicate_index_recipe_ids_fail_preflight(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    recipe = RecipeCatalog.from_store(TemplateStore.from_directory(TRACKED_CATALOG)).recipes[0]
    recipe_path = catalog / "recipe.json"
    recipe_path.write_text(recipe.model_dump_json(), encoding="utf-8")
    entry = {
        "recipe_id": recipe.recipe_id,
        "name": recipe.name,
        "template_type": recipe.template_type.value,
        "visual_intent": recipe.visual_intent.value,
        "file": recipe_path.name,
    }
    (catalog / "index.json").write_text(json.dumps({"entries": [entry, entry]}), encoding="utf-8")

    with (
        patch("twinklr.core.pipeline.display_wiring.build_display_pipeline") as builder,
        pytest.raises(ValueError, match="duplicate recipe_id"),
    ):
        prepare_display_pipeline(
            layout_path=FIXTURES / "display_layout_a.xml",
            job_config=JobConfig(),
            catalog_dir=catalog,
            song_name="song",
        )
    builder.assert_not_called()


@pytest.mark.parametrize("failure", ["missing", "corrupt", "mismatch"])
def test_invalid_catalog_entry_fails_actionably(tmp_path: Path, failure: str) -> None:
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    recipe = RecipeCatalog.from_store(TemplateStore.from_directory(TRACKED_CATALOG)).recipes[0]
    recipe_path = catalog / "recipe.json"
    if failure == "corrupt":
        recipe_path.write_text("{not json", encoding="utf-8")
    elif failure == "mismatch":
        recipe_path.write_text(recipe.model_dump_json(), encoding="utf-8")
    entry_id = "different_index_id" if failure == "mismatch" else recipe.recipe_id
    (catalog / "index.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "recipe_id": entry_id,
                        "name": recipe.name,
                        "template_type": recipe.template_type.value,
                        "visual_intent": recipe.visual_intent.value,
                        "file": recipe_path.name,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=f"{entry_id}.*{recipe_path.name}"):
        prepare_display_pipeline(
            layout_path=FIXTURES / "display_layout_a.xml",
            job_config=JobConfig(),
            catalog_dir=catalog,
            song_name="song",
        )


def test_duplicate_fe_promoted_ids_fail_effective_catalog_preflight() -> None:
    recipe = RecipeCatalog.from_store(TemplateStore.from_directory(TRACKED_CATALOG)).recipes[0]
    promoted = recipe.model_copy(update={"recipe_id": "same_promoted_id"})
    with pytest.raises(ValueError, match="duplicate recipe IDs"):
        prepare_display_pipeline(
            layout_path=FIXTURES / "display_layout_a.xml",
            job_config=JobConfig(),
            catalog_dir=TRACKED_CATALOG,
            fe_bundle=FEArtifactBundle(recipe_catalog_entries=(promoted, promoted)),
            song_name="song",
        )


def test_invalid_local_overlay_cannot_hide_behind_tracked_catalog(tmp_path: Path) -> None:
    local = tmp_path / "local"
    local.mkdir()
    recipe = RecipeCatalog.from_store(TemplateStore.from_directory(TRACKED_CATALOG)).recipes[0]
    missing = local / "missing-override.json"
    (local / "index.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "recipe_id": recipe.recipe_id,
                        "name": recipe.name,
                        "template_type": recipe.template_type.value,
                        "visual_intent": recipe.visual_intent.value,
                        "file": missing.name,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=f"{recipe.recipe_id}.*{missing.name}"):
        prepare_display_pipeline(
            layout_path=FIXTURES / "display_layout_a.xml",
            job_config=JobConfig(),
            catalog_dir=TRACKED_CATALOG,
            local_catalog_dir=local,
            song_name="song",
        )


def test_assets_remain_disabled() -> None:
    wiring = prepare_display_pipeline(
        layout_path=FIXTURES / "display_layout_a.xml",
        job_config=JobConfig(),
        catalog_dir=TRACKED_CATALOG,
        song_name="song",
    )
    assert all(stage.id != "asset_creation" for stage in wiring.pipeline.stages)


def test_assets_enabled_through_typed_job_config() -> None:
    wiring = prepare_display_pipeline(
        layout_path=FIXTURES / "display_layout_a.xml",
        job_config=JobConfig(assets=AssetGenerationConfig(enabled=True, dry_run=True)),
        catalog_dir=TRACKED_CATALOG,
        song_name="song",
    )
    assert any(stage.id == "asset_creation" for stage in wiring.pipeline.stages)


def test_job_config_controls_display_planner_iterations_and_threshold() -> None:
    job = JobConfig()
    job.agent.max_iterations = 0
    job.agent.success_threshold = 83
    wiring = prepare_display_pipeline(
        layout_path=FIXTURES / "display_layout_a.xml",
        job_config=job,
        catalog_dir=TRACKED_CATALOG,
        song_name="song",
    )
    planner = _planner_stage(wiring)
    assert planner.max_iterations == 0
    assert planner.min_pass_score == 8.3


@pytest.mark.asyncio
async def test_audio_stage_preserves_irregular_detected_beat_grid() -> None:
    bundle = MagicMock()
    bundle.features = {
        "tempo_bpm": 120.0,
        "beats_s": [0.1, 0.61, 1.17, 1.64],
        "bars_s": [0.1, 1.64],
        "assumptions": {"beats_per_bar": 4},
    }
    bundle.timing.duration_ms = 2200
    bundle.lyrics = None
    analyzer = MagicMock()
    analyzer.analyze = AsyncMock(return_value=bundle)
    analyzer.aclose = AsyncMock()
    session = MagicMock()
    session.app_config = MagicMock()
    session.job_config = MagicMock()
    context = PipelineContext(session=session)

    with patch("twinklr.core.audio.analyzer.AudioAnalyzer", return_value=analyzer):
        result = await AudioAnalysisStage().execute("song.wav", context)

    assert result.success
    grid = context.get_state("beat_grid")
    assert grid.beat_boundaries == [100.0, 610.0, 1170.0, 1640.0]
    assert grid.beat_boundaries[2] - grid.beat_boundaries[1] == 560.0
