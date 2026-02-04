"""Moving head rendering pipeline stage.

Wraps RenderingPipeline for pipeline execution.
Converts ChoreographyPlan to XSQ effects file.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from twinklr.core.config.fixtures import FixtureGroup
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult

logger = logging.getLogger(__name__)


class MovingHeadRenderingStage:
    """Pipeline stage for moving head rendering.

    Renders choreography plan to XSQ effects file using the RenderingPipeline.
    Consumes choreography_plan and beat_grid from pipeline state (set by MovingHeadStage).

    Input: dict with keys:
        - "moving_heads": ChoreographyPlan (from MovingHeadStage output)
    Output: Path to generated XSQ file

    State consumed:
        - "beat_grid": BeatGrid (set by MovingHeadStage)
        - "choreography_plan": ChoreographyPlan (set by MovingHeadStage)

    State stored:
        - "xsq_output_path": Path to generated XSQ file
        - "rendered_segment_count": Number of segments rendered

    Example:
        >>> stage = MovingHeadRenderingStage(
        ...     fixture_config_path="fixtures.json",
        ...     xsq_template_path="template.xsq",
        ...     xsq_output_path="output.xsq",
        ... )
        >>> input = {"moving_heads": choreography_plan}
        >>> result = await stage.execute(input, context)
        >>> if result.success:
        ...     xsq_path = result.output  # Path to XSQ file
    """

    def __init__(
        self,
        xsq_output_path: str | Path,
        xsq_template_path: str | Path | None = None,
        fixture_config_path: str | Path | None = None,
    ) -> None:
        """Initialize moving head rendering stage.

        Args:
            xsq_output_path: Path for output XSQ file
            xsq_template_path: Optional template XSQ to use as base
            fixture_config_path: Optional path to fixture config JSON
        """
        self.xsq_output_path = Path(xsq_output_path)
        self.xsq_template_path = Path(xsq_template_path) if xsq_template_path else None
        self.fixture_config_path = Path(fixture_config_path) if fixture_config_path else None

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "moving_head_rendering"

    async def execute(
        self,
        input: dict[str, Any],
        context: PipelineContext,
    ) -> StageResult[Path]:
        """Render choreography plan to XSQ file.

        Args:
            input: Dict with "moving_heads" (ChoreographyPlan)
            context: Pipeline context with state and config

        Returns:
            StageResult containing output XSQ Path

        Side Effects:
            - Stores "xsq_output_path" in context.state
            - Stores "rendered_segment_count" in context.state
            - Adds "mh_render_segments" to context.metrics
            - Adds "mh_render_transitions" to context.metrics
        """
        from twinklr.core.pipeline.result import failure_result, success_result
        from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline

        try:
            # Get choreography plan from input (output of MovingHeadStage)
            # Input may be a dict with keys or the ChoreographyPlan directly
            from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan

            if isinstance(input, ChoreographyPlan):
                choreography_plan = input
            elif isinstance(input, dict):
                choreography_plan = input.get("moving_heads")
            else:
                choreography_plan = None

            if choreography_plan is None:
                return failure_result(
                    "Missing 'moving_heads' input (ChoreographyPlan)",
                    stage_name=self.name,
                )

            # Get beat_grid from state (set by MovingHeadStage)
            beat_grid = context.get_state("beat_grid")
            if beat_grid is None:
                return failure_result(
                    "Missing 'beat_grid' in pipeline state (set by MovingHeadStage)",
                    stage_name=self.name,
                )

            # Load fixture configuration
            fixture_group = self._load_fixture_config(context)
            if fixture_group is None:
                return failure_result(
                    f"Could not load fixture config from {self.fixture_config_path}",
                    stage_name=self.name,
                )

            logger.debug(
                f"Starting rendering: {len(choreography_plan.sections)} sections, "
                f"{beat_grid.total_bars} bars"
            )

            # Create and run rendering pipeline
            pipeline = RenderingPipeline(
                choreography_plan=choreography_plan,
                beat_grid=beat_grid,
                fixture_group=fixture_group,
                job_config=context.job_config,
                output_path=self.xsq_output_path,
                template_xsq=self.xsq_template_path,
            )

            # Render to segments and export to XSQ
            segments = pipeline.render()

            logger.debug(f"✅ Rendered {len(segments)} segments to {self.xsq_output_path}")

            # Store state for downstream stages
            context.set_state("xsq_output_path", self.xsq_output_path)
            context.set_state("rendered_segment_count", len(segments))

            # Track metrics
            context.add_metric("mh_render_segments", len(segments))
            context.add_metric("mh_render_sections", len(choreography_plan.sections))

            return success_result(self.xsq_output_path, stage_name=self.name)

        except Exception as e:
            logger.exception("Rendering failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    def _load_fixture_config(self, context: PipelineContext) -> FixtureGroup | None:
        """Load fixture configuration.

        Tries in order:
        1. fixture_config_path (from constructor)
        2. job_config.fixture_config_path

        Args:
            context: Pipeline context with job_config

        Returns:
            FixtureGroup or None if loading fails
        """
        from twinklr.core.config.loader import load_fixture_group

        # Try constructor path first
        if self.fixture_config_path and self.fixture_config_path.exists():
            try:
                return load_fixture_group(self.fixture_config_path)
            except Exception as e:
                logger.warning(
                    f"Failed to load fixture config from {self.fixture_config_path}: {e}"
                )

        # Try job_config path
        if hasattr(context.job_config, "fixture_config_path"):
            fixture_path = getattr(context.job_config, "fixture_config_path", None)
            if fixture_path and Path(fixture_path).exists():
                try:
                    return load_fixture_group(Path(fixture_path))
                except Exception as e:
                    logger.warning(f"Failed to load fixture config from {fixture_path}: {e}")

        logger.error("No fixture configuration provided - fixture_config_path required")
        return None
