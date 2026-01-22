"""Moving head domain manager - orchestrates moving head choreography pipeline.

This module provides the MovingHeadManager class which orchestrates the complete
moving head sequencing pipeline while leveraging universal session services.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from blinkb0t.core.config.fixtures import FixtureGroup
from blinkb0t.core.sequencer.moving_heads.base import DomainManager

if TYPE_CHECKING:
    from blinkb0t.core.agents.moving_heads.orchestrator import AgentOrchestrator
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
            # Import locally to avoid circular dependency
            from blinkb0t.core.config.loader import load_fixture_group

            # Load from job_config.fixture_config_path
            fixture_path = Path(session.job_config.fixture_config_path)
            if not fixture_path.is_absolute():
                # Make relative to job config location if possible
                # For now, assume current directory
                fixture_path = Path.cwd() / fixture_path
            self.fixtures = load_fixture_group(fixture_path)
            logger.debug(f"Loaded fixtures from {fixture_path}")
        elif isinstance(fixtures, (Path, str)):
            # Import locally to avoid circular dependency
            from blinkb0t.core.config.loader import load_fixture_group

            self.fixtures = load_fixture_group(Path(fixtures))
            logger.debug(f"Loaded fixtures from {fixtures}")
        else:
            self.fixtures = fixtures
            logger.debug("Using provided FixtureGroup")

    @property
    def planner(self) -> AgentOrchestrator:
        """Getagent orchestrator for moving heads (lazy-loaded).

        Returns:
            AgentOrchestrator configured with session configs
        """
        if not hasattr(self, "_planner"):
            from blinkb0t.core.agents.moving_heads.orchestrator import AgentOrchestrator

            self._planner = AgentOrchestrator(
                job_config=self.session.job_config,
            )
            logger.debug("AgentOrchestrator initialized")
        return self._planner

    def run_pipeline(
        self,
        audio_path: str | Path,
        xsq_in: str | Path,
        xsq_out: str | Path,
    ) -> None:
        """Run complete moving head pipeline.

        Executes all steps:
        1. Audio analysis (song features)
        2. Sequence fingerprinting
        3. Plan generation
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
        logger.info(f"Runningmoving head pipeline: {audio_path} -> {xsq_out}")

        # Step 1: Analyze audio (universal service)
        logger.info("Step 1/4: Analyzing audio...")
        song_features = self.session.audio.analyze(str(audio_path))
        logger.info(f"Song features: {song_features}")

        # Step 2: Fingerprint sequence (universal service)
        # Note: orchestrator handles fingerprinting internally, so we don't need to call it here
        # The orchestrator will fingerprint the sequence when it runs
        logger.info("Step 2/4: Fingerprinting sequence (handled by orchestrator)...")

        # Step 3: Generate plan usingorchestrator (multi-stage agent pipeline)
        logger.info("Step 3/4: Runningagent orchestration...")
        orchestrator_result = self.planner.run(
            audio_path=str(audio_path),
            xsq_path=str(xsq_in),
        )

        # Check orchestrator status
        from blinkb0t.core.agents.moving_heads.orchestrator import OrchestratorStatus

        if orchestrator_result.status == OrchestratorStatus.FAILED:
            error_msg = f"Agent orchestration failed: {orchestrator_result.error}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Check if we have a valid implementation
        if not orchestrator_result.implementation:
            if orchestrator_result.status == OrchestratorStatus.INCOMPLETE:
                error_msg = (
                    f"Agent orchestration incomplete after {orchestrator_result.iterations} iterations. "
                    f"No valid implementation was generated. "
                    f"Best score: {orchestrator_result.evaluation.overall_score if orchestrator_result.evaluation else 'N/A'}/100. "
                    f"The agent may be struggling with the song structure or timing. "
                    f"Check the orchestrator logs for details."
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            else:
                error_msg = "No implementation generated by orchestrator (unknown reason)"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

        # Log orchestration status
        if orchestrator_result.status == OrchestratorStatus.INCOMPLETE:
            logger.warning(
                f"Agent orchestration incomplete after {orchestrator_result.iterations} iterations. "
                f"Using best attempt (score: {orchestrator_result.evaluation.overall_score if orchestrator_result.evaluation else 'N/A'})"
            )
        else:
            logger.info(
                f"Agent orchestration successful: {orchestrator_result.iterations} iterations, "
                f"score: {orchestrator_result.evaluation.overall_score if orchestrator_result.evaluation else 'N/A'}"
            )

        # Step 4: Apply implementation to sequence
        logger.info("Step 4/4: Applying implementation to sequence...")

        # Convert AgentImplementation to LLMChoreographyPlan
        from blinkb0t.core.agents.moving_heads.models_llm_plan import (
            LLMChoreographyPlan,
            SectionSelection,
        )

        # Build LLMChoreographyPlan from AgentImplementation
        # AgentImplementation has sections with template_id, params, etc.
        sections = []
        for impl_section in orchestrator_result.implementation.sections:
            section = SectionSelection(
                section_name=impl_section.name,
                start_bar=impl_section.start_bar,
                end_bar=impl_section.end_bar,
                section_role=impl_section.params.get("section_role"),  # Optional context
                energy_level=impl_section.params.get("energy_level"),  # Optional context
                template_id=impl_section.template_id,
                preset_id=impl_section.params.get("preset_id"),  # Extract preset from params
                modifiers=impl_section.params,  # Pass all params as modifiers
                reasoning=impl_section.reasoning,
            )
            sections.append(section)

        llm_plan = LLMChoreographyPlan(
            sections=sections,
            overall_strategy=orchestrator_result.implementation.overall_strategy
            or "Generated choreography",
            template_variety_notes=None,  # Optional field
        )

        # Create beat grid from song features
        from blinkb0t.core.sequencer.timing.beat_grid import BeatGrid

        beat_grid = BeatGrid.from_song_features(song_features)
        logger.debug(
            f"Created beat grid: tempo={beat_grid.tempo_bpm} BPM, "
            f"duration={beat_grid.duration_ms}ms"
        )

        # Create and run rendering pipeline
        from blinkb0t.core.sequencer.moving_heads.pipeline import RenderingPipeline

        pipeline = RenderingPipeline(
            llm_plan=llm_plan,
            beat_grid=beat_grid,
            fixture_group=self.fixtures,
            job_config=self.session.job_config,
            output_path=Path(xsq_out),
            template_xsq=Path(xsq_in),
        )

        # Render segments and export to XSQ
        segments = pipeline.render()
        logger.info(f"Rendered {len(segments)} fixture segments")

        logger.info(
            f"Pipeline complete: {xsq_out} "
            f"(tokens: {orchestrator_result.tokens_used}, time: {orchestrator_result.execution_time_s:.1f}s)"
        )

    def generate_plan_only(
        self,
        audio_path: str | Path,
        xsq_in: str | Path,
    ) -> dict[str, Any]:
        """Generate plan without applying it to sequence.

        Useful for:
        - Previewing plans
        - Debugging plan generation
        - Saving plans for later use

        Args:
            audio_path: Path to audio file
            xsq_in: Input xLights sequence path

        Returns:
            Generated plan dictionary (from AgentImplementation)

        Example:
            plan = mh.generate_plan_only("song.mp3", "input.xsq")
            # Inspect plan before applying
            print(f"Generated {len(plan['sections'])} sections")
        """
        logger.info("Generatingplan only (no sequencing)")

        # Runorchestrator
        orchestrator_result = self.planner.run(
            audio_path=str(audio_path),
            xsq_path=str(xsq_in),
        )

        # Check status
        from blinkb0t.core.agents.moving_heads.orchestrator import OrchestratorStatus

        if orchestrator_result.status == OrchestratorStatus.FAILED:
            raise RuntimeError(f"Agent orchestration failed: {orchestrator_result.error}")

        if orchestrator_result.status == OrchestratorStatus.INCOMPLETE:
            logger.warning(
                f"Agent orchestration incomplete. Using best attempt "
                f"(score: {orchestrator_result.evaluation.overall_score if orchestrator_result.evaluation else 'N/A'})"
            )

        # Convert implementation to dict
        if orchestrator_result.implementation:
            plan_dict: dict[str, Any] = orchestrator_result.implementation.model_dump()
        else:
            raise RuntimeError("No implementation generated by orchestrator")

        logger.info("plan generation complete")
        return plan_dict

    def apply_plan_only(
        self,
        xsq_in: str | Path,
        xsq_out: str | Path,
        plan: dict[str, Any],
        song_features: dict[str, Any],
    ) -> None:
        """Apply an existing plan to a sequence.

        Useful for:
        - Reapplying plans
        - Testing plan modifications
        - Applying saved plans

        Args:
            xsq_in: Input xLights sequence path
            xsq_out: Output xLights sequence path
            plan: Pre-generated plan dictionary (AgentImplementation format)
            song_features: Pre-analyzed song features

        Example:
            # Load saved plan and features
            plan = json.load(open("saved_plan.json"))
            features = json.load(open("saved_features.json"))

            # Apply to sequence
            mh.apply_plan_only("input.xsq", "output.xsq", plan, features)
        """
        logger.info("Applying plan to sequence...")

        # Convert plan dict to LLMChoreographyPlan
        from blinkb0t.core.agents.moving_heads.models_llm_plan import (
            LLMChoreographyPlan,
            SectionSelection,
        )

        sections = []
        for section_data in plan.get("sections", []):
            section = SectionSelection(
                section_name=section_data["name"],
                start_bar=section_data["start_bar"],
                end_bar=section_data["end_bar"],
                section_role=section_data.get("section_role"),  # Optional context
                energy_level=section_data.get("energy_level"),  # Optional context
                template_id=section_data["template_id"],
                preset_id=section_data.get("params", {}).get("preset_id"),
                modifiers=section_data.get("params", {}),
                reasoning=section_data.get("reasoning", ""),
            )
            sections.append(section)

        llm_plan = LLMChoreographyPlan(
            sections=sections,
            overall_strategy=plan.get("overall_strategy", ""),
            template_variety_notes=plan.get("template_variety_notes"),  # Optional field
        )

        # Create beat grid
        from blinkb0t.core.sequencer.timing.beat_grid import BeatGrid

        beat_grid = BeatGrid.from_song_features(song_features)

        # Create and run rendering pipeline
        from blinkb0t.core.sequencer.moving_heads.pipeline import RenderingPipeline

        pipeline = RenderingPipeline(
            llm_plan=llm_plan,
            beat_grid=beat_grid,
            fixture_group=self.fixtures,
            job_config=self.session.job_config,
            output_path=Path(xsq_out),
            template_xsq=Path(xsq_in),
        )

        segments = pipeline.render()
        logger.info(f"Applied plan: {len(segments)} segments written to {xsq_out}")
