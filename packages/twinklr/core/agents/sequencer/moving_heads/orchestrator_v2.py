"""V2 Orchestrator for Moving Heads using StandardIterationController.

This module provides an async orchestrator that coordinates the MovingHead planner
with heuristic validation and judge-based refinement using the StandardIterationController.

V2 Migration: Replaces legacy synchronous Orchestrator with async implementation.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.sequencer.moving_heads.context import MovingHeadPlanningContext
from twinklr.core.agents.sequencer.moving_heads.heuristic_validator import (
    create_validator_function,
)
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.agents.sequencer.moving_heads.specs import (
    get_judge_spec,
    get_planner_spec,
)
from twinklr.core.agents.shared.judge.controller import (
    IterationConfig,
    IterationResult,
    StandardIterationController,
)
from twinklr.core.agents.shared.judge.feedback import FeedbackManager
from twinklr.core.agents.spec import AgentSpec

logger = logging.getLogger(__name__)


def build_planner_variables(
    context: MovingHeadPlanningContext,
    iteration: int = 0,
    feedback: str | None = None,
    revision_focus: list[str] | None = None,
) -> dict[str, Any]:
    """Build variables for planner prompt template.

    Transforms MovingHeadPlanningContext into template-ready variables
    for both initial planning (iteration 0) and refinement (iteration > 0).

    Args:
        context: MovingHead planning context
        iteration: Current iteration (0 = initial, >0 = refinement)
        feedback: Feedback string for refinement iterations
        revision_focus: Priority issues to address

    Returns:
        Dict of variables for planner prompt template
    """
    # Get prompt-ready context
    prompt_context = context.for_prompt()

    variables: dict[str, Any] = {
        # Iteration state
        "iteration": iteration,
        # Song metadata
        "song_title": context.song_title,
        "song_artist": context.song_artist,
        "genre": None,  # Not available in current context model
        # Beat grid
        "tempo": context.tempo,
        "time_signature": context.time_signature,
        "total_bars": context.total_bars,
        # Fixtures
        "fixture_count": context.fixtures.count,
        "fixture_groups": context.fixtures.groups,
        # Templates
        "available_templates": context.available_templates,
        # Sections (with bar positions)
        "sections": prompt_context["song_structure"]["sections"],
        # Audio profile (for initial iteration)
        "audio_profile": context.audio_profile if iteration == 0 else None,
        # Lyric context (for initial iteration)
        "lyric_context": context.lyric_context if iteration == 0 else None,
        # Macro plan guidance (always include for coordination)
        "macro_plan": prompt_context["macro_plan"],
        # Feedback (for refinement iterations)
        "feedback": feedback,
        "revision_focus": revision_focus,
    }

    return variables


def build_judge_variables(
    context: MovingHeadPlanningContext,
    plan: ChoreographyPlan,
    iteration: int,
    previous_feedback: list[str] | None = None,
    previous_issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build variables for judge prompt template.

    Args:
        context: MovingHead planning context
        plan: Choreography plan to judge
        iteration: Current iteration number
        previous_feedback: Feedback from previous iterations
        previous_issues: Issues from previous iterations

    Returns:
        Dict of variables for judge prompt template
    """
    prompt_context = context.for_prompt()

    variables: dict[str, Any] = {
        # Plan to judge
        "plan": plan.model_dump(mode="json"),
        # Song structure
        "sections": prompt_context["song_structure"]["sections"],
        "total_bars": context.total_bars,
        "tempo": context.tempo,
        "time_signature": context.time_signature,
        # Templates
        "available_templates": context.available_templates,
        # Iteration context
        "iteration": iteration,
        "previous_feedback": previous_feedback or [],
        "previous_issues": previous_issues or [],
        # Audio profile (for context)
        "audio_profile": context.audio_profile,
        # Macro plan guidance (for coordination validation)
        "macro_plan": prompt_context["macro_plan"],
    }

    return variables


class MovingHeadPlannerOrchestrator:
    """V2 Orchestrator for MovingHead planner with judge-based iteration.

    Provides an async interface for running the MovingHead planner with:
    - Heuristic validation (fast, deterministic quality checks)
    - Judge-based evaluation (LLM-driven quality assessment)
    - Iterative refinement with feedback

    Uses StandardIterationController for consistent iteration behavior
    across all V2 agents.

    Example:
        provider = OpenAIProvider(api_key=api_key)
        orchestrator = MovingHeadPlannerOrchestrator(provider=provider)

        result = await orchestrator.run(planning_context)
        if result.success:
            plan = result.plan  # ChoreographyPlan
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        planner_spec: AgentSpec | None = None,
        judge_spec: AgentSpec | None = None,
        max_iterations: int = 3,
        min_pass_score: float = 7.0,
        token_budget: int | None = None,
        llm_logger: LLMCallLogger | None = None,
        prompt_base_path: Path | str | None = None,
    ):
        """Initialize MovingHead planner orchestrator.

        Args:
            provider: LLM provider for agent execution
            planner_spec: Optional planner spec (uses default if None)
            judge_spec: Optional judge spec (uses default if None)
            max_iterations: Maximum refinement iterations (default: 3)
            min_pass_score: Minimum score for approval (default: 7.0)
            token_budget: Optional token budget limit
            llm_logger: Optional LLM call logger
            prompt_base_path: Base path for prompt packs
        """
        self.planner_spec = planner_spec or get_planner_spec()
        self.judge_spec = judge_spec or get_judge_spec()
        self.provider = provider
        self.llm_logger = llm_logger or NullLLMCallLogger()

        # Default prompt path
        if prompt_base_path is None:
            prompt_base_path = Path(__file__).parent.parent.parent.parent
        self.prompt_base_path = Path(prompt_base_path)

        # Create iteration config
        config = IterationConfig(
            max_iterations=max_iterations,
            approval_score_threshold=min_pass_score,
            token_budget=token_budget,
        )

        # Create feedback manager
        feedback_manager = FeedbackManager()

        # Create controller
        self.controller = StandardIterationController[ChoreographyPlan](
            config=config,
            feedback_manager=feedback_manager,
        )

        logger.debug(
            f"MovingHeadPlannerOrchestrator initialized "
            f"(max_iterations={max_iterations}, min_pass_score={min_pass_score})"
        )

    async def get_cache_key(self, context: MovingHeadPlanningContext) -> str:
        """Generate cache key for deterministic caching.

        Cache key includes all inputs that affect choreography plan output:
        - Audio profile (musical analysis)
        - Lyric context (narrative/themes, if present)
        - Fixture configuration
        - Available templates
        - Max iterations
        - Min pass score
        - Model configuration

        Args:
            context: Planning context for this run

        Returns:
            SHA256 hash of canonical inputs
        """
        key_data = {
            "audio_profile": context.audio_profile.model_dump(),
            "lyric_context": (
                context.lyric_context.model_dump() if context.lyric_context else None
            ),
            "macro_plan": (
                [sp.model_dump() for sp in context.macro_plan] if context.macro_plan else None
            ),
            "fixtures": {
                "count": context.fixtures.count,
                "groups": context.fixtures.groups,
            },
            "available_templates": sorted(context.available_templates),
            "max_iterations": self.controller.config.max_iterations,
            "min_pass_score": self.controller.config.approval_score_threshold,
            "planner_model": self.planner_spec.model,
            "judge_model": self.judge_spec.model,
        }

        # Canonical JSON encoding for stable hashing
        canonical = json.dumps(
            key_data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )

        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def run(
        self,
        context: MovingHeadPlanningContext,
    ) -> IterationResult[ChoreographyPlan]:
        """Run MovingHead planner with iterative refinement.

        Executes the complete MovingHead planner workflow:
        1. Generate initial plan (planner agent)
        2. Validate plan (heuristic validator)
        3. Evaluate plan (judge agent)
        4. Refine if needed (repeat with feedback)
        5. Return final plan or best attempt

        Args:
            context: MovingHead planning context containing:
                - audio_profile: Musical analysis and creative guidance
                - lyric_context: Narrative and thematic analysis (optional)
                - fixtures: Fixture configuration
                - available_templates: List of valid template IDs

        Returns:
            IterationResult containing the final ChoreographyPlan and metadata

        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        if not context.sections:
            raise ValueError("AudioProfile must have at least one section")

        if context.fixtures.count < 1:
            raise ValueError("At least one fixture must be configured")

        if not context.available_templates:
            raise ValueError("At least one template must be available")

        logger.debug(
            f"Starting MovingHead orchestration: {context.song_title} by {context.song_artist}"
        )
        if context.has_lyrics:
            logger.debug("  ✅ Lyric context available")
        else:
            logger.debug("  ⏭️  No lyric context (musical analysis only)")

        # Prepare initial variables for planner
        initial_variables = build_planner_variables(context, iteration=0)

        # Create validator function from context
        validator = create_validator_function(context)

        # Run iteration loop
        result = await self.controller.run(
            planner_spec=self.planner_spec,
            judge_spec=self.judge_spec,
            initial_variables=initial_variables,
            validator=validator,
            provider=self.provider,
            llm_logger=self.llm_logger,
            prompt_base_path=self.prompt_base_path,
        )

        if result.success:
            logger.debug(
                f"✅ MovingHead planner succeeded: {result.context.current_iteration} iterations"
                + (
                    f", score {result.context.final_verdict.score:.1f}"
                    if result.context.final_verdict
                    else ""
                )
            )
        else:
            logger.warning(
                f"⚠️ MovingHead planner completed without approval: "
                f"{result.context.current_iteration} iterations, "
                f"termination: {result.context.termination_reason}"
            )

        return result
