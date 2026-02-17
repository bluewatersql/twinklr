"""Display pipeline definition factory.

Builds the complete display sequencer pipeline:
    audio → profile + lyrics → macro → groups (FAN_OUT) →
    aggregate → holistic → asset_resolution → display_render

This pipeline generates xLights group-level choreography for display
elements (outlines, trees, props, arches, etc.), coordinating across
display groups and rendering to an xLights .xsq sequence file.
"""

from __future__ import annotations

from twinklr.core.agents.assets.stage import AssetCreationStage
from twinklr.core.agents.sequencer.group_planner.holistic_stage import (
    HolisticEvaluatorStage,
)
from twinklr.core.agents.sequencer.group_planner.stage import (
    GroupPlanAggregatorStage,
    GroupPlannerStage,
)
from twinklr.core.pipeline import ExecutionPattern, PipelineDefinition, StageDefinition
from twinklr.core.pipeline.definitions.common import build_common_stages
from twinklr.core.pipeline.display_stages import (
    AssetResolutionStage,
    DisplayRenderStage,
)
from twinklr.core.sequencer.display.xlights_mapping import XLightsMapping
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
)


def build_display_pipeline(
    choreo_graph: ChoreographyGraph,
    template_catalog: TemplateCatalog,
    display_groups: list[dict[str, object]],
    *,
    song_name: str = "sequence",
    max_iterations: int = 3,
    min_pass_score: float = 0.7,
    enable_holistic: bool = True,
    enable_assets: bool = False,
    xlights_mapping: XLightsMapping | None = None,
) -> PipelineDefinition:
    """Build the display sequencer pipeline.

    Stages:
        audio → profile + lyrics → macro → groups (FAN_OUT) →
        aggregate → holistic → [asset_creation →] asset_resolution → display_render

    The holistic stage is an informational pass-through that evaluates
    the complete GroupPlanSet for cross-section quality without altering
    the plan data.

    When ``enable_assets`` is True, the ``AssetCreationStage`` is inserted
    between holistic evaluation and asset resolution to extract, enrich,
    and generate figurative/narrative assets.

    Args:
        choreo_graph: Choreographic display configuration.
        template_catalog: Available group templates for planning.
        display_groups: Display group configs for MacroPlannerStage.
        song_name: Song name for plan set identification.
        max_iterations: Maximum GroupPlanner iteration cycles.
        min_pass_score: Minimum score for section plan approval (0.0-1.0).
        enable_holistic: Include the holistic evaluation stage.
        enable_assets: Include the asset creation stage (extract → enrich → generate).
        xlights_mapping: xLights element name resolution.

    Returns:
        PipelineDefinition ready for execution.

    Example:
        >>> pipeline = build_display_pipeline(
        ...     choreo_graph=graph,
        ...     template_catalog=catalog,
        ...     display_groups=[{"role_key": "OUTLINE", "model_count": 10, ...}],
        ...     enable_holistic=True,
        ...     enable_assets=True,
        ... )
        >>> result = await PipelineExecutor().execute(pipeline, audio_path, context)
    """
    common = build_common_stages(display_groups=display_groups)

    # GroupPlanner FAN_OUT per macro section
    display_stages: list[StageDefinition] = [
        StageDefinition(
            id="groups",
            stage=GroupPlannerStage(
                choreo_graph=choreo_graph,
                template_catalog=template_catalog,
                max_iterations=max_iterations,
                min_pass_score=min_pass_score,
            ),
            inputs=["macro"],
            pattern=ExecutionPattern.FAN_OUT,
            input_type="MacroSectionPlan",
            output_type="SectionCoordinationPlan",
            description="Generate section coordination plans (parallel per section)",
        ),
        StageDefinition(
            id="aggregate",
            stage=GroupPlanAggregatorStage(plan_set_id=f"{song_name}_group_plan"),
            inputs=["groups"],
            input_type="list[SectionCoordinationPlan]",
            output_type="GroupPlanSet",
            description="Aggregate section plans into GroupPlanSet",
        ),
    ]

    # Holistic evaluation (informational pass-through)
    aggregate_output_id = "aggregate"
    if enable_holistic:
        display_stages.append(
            StageDefinition(
                id="holistic",
                stage=HolisticEvaluatorStage(
                    choreo_graph=choreo_graph,
                    template_catalog=template_catalog,
                ),
                inputs=["aggregate"],
                input_type="GroupPlanSet",
                output_type="GroupPlanSet",
                description="Evaluate complete GroupPlanSet quality",
            )
        )
        aggregate_output_id = "holistic"

    # Asset creation (if enabled) — extract, enrich, and generate assets
    resolution_inputs = [aggregate_output_id]
    if enable_assets:
        display_stages.append(
            StageDefinition(
                id="asset_creation",
                stage=AssetCreationStage(),
                inputs=[aggregate_output_id],
                input_type="GroupPlanSet",
                output_type="GroupPlanSet",
                description="Extract, enrich, and generate assets (pass-through; catalog in state)",
            )
        )
        resolution_inputs.append("asset_creation")

    # Asset resolution and rendering
    display_stages.extend(
        [
            StageDefinition(
                id="asset_resolution",
                stage=AssetResolutionStage(),
                inputs=resolution_inputs,
                input_type="GroupPlanSet | dict[str, GroupPlanSet]",
                output_type="GroupPlanSet",
                description="Resolve plan assets against catalog (overlay rendering)",
            ),
            StageDefinition(
                id="display_render",
                stage=DisplayRenderStage(
                    choreo_graph=choreo_graph,
                    xlights_mapping=xlights_mapping,
                ),
                inputs=["asset_resolution"],
                input_type="GroupPlanSet",
                output_type="dict[str, Any]",
                description="Render effects into xLights .xsq sequence",
            ),
        ]
    )

    return PipelineDefinition(
        name="display_pipeline",
        description="Display group choreography pipeline",
        fail_fast=True,
        stages=common + display_stages,
    )
