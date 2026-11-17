"""Re-render choreography plans through the sequencing pipeline.

This module re-executes the full MovingHead sequencing pipeline to generate
IR segments and, for a physical render, its encoded frames from a saved plan.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.fixtures import FixtureCapabilities
from twinklr.core.config.loader import load_fixture_group
from twinklr.core.config.models import JobConfig, MHRenderPolicy
from twinklr.core.config.render_policy import UnsupportedRenderModeError
from twinklr.core.reporting.evaluation.collect import RecordedRender
from twinklr.core.sequencer.moving_heads.export.frame_encoder import EncodedFixtureFrame
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.moving_heads.templates import get_template, load_builtin_templates
from twinklr.core.sequencer.moving_heads.templates.data_loader import admit_physical_catalog
from twinklr.core.sequencer.moving_heads.templates.library import TemplateNotFoundError
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PhysicalRerender:
    """What a physical re-render adds to its result.

    Attributes:
        frames: Every fixture's encoded frames, in rig order.
        profiles: Each fixture's physical profile.
        render_record: The render's trace record (`RenderingPipeline.render_record`).
        run_fingerprint: The render fingerprint the run recorded.
        run_inputs: The input hashes the run recorded (`RecordedRender.inputs`).
        rerender_inputs: The re-render's own, in the same shape (`inputs` of
            `RenderingPipeline.checkpoint_record`).
    """

    frames: tuple[EncodedFixtureFrame, ...]
    profiles: dict[str, FixtureCapabilities]
    render_record: dict[str, Any]
    run_fingerprint: str
    run_inputs: Mapping[str, Any]
    rerender_inputs: Mapping[str, Any]

    @property
    def fingerprint(self) -> str:
        """The re-render's own render fingerprint."""
        return str(self.render_record["render_fingerprint"])


class RerenderResult:
    """Result of re-rendering a choreography plan.

    Contains all compiled segments, audio features, and fixture contexts
    needed for analysis.

    Attributes:
        segments: Compiled IR segments with curves
        song_features: Audio analysis results (dict)
        fixture_group: Fixture configuration
        beat_grid: Timing grid for bar/ms conversions
        fixture_contexts: List of fixture contexts with roles
        physical: A physical re-render's frames, profiles and identity; None for legacy
    """

    def __init__(
        self,
        *,
        segments: list[Any],
        song_features: dict[str, Any],
        fixture_group: Any,
        beat_grid: BeatGrid,
        fixture_contexts: list[Any],
        physical: PhysicalRerender | None = None,
    ):
        self.segments = segments
        self.song_features = song_features
        self.fixture_group = fixture_group
        self.beat_grid = beat_grid
        self.fixture_contexts = fixture_contexts
        self.physical = physical


def admit_plan_templates(plan: ChoreographyPlan, policy: MHRenderPolicy) -> None:
    """Load the templates a physical plan's run could name, and refuse a plan naming any
    other: the physical family catalog is admitted as `twinklr run` admits it.

    Raises:
        UnsupportedRenderModeError: Naming each template id the registry does not hold,
            such as one a run loaded with `--template-dir`.
    """
    load_builtin_templates()
    admit_physical_catalog(JobConfig(schema_version="3.1", moving_heads=policy))
    named = {
        selection.template_id
        for section in plan.sections
        for selection in (section, *(section.segments or ()))
        if selection.template_id
    }
    missing = []
    for template_id in sorted(named):
        try:
            get_template(template_id)
        except TemplateNotFoundError:
            missing.append(template_id)
    if missing:
        raise UnsupportedRenderModeError(
            f"`twinklr eval-report` cannot re-render this plan: it names template(s) "
            f"{missing} that are neither built in nor in the physical catalog; a plan using "
            "`--template-dir` templates cannot be re-rendered by `eval-report`"
        )


async def rerender_plan(
    *,
    plan: ChoreographyPlan,
    audio_path: Path,
    fixture_config_path: Path,
    render_policy: MHRenderPolicy | RecordedRender,
) -> RerenderResult:
    """Re-render a choreography plan through the sequencing pipeline.

    This function re-executes the complete RenderingPipeline to generate
    IR segments and curves from a saved plan. It uses the same sequencer
    code as production.

    Evaluation reads segments and curves, so nothing here writes a `.xsq` — this used
    to take the user's sequence as a template and drop a `temp_eval.xsq` next to their
    audio on every report. It is the third export-path caller P1P-T11 detached from the
    user's document, and the easiest of the three to miss.

    A `physical_v2` plan is re-rendered from the render its run recorded: under the
    recorded policy, against the recorded beat grid, over the recorded dark spans (a
    show's coordination rests) and with the recorded gate result, which decides the
    variant a section naming no preset renders, with the physical
    family catalog admitted as `twinklr run` admits it (`admit_plan_templates`). The
    audio is analyzed only for the song's metadata. The re-render's fingerprint is
    returned beside the run's, for the caller to compare.

    Args:
        plan: ChoreographyPlan to render
        audio_path: Path to audio file (for tempo/structure)
        fixture_config_path: Path to fixture configuration
        render_policy: How the job rendered the plan: its legacy render policy, or the
            physical render its run recorded, whose policy is used. A plan is never
            re-rendered under a policy other than its job's.

    Returns:
        RerenderResult with segments, audio features, and fixture contexts

    Raises:
        UnsupportedRenderModeError: If `render_policy` is a `physical_v2` policy rather
            than a recorded render, or the plan names a template that cannot be loaded;
            raised before any file is read or audio analyzed
        FileNotFoundError: If any input file doesn't exist
        ValueError: If plan cannot be rendered

    Example:
        >>> result = await rerender_plan(
        ...     plan=plan,
        ...     audio_path=Path("song.mp3"),
        ...     fixture_config_path=Path("fixtures.json"),
        ...     render_policy=MHRenderPolicy(),
        ... )
        >>> len(result.segments) > 0
        True
    """
    recorded = render_policy if isinstance(render_policy, RecordedRender) else None
    policy = recorded.policy if recorded is not None else render_policy
    assert isinstance(policy, MHRenderPolicy)
    physical = policy.mode == "physical_v2"
    if physical and recorded is None:
        raise UnsupportedRenderModeError(
            "`twinklr eval-report` re-renders a moving_heads.mode 'physical_v2' plan only "
            "from the render its run recorded in the checkpoint"
        )
    job_config = JobConfig(
        schema_version="3.1" if physical else "3.0",
        fixture_config_path=str(fixture_config_path),
        moving_heads=policy,
    )
    if physical:
        admit_plan_templates(plan, policy)

    # Validate input files exist
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if not fixture_config_path.exists():
        raise FileNotFoundError(f"Fixture config not found: {fixture_config_path}")

    logger.debug(f"Re-rendering plan with {len(plan.sections)} sections")

    # Load fixtures
    logger.debug(f"Loading fixtures from {fixture_config_path.name}")
    fixture_group = load_fixture_group(fixture_config_path)

    # Analyze audio (async)
    logger.debug(f"Analyzing audio: {audio_path.name}")
    from twinklr.core.audio.analyzer import AudioAnalyzer
    from twinklr.core.config.models import AppConfig

    # Create minimal configs for audio analysis
    app_config = AppConfig.load_or_default()

    async with AudioAnalyzer(app_config=app_config, job_config=job_config) as analyzer:
        song_bundle = await analyzer.analyze(str(audio_path))

    if recorded is not None:
        # The grid the run rendered against.
        beat_grid = recorded.beat_grid
    else:
        logger.debug("Building beat grid")
        beat_grid = BeatGrid.from_song_features(song_bundle.features)

    # Create rendering pipeline
    logger.debug("Creating rendering pipeline")

    pipeline = RenderingPipeline(
        choreography_plan=plan,
        beat_grid=beat_grid,
        fixture_group=fixture_group,
        job_config=job_config,
        output_path=None,  # Evaluation reads segments; it writes no sequence file.
        admission=None if recorded is None else recorded.admission,
        dark_spans=() if recorded is None else recorded.dark_spans,
    )

    # Render segments
    logger.debug("Rendering segments")
    segments = pipeline.render()

    # Build fixture contexts (same logic as pipeline)
    fixture_contexts = pipeline._build_fixture_contexts()

    logger.debug(f"Re-rendered {len(segments)} segments")

    physical_rerender = None
    if recorded is not None:
        assert pipeline.render_record is not None  # set by a physical render
        profiles = {}
        for fixture in fixture_group.expand_fixtures():
            assert fixture.config.physical_profile is not None  # required by the render
            profiles[fixture.fixture_id] = fixture.config.physical_profile
        physical_rerender = PhysicalRerender(
            frames=pipeline.frames,
            profiles=profiles,
            render_record=pipeline.render_record,
            run_fingerprint=recorded.fingerprint,
            run_inputs=recorded.inputs,
            rerender_inputs=pipeline.checkpoint_record()["inputs"],
        )

    # Return wrapped result (pass features dict for backward compatibility)
    return RerenderResult(
        segments=segments,
        song_features=song_bundle.features,
        fixture_group=fixture_group,
        beat_grid=beat_grid,
        fixture_contexts=fixture_contexts,
        physical=physical_rerender,
    )
