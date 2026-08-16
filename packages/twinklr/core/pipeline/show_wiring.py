"""Strict one-layout dependency wiring for the combined show pipeline."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.feature_engineering.loader import FEArtifactBundle
from twinklr.core.formats.xlights.layout import layout_to_choreography, load_layout
from twinklr.core.pipeline.definition import PipelineDefinition
from twinklr.core.pipeline.definitions.show import build_combined_show_pipeline
from twinklr.core.pipeline.display_wiring import tracked_catalog_dir
from twinklr.core.sequencer.display.xlights_mapping import XLightsMapping
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    build_template_catalog_from_recipes,
)
from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.templates.group.store import TemplateStore


@dataclass(frozen=True)
class CombinedShowWiring:
    """Verifier-visible combined dependencies derived from one parsed layout."""

    pipeline: PipelineDefinition
    choreo_graph: ChoreographyGraph
    display_graph: ChoreographyGraph
    xlights_mapping: XLightsMapping
    template_catalog: TemplateCatalog
    recipe_catalog: RecipeCatalog
    fe_bundle: FEArtifactBundle | None
    moving_head_target_ids: frozenset[str]


def _active(model: object) -> bool:
    extra = getattr(model, "model_extra", None) or {}
    return str(extra.get("Active", "1")) != "0"


def validate_fixture_ownership(layout: object, fixture_group: FixtureGroup) -> None:
    group_name = fixture_group.xlights_group
    if not group_name:
        raise ValueError("Combined show fixture config requires a dedicated xlights_group")
    groups = list(getattr(getattr(layout, "modelGroups", None), "modelGroup", []) or [])
    models = list(getattr(getattr(layout, "models", None), "model", []) or [])
    duplicate_group_names = sorted(
        name for name, count in Counter(group.name for group in groups).items() if count > 1
    )
    if duplicate_group_names:
        raise ValueError(f"Layout contains duplicate model-group names: {duplicate_group_names}")
    duplicate_model_names = sorted(
        name for name, count in Counter(model.name for model in models).items() if count > 1
    )
    if duplicate_model_names:
        raise ValueError(f"Layout contains duplicate model declarations: {duplicate_model_names}")
    group_by_name = {group.name: group for group in groups}
    matching = [group for group in groups if group.name == group_name]
    if len(matching) != 1:
        raise ValueError(
            f"Fixture xLights group {group_name!r} must exist exactly once in the layout"
        )
    active = {model.name for model in models if _active(model)}
    inactive = {model.name for model in models if not _active(model)}
    expected = {fixture.xlights_model_name for fixture in fixture_group.expand_fixtures()}
    if len(expected) != len(fixture_group.expand_fixtures()):
        raise ValueError("Fixture config contains duplicate xlights_model_name ownership")
    raw_members = matching[0].get_model_list()
    if len(raw_members) != len(set(raw_members)):
        raise ValueError("Moving-head group contains duplicate direct model members")
    submodel_members = sorted(member for member in raw_members if "/" in member)
    if submodel_members:
        raise ValueError(
            f"Moving-head group must contain whole models, not submodels: {submodel_members}"
        )
    members = set(raw_members)
    nested = sorted(members & {group.name for group in groups})
    if nested:
        raise ValueError(
            f"Moving-head group must contain direct models, not nested groups: {nested}"
        )
    inactive_members = sorted(expected & inactive)
    if inactive_members:
        raise ValueError(f"Moving-head fixture model(s) are inactive in layout: {inactive_members}")
    missing = sorted(expected - active)
    if missing:
        raise ValueError(f"Moving-head fixture model(s) missing from layout: {missing}")
    if members != expected:
        raise ValueError(
            "Moving-head layout membership must exactly match fixture config: "
            f"missing={sorted(expected - members)}, extra={sorted(members - expected)}"
        )

    def resolve_members(name: str, stack: tuple[str, ...] = ()) -> set[str]:
        if name in stack:
            raise ValueError(
                f"xLights model-group membership cycle while reconciling fixtures: "
                f"{' -> '.join((*stack, name))}"
            )
        resolved: set[str] = set()
        for member in group_by_name[name].get_model_list():
            base = member.split("/", 1)[0]
            if base in group_by_name:
                resolved.update(resolve_members(base, (*stack, name)))
            else:
                resolved.add(base)
        return resolved

    overlaps = [
        group.name
        for group in groups
        if group.name != group_name and expected & resolve_members(group.name)
    ]
    if overlaps:
        raise ValueError(
            f"Moving-head models have ambiguous ownership in other layout groups: {sorted(overlaps)}"
        )


def prepare_combined_show_pipeline(
    *,
    layout_path: Path,
    fixture_group: FixtureGroup,
    job_config: JobConfig,
    available_templates: list[str],
    song_name: str,
    catalog_dir: Path | None = None,
    local_catalog_dir: Path | None = None,
    fe_bundle: FEArtifactBundle | None = None,
) -> CombinedShowWiring:
    """Parse the layout once, reconcile MH ownership, then partition by backend."""

    resolved_catalog = catalog_dir or tracked_catalog_dir()
    expected_index = resolved_catalog / "index.json"
    if not expected_index.is_file():
        raise FileNotFoundError(
            f"Tracked display recipe catalog is missing; expected {expected_index}"
        )

    layout = load_layout(layout_path)
    validate_fixture_ownership(layout, fixture_group)
    graph, mapping = layout_to_choreography(layout, graph_id=f"{song_name}_show")
    matching = [
        entry for entry in mapping.entries if entry.group_name == fixture_group.xlights_group
    ]
    if len(matching) != 1:
        raise ValueError("Dedicated moving-head layout group has ambiguous choreography mapping")
    moving_ids = frozenset({matching[0].choreo_id})
    display_groups = [group for group in graph.groups if group.id not in moving_ids]
    if not display_groups:
        raise ValueError("Combined show layout must contain at least one display target")
    display_graph = ChoreographyGraph(graph_id=f"{song_name}_display", groups=display_groups)

    store = TemplateStore.from_catalog_with_local_extensions_strict(
        resolved_catalog, local_catalog_dir
    )
    recipe_catalog = RecipeCatalog.from_store_strict(
        store,
        promoted=list(fe_bundle.recipe_catalog_entries) if fe_bundle is not None else None,
    )
    if not recipe_catalog.recipes:
        raise ValueError(
            f"Display recipe catalog at {resolved_catalog} contains no loadable recipes"
        )
    template_catalog = build_template_catalog_from_recipes(recipe_catalog.recipes)
    planner_ids = {entry.template_id for entry in template_catalog.entries}
    renderer_ids = {recipe.recipe_id for recipe in recipe_catalog.recipes}
    if planner_ids != renderer_ids:
        raise ValueError(
            "Effective display catalog mismatch between planner and renderer: "
            f"planner_only={sorted(planner_ids - renderer_ids)}, "
            f"renderer_only={sorted(renderer_ids - planner_ids)}"
        )
    pipeline = build_combined_show_pipeline(
        choreo_graph=graph,
        display_graph=display_graph,
        template_catalog=template_catalog,
        recipe_catalog=recipe_catalog,
        display_groups=graph.to_planner_summary(),
        xlights_mapping=mapping,
        fixture_group=fixture_group,
        available_templates=available_templates,
        moving_head_target_ids=set(moving_ids),
        fe_bundle=fe_bundle,
        song_name=song_name,
        max_iterations=job_config.agent.max_iterations,
        min_pass_score=job_config.agent.min_pass_score,
    )
    return CombinedShowWiring(
        pipeline=pipeline,
        choreo_graph=graph,
        display_graph=display_graph,
        xlights_mapping=mapping,
        template_catalog=template_catalog,
        recipe_catalog=recipe_catalog,
        fe_bundle=fe_bundle,
        moving_head_target_ids=moving_ids,
    )


__all__ = [
    "CombinedShowWiring",
    "prepare_combined_show_pipeline",
    "validate_fixture_ownership",
]
