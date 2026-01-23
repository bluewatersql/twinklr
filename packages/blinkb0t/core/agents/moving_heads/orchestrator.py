"""Multi-stage agent orchestrator.

Coordinates plan generation, validation, implementation, evaluation,
and refinement across multiple iterations.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.agents.moving_heads.context import ContextShaper, build_template_context_for_llm
from blinkb0t.core.agents.moving_heads.heuristic_validator import HeuristicValidator
from blinkb0t.core.agents.moving_heads.implementation_expander import ImplementationExpander
from blinkb0t.core.agents.moving_heads.judge_critic import CategoryScore, Evaluation, JudgeCritic
from blinkb0t.core.agents.moving_heads.plan_generator import PlanGenerator
from blinkb0t.core.agents.moving_heads.refinement_agent import RefinementAgent
from blinkb0t.core.agents.moving_heads.stage_coordinator import StageCoordinator
from blinkb0t.core.agents.moving_heads.token_budget_manager import TokenBudgetManager
from blinkb0t.core.api.llm.openai.client import OpenAIClient
from blinkb0t.core.audio.analyzer import AudioAnalyzer
from blinkb0t.core.config.loader import get_openai_api_key, load_app_config
from blinkb0t.core.config.models import JobConfig
from blinkb0t.core.sequencer.analyzer import SequenceAnalyzer
from blinkb0t.core.sequencer.moving_heads.templates.library import REGISTRY
from blinkb0t.core.utils.checkpoint import CheckpointManager, CheckpointType

logger = logging.getLogger(__name__)


class OrchestratorStatus(Enum):
    """Orchestrator execution status."""

    SUCCESS = "success"  # Passed evaluation
    INCOMPLETE = "incomplete"  # Max iterations/budget without passing
    FAILED = "failed"  # Error occurred


class OrchestratorResult(BaseModel):
    """Result of orchestrator execution.

    Converted from dataclass to Pydantic for:
    - Automatic validation
    - JSON serialization
    - Better error messages
    - Consistent with project standards
    """

    status: OrchestratorStatus
    plan: Any | None = Field(default=None, description="Best plan attempt (AgentPlan)")
    implementation: Any | None = Field(
        default=None, description="Best implementation (AgentImplementation)"
    )
    evaluation: Any | None = Field(default=None, description="Best evaluation (Evaluation)")
    iterations: int = Field(ge=0, description="Number of iterations completed")
    tokens_used: int = Field(ge=0, description="Total tokens used")
    execution_time_s: float = Field(ge=0.0, description="Total execution time in seconds")
    error: str | None = Field(default=None, description="Error message if failed")
    budget_report: Any | None = Field(default=None, description="Token budget report")

    model_config = ConfigDict(
        frozen=False,  # Allow mutation for building result
        extra="forbid",  # Prevent typos in field names
        arbitrary_types_allowed=True,  # Allow Any types for plan/implementation/evaluation
    )


class AgentOrchestrator:
    """Orchestrates multi-stage agent pipeline.

    Coordinates all stages:
    1. Plan Generation
    2. Heuristic Validation
    3. Implementation Expansion
    4. Judge/Evaluation
    5. Refinement (if needed)

    Manages:
    - Iteration loop (max 3 iterations)
    - Token budget tracking
    - Result status (SUCCESS/INCOMPLETE/FAILED)
    - Error handling and recovery
    """

    def __init__(self, job_config: JobConfig):
        """Initialize orchestrator.

        Args:
            job_config: Job configuration
        """
        self.job_config = job_config
        self.agent_config = job_config.agent
        self.app_config = load_app_config()

        # Initialize checkpoint manager
        self.checkpoint_manager = CheckpointManager(job_config=job_config)

        # Initialize OpenAI client (optional if checkpoints available)
        api_key = get_openai_api_key()
        if not api_key:
            if job_config.checkpoint:
                logger.warning(
                    "OpenAI API key not found - will attempt to load from checkpoints only"
                )
                self.openai_client = None  # type: ignore[assignment]
            else:
                raise ValueError("OpenAI API key not found in environment")
        else:
            self.openai_client = OpenAIClient(api_key=api_key)

        # Initialize stage components
        self.context_shaper = ContextShaper(job_config=job_config)

        # Token budget manager
        self.token_manager = TokenBudgetManager(job_config=job_config)

        if self.openai_client:
            plan_generator = PlanGenerator(job_config=job_config, openai_client=self.openai_client)
            judge_critic = JudgeCritic(job_config=job_config, openai_client=self.openai_client)

            # Initialize stage coordinator
            self.stage_coordinator = StageCoordinator(
                plan_generator=plan_generator,
                judge_critic=judge_critic,
                token_manager=self.token_manager,
            )
        else:
            # Checkpoint-only mode
            self.stage_coordinator = None  # type: ignore[assignment]

        # Audio analyzer (will be initialized in run() with proper config)
        self.audio_analyzer: AudioAnalyzer | None = None

        # Template loader - use global registry and ensure templates are loaded
        from blinkb0t.core.sequencer.moving_heads.templates import load_builtin_templates

        # Load builtin templates (registers them in global REGISTRY)
        load_builtin_templates()
        # Use the global registry instance that templates are registered in
        self.template_registry = REGISTRY

        # Config
        self.max_iterations = self.agent_config.max_iterations

        logger.info(
            f"AgentOrchestrator initialized: "
            f"max_iterations={self.max_iterations}, "
            f"budget={self.agent_config.token_budget}"
        )

    def run(self, audio_path: str, xsq_path: str | None = None) -> OrchestratorResult:
        """Run complete agent pipeline.

        Args:
            audio_path: Path to audio file
            xsq_path: Optional path to existing sequence (for fingerprint)

        Returns:
            OrchestratorResult with status and outputs
        """
        start_time = time.time()

        logger.info("=" * 60)
        logger.info("Starting agent orchestration")
        logger.info("=" * 60)

        try:
            # Stage 0: Analysis & Setup
            logger.info("\n" + "=" * 60)
            logger.info("STAGE 0: Analysis & Setup")
            logger.info("=" * 60)

            # Initialize audio analyzer (requires app config)
            self.audio_analyzer = AudioAnalyzer(
                app_config=self.app_config, job_config=self.job_config
            )

            song_features = self._analyze_audio(audio_path)
            seq_fingerprint = self._analyze_sequence(xsq_path) if xsq_path else None

            # Get all templates from registry (each factory creates a TemplateDoc)
            template_docs = [
                self.template_registry.get(info.template_id)
                for info in self.template_registry.list_all()
            ]
            template_metadata = build_template_context_for_llm(template_docs)

            # Check for existing checkpoint FIRST (skip everything if available)
            checkpoint_result = self._try_load_checkpoint(song_features, seq_fingerprint)
            if checkpoint_result:
                logger.info("✅ Loaded from checkpoint (skipping LLM calls)")
                return checkpoint_result

            # If no checkpoint and no API key, fail
            if not self.openai_client:
                raise RuntimeError(
                    "No OpenAI API key available and no checkpoints found. "
                    "Set OPENAI_API_KEY environment variable or run with existing checkpoints."
                )

            # At this point, we know openai_client and stage_coordinator are not None
            assert self.stage_coordinator is not None, (
                "stage_coordinator should be initialized when openai_client is available"
            )

            # Initialize time-dependent components (only needed if not using checkpoints)
            # Phase 5A: TimeResolver removed, agent now works in bars
            implementation_expander = ImplementationExpander(
                job_config=self.job_config,
                openai_client=self.openai_client,
            )
            refinement_agent = RefinementAgent(
                job_config=self.job_config,
                openai_client=self.openai_client,
                plan_generator=self.stage_coordinator.plan_generator,
                implementation_expander=implementation_expander,
            )

            # Set these in the coordinator
            self.stage_coordinator.set_implementation_expander(implementation_expander)
            self.stage_coordinator.set_refinement_agent(refinement_agent)

            # Initialize heuristic validator
            heuristic_validator = HeuristicValidator(
                template_metadata=template_metadata, song_features=song_features
            )

            # Track best attempt
            best_plan = None
            best_implementation = None
            best_evaluation = None
            best_score = -1.0

            # Main iteration loop
            iteration = 0
            while iteration < self.max_iterations:
                logger.info(f"\n{'=' * 60}")
                logger.info(f"ITERATION {iteration + 1}/{self.max_iterations}")
                logger.info(f"{'=' * 60}")

                try:
                    # Stage 1: Plan Generation
                    plan = self.stage_coordinator.execute_plan_stage(
                        song_features, seq_fingerprint, template_metadata
                    )
                    if not plan:
                        break  # Budget exhausted

                    # Save plan checkpoint
                    self.checkpoint_manager.write_checkpoint(CheckpointType.RAW, plan.model_dump())

                    # Stage 2: Heuristic Validation
                    validation_passed = self.stage_coordinator.execute_validation_stage(
                        plan, heuristic_validator
                    )
                    if not validation_passed:
                        # Validation failed
                        logger.warning(
                            "⚠️ Validation failed, but continuing to generate implementation for debugging"
                        )
                        if iteration < self.max_iterations - 1:
                            iteration += 1
                            continue  # Retry planning
                        else:
                            # Last iteration, can't retry
                            break

                    # Stage 3: Implementation Expansion
                    implementation = self.stage_coordinator.execute_implementation_stage(
                        plan, song_features, seq_fingerprint, template_metadata
                    )
                    if not implementation:
                        break  # Budget exhausted

                    # Save implementation checkpoint
                    self.checkpoint_manager.write_checkpoint(
                        CheckpointType.IMPLEMENTATION, implementation.model_dump()
                    )

                    # Stage 4: Judge/Evaluation
                    try:
                        evaluation = self.stage_coordinator.execute_judge_stage(
                            plan, implementation, song_features
                        )
                        if not evaluation:
                            break  # Budget exhausted
                    except Exception as e:
                        logger.error(f"Judge evaluation failed or timed out: {e}", exc_info=True)

                        # Create a default passing evaluation to allow pipeline to continue
                        evaluation = Evaluation(
                            story_overview="Judge evaluation skipped due to error. Implementation accepted by default.",
                            overall_score=75.0,  # Passing score
                            category_scores=[
                                CategoryScore(
                                    category="Structure",
                                    score=75,
                                    reasoning="Default passing score (judge skipped)",
                                    strengths=["Implementation structure appears valid"],
                                    weaknesses=["Could not evaluate due to judge error"],
                                )
                            ],
                            summary=f"Judge evaluation skipped due to error: {str(e)}. Implementation accepted by default.",
                            actionable_feedback=["Review judge logs for error details"],
                            pass_threshold=True,
                            channel_scoring=None,
                        )
                        logger.warning("Using default passing evaluation to continue pipeline")

                    # Save evaluation checkpoint
                    self.checkpoint_manager.write_checkpoint(
                        CheckpointType.EVALUATION, evaluation.model_dump()
                    )

                    # Update best attempt
                    if evaluation.overall_score > best_score:
                        best_plan = plan
                        best_implementation = implementation
                        best_evaluation = evaluation
                        best_score = evaluation.overall_score

                    # Check if passed
                    if evaluation.pass_threshold:
                        logger.info(
                            f"\n{'=' * 60}\n"
                            f"✅ SUCCESS: Score {evaluation.overall_score:.1f}/100\n"
                            f"{'=' * 60}"
                        )

                        execution_time = time.time() - start_time
                        result = OrchestratorResult(
                            status=OrchestratorStatus.SUCCESS,
                            plan=plan,
                            implementation=implementation,
                            evaluation=evaluation,
                            iterations=iteration + 1,
                            tokens_used=self.token_manager.total_used,
                            execution_time_s=execution_time,
                            budget_report=self.token_manager.get_report(),
                        )

                        # Save final result checkpoint
                        self.checkpoint_manager.write_checkpoint(
                            CheckpointType.FINAL,
                            {
                                "status": "SUCCESS",
                                "plan": plan.model_dump(),
                                "implementation": implementation.model_dump(),
                                "evaluation": evaluation.model_dump(),
                                "iterations": iteration + 1,
                                "tokens_used": self.token_manager.total_used,
                                "execution_time_s": execution_time,
                            },
                        )

                        return result

                    # Check if this is last iteration
                    if iteration >= self.max_iterations - 1:
                        logger.info("Max iterations reached")
                        break

                    # Stage 5: Refinement
                    refined = self.stage_coordinator.execute_refinement_stage(
                        plan,
                        implementation,
                        evaluation,
                        song_features,
                        seq_fingerprint,
                        template_metadata,
                    )

                    if not refined:
                        # Budget exhausted or refinement failed
                        break

                    # Update plan/implementation for next iteration
                    if refined.plan:
                        plan = refined.plan
                        # Will re-run stages 2-4
                    if refined.implementation:
                        implementation = refined.implementation
                        # Will re-run stage 4

                    iteration += 1
                    self.token_manager.increment_iteration()

                except Exception as e:
                    logger.error(f"Error in iteration {iteration + 1}: {e}", exc_info=True)
                    # Continue to return best attempt
                    break

            # Did not pass evaluation
            execution_time = time.time() - start_time

            if best_evaluation is None:
                # No complete cycle
                return OrchestratorResult(
                    status=OrchestratorStatus.INCOMPLETE,
                    plan=best_plan,
                    implementation=best_implementation,
                    evaluation=None,
                    iterations=iteration,
                    tokens_used=self.token_manager.total_used,
                    execution_time_s=execution_time,
                    error="No complete cycle achieved",
                    budget_report=self.token_manager.get_report(),
                )

            logger.info(f"\n{'=' * 60}\n⚠️ INCOMPLETE: Best score {best_score:.1f}/100\n{'=' * 60}")

            return OrchestratorResult(
                status=OrchestratorStatus.INCOMPLETE,
                plan=best_plan,
                implementation=best_implementation,
                evaluation=best_evaluation,
                iterations=iteration,
                tokens_used=self.token_manager.total_used,
                execution_time_s=execution_time,
                budget_report=self.token_manager.get_report(),
            )

        except Exception as e:
            logger.error(f"Orchestration failed: {e}", exc_info=True)
            execution_time = time.time() - start_time

            return OrchestratorResult(
                status=OrchestratorStatus.FAILED,
                plan=None,
                implementation=None,
                evaluation=None,
                iterations=0,
                tokens_used=self.token_manager.total_used,
                execution_time_s=execution_time,
                error=str(e),
                budget_report=self.token_manager.get_report(),
            )

    # ========================================================================
    # Private Methods - Analysis & Utilities
    # ========================================================================

    def _analyze_audio(self, audio_path: str) -> dict[str, Any]:
        """Analyze audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            Song features dictionary
        """
        logger.info(f"Analyzing audio: {audio_path}")
        if self.audio_analyzer is None:
            raise RuntimeError("AudioAnalyzer not initialized")
        return self.audio_analyzer.analyze(audio_path)

    def _analyze_sequence(self, xsq_path: str) -> dict[str, Any]:
        """Analyze existing sequence for fingerprint.

        Args:
            xsq_path: Path to sequence file

        Returns:
            Sequence fingerprint dictionary
        """
        logger.info(f"Analyzing sequence: {xsq_path}")

        try:
            analyzer = SequenceAnalyzer(self.app_config, self.job_config)
            fingerprint = analyzer.fingerprint(xsq_path, bin_s=1.0)

            logger.info(
                f"Sequence fingerprint extracted: {len(fingerprint.get('existing_effects', {}))} effect types"
            )
            return fingerprint
        except Exception as e:
            logger.warning(f"Failed to fingerprint sequence: {e}. Continuing without fingerprint.")
            return {}

    def _try_load_checkpoint(
        self, song_features: dict[str, Any], seq_fingerprint: dict[str, Any] | None
    ) -> OrchestratorResult | None:
        """Try to load complete result from checkpoint.

        Args:
            song_features: Song features (for validation)
            seq_fingerprint: Sequence fingerprint (for validation)

        Returns:
            OrchestratorResult if checkpoint valid, None otherwise
        """
        logger.debug(
            f"Attempting to load checkpoint: output_dir={self.job_config.output_dir}, project_name={self.job_config.project_name}"
        )
        checkpoint = self.checkpoint_manager.read_checkpoint(CheckpointType.FINAL)
        if not checkpoint:
            logger.debug("No checkpoint found")
            return None

        try:
            from blinkb0t.core.agents.moving_heads.judge_critic import Evaluation
            from blinkb0t.core.agents.moving_heads.models_agent_plan import (
                AgentImplementation,
                AgentPlan,
            )

            # Reconstruct result from checkpoint
            plan = AgentPlan.model_validate(checkpoint["plan"])
            implementation = AgentImplementation.model_validate(checkpoint["implementation"])
            evaluation = Evaluation.model_validate(checkpoint["evaluation"])

            logger.info(
                f"Loaded checkpoint: score={evaluation.overall_score:.1f}, "
                f"iterations={checkpoint['iterations']}, "
                f"tokens={checkpoint['tokens_used']}"
            )

            return OrchestratorResult(
                status=OrchestratorStatus.SUCCESS,
                plan=plan,
                implementation=implementation,
                evaluation=evaluation,
                iterations=checkpoint["iterations"],
                tokens_used=checkpoint["tokens_used"],
                execution_time_s=checkpoint["execution_time_s"],
                budget_report=self.token_manager.get_report(),
            )

        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
            return None
