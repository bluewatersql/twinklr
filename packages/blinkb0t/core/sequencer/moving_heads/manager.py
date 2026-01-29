"""Moving head domain manager - orchestrates moving head choreography pipeline.

This module provides the MovingHeadManager class which orchestrates the complete
moving head sequencing pipeline while leveraging universal session services.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from blinkb0t.core.agents.logging import create_llm_logger
from blinkb0t.core.agents.providers import OpenAIProvider
from blinkb0t.core.agents.sequencer.moving_heads import (
    ChoreographyPlan,
    OrchestrationConfig,
    Orchestrator,
)
from blinkb0t.core.config.fixtures import FixtureGroup
from blinkb0t.core.config.loader import load_fixture_group
from blinkb0t.core.sequencer.moving_heads.base import DomainManager
from blinkb0t.core.sequencer.moving_heads.pipeline import RenderingPipeline
from blinkb0t.core.sequencer.moving_heads.templates import load_builtin_templates
from blinkb0t.core.sequencer.moving_heads.templates.library import list_templates
from blinkb0t.core.sequencer.timing.beat_grid import BeatGrid

if TYPE_CHECKING:
    from blinkb0t.core.session import BlinkB0tSession

logger = logging.getLogger(__name__)


class MovingHeadManager(DomainManager):
    """Domain manager for moving head choreography.

    Orchestrates the moving head-specific pipeline:
    1. Audio analysis (via session.audio)
    2. Sequence fingerprinting (via session.sequence)
    3. Plan generation (domain-specific)
    4. Sequencing (domain-specific)

    Provides both full pipeline execution and individual step access
    for flexibility and testing.
    """

    def __init__(
        self,
        session: BlinkB0tSession,
        fixtures: FixtureGroup | Path | str | None = None,
    ):
        """Initialize moving head manager.

        Args:
            session: BlinkB0t session providing universal services
            fixtures: Fixture configuration (loaded from job_config if None)

        Example:
            # Load fixtures from job_config
            mh = MovingHeadManager(session)

            # Provide fixtures explicitly
            mh = MovingHeadManager(session, fixtures=my_fixtures)

            # Load fixtures from path
            mh = MovingHeadManager(session, fixtures="fixtures.json")
        """
        super().__init__(session)

        # Load fixtures
        if fixtures is None:
            # Load from job_config.fixture_config_path
            fixture_path = Path(session.job_config.fixture_config_path)
            if not fixture_path.is_absolute():
                # Make relative to job config location if possible
                # For now, assume current directory
                fixture_path = Path.cwd() / fixture_path
            self.fixtures = load_fixture_group(fixture_path)
            logger.debug(f"Loaded fixtures from {fixture_path}")
        elif isinstance(fixtures, (Path, str)):
            self.fixtures = load_fixture_group(Path(fixtures))
            logger.debug(f"Loaded fixtures from {fixtures}")
        else:
            self.fixtures = fixtures
            logger.debug("Using provided FixtureGroup")

    @property
    def planner(self) -> Orchestrator:
        """Get agent orchestrator for moving heads (lazy-loaded).

        Returns:
            Orchestrator configured with session configs
        """
        if not hasattr(self, "_planner"):
            # Initialize LLM provider (get API key from environment)
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")

            provider = OpenAIProvider(api_key=api_key)

            # Create LLM logger from job config settings
            llm_logging_config = self.session.job_config.agent.llm_logging
            llm_logger = create_llm_logger(
                enabled=llm_logging_config.enabled,
                output_dir=self.session.artifact_dir / "llm_calls"
                if self.session.artifact_dir
                else None,
                run_id=self.session.job_config.project_name or "run",
                log_level=llm_logging_config.log_level,
                format=llm_logging_config.format,
                sanitize=llm_logging_config.sanitize,
            )
            logger.debug(
                f"LLM logger initialized: enabled={llm_logging_config.enabled}, "
                f"level={llm_logging_config.log_level}, format={llm_logging_config.format}"
            )

            config = OrchestrationConfig(
                max_iterations=self.session.job_config.agent.max_iterations,
                token_budget=self.session.job_config.agent.token_budget,
                llm_logger=llm_logger,
            )

            self._planner = Orchestrator(
                provider=provider,
                config=config,
            )
            logger.debug("Orchestrator initialized")
        return self._planner

    def run_pipeline(
        self,
        audio_path: str | Path,
        xsq_in: str | Path,
        xsq_out: str | Path,
    ) -> None:
        """Run complete moving head pipeline.

        Executes all steps:
        1. Audio analysis (song features) - uses async caching internally
        2. Sequence fingerprinting
        3. Plan generation - with LLM logging from job_config
        4. Sequence application

        Args:
            audio_path: Path to audio file (mp3, wav, etc.)
            xsq_in: Input xLights sequence path
            xsq_out: Output xLights sequence path

        Example:
            session = BlinkB0tSession.from_directory(".")
            mh = MovingHeadManager(session)
            mh.run_pipeline("song.mp3", "input.xsq", "output.xsq")
        """
        logger.debug(f"Running moving head pipeline: {audio_path} -> {xsq_out}")

        # Step 1: Analyze audio (universal service with async caching)
        logger.debug("Step 1/4: Analyzing audio...")
        song_bundle = self.session.audio.analyze_sync(str(audio_path))

        # Step 2: Build beat grid
        logger.debug("Step 2/4: Building beat grid...")
        beat_grid = BeatGrid.from_song_features(song_bundle.features)
        logger.debug(
            f"Created beat grid: tempo={beat_grid.tempo_bpm} BPM, "
            f"total_bars={beat_grid.total_bars}, ms_per_bar={beat_grid.ms_per_bar:.2f}ms, "
            f"duration={beat_grid.duration_ms:.0f}ms"
        )

        # Step 3: Generate plan using orchestrator (multi-agent pipeline)
        logger.debug("Step 3/4: Running agent orchestration...")

        # Load builtin templates (registers them in global REGISTRY)
        load_builtin_templates()

        # Build context for orchestrator
        available_templates = [t.template_id for t in list_templates()]

        # Extract song structure from features
        structure_sections = song_bundle.features.get("structure", {}).get("sections", {})
        total_bars = song_bundle.features.get("structure", {}).get(
            "total_bars", len(beat_grid.bar_boundaries)
        )

        # Extract metadata for LLM context
        # Handle both dict (from cache) and object forms
        metadata_context: dict[str, Any] = {}
        if song_bundle.metadata:
            if isinstance(song_bundle.metadata, dict):
                # Dict form (from cache)
                resolved = song_bundle.metadata.get("resolved", {})
                embedded = song_bundle.metadata.get("embedded", {})
                if resolved and resolved.get("artist"):
                    metadata_context["artist"] = resolved["artist"]
                if resolved and resolved.get("title"):
                    metadata_context["title"] = resolved["title"]
                elif embedded:
                    if embedded.get("artist"):
                        metadata_context["artist"] = embedded["artist"]
                    if embedded.get("title"):
                        metadata_context["title"] = embedded["title"]
                    if embedded.get("genre"):
                        metadata_context["genre"] = embedded["genre"]
            else:
                # Object form (MetadataBundle)
                if song_bundle.metadata.resolved:
                    if song_bundle.metadata.resolved.artist:
                        metadata_context["artist"] = song_bundle.metadata.resolved.artist
                    if song_bundle.metadata.resolved.title:
                        metadata_context["title"] = song_bundle.metadata.resolved.title
                    if (
                        song_bundle.metadata.resolved.mbids
                        and song_bundle.metadata.resolved.mbids.artist_mbids
                    ):
                        metadata_context["genre_hints"] = "Available via MusicBrainz"
                elif song_bundle.metadata.embedded:
                    if song_bundle.metadata.embedded.artist:
                        metadata_context["artist"] = song_bundle.metadata.embedded.artist
                    if song_bundle.metadata.embedded.title:
                        metadata_context["title"] = song_bundle.metadata.embedded.title
                    if song_bundle.metadata.embedded.genre:
                        metadata_context["genre"] = song_bundle.metadata.embedded.genre

        context: dict[str, Any] = {
            "song_structure": {
                "sections": structure_sections,
                "total_bars": total_bars,
            },
            "fixtures": {
                "count": len(self.fixtures.fixtures),
                "groups": [],  # FixtureGroup doesn't have groups attribute
            },
            "available_templates": available_templates,
            "beat_grid": {
                "tempo": beat_grid.tempo_bpm,
                "time_signature": f"{beat_grid.beats_per_bar}/4",
                "total_bars": len(beat_grid.bar_boundaries),
            },
        }

        # Add metadata if available
        if metadata_context:
            context["metadata"] = metadata_context
            logger.debug(f"Added metadata to context: {metadata_context}")

        # Run orchestration
        orchestration_result = self.planner.orchestrate(context)

        # Handle orchestration result
        choreography_plan: ChoreographyPlan
        if not orchestration_result.success:
            error_msg = (
                f"Agent orchestration failed: {orchestration_result.error_message or 'Unknown error'}. "
                f"Iterations: {orchestration_result.iterations}, "
                f"Tokens: {orchestration_result.total_tokens}, "
                f"Final state: {orchestration_result.final_state.value}"
            )
            logger.error(error_msg)

            # If we have a partial plan, use it as best attempt
            if orchestration_result.plan:
                logger.warning(
                    f"Using best attempt plan from {orchestration_result.iterations} iterations"
                )
                choreography_plan = orchestration_result.plan
            else:
                raise RuntimeError(error_msg)
        else:
            logger.debug(
                f"Agent orchestration successful: {orchestration_result.iterations} iterations, "
                f"tokens: {orchestration_result.total_tokens}, "
                f"duration: {orchestration_result.duration_seconds:.1f}s"
            )
            if not orchestration_result.plan:
                raise RuntimeError("Orchestration succeeded but no plan returned")
            choreography_plan = orchestration_result.plan

        # Step 4: Apply plan to sequence
        logger.debug("Step 4/4: Applying plan to sequence...")

        pipeline = RenderingPipeline(
            choreography_plan=choreography_plan,
            beat_grid=beat_grid,
            fixture_group=self.fixtures,
            job_config=self.session.job_config,
            output_path=Path(xsq_out),
            template_xsq=Path(xsq_in),
        )

        # Render segments and export to XSQ
        segments = pipeline.render()
        logger.debug(f"Rendered {len(segments)} fixture segments")

        logger.debug(
            f"Pipeline complete: {xsq_out} "
            f"(tokens: {orchestration_result.total_tokens}, "
            f"time: {orchestration_result.duration_seconds:.1f}s)"
        )
