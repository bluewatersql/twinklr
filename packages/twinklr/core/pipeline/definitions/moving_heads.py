"""Moving-head pipeline definition factory.

Builds the complete moving-head sequencer pipeline:
    audio → profile + lyrics → macro → moving_heads → render

This pipeline generates DMX choreography for moving head fixtures,
rendering to an xLights .xsq sequence file.
"""

from __future__ import annotations

from pathlib import Path

from twinklr.core.agents.sequencer.moving_heads.rendering_stage import (
    MovingHeadRenderingStage,
)
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage
from twinklr.core.pipeline import PipelineDefinition, StageDefinition
from twinklr.core.pipeline.definitions.common import build_common_stages


def build_moving_heads_pipeline(
    display_groups: list[dict[str, object]],
    *,
    fixture_count: int,
    available_templates: list[str],
    xsq_output_path: Path,
    max_iterations: int = 3,
    min_pass_score: float = 7.0,
    xsq_template_path: Path | None = None,
    fixture_config_path: Path | None = None,
) -> PipelineDefinition:
    """Build the moving-head sequencer pipeline.

    Stages:
        audio → profile + lyrics → macro → moving_heads → render

    Args:
        display_groups: Display group configs for MacroPlannerStage.
        fixture_count: Number of moving head fixtures.
        available_templates: List of available template IDs.
        xsq_output_path: Output path for the generated .xsq file.
        max_iterations: Maximum agent orchestration iterations.
        min_pass_score: Minimum score for plan approval (0-10).
        xsq_template_path: Optional template .xsq to merge into.
        fixture_config_path: Optional path to fixture config JSON.

    Returns:
        PipelineDefinition ready for execution.

    Example:
        >>> pipeline = build_moving_heads_pipeline(
        ...     display_groups=[{"role_key": "MH", "model_count": 4, "group_type": "mh"}],
        ...     fixture_count=4,
        ...     available_templates=["sweep_slow"],
        ...     xsq_output_path=Path("output.xsq"),
        ... )
        >>> result = await PipelineExecutor().execute(pipeline, audio_path, context)
    """
    common = build_common_stages(display_groups=display_groups)

    mh_stages = [
        StageDefinition(
            id="moving_heads",
            stage=MovingHeadStage(
                fixture_count=fixture_count,
                available_templates=available_templates,
                max_iterations=max_iterations,
                min_pass_score=min_pass_score,
            ),
            inputs=["audio", "profile", "lyrics", "macro"],
            input_type="dict[str, Any]",
            output_type="ChoreographyPlan",
            description="Generate moving head choreography",
        ),
        StageDefinition(
            id="render",
            stage=MovingHeadRenderingStage(
                xsq_output_path=xsq_output_path,
                xsq_template_path=xsq_template_path,
                fixture_config_path=fixture_config_path,
            ),
            inputs=["moving_heads"],
            input_type="ChoreographyPlan",
            output_type="Path",
            description="Render choreography to XSQ",
        ),
    ]

    return PipelineDefinition(
        name="moving_heads_pipeline",
        description="Moving head DMX choreography pipeline",
        fail_fast=True,
        stages=common + mh_stages,
    )
