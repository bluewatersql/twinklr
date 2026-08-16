"""Final render barrier for the coordinated moving-head + display show."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.formats.xlights.sequence.models.xsq import TimeMarker
from twinklr.core.pipeline.display_stages import DisplayRenderStage
from twinklr.core.pipeline.result import StageResult, failure_result, success_result
from twinklr.core.sequencer.planning import GroupPlanSet, MacroPlan
from twinklr.core.sequencer.show_coordination import (
    coordinate_moving_head_plan,
    coordinate_moving_head_segments,
)
from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph

if TYPE_CHECKING:
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.sequencer.display.xlights_mapping import XLightsMapping
    from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog


class CombinedShowRenderStage:
    """Compile both branches in memory and append them to one ``XSequence`` once."""

    def __init__(
        self,
        *,
        fixture_group: FixtureGroup,
        choreo_graph: ChoreographyGraph,
        display_graph: ChoreographyGraph,
        xlights_mapping: XLightsMapping,
        recipe_catalog: RecipeCatalog,
        moving_head_target_ids: set[str],
        available_templates: list[str],
    ) -> None:
        self._fixture_group = fixture_group
        self._graph = choreo_graph
        self._moving_head_target_ids = set(moving_head_target_ids)
        self._available_templates = list(available_templates)
        self._display_stage = DisplayRenderStage(
            choreo_graph=display_graph,
            xlights_mapping=xlights_mapping,
            recipe_catalog=recipe_catalog,
            coordinate_show=True,
            moving_head_target_ids=moving_head_target_ids,
            coordination_graph=choreo_graph,
        )

    @property
    def name(self) -> str:
        return "combined_show_render"

    async def execute(
        self,
        input: dict[str, Any],
        context: PipelineContext,
    ) -> StageResult[dict[str, Any]]:
        """Render the barrier input without rebuilding the macro plan or BeatGrid."""

        from twinklr.core.agents.sequencer.moving_heads.rendering_stage import (
            MovingHeadRenderingStage,
        )
        from twinklr.core.sequencer.moving_heads.delivery import build_sequence
        from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline

        try:
            mh_plan = ChoreographyPlan.model_validate(input.get("moving_heads"))
            display_plan = GroupPlanSet.model_validate(input.get("asset_resolution"))
            macro_plan = MacroPlan.model_validate(context.get_state("macro_plan"))
            beat_grid = context.get_state("beat_grid")
            if beat_grid is None:
                raise ValueError("combined render requires AudioAnalysisStage BeatGrid")

            coordinated_mh = coordinate_moving_head_plan(
                mh_plan,
                macro_plan,
                beat_grid,
                self._moving_head_target_ids,
                self._available_templates,
                self._graph,
            )
            media_file, song, artist = MovingHeadRenderingStage._resolve_media_metadata(context)
            timeline_tracks = MovingHeadRenderingStage._build_timeline_tracks(beat_grid, context)
            pipeline = RenderingPipeline(
                choreography_plan=coordinated_mh,
                beat_grid=beat_grid,
                fixture_group=self._fixture_group,
                job_config=context.job_config,
                output_path=None,
                timeline_tracks=timeline_tracks,
                media_file=media_file,
                song=song,
                artist=artist,
            )
            raw_segments = pipeline.render()
            segments = coordinate_moving_head_segments(
                raw_segments,
                macro_plan,
                beat_grid,
                self._graph,
                moving_head_target_ids=self._moving_head_target_ids,
            )
            markers = [
                TimeMarker(
                    name=section.section.section_id,
                    time_ms=section.section.start_ms,
                    end_time_ms=section.section.end_ms,
                )
                for section in macro_plan.sections
            ]
            sequence = build_sequence(
                segments,
                markers,
                fixture_group=self._fixture_group,
                media_file=media_file,
                duration_ms=int(beat_grid.duration_ms),
                song=song,
                artist=artist,
                timeline_tracks=timeline_tracks,
            )
            context.set_state("sequence", sequence)
            context.set_state("coordinated_mh_plan", coordinated_mh)
            context.set_state("rendered_segments", tuple(segments))
            context.set_state("mh_render_beat_grid", beat_grid)

            display_result = await self._display_stage.execute(
                {"plan_set": display_plan, "sequence": sequence}, context
            )
            if not display_result.success or display_result.output is None:
                raise ValueError(display_result.error or "display render failed")
            context.set_state("display_render_beat_grid", beat_grid)
            return success_result(
                {
                    **display_result.output,
                    "moving_head_plan": coordinated_mh,
                    "moving_head_segments": tuple(segments),
                    "beat_grid": beat_grid,
                },
                stage_name=self.name,
            )
        except Exception as error:
            return failure_result(str(error), stage_name=self.name)


__all__ = ["CombinedShowRenderStage"]
