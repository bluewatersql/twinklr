"""LLM-based refinement agent for iterative improvement.

Improves plans/implementations based on judge feedback.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from blinkb0t.core.agents.moving_heads.context import ContextShaper, Stage
from blinkb0t.core.agents.moving_heads.implementation_expander import (
    ImplementationExpander,
)
from blinkb0t.core.agents.moving_heads.judge_critic import Evaluation, FailureAnalysis
from blinkb0t.core.agents.moving_heads.models_agent_plan import AgentImplementation, AgentPlan
from blinkb0t.core.agents.moving_heads.plan_generator import PlanGenerator
from blinkb0t.core.api.llm.openai.client import OpenAIClient, Verbosity
from blinkb0t.core.config.models import JobConfig

logger = logging.getLogger(__name__)


class RefineStrategy(Enum):
    """Refinement strategy."""

    REPLAN = "replan"  # Regenerate plan (Stage 1)
    REFINE_IMPLEMENTATION = "refine_impl"  # Fix implementation (Stage 3)
    FULL_REPLAN = "full_replan"  # Start over completely


class RefinementResult(BaseModel):
    """Result of refinement.

    Converted from dataclass to Pydantic for validation and serialization.
    Uses SkipValidation for plan/implementation to allow Mocks in tests.
    """

    success: bool = Field(description="Whether refinement succeeded")
    strategy: RefineStrategy = Field(description="Refinement strategy used")
    plan: SkipValidation[AgentPlan | None] = Field(
        default=None, description="Refined plan if applicable"
    )
    implementation: SkipValidation[AgentImplementation | None] = Field(
        default=None, description="Refined implementation if applicable"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    tokens_used: int = Field(ge=0, description="Number of tokens used")

    model_config = ConfigDict(
        frozen=False,
        extra="forbid",
    )


class RefinementAgent:
    """Refines plans/implementations based on feedback.

    Responsibilities:
    1. Analyze failure (what went wrong)
    2. Determine strategy (replan vs refine_impl)
    3. Build refinement prompt with feedback
    4. Call appropriate LLM (plan or implementation)
    5. Parse and validate refined output

    Example:
        agent = RefinementAgent(
            job_config=job_config,
            openai_client=openai_client,
            plan_generator=plan_generator,
            implementation_expander=implementation_expander
        )

        result = agent.refine(
            plan=original_plan,
            implementation=original_implementation,
            evaluation=evaluation,
            failure_analysis=failure_analysis,
            song_features=song_features,
            seq_fingerprint=seq_fingerprint,
            template_metadata=template_metadata
        )

        if result.success:
            # Use refined plan/implementation
            if result.strategy == RefineStrategy.REPLAN:
                new_plan = result.plan
            elif result.strategy == RefineStrategy.REFINE_IMPLEMENTATION:
                new_implementation = result.implementation
    """

    def __init__(
        self,
        job_config: JobConfig,
        openai_client: OpenAIClient,
        plan_generator: PlanGenerator,
        implementation_expander: ImplementationExpander,
    ):
        """Initialize refinement agent.

        Args:
            job_config: Job configuration
            openai_client: OpenAI API client
            plan_generator: Plan generator for replanning
            implementation_expander: Implementation expander for refining impl
        """
        self.job_config = job_config
        self.openai_client = openai_client
        self.plan_generator = plan_generator
        self.implementation_expander = implementation_expander
        self.context_shaper = ContextShaper(job_config=job_config)

        # Get agent config
        self.refinement_config = job_config.agent.refinement_agent

        logger.debug("RefinementAgent initialized")

    def refine(
        self,
        plan: AgentPlan,
        implementation: AgentImplementation,
        evaluation: Evaluation,
        failure_analysis: FailureAnalysis | None,
        song_features: dict[str, Any],
        seq_fingerprint: dict[str, Any],
        template_metadata: list[dict[str, Any]],
        plan_original_messages: list[dict[str, str]] | None = None,
        implementation_original_messages: list[dict[str, str]] | None = None,
    ) -> RefinementResult:
        """Refine plan/implementation based on feedback using conversational pattern.

        Args:
            plan: Original plan
            implementation: Original implementation
            evaluation: Evaluation results
            failure_analysis: Analysis of what failed (None = analyze internally)
            song_features: Audio features
            seq_fingerprint: Sequence fingerprint
            template_metadata: Template metadata
            plan_original_messages: Original messages used to generate the plan
            implementation_original_messages: Original messages used to generate the implementation

        Returns:
            RefinementResult with refined output
        """
        # If no failure analysis provided, create a simple one
        if failure_analysis is None:
            from blinkb0t.core.agents.moving_heads.judge_critic import FailureAnalysis

            # Simple heuristic: replan if very low score, else refine implementation
            fix_strategy = "replan" if evaluation.overall_score < 60 else "refine_implementation"
            failure_analysis = FailureAnalysis(
                primary_issue="plan" if evaluation.overall_score < 60 else "implementation",
                failure_categories=[
                    cat.category for cat in evaluation.category_scores if cat.score < 70
                ],
                root_cause="Score below threshold",
                fix_strategy=fix_strategy,
            )

        logger.info(
            f"Refining: strategy={failure_analysis.fix_strategy}, "
            f"score={evaluation.overall_score:.1f}"
        )

        # Determine strategy
        if failure_analysis.fix_strategy == "replan":
            strategy = RefineStrategy.REPLAN
        elif failure_analysis.fix_strategy == "refine_implementation":
            strategy = RefineStrategy.REFINE_IMPLEMENTATION
        else:
            strategy = RefineStrategy.FULL_REPLAN

        # Execute strategy
        if strategy == RefineStrategy.REPLAN:
            return self._replan(
                original_plan=plan,
                evaluation=evaluation,
                failure_analysis=failure_analysis,
                song_features=song_features,
                seq_fingerprint=seq_fingerprint,
                template_metadata=template_metadata,
                original_messages=plan_original_messages,
            )
        elif strategy == RefineStrategy.REFINE_IMPLEMENTATION:
            return self._refine_implementation(
                plan=plan,
                original_implementation=implementation,
                evaluation=evaluation,
                failure_analysis=failure_analysis,
                song_features=song_features,
                seq_fingerprint=seq_fingerprint,
                template_metadata=template_metadata,
                original_messages=implementation_original_messages,
            )
        else:  # FULL_REPLAN
            # Same as REPLAN but with more aggressive feedback
            return self._replan(
                original_plan=plan,
                evaluation=evaluation,
                failure_analysis=failure_analysis,
                song_features=song_features,
                seq_fingerprint=seq_fingerprint,
                template_metadata=template_metadata,
                aggressive=True,
                original_messages=plan_original_messages,
            )

    # ========================================================================
    # Private Methods - Replan Strategy
    # ========================================================================

    def _replan(
        self,
        original_plan: AgentPlan,
        evaluation: Evaluation,
        failure_analysis: FailureAnalysis,
        song_features: dict[str, Any],
        seq_fingerprint: dict[str, Any],
        template_metadata: list[dict[str, Any]],
        aggressive: bool = False,
        original_messages: list[dict[str, str]] | None = None,
    ) -> RefinementResult:
        """Regenerate plan with feedback using conversational pattern.

        Uses multi-turn conversation to provide context of original plan and feedback.
        """
        logger.info("Replanning with feedback (conversational)...")

        # Build feedback context
        feedback_context = self._build_feedback_context(evaluation, failure_analysis, focus="plan")

        # Shape context with feedback
        shaped_context = self.context_shaper.shape_for_stage(
            stage=Stage.REFINEMENT,
            song_features=song_features,
            seq_fingerprint=seq_fingerprint,
            template_metadata=template_metadata,
            plan=original_plan.model_dump(),
        )

        # Add feedback to context
        shaped_context.data["feedback"] = feedback_context
        shaped_context.data["previous_issues"] = self._extract_issues(evaluation)

        # Build refinement prompt (feedback only)
        feedback_prompt = self._build_feedback_prompt(evaluation, feedback_context)

        messages: list[dict[str, str]] = []
        # Build conversational messages
        if original_messages:
            # Use conversational pattern: original task -> original response -> feedback
            messages.extend(original_messages)  # Copy original [system, user]
            messages.append(
                {"role": "assistant", "content": json.dumps(original_plan.model_dump(), indent=2)}
            )
            messages.append({"role": "user", "content": feedback_prompt})
            logger.info("Using conversational refinement (4 messages)")
        else:
            # Fallback to old approach if original messages not available
            prompt = self._build_replan_prompt(shaped_context.data)
            messages.extend(
                [
                    {"role": "developer", "content": self._get_replan_system_prompt()},
                    {"role": "user", "content": prompt},
                ]
            )
            logger.warning("Original messages not available, using fallback approach")

        # Call LLM
        try:
            data = self.openai_client.generate_json(
                messages=messages,
                model=self.refinement_config.model,
                temperature=self.refinement_config.temperature,
                verbosity=Verbosity.HIGH,
            )

            prompt_tokens = self.openai_client.get_total_token_usage().prompt_tokens
            response_tokens = self.openai_client.get_total_token_usage().completion_tokens
            tokens_used = self.openai_client.get_total_token_usage().total_tokens

            logger.info(f"Prompt tokens: {prompt_tokens}")
            logger.info(f"Response tokens: {response_tokens}")
            logger.info(f"Plan generated: {json.dumps(data, indent=2)}")

            # Parse new plan
            new_plan = AgentPlan.model_validate(data)

            logger.info(f"Replanned: {len(new_plan.sections)} sections")

            return RefinementResult(
                success=True,
                strategy=(RefineStrategy.REPLAN if not aggressive else RefineStrategy.FULL_REPLAN),
                plan=new_plan,
                implementation=None,
                error=None,
                tokens_used=tokens_used,
            )

        except Exception as e:
            logger.error(f"Replanning failed: {e}")
            return RefinementResult(
                success=False,
                strategy=RefineStrategy.REPLAN,
                plan=None,
                implementation=None,
                error=str(e),
                tokens_used=0,
            )

    # ========================================================================
    # Private Methods - Refine Implementation Strategy
    # ========================================================================

    def _refine_implementation(
        self,
        plan: AgentPlan,
        original_implementation: AgentImplementation,
        evaluation: Evaluation,
        failure_analysis: FailureAnalysis,
        song_features: dict[str, Any],
        seq_fingerprint: dict[str, Any],
        template_metadata: list[dict[str, Any]],
        original_messages: list[dict[str, str]] | None = None,
    ) -> RefinementResult:
        """Refine implementation with feedback using conversational pattern.

        Uses multi-turn conversation to provide context of original implementation and feedback.
        """
        logger.info("Refining implementation with feedback (conversational)...")

        # Build feedback context
        feedback_context = self._build_feedback_context(
            evaluation, failure_analysis, focus="implementation"
        )

        # Shape context
        shaped_context = self.context_shaper.shape_for_stage(
            stage=Stage.REFINEMENT,
            song_features=song_features,
            seq_fingerprint=seq_fingerprint,
            template_metadata=template_metadata,
            plan=plan.model_dump(),
        )

        # Add feedback
        shaped_context.data["feedback"] = feedback_context
        shaped_context.data["previous_issues"] = self._extract_issues(evaluation)
        shaped_context.data["original_implementation"] = self._summarize_implementation(
            original_implementation
        )

        # Build refinement prompt (feedback only)
        feedback_prompt = self._build_feedback_prompt(evaluation, feedback_context)

        # Build conversational messages
        messages: list[dict[str, str]]
        if original_messages:
            # Use conversational pattern: original task -> original response -> feedback
            messages = list(original_messages)  # Copy original [system, user]
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(original_implementation.model_dump(), indent=2),
                }
            )
            messages.append({"role": "user", "content": feedback_prompt})
            logger.info("Using conversational refinement (4 messages)")
        else:
            # Fallback to old approach if original messages not available
            prompt = self._build_refine_impl_prompt(shaped_context.data)
            messages = [
                {
                    "role": "developer",
                    "content": self._get_refine_impl_system_prompt(),
                },
                {"role": "user", "content": prompt},
            ]
            logger.warning("Original messages not available, using fallback approach")

        # Call LLM
        try:
            data = self.openai_client.generate_json(
                messages=messages,
                model=self.refinement_config.model,
                temperature=self.refinement_config.temperature,
                verbosity=Verbosity.MEDIUM,
            )

            tokens_used = self.openai_client.get_total_token_usage().total_tokens
            prompt_tokens = self.openai_client.get_total_token_usage().prompt_tokens
            response_tokens = self.openai_client.get_total_token_usage().completion_tokens

            logger.info(f"Prompt tokens: {prompt_tokens}")
            logger.info(f"Response tokens: {response_tokens}")

            # Parse new implementation
            new_implementation = AgentImplementation.model_validate(data)

            logger.info(
                f"Implementation refined: {len(new_implementation.sections)} sections, "
                f"{tokens_used} tokens used"
            )

            return RefinementResult(
                success=True,
                strategy=RefineStrategy.REFINE_IMPLEMENTATION,
                plan=None,
                implementation=new_implementation,
                error=None,
                tokens_used=tokens_used,
            )

        except Exception as e:
            logger.error(f"Implementation refinement failed: {e}")
            return RefinementResult(
                success=False,
                strategy=RefineStrategy.REFINE_IMPLEMENTATION,
                plan=None,
                implementation=None,
                error=str(e),
                tokens_used=0,
            )

    # ========================================================================
    # Private Methods - Feedback & Prompts
    # ========================================================================

    def _build_feedback_context(
        self, evaluation: Evaluation, failure_analysis: FailureAnalysis, focus: str
    ) -> dict[str, Any]:
        """Build feedback context for refinement."""
        return {
            "overall_score": evaluation.overall_score,
            "failing_categories": failure_analysis.failure_categories,
            "root_cause": failure_analysis.root_cause,
            "actionable_feedback": evaluation.actionable_feedback,
            "category_details": [
                {
                    "category": score.category,
                    "score": score.score,
                    "weaknesses": score.weaknesses,
                }
                for score in evaluation.category_scores
                if score.score < 70  # Focus on low-scoring categories
            ],
        }

    def _extract_issues(self, evaluation: Evaluation) -> list[str]:
        """Extract specific issues from evaluation."""
        issues = []
        for category_score in evaluation.category_scores:
            if category_score.score < 70:
                issues.extend(category_score.weaknesses)
        return issues

    def _summarize_implementation(self, implementation: AgentImplementation) -> dict[str, Any]:
        """Summarize implementation for context."""
        return {
            "section_count": len(implementation.sections),
            "total_duration_bars": implementation.total_duration_bars,
            "sections": [
                {
                    "name": s.name,
                    "start_bar": s.start_bar,
                    "end_bar": s.end_bar,
                    "template_id": s.template_id,
                }
                for s in implementation.sections
            ],
        }

    def _get_replan_system_prompt(self) -> str:
        """System prompt for replanning."""
        return """You are refining a lighting choreography plan based on feedback.

The previous plan had issues. Your task is to create an improved plan that addresses all feedback.

Key improvements to make:
1. Fix identified weaknesses
2. Address low-scoring categories
3. Implement actionable suggestions
4. Maintain what worked well

Do not repeat the same mistakes. Be creative and responsive to feedback.

Output valid JSON matching the plan schema."""

    def _get_refine_impl_system_prompt(self) -> str:
        """System prompt for refining implementation."""
        return """You are refining a lighting choreography implementation based on feedback.

The previous implementation had issues. Your task is to create an improved implementation that addresses all feedback.

Key improvements to make:
1. Fix timing issues (alignment, gaps, overlaps)
2. Improve transitions
3. Adjust targeting if needed
4. Maintain the strategic plan

Do not repeat the same mistakes. Focus on execution details.

Output valid JSON matching the implementation schema."""

    def _build_replan_prompt(self, shaped_context: dict[str, Any]) -> str:
        """Build prompt for replanning using version resolution."""
        from pathlib import Path

        from blinkb0t.core.config.models import SequencingVersionConfig

        feedback = shaped_context.get("feedback", {})
        previous_issues = shaped_context.get("previous_issues", [])

        # Get version config for prompt version
        version_config = SequencingVersionConfig()

        # Extract major version (e.g., "1.0.0" -> "v1")
        major_version = version_config.prompt.split(".")[0]
        version_dir = f"v{major_version}"

        # Load prompt template
        prompt_path = Path(__file__).parent / "prompts" / version_dir / "refinement_replan.txt"
        prompt_template = prompt_path.read_text()

        # Format template
        return prompt_template.format(
            overall_score=f"{feedback.get('overall_score', 0):.1f}",
            failing_categories=", ".join(feedback.get("failing_categories", [])),
            root_cause=feedback.get("root_cause", "Unknown"),
            previous_issues="\n".join(f"- {issue}" for issue in previous_issues),
            actionable_feedback="\n".join(
                f"- {fb}" for fb in feedback.get("actionable_feedback", [])
            ),
            context=self._format_context_for_refinement(shaped_context),
        )

    def _build_refine_impl_prompt(self, shaped_context: dict[str, Any]) -> str:
        """Build prompt for refining implementation using version resolution."""
        from pathlib import Path

        from blinkb0t.core.config.models import SequencingVersionConfig

        feedback = shaped_context.get("feedback", {})
        previous_issues = shaped_context.get("previous_issues", [])

        # Get version config for prompt version
        version_config = SequencingVersionConfig()

        # Extract major version (e.g., "1.0.0" -> "v1")
        major_version = version_config.prompt.split(".")[0]
        version_dir = f"v{major_version}"

        # Load prompt template
        prompt_path = (
            Path(__file__).parent / "prompts" / version_dir / "refinement_implementation.txt"
        )
        prompt_template = prompt_path.read_text()

        # Format template
        return prompt_template.format(
            overall_score=f"{feedback.get('overall_score', 0):.1f}",
            failing_categories=", ".join(feedback.get("failing_categories", [])),
            previous_issues="\n".join(f"- {issue}" for issue in previous_issues),
            actionable_feedback="\n".join(
                f"- {fb}" for fb in feedback.get("actionable_feedback", [])
            ),
            context=self._format_context_for_refinement(shaped_context),
        )

    def _format_context_for_refinement(self, shaped_context: dict[str, Any]) -> str:
        """Format context for refinement prompts."""
        # Include relevant context sections
        lines = []

        if "timing" in shaped_context:
            lines.append("## Timing Information")
            timing = shaped_context["timing"]
            lines.append(f"- Bars: {len(timing.get('bars_s', []))}")
            lines.append(f"- Tempo: {timing.get('tempo_bpm')} BPM")

        if "templates" in shaped_context:
            lines.append("\n## Available Templates")
            lines.append(f"{len(shaped_context['templates'])} templates available")

        return "\n".join(lines)

    def _build_feedback_prompt(
        self, evaluation: Evaluation, feedback_context: dict[str, Any]
    ) -> str:
        """Build conversational feedback prompt for refinement.

        This is used in multi-turn conversations where the LLM sees its original output.
        The prompt should be concise and focus on specific issues to address.

        Args:
            evaluation: Judge evaluation results
            feedback_context: Structured feedback from _build_feedback_context

        Returns:
            Feedback prompt string
        """
        lines = [
            f"Your choreography plan scored {evaluation.overall_score:.1f}/100.",
            "",
            "## Issues Identified:",
        ]

        # Add specific category scores that failed
        for cat in evaluation.category_scores:
            if cat.score < 70:
                # Build feedback from reasoning and weaknesses
                feedback_parts = [cat.reasoning]
                if cat.weaknesses:
                    feedback_parts.append("Weaknesses: " + ", ".join(cat.weaknesses))
                feedback = " - ".join(feedback_parts)
                lines.append(f"- **{cat.category}** ({cat.score}/100): {feedback}")

        lines.append("")
        lines.append("## Required Improvements:")

        # Add actionable feedback
        if "actionable_feedback" in feedback_context:
            for fb in feedback_context["actionable_feedback"]:
                lines.append(f"- {fb}")
        else:
            lines.append("- Address the issues identified above")
            lines.append("- Maintain what worked well in the original plan")

        lines.append("")
        lines.append(
            "Please revise your plan to address these specific issues while preserving "
            "the successful elements. Return the complete revised plan in JSON format."
        )

        return "\n".join(lines)
