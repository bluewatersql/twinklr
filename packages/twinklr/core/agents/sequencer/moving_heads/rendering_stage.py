"""Moving head rendering pipeline stage.

Wraps RenderingPipeline for pipeline execution.
Converts ChoreographyPlan to XSQ effects file.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
    from twinklr.core.config.fixtures import FixtureGroup
    from twinklr.core.formats.xlights.sequence.models.xsq import TimingTrack
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult
    from twinklr.core.sequencer.timing.beat_grid import BeatGrid

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
        - "delivery_artifacts": DeliveryArtifacts (.xsq, .xtiming files, .xmap)
        - "rendered_segment_count": Number of segments rendered

    Example:
        >>> stage = MovingHeadRenderingStage(
        ...     fixture_config_path="fixtures.json",
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
        fixture_config_path: str | Path | None = None,
    ) -> None:
        """Initialize moving head rendering stage.

        Args:
            xsq_output_path: Path for the delivered .xsq; the .xtiming and .xmap
                sidecars are written beside it.
            fixture_config_path: Optional path to fixture config JSON
        """
        self.xsq_output_path = Path(xsq_output_path)
        self.fixture_config_path = Path(fixture_config_path) if fixture_config_path else None

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "moving_head_rendering"

    async def execute(
        self,
        input: ChoreographyPlan | dict[str, Any],
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
            - Stores "delivery_artifacts" in context.state
            - Stores "rendered_segment_count" in context.state
            - Adds "mh_render_segments" to context.metrics
            - Adds "mh_render_transitions" to context.metrics
        """
        from twinklr.core.agents.sequencer.moving_heads.models import (
            ChoreographyPlan as _ChoreographyPlan,
        )
        from twinklr.core.pipeline.result import failure_result, success_result
        from twinklr.core.pipeline.stage import resolve_typed_input
        from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
            UnsupportedRigShapeError,
        )
        from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline

        try:
            choreography_plan, _extras = resolve_typed_input(
                input, _ChoreographyPlan, "moving_heads"
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

            # Build timeline tracks from audio data
            timeline_tracks = self._build_timeline_tracks(beat_grid, context)
            media_file, song, artist = self._resolve_media_metadata(context)

            # Create and run rendering pipeline
            pipeline = RenderingPipeline(
                choreography_plan=choreography_plan,
                beat_grid=beat_grid,
                fixture_group=fixture_group,
                job_config=context.job_config,
                output_path=self.xsq_output_path,
                timeline_tracks=timeline_tracks,
                media_file=media_file,
                song=song,
                artist=artist,
            )

            # Render to segments and write the delivery
            segments = pipeline.render()

            logger.debug(f"✅ Rendered {len(segments)} segments to {self.xsq_output_path}")

            # Store state for downstream stages
            context.set_state("xsq_output_path", self.xsq_output_path)
            context.set_state("delivery_artifacts", pipeline.artifacts)
            context.set_state("rendered_segment_count", len(segments))
            context.set_state("rendered_segments", tuple(segments))

            # Track metrics
            context.add_metric("mh_render_segments", len(segments))
            context.add_metric("mh_render_sections", len(choreography_plan.sections))

            return success_result(self.xsq_output_path, stage_name=self.name)

        except UnsupportedRigShapeError as e:
            # The rig cannot fill a group the plan's template addresses (e.g. a template
            # written for LEFT/RIGHT against a single-head rig). The exception text
            # already names the template, step, group and the rig's roles, so it is the
            # actionable message — reported without a traceback, which would bury it.
            logger.error("Rendering failed: %s", e)
            return failure_result(
                f"{e} Pick a template your rig can fill, or add fixtures to the rig "
                f"config so the group has heads to address.",
                stage_name=self.name,
            )
        except Exception as e:
            logger.exception("Rendering failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    @staticmethod
    def _resolve_media_metadata(context: PipelineContext) -> tuple[str, str, str]:
        """Resolve the sequence head's media file, song and artist from the audio bundle.

        The emitted `.xsq` names the audio it was choreographed against; an empty
        `mediaFile` is fatal to both xLights and Twinklr's own parser, so the resolver
        always returns a non-empty name.

        Args:
            context: Pipeline context with audio_bundle in state.

        Returns:
            `(media_file, song, artist)`.
        """
        from twinklr.core.formats.xlights.sequence.fresh import resolve_media_file

        audio_bundle = context.get_state("audio_bundle")
        media_file = resolve_media_file(getattr(audio_bundle, "audio_path", None))

        embedded = getattr(getattr(audio_bundle, "metadata", None), "embedded", None)
        song = getattr(embedded, "title", None) or ""
        artist = getattr(embedded, "artist", None) or ""
        return media_file, song, artist

    @staticmethod
    def _build_timeline_tracks(
        beat_grid: BeatGrid,
        context: PipelineContext,
    ) -> list[TimingTrack]:
        """Build timeline tracks from audio data in pipeline context.

        Reads the audio bundle from context state to extract lyrics and
        phonemes, then builds timing tracks according to job config.

        Args:
            beat_grid: Musical timing grid.
            context: Pipeline context with audio_bundle in state.

        Returns:
            List of TimingTrack objects for XSQ export.
        """
        from twinklr.core.formats.xlights.sequence.timeline import build_timeline_tracks

        audio_bundle = context.get_state("audio_bundle")
        lyrics_bundle = getattr(audio_bundle, "lyrics", None) if audio_bundle else None
        phoneme_bundle = getattr(audio_bundle, "phonemes", None) if audio_bundle else None

        return build_timeline_tracks(
            config=context.job_config.timeline_tracks,
            beat_grid=beat_grid,
            lyrics_bundle=lyrics_bundle,
            phoneme_bundle=phoneme_bundle,
        )

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
        from twinklr.core.config.fixtures import FixtureGroup
        from twinklr.core.config.loader import load_fixture_group

        live_fixture_group = context.get_state("live_fixture_group")
        if isinstance(live_fixture_group, FixtureGroup):
            return live_fixture_group

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
            if fixture_path:
                candidate_path = Path(fixture_path)
                if not candidate_path.is_absolute():
                    job_config_dir = context.get_state("job_config_dir")
                    if isinstance(job_config_dir, Path):
                        candidate_path = job_config_dir / candidate_path

                if candidate_path.exists():
                    try:
                        return load_fixture_group(candidate_path)
                    except Exception as e:
                        logger.warning(
                            "Failed to load fixture config from %s: %s",
                            candidate_path,
                            e,
                        )
                else:
                    logger.warning("Fixture config does not exist at %s", candidate_path)

        logger.error("No fixture configuration provided - fixture_config_path required")
        return None
