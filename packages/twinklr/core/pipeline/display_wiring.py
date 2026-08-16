"""Offline-first dependency wiring for the display pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from twinklr.core.config.models import JobConfig
from twinklr.core.feature_engineering.loader import FEArtifactBundle
from twinklr.core.formats.xlights.layout import layout_to_choreography, load_layout
from twinklr.core.pipeline.definition import PipelineDefinition
from twinklr.core.pipeline.definitions.display import build_display_pipeline
from twinklr.core.sequencer.display.xlights_mapping import XLightsMapping
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    build_template_catalog_from_recipes,
)
from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.templates.group.store import TemplateStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DisplayPipelineWiring:
    """All resolved display dependencies, exposed for inspection and reuse."""

    pipeline: PipelineDefinition
    choreo_graph: ChoreographyGraph
    xlights_mapping: XLightsMapping
    template_catalog: TemplateCatalog
    recipe_catalog: RecipeCatalog
    fe_bundle: FEArtifactBundle | None


def tracked_catalog_dir() -> Path:
    """Return the repository's tracked starter-catalog location."""
    return Path(__file__).resolve().parents[4] / "catalog" / "templates"


def default_local_catalog_dir() -> Path:
    """Return the repository's canonical optional untracked catalog overlay."""
    return Path(__file__).resolve().parents[4] / "data" / "templates"  # local-extensions overlay


def prepare_display_pipeline(
    *,
    layout_path: Path,
    job_config: JobConfig,
    catalog_dir: Path,
    song_name: str,
    local_catalog_dir: Path | None = None,
    fe_bundle: FEArtifactBundle | None = None,
) -> DisplayPipelineWiring:
    """Resolve user layout, tracked recipes, optional overlay, and FE context."""
    expected_index = catalog_dir / "index.json"
    if not expected_index.is_file():
        raise FileNotFoundError(
            f"Tracked display recipe catalog is missing; expected {expected_index}"
        )

    layout = load_layout(layout_path)
    graph, mapping = layout_to_choreography(layout, graph_id=f"{song_name}_display")
    store = TemplateStore.from_catalog_with_local_extensions_strict(catalog_dir, local_catalog_dir)
    recipe_catalog = RecipeCatalog.from_store_strict(
        store,
        promoted=list(fe_bundle.recipe_catalog_entries) if fe_bundle is not None else None,
    )
    if not recipe_catalog.recipes:
        raise ValueError(f"Display recipe catalog at {catalog_dir} contains no loadable recipes")
    template_catalog = build_template_catalog_from_recipes(recipe_catalog.recipes)
    planner_ids = {entry.template_id for entry in template_catalog.entries}
    renderer_ids = {recipe.recipe_id for recipe in recipe_catalog.recipes}
    if planner_ids != renderer_ids:
        raise ValueError(
            "Effective display catalog mismatch between planner and renderer: "
            f"planner_only={sorted(planner_ids - renderer_ids)}, "
            f"renderer_only={sorted(renderer_ids - planner_ids)}"
        )
    if fe_bundle is None:
        logger.info("No feature-engineering output supplied; planning without FE context")

    pipeline = build_display_pipeline(
        choreo_graph=graph,
        template_catalog=template_catalog,
        display_groups=graph.to_planner_summary(),
        recipe_catalog=recipe_catalog,
        fe_bundle=fe_bundle,
        song_name=song_name,
        max_iterations=job_config.agent.max_iterations,
        min_pass_score=job_config.agent.min_pass_score,
        enable_assets=False,
        xlights_mapping=mapping,
    )
    return DisplayPipelineWiring(
        pipeline=pipeline,
        choreo_graph=graph,
        xlights_mapping=mapping,
        template_catalog=template_catalog,
        recipe_catalog=recipe_catalog,
        fe_bundle=fe_bundle,
    )


__all__ = [
    "DisplayPipelineWiring",
    "default_local_catalog_dir",
    "prepare_display_pipeline",
    "tracked_catalog_dir",
]
