"""Combined show pipeline assembled from the existing branch definitions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import AssetGenerationConfig
from twinklr.core.pipeline import PipelineDefinition, StageDefinition
from twinklr.core.pipeline.definitions.display import build_display_pipeline
from twinklr.core.pipeline.definitions.moving_heads import build_moving_heads_pipeline
from twinklr.core.pipeline.show_stages import CombinedShowRenderStage
from twinklr.core.sequencer.display.xlights_mapping import XLightsMapping
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog

if TYPE_CHECKING:
    from twinklr.core.feature_engineering.loader import FEArtifactBundle


def build_combined_show_pipeline(
    *,
    choreo_graph: ChoreographyGraph,
    display_graph: ChoreographyGraph,
    template_catalog: TemplateCatalog,
    recipe_catalog: RecipeCatalog,
    display_groups: list[dict[str, object]],
    xlights_mapping: XLightsMapping,
    fixture_group: FixtureGroup,
    available_templates: list[str],
    moving_head_target_ids: set[str],
    fe_bundle: FEArtifactBundle | None = None,
    song_name: str = "sequence",
    max_iterations: int = 3,
    min_pass_score: float = 7.0,
    assets: AssetGenerationConfig | None = None,
) -> PipelineDefinition:
    """Build one DAG whose common prefix executes once before two planning branches."""

    display = build_display_pipeline(
        choreo_graph=display_graph,
        template_catalog=template_catalog,
        display_groups=display_groups,
        recipe_catalog=recipe_catalog,
        fe_bundle=fe_bundle,
        song_name=song_name,
        max_iterations=max_iterations,
        min_pass_score=min_pass_score,
        assets=assets,
        xlights_mapping=xlights_mapping,
        macro_choreo_graph=choreo_graph,
    )
    # The existing MH definition remains the authority for its planner-stage wiring.
    # Its renderer is replaced by the single combined barrier below.
    moving_heads = build_moving_heads_pipeline(
        display_groups=display_groups,
        fixture_count=len(fixture_group.expand_fixtures()),
        available_templates=available_templates,
        xsq_output_path=Path(f"{song_name}.unused.xsq"),
        max_iterations=max_iterations,
        min_pass_score=min_pass_score,
        fixture_groups=[
            {
                "fixture_id": fixture.fixture_id,
                "xlights_model_name": fixture.xlights_model_name,
                "channels": {
                    "pan": fixture.config.dmx_mapping.pan,
                    "tilt": fixture.config.dmx_mapping.tilt,
                    "dimmer": fixture.config.dmx_mapping.dimmer,
                    "color": fixture.config.dmx_mapping.color,
                    "gobo": fixture.config.dmx_mapping.gobo,
                    "shutter": fixture.config.dmx_mapping.shutter,
                },
            }
            for fixture in fixture_group.expand_fixtures()
        ],
    )
    common_ids = {"audio", "profile", "lyrics", "macro"}
    display_branch = [
        stage
        for stage in display.stages
        if stage.id not in common_ids and stage.id != "display_render"
    ]
    moving_stage = next(stage for stage in moving_heads.stages if stage.id == "moving_heads")
    final = StageDefinition(
        id="show_render",
        stage=CombinedShowRenderStage(
            fixture_group=fixture_group,
            choreo_graph=choreo_graph,
            display_graph=display_graph,
            xlights_mapping=xlights_mapping,
            recipe_catalog=recipe_catalog,
            moving_head_target_ids=moving_head_target_ids,
            available_templates=available_templates,
        ),
        inputs=["asset_resolution", "moving_heads"],
        input_type="dict[str, Any]",
        output_type="dict[str, Any]",
        description="Render both branches into one coordinated XSequence",
    )
    common = [stage for stage in display.stages if stage.id in common_ids]
    return PipelineDefinition(
        name="combined_show_pipeline",
        description="One macro plan coordinating moving heads and display",
        stages=[*common, *display_branch, moving_stage, final],
    )


__all__ = ["build_combined_show_pipeline"]
