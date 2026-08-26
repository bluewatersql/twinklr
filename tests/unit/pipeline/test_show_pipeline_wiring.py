"""Strict shared-layout and backend-partition wiring for P3-T5."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from twinklr.core.agents.sequencer.group_planner.stage import GroupPlannerStage
from twinklr.core.config.fixtures import FixtureGroup, FixtureInstance
from twinklr.core.config.fixtures.dmx import DmxMapping
from twinklr.core.config.fixtures.instances import FixtureConfig
from twinklr.core.config.models import AssetGenerationConfig, JobConfig
from twinklr.core.feature_engineering.loader import FEArtifactBundle
from twinklr.core.formats.xlights.layout.models.rgb_effects import (
    Layout,
    Model,
    ModelGroup,
    ModelGroups,
    Models,
)
from twinklr.core.pipeline.show_stages import CombinedShowRenderStage
from twinklr.core.pipeline.show_wiring import (
    prepare_combined_show_pipeline,
    validate_fixture_ownership,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.templates.group.store import TemplateStore
from twinklr.core.sequencer.vocabulary.choreography import TargetType

REPO_ROOT = Path(__file__).resolve().parents[3]
TRACKED_CATALOG = REPO_ROOT / "catalog" / "templates"


def _fixture_group() -> FixtureGroup:
    group = FixtureGroup(group_id="MOVING_HEADS", xlights_group="Moving Heads")
    for index in range(2):
        fixture_id = f"MH{index + 1}"
        group.add_fixture(
            FixtureInstance(
                fixture_id=fixture_id,
                config=FixtureConfig(
                    fixture_id=fixture_id,
                    dmx_mapping=DmxMapping(pan_channel=1, tilt_channel=2, dimmer_channel=3),
                ),
                xlights_model_name=f"Dmx {fixture_id}",
            )
        )
    return group


def _layout(*, mh_members: str = "Dmx MH1,Dmx MH2") -> Layout:
    return Layout(
        models=Models(
            model=[
                Model(name="Dmx MH1", DisplayAs="Dmx"),
                Model(name="Dmx MH2", DisplayAs="Dmx"),
                Model(name="Mega Tree", DisplayAs="Tree 360"),
                Model(name="Arch 1", DisplayAs="Arches"),
            ]
        ),
        modelGroups=ModelGroups(
            modelGroup=[
                ModelGroup(name="Moving Heads", models=mh_members),
                ModelGroup(name="Yard Arches", models="Arch 1"),
            ]
        ),
    )


def _write_layout(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xrgb>
  <models>
    <model name="Dmx MH1" DisplayAs="Dmx" />
    <model name="Dmx MH2" DisplayAs="Dmx" />
    <model name="Mega Tree" DisplayAs="Tree 360" parm1="16" parm2="50" />
    <model name="Arch 1" DisplayAs="Arches" parm1="1" parm2="50" />
  </models>
  <modelGroups>
    <modelGroup name="Moving Heads" models="Dmx MH1,Dmx MH2" />
    <modelGroup name="Yard Arches" models="Arch 1" />
  </modelGroups>
</xrgb>
""",
        encoding="utf-8",
    )


def _prepare(layout_path: Path, **kwargs: object):
    job_config = kwargs.pop("job_config", JobConfig())
    return prepare_combined_show_pipeline(
        layout_path=layout_path,
        fixture_group=_fixture_group(),
        job_config=job_config,
        available_templates=["sweep_lr_fan_hold"],
        song_name="test_show",
        **kwargs,
    )


def test_show_assets_enabled_through_typed_job_config(tmp_path: Path) -> None:
    layout = tmp_path / "layout.xml"
    _write_layout(layout)
    wiring = _prepare(
        layout,
        job_config=JobConfig(assets=AssetGenerationConfig(enabled=True, dry_run=True)),
    )
    assert any(stage.id == "asset_creation" for stage in wiring.pipeline.stages)


def test_dedicated_layout_group_exactly_matches_active_fixture_models() -> None:
    validate_fixture_ownership(_layout(), _fixture_group())


@pytest.mark.parametrize(
    ("layout", "message"),
    [
        (_layout(mh_members="Dmx MH1"), "missing=['Dmx MH2']"),
        (_layout(mh_members="Dmx MH1,Dmx MH2,Mega Tree"), "extra=['Mega Tree']"),
    ],
)
def test_mh_group_membership_mismatch_fails_closed(layout: Layout, message: str) -> None:
    with pytest.raises(ValueError, match=message.replace("[", r"\[").replace("]", r"\]")):
        validate_fixture_ownership(layout, _fixture_group())


def test_duplicate_raw_mh_group_member_is_rejected() -> None:
    layout = _layout(mh_members="Dmx MH1,Dmx MH1,Dmx MH2")

    with pytest.raises(ValueError, match="duplicate direct model members"):
        validate_fixture_ownership(layout, _fixture_group())


def test_duplicate_layout_model_declarations_are_rejected_before_membership_sets() -> None:
    layout = _layout()
    assert layout.models is not None
    layout.models.model.append(Model(name="Dmx MH1", DisplayAs="Dmx"))

    with pytest.raises(ValueError, match=r"duplicate model declarations.*Dmx MH1"):
        validate_fixture_ownership(layout, _fixture_group())


def test_duplicate_non_dedicated_layout_group_names_are_rejected() -> None:
    layout = _layout()
    assert layout.modelGroups is not None
    layout.modelGroups.modelGroup.append(ModelGroup(name="Yard Arches", models="Mega Tree"))

    with pytest.raises(ValueError, match=r"duplicate model-group names.*Yard Arches"):
        validate_fixture_ownership(layout, _fixture_group())


def test_duplicate_non_dedicated_group_cannot_mask_moving_head_overlap() -> None:
    layout = _layout()
    assert layout.modelGroups is not None
    layout.modelGroups.modelGroup.extend(
        [
            ModelGroup(name="All Models", models="Dmx MH1,Mega Tree,Arch 1"),
            ModelGroup(name="All Models", models="Mega Tree,Arch 1"),
        ]
    )

    with pytest.raises(ValueError, match=r"duplicate model-group names.*All Models"):
        validate_fixture_ownership(layout, _fixture_group())


def test_slash_qualified_mh_submodel_member_is_rejected() -> None:
    layout = _layout(mh_members="Dmx MH1/Submodel,Dmx MH2")

    with pytest.raises(ValueError, match="whole models, not submodels"):
        validate_fixture_ownership(layout, _fixture_group())


def test_inactive_fixture_model_fails_closed() -> None:
    layout = _layout()
    assert layout.models is not None
    layout.models.model[1] = Model(name="Dmx MH2", DisplayAs="Dmx", Active="0")
    with pytest.raises(ValueError, match="inactive"):
        validate_fixture_ownership(layout, _fixture_group())


def test_overlapping_display_group_is_ambiguous_output_ownership() -> None:
    layout = _layout()
    assert layout.modelGroups is not None
    layout.modelGroups.modelGroup.append(
        ModelGroup(name="All Models", models="Dmx MH1,Mega Tree,Arch 1")
    )
    with pytest.raises(ValueError, match="ambiguous ownership"):
        validate_fixture_ownership(layout, _fixture_group())


def test_nested_all_models_group_overlapping_mh_is_ambiguous() -> None:
    layout = _layout()
    assert layout.modelGroups is not None
    layout.modelGroups.modelGroup.append(
        ModelGroup(name="All Models", models="Moving Heads,Mega Tree,Arch 1")
    )
    with pytest.raises(ValueError, match="ambiguous ownership"):
        validate_fixture_ownership(layout, _fixture_group())


def test_nested_mh_group_is_rejected() -> None:
    layout = _layout(mh_members="MH Pair")
    assert layout.modelGroups is not None
    layout.modelGroups.modelGroup.append(ModelGroup(name="MH Pair", models="Dmx MH1,Dmx MH2"))
    with pytest.raises(ValueError, match="direct models"):
        validate_fixture_ownership(layout, _fixture_group())


def test_combined_pipeline_has_one_common_prefix_and_one_render_barrier(tmp_path) -> None:
    layout_path = tmp_path / "xlights_rgbeffects.xml"
    _write_layout(layout_path)
    wiring = _prepare(layout_path)

    stage_ids = [stage.id for stage in wiring.pipeline.stages]
    assert wiring.pipeline.validate_pipeline() == []
    assert all(
        stage_ids.count(stage_id) == 1 for stage_id in ("audio", "profile", "lyrics", "macro")
    )
    assert stage_ids.count("show_render") == 1
    assert "render" not in stage_ids
    assert "display_render" not in stage_ids
    assert len(wiring.moving_head_target_ids) == 1
    assert set(wiring.moving_head_target_ids).isdisjoint(
        group.id for group in wiring.display_graph.groups
    )


def test_missing_catalog_names_expected_index_path(tmp_path: Path) -> None:
    layout_path = tmp_path / "xlights_rgbeffects.xml"
    _write_layout(layout_path)
    missing = tmp_path / "missing-catalog"

    with pytest.raises(FileNotFoundError, match=str(missing / "index.json")):
        _prepare(layout_path, catalog_dir=missing)


def test_empty_effective_catalog_is_rejected(tmp_path: Path) -> None:
    layout_path = tmp_path / "xlights_rgbeffects.xml"
    _write_layout(layout_path)
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "index.json").write_text('{"entries": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="contains no loadable recipes"):
        _prepare(layout_path, catalog_dir=catalog)


def test_catalog_layers_tracked_local_then_fe_promoted_and_preserves_parity(
    tmp_path: Path,
) -> None:
    layout_path = tmp_path / "xlights_rgbeffects.xml"
    _write_layout(layout_path)
    tracked_recipes = RecipeCatalog.from_store(
        TemplateStore.from_directory(TRACKED_CATALOG)
    ).recipes
    base = tracked_recipes[0]
    local_recipe = base.model_copy(update={"name": "Local Override"})
    local = tmp_path / "local"
    local.mkdir()
    (local / "override.json").write_text(local_recipe.model_dump_json(), encoding="utf-8")
    (local / "index.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "recipe_id": local_recipe.recipe_id,
                        "name": local_recipe.name,
                        "template_type": local_recipe.template_type.value,
                        "visual_intent": local_recipe.visual_intent.value,
                        "file": "override.json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    promoted = local_recipe.model_copy(update={"name": "FE Promoted Override"})
    bundle = FEArtifactBundle(recipe_catalog_entries=(promoted,))

    wiring = _prepare(
        layout_path,
        catalog_dir=TRACKED_CATALOG,
        local_catalog_dir=local,
        fe_bundle=bundle,
    )

    assert wiring.fe_bundle is bundle
    assert wiring.recipe_catalog.get_recipe(base.recipe_id).name == "FE Promoted Override"
    planner = next(stage.stage for stage in wiring.pipeline.stages if stage.id == "groups")
    renderer = next(stage.stage for stage in wiring.pipeline.stages if stage.id == "show_render")
    assert isinstance(planner, GroupPlannerStage)
    assert isinstance(renderer, CombinedShowRenderStage)
    assert planner.fe_bundle is bundle
    assert planner.recipe_catalog is wiring.recipe_catalog
    assert renderer._display_stage._recipe_catalog is wiring.recipe_catalog
    assert {entry.template_id for entry in wiring.template_catalog.entries} == {
        recipe.recipe_id for recipe in wiring.recipe_catalog.recipes
    }


def test_absent_local_overlay_and_fe_bundle_are_optional(tmp_path: Path) -> None:
    layout_path = tmp_path / "xlights_rgbeffects.xml"
    _write_layout(layout_path)

    wiring = _prepare(
        layout_path,
        catalog_dir=TRACKED_CATALOG,
        local_catalog_dir=tmp_path / "absent-local",
    )

    assert wiring.fe_bundle is None
    assert wiring.recipe_catalog.recipes


def test_duplicate_fe_promoted_ids_fail_effective_catalog_preflight(tmp_path: Path) -> None:
    layout_path = tmp_path / "xlights_rgbeffects.xml"
    _write_layout(layout_path)
    recipe = RecipeCatalog.from_store(TemplateStore.from_directory(TRACKED_CATALOG)).recipes[0]
    promoted = recipe.model_copy(update={"recipe_id": "same_promoted_id"})

    with pytest.raises(ValueError, match="duplicate recipe IDs"):
        _prepare(
            layout_path,
            catalog_dir=TRACKED_CATALOG,
            fe_bundle=FEArtifactBundle(recipe_catalog_entries=(promoted, promoted)),
        )


def test_catalog_id_mismatch_fails_before_pipeline_construction(tmp_path: Path) -> None:
    layout_path = tmp_path / "xlights_rgbeffects.xml"
    _write_layout(layout_path)
    mismatched_catalog = MagicMock()
    mismatched_catalog.entries = []

    with (
        patch(
            "twinklr.core.pipeline.show_wiring.build_template_catalog_from_recipes",
            return_value=mismatched_catalog,
        ),
        patch("twinklr.core.pipeline.show_wiring.build_combined_show_pipeline") as builder,
        pytest.raises(ValueError, match="catalog mismatch between planner and renderer"),
    ):
        _prepare(layout_path, catalog_dir=TRACKED_CATALOG)

    builder.assert_not_called()


def test_display_focus_partition_does_not_expose_mh_group_to_display_planner() -> None:
    display_graph = ChoreographyGraph(
        graph_id="display", groups=[ChoreoGroup(id="MEGA_TREE", role="MEGA_TREE")]
    )
    stage = GroupPlannerStage(
        choreo_graph=display_graph,
        macro_choreo_graph=ChoreographyGraph(
            graph_id="show",
            groups=[
                *display_graph.groups,
                ChoreoGroup(id="MOVING_HEADS", role="MOVING_HEADS"),
            ],
        ),
        template_catalog=MagicMock(),
    )

    assert (
        stage._resolve_focus_targets([PlanTarget(type=TargetType.GROUP, id="MOVING_HEADS")]) == []
    )
    assert stage._resolve_focus_targets([PlanTarget(type=TargetType.GROUP, id="MEGA_TREE")]) == [
        "MEGA_TREE"
    ]
