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
    from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
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
        - "layout_models", "layout_sha256": the xLights layout `twinklr run --layout`
          loaded, if any; only a physical render uses them
        - "template_admission": the render preflight's result, if any; a physical
          render applies only the presets it admitted, plays each template's effective
          variant where a section names none, and traces both

    State stored:
        - "xsq_output_path": Path to generated XSQ file
        - "delivery_artifacts": DeliveryArtifacts (.xsq, .xtiming files, .xmap)
        - "rendered_segment_count": Number of segments rendered
        - "rendered_sequence", "render_fingerprint": a physical render's sequence, the
          one its .xsq is written from and live injection reads, and its render identity
        - "unplayable_warning": a physical render's warning about the cues it kept
          dark under `on_unplayable`, when it kept any

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
            - Adds a physical render's record to the run's plan checkpoint, when the
              planning stage wrote one (`_record_render`)
        """
        from twinklr.core.agents.sequencer.moving_heads.models import (
            ChoreographyPlan as _ChoreographyPlan,
        )
        from twinklr.core.pipeline.result import failure_result, success_result
        from twinklr.core.pipeline.stage import resolve_typed_input
        from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
            UnsupportedRigShapeError,
        )
        from twinklr.core.sequencer.moving_heads.pipeline import (
            RenderingPipeline,
            TemplateAdmission,
        )

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
            admission = context.get_state("template_admission")
            if not isinstance(admission, TemplateAdmission):
                admission = None

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
                layout_models=context.get_state("layout_models"),
                layout_sha256=context.get_state("layout_sha256"),
                admission=admission,
            )

            # Render to segments and write the delivery
            segments = pipeline.render()
            if pipeline.render_record is not None:
                _record_render(pipeline, context)

            logger.debug(f"✅ Rendered {len(segments)} segments to {self.xsq_output_path}")

            # Store state for downstream stages
            context.set_state("xsq_output_path", self.xsq_output_path)
            context.set_state("delivery_artifacts", pipeline.artifacts)
            context.set_state("rendered_segment_count", len(segments))
            context.set_state("rendered_segments", tuple(segments))
            if pipeline.sequence is not None and pipeline.render_record is not None:
                context.set_state("rendered_sequence", pipeline.sequence)
                context.set_state(
                    "render_fingerprint", pipeline.render_record["render_fingerprint"]
                )
            if pipeline.unplayable_warning is not None:
                context.set_state("unplayable_warning", pipeline.unplayable_warning)

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
        """Load fixture configuration; see `load_render_fixture_group`."""
        return load_render_fixture_group(context, self.fixture_config_path)


def _record_render(pipeline: RenderingPipeline, context: PipelineContext) -> None:
    """Add a physical render's identity and inputs to the run's plan checkpoint.

    `twinklr eval-report` re-renders the plan from them exactly as this render ran: its
    `render_fingerprint` (the run's, checked against the re-render's), the render
    `policy`, the `beat_grid` it rendered against and the pre-planning gate's
    `admission` (null when none ran), under the checkpoint's `render` key, with the
    trace's input hashes (`inputs`) that name what differs on a mismatch. Only a
    checkpoint the planning stage wrote is extended; a legacy render records nothing.

    The checkpoint is replaced atomically. The delivery is already written, so a
    checkpoint that cannot be read or written is logged and left as it was.
    """
    import dataclasses
    import json
    import os
    import stat
    import tempfile

    if not context.job_config.write_checkpoint or context.output_dir is None:
        return
    checkpoint_path = context.output_dir / "checkpoints" / "plans" / "final.json"
    if not checkpoint_path.exists():
        return
    record = pipeline.render_record
    assert record is not None  # set by a physical render
    try:
        data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        data["render"] = {
            "render_fingerprint": record["render_fingerprint"],
            "policy": pipeline.job_config.moving_heads.model_dump(mode="json"),
            "beat_grid": pipeline.beat_grid.model_dump(mode="json"),
            "admission": (
                None if pipeline.admission is None else dataclasses.asdict(pipeline.admission)
            ),
            "inputs": {
                key: record[key]
                for key in (
                    "fixtures",
                    "template_sha256",
                    "beat_grid_sha256",
                    "renderer_revision",
                    "encoder_version",
                )
            },
        }
        handle, name = tempfile.mkstemp(
            dir=checkpoint_path.parent, prefix=".final.", suffix=".json.tmp"
        )
        temporary = Path(name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2)
            # The replacement keeps the checkpoint's mode (a temp file is created 0600).
            temporary.chmod(stat.S_IMODE(checkpoint_path.stat().st_mode))
            temporary.replace(checkpoint_path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    except (OSError, ValueError, TypeError) as error:
        logger.warning(
            "physical_v2: could not record the render in the checkpoint %s, so "
            "`twinklr eval-report` cannot re-render this run: %s",
            checkpoint_path,
            error,
        )


def load_render_fixture_group(
    context: PipelineContext, fixture_config_path: Path | None
) -> FixtureGroup | None:
    """Load the fixtures a moving-head render targets.

    Tries in order:
    1. the live layout's reconciled rig in state (`live_fixture_group`)
    2. `fixture_config_path`
    3. job_config.fixture_config_path, relative to `job_config_dir` in state

    Args:
        context: Pipeline context with job_config
        fixture_config_path: Fixture config given to the stage, if any

    Returns:
        FixtureGroup or None if loading fails
    """
    from twinklr.core.config.fixtures import FixtureGroup
    from twinklr.core.config.loader import load_fixture_group

    live_fixture_group = context.get_state("live_fixture_group")
    if isinstance(live_fixture_group, FixtureGroup):
        return live_fixture_group

    # Try constructor path first
    if fixture_config_path and fixture_config_path.exists():
        try:
            return load_fixture_group(fixture_config_path)
        except Exception as e:
            logger.warning(f"Failed to load fixture config from {fixture_config_path}: {e}")

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


class RenderPreflightStage:
    """Refuse a job the moving-head renderer cannot render, before any planning.

    Runs right after audio analysis; every planner (profile, lyrics, macro, moving
    heads) reads the audio through it, so a refusal spends no provider request. A
    `legacy_v1` job passes through untouched. A `physical_v2` job is checked against
    the fixtures the render stage will load (`preflight_render_policy`), the templates
    the planner will be offered (`offered_template_ids`; every one must carry physical
    data, and each must dry-compile on this rig and plan the dark repositioning between
    its own cues under the job's `reposition_fallback`, at the placements its
    `on_unplayable` leaves to the gate: `check_physical_templates`; a template of the
    shipped physical catalog passes through the first of its base and declared presets
    that does, its effective variant, and one none of whose variants passes is left out
    of the offer instead of refusing the run, unless none remains; the result is stored
    in state as `template_admission`, which the planner offers and the render applies
    and traces), the
    song's musical phase map, built from the detected BeatGrid, which the renderer
    never infers (it holds every fixture dark outside the map's covered span, which
    is logged), and, when the run supplies an xLights layout (`layout_models` in
    state), every fixture's model (`check_physical_models`).

    Input and output: the audio stage's SongBundle, unchanged.
    """

    def __init__(
        self, available_templates: list[str], fixture_config_path: str | Path | None = None
    ) -> None:
        self.available_templates = list(available_templates)
        self.fixture_config_path = Path(fixture_config_path) if fixture_config_path else None

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "render_preflight"

    async def execute(self, input: Any, context: PipelineContext) -> StageResult[Any]:
        """Pass the audio through, or fail with the reason the job cannot render."""
        from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
        from twinklr.core.agents.sequencer.moving_heads.stage import (
            check_regeneration_base,
            resolve_beat_grid,
        )
        from twinklr.core.config.render_policy import (
            UnsupportedRenderModeError,
            preflight_render_policy,
        )
        from twinklr.core.pipeline.result import failure_result, success_result
        from twinklr.core.sequencer.moving_heads.export.frame_encoder import PhysicalOutputError
        from twinklr.core.sequencer.moving_heads.export.xsq_adapter import check_physical_models
        from twinklr.core.sequencer.moving_heads.pipeline import (
            check_physical_templates,
            offered_template_ids,
        )
        from twinklr.core.sequencer.moving_heads.templates.data_loader import (
            in_physical_catalog,
        )
        from twinklr.core.sequencer.timing.musical_phase import (
            MusicalPhaseError,
            build_musical_phase_map,
        )

        job_config = context.job_config
        if job_config.moving_heads.mode == "legacy_v1":
            return success_result(input, stage_name=self.name)

        fixture_group = load_render_fixture_group(context, self.fixture_config_path)
        if fixture_group is None:
            return failure_result(
                "physical_v2 needs the rig's fixtures before planning; none could be loaded",
                stage_name=self.name,
            )
        try:
            preflight_render_policy(job_config, fixture_group)
            offered = offered_template_ids(job_config, self.available_templates)
            unrenderable = [t for t in self.available_templates if t not in offered]
            if unrenderable:
                raise UnsupportedRenderModeError(
                    "moving_heads.mode 'physical_v2' would offer the planner templates "
                    f"without physical data, which cannot render: {sorted(unrenderable)}"
                )
            beat_grid = resolve_beat_grid(context, input)
            try:
                phase_map = build_musical_phase_map(beat_grid)
            except MusicalPhaseError as error:
                raise UnsupportedRenderModeError(
                    "moving_heads.mode 'physical_v2' needs a musical phase over the song's "
                    f"detected beats, and this beat grid gives none: {error}. The renderer "
                    "does not infer tempo"
                ) from error
            logger.info(
                "physical_v2 renders the covered span [%s, %s] ms of the song's [0, %s] ms; "
                "every fixture is held dark outside it",
                phase_map.covered_start_ms,
                phase_map.covered_end_ms,
                phase_map.duration_ms,
            )
            admission = check_physical_templates(
                offered,
                beat_grid=beat_grid,
                fixture_group=fixture_group,
                initial_states=job_config.moving_heads.initial_states,
                failure_mode=job_config.moving_heads.reposition_fallback,
                on_unplayable=job_config.moving_heads.on_unplayable,
                excludable=[t for t in offered if in_physical_catalog(t)],
            )
            layout_models = context.get_state("layout_models")
            if layout_models is not None:
                check_physical_models(fixture_group.expand_fixtures(), layout_models)
        except (UnsupportedRenderModeError, PhysicalOutputError) as error:
            logger.error("Render preflight refused the job: %s", error)
            return failure_result(str(error), stage_name=self.name)
        base = context.get_state("regeneration_base_plan")
        if isinstance(base, ChoreographyPlan):
            # A physical regeneration re-renders the whole song from the injected plan;
            # one this gate would not render as injected is refused here, before any
            # planner.
            try:
                check_regeneration_base(
                    base, str(context.get_state("regeneration_section_id")), admission
                )
            except ValueError as error:
                logger.error("Render preflight refused the regeneration: %s", error)
                return failure_result(str(error), stage_name=self.name)
        context.set_state("template_admission", admission)
        return success_result(input, stage_name=self.name)
