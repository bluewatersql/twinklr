"""Final render barrier for the coordinated moving-head + display show."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.formats.xlights.sequence.models.xsq import TimeMarker
from twinklr.core.pipeline.display_stages import DisplayRenderStage
from twinklr.core.pipeline.result import StageResult, failure_result, success_result
from twinklr.core.sequencer.planning import GroupPlanSet, MacroPlan
from twinklr.core.sequencer.show_coordination import moving_head_dark_spans
from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph

if TYPE_CHECKING:
    from twinklr.core.formats.xlights.sequence.models.xsq import TimingTrack, XSequence
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.sequencer.display.xlights_mapping import XLightsMapping
    from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
    from twinklr.core.sequencer.timing.beat_grid import BeatGrid


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
    ) -> None:
        self._fixture_group = fixture_group
        self._graph = choreo_graph
        self._xlights_mapping = xlights_mapping
        self._moving_head_target_ids = set(moving_head_target_ids)
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
        """Render the barrier input without rebuilding the macro plan or BeatGrid.

        The moving heads render on the frame grid: the coordination schedule's rests
        become the renderer's dark spans, planned before section entry
        and repositioning (`moving_head_dark_spans`), and the output carries the render
        record and frame runs the export traces and budgets, and the record `twinklr
        show` adds to the plan checkpoint once the export is written
        (`checkpoint_record`), for `eval-report` to re-render. A section's palette-role
        colour resolves through its macro palette, as under `twinklr run`
        (`section_palettes`). The macro focal role is not projected onto the moving
        heads yet (a known regression the song-intent rendering plan fixes); the render
        record says so per section.
        """

        from twinklr.core.agents.sequencer.moving_heads.rendering_stage import (
            MovingHeadRenderingStage,
        )

        try:
            mh_plan = ChoreographyPlan.model_validate(input.get("moving_heads"))
            display_plan = GroupPlanSet.model_validate(input.get("asset_resolution"))
            macro_plan = MacroPlan.model_validate(context.get_state("macro_plan"))
            beat_grid = context.get_state("beat_grid")
            if beat_grid is None:
                raise ValueError("combined render requires AudioAnalysisStage BeatGrid")

            media_file, song, artist = MovingHeadRenderingStage._resolve_media_metadata(context)
            timeline_tracks = MovingHeadRenderingStage._build_timeline_tracks(beat_grid, context)
            markers = [
                TimeMarker(
                    name=section.section.section_id,
                    time_ms=section.section.start_ms,
                    end_time_ms=section.section.end_ms,
                )
                for section in macro_plan.sections
            ]
            sequence, moving_heads = self._render_moving_heads(
                mh_plan,
                macro_plan,
                beat_grid,
                context,
                markers=markers,
                media_file=media_file,
                song=song,
                artist=artist,
                timeline_tracks=timeline_tracks,
            )
            context.set_state("sequence", sequence)
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
                    **moving_heads,
                    "beat_grid": beat_grid,
                    "evaluation_contract": {
                        "macro_plan": macro_plan,
                        "choreography_graph": self._graph,
                        "xlights_mapping": self._xlights_mapping,
                        "moving_head_target_ids": sorted(self._moving_head_target_ids),
                    },
                },
                stage_name=self.name,
            )
        except Exception as error:
            return failure_result(str(error), stage_name=self.name)

    def _render_moving_heads(
        self,
        mh_plan: ChoreographyPlan,
        macro_plan: MacroPlan,
        beat_grid: BeatGrid,
        context: PipelineContext,
        *,
        markers: list[TimeMarker],
        media_file: str,
        song: str,
        artist: str,
        timeline_tracks: list[TimingTrack],
    ) -> tuple[XSequence, dict[str, Any]]:
        """Render the moving heads, resting them dark where the schedule does.

        Returns:
            The sequence holding the moving-head frame runs, and the stage output's
            moving-head entries: the plan as rendered, its planned segments, the render
            record, the frame runs and the render's checkpoint record.
        """
        from twinklr.core.sequencer.moving_heads.delivery import build_sequence
        from twinklr.core.sequencer.moving_heads.diagnostics import MHDiagnostic
        from twinklr.core.sequencer.moving_heads.pipeline import (
            RenderingPipeline,
            TemplateAdmission,
        )
        from twinklr.core.sequencer.moving_heads.song_intent import section_palettes

        admission = context.get_state("template_admission")
        pipeline = RenderingPipeline(
            choreography_plan=mh_plan,
            beat_grid=beat_grid,
            fixture_group=self._fixture_group,
            job_config=context.job_config,
            output_path=None,
            timeline_tracks=timeline_tracks,
            media_file=media_file,
            song=song,
            artist=artist,
            layout_models=context.get_state("layout_models"),
            layout_sha256=context.get_state("layout_sha256"),
            admission=admission if isinstance(admission, TemplateAdmission) else None,
            dark_spans=moving_head_dark_spans(
                macro_plan,
                beat_grid,
                self._graph,
                moving_head_target_ids=self._moving_head_target_ids,
            ),
            palettes=section_palettes(macro_plan),
        )
        segments = pipeline.render()
        assert pipeline.render_record is not None  # set by every render
        sequence = build_sequence(
            pipeline.requests,
            markers,
            media_file=media_file,
            duration_ms=int(beat_grid.duration_ms),
            song=song,
            artist=artist,
            timeline_tracks=timeline_tracks,
        )
        unprojected = [
            MHDiagnostic(
                code="unsupported_attribute",
                severity="warning",
                message=(
                    f"section {section.section.section_id!r}: the show's macro focal role "
                    "(intensity) is not projected onto the moving heads yet, a known "
                    "regression being fixed under "
                    "changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md; the "
                    "heads' colour follows the plan's colour through the section's macro "
                    "palette"
                ),
                section_id=section.section.section_id,
                action="unchanged",
            ).model_dump(mode="json")
            for section in macro_plan.sections
        ]
        record = {
            **pipeline.render_record,
            "diagnostics": [*pipeline.render_record["diagnostics"], *unprojected],
        }
        return sequence, {
            "moving_head_plan": mh_plan,
            "moving_head_segments": tuple(segments),
            "render_record": record,
            "moving_head_runs": pipeline.runs,
            "checkpoint_record": pipeline.checkpoint_record(),
        }


__all__ = ["CombinedShowRenderStage"]
