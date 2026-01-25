"""Re-render choreography plans through the sequencing pipeline.

This module re-executes the full MovingHead sequencing pipeline to generate
IR segments and curves from a saved choreography plan.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from blinkb0t.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from blinkb0t.core.config.loader import load_fixture_group
from blinkb0t.core.sequencer.moving_heads.pipeline import RenderingPipeline
from blinkb0t.core.sequencer.timing.beat_grid import BeatGrid

logger = logging.getLogger(__name__)


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
    """

    def __init__(
        self,
        *,
        segments: list[Any],
        song_features: dict[str, Any],
        fixture_group: Any,
        beat_grid: BeatGrid,
        fixture_contexts: list[Any],
    ):
        self.segments = segments
        self.song_features = song_features
        self.fixture_group = fixture_group
        self.beat_grid = beat_grid
        self.fixture_contexts = fixture_contexts


def rerender_plan(
    *,
    plan: ChoreographyPlan,
    audio_path: Path,
    fixture_config_path: Path,
    xsq_path: Path,
) -> RerenderResult:
    """Re-render a choreography plan through the sequencing pipeline.

    This function re-executes the complete RenderingPipeline to generate
    IR segments and curves from a saved plan. It uses the same sequencer
    code as production.

    Args:
        plan: ChoreographyPlan to render
        audio_path: Path to audio file (for tempo/structure)
        fixture_config_path: Path to fixture configuration
        xsq_path: Path to xLights sequence file

    Returns:
        RerenderResult with segments, audio features, and fixture contexts

    Raises:
        FileNotFoundError: If any input file doesn't exist
        ValueError: If plan cannot be rendered

    Example:
        >>> result = rerender_plan(
        ...     plan=plan,
        ...     audio_path=Path("song.mp3"),
        ...     fixture_config_path=Path("fixtures.json"),
        ...     xsq_path=Path("sequence.xsq"),
        ... )
        >>> len(result.segments) > 0
        True
    """
    # Validate input files exist
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if not fixture_config_path.exists():
        raise FileNotFoundError(f"Fixture config not found: {fixture_config_path}")
    if not xsq_path.exists():
        raise FileNotFoundError(f"XSQ file not found: {xsq_path}")

    logger.info(f"Re-rendering plan with {len(plan.sections)} sections")

    # Load fixtures
    logger.debug(f"Loading fixtures from {fixture_config_path.name}")
    fixture_group = load_fixture_group(fixture_config_path)

    # Analyze audio
    logger.debug(f"Analyzing audio: {audio_path.name}")
    from blinkb0t.core.audio.analyzer import AudioAnalyzer
    from blinkb0t.core.config.models import AppConfig, JobConfig

    # Create job_config first
    job_config = JobConfig(
        project_name="eval_report",
        fixture_config_path=str(fixture_config_path),
    )

    # Create minimal configs for audio analysis
    app_config = AppConfig.load_or_default()

    analyzer = AudioAnalyzer(app_config=app_config, job_config=job_config)
    song_features = analyzer.analyze(str(audio_path))

    # Build beat grid
    logger.debug("Building beat grid")
    beat_grid = BeatGrid.from_song_features(song_features)

    # Create rendering pipeline
    logger.debug("Creating rendering pipeline")

    pipeline = RenderingPipeline(
        choreography_plan=plan,
        beat_grid=beat_grid,
        fixture_group=fixture_group,
        job_config=job_config,
        output_path=audio_path.parent / "temp_eval.xsq",  # Temp path, won't export
        template_xsq=xsq_path,
    )

    # Render segments
    logger.debug("Rendering segments")
    segments = pipeline.render()

    # Build fixture contexts (same logic as pipeline)
    fixture_contexts = pipeline._build_fixture_contexts()

    logger.info(f"Re-rendered {len(segments)} segments")

    # Return wrapped result
    return RerenderResult(
        segments=segments,
        song_features=song_features,
        fixture_group=fixture_group,
        beat_grid=beat_grid,
        fixture_contexts=fixture_contexts,
    )
