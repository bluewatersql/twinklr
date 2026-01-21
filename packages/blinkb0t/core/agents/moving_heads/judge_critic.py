"""LLM-based quality assessment for plans and implementations.

Provides objective scoring with actionable feedback.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from blinkb0t.core.agents.moving_heads.context import ContextShaper, Stage
from blinkb0t.core.agents.moving_heads.models_agent_plan import (
    AgentImplementation,
    AgentPlan,
    ChannelScoring,
)
from blinkb0t.core.api.llm.openai.client import OpenAIClient, Verbosity
from blinkb0t.core.config.models import JobConfig

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models for Evaluation
# ============================================================================


class CategoryScore(BaseModel):
    """Score for a single category."""

    category: str = Field(description="Category name")
    score: int = Field(description="Score 0-100", ge=0, le=100)
    reasoning: str = Field(description="Why this score was given")
    strengths: list[str] = Field(description="What works well")
    weaknesses: list[str] = Field(description="What needs improvement")


class Evaluation(BaseModel):
    """Complete evaluation result (extended with channel scoring)."""

    story_overview: str = Field(
        description="2-3 sentence narrative describing the choreographic vision and story"
    )
    overall_score: float = Field(description="Overall score 0-100", ge=0, le=100)
    category_scores: list[CategoryScore] = Field(description="Scores per category")
    summary: str = Field(description="Overall assessment summary")
    actionable_feedback: list[str] = Field(description="Specific improvement suggestions")
    pass_threshold: bool = Field(description="Whether score meets passing threshold")

    # Channel scoring (optional for backward compatibility)
    channel_scoring: ChannelScoring | None = Field(
        default=None, description="Channel usage evaluation (addition)"
    )


class FailureAnalysis(BaseModel):
    """Analysis of what failed and why."""

    primary_issue: str = Field(description="Main problem (plan or implementation)")
    failure_categories: list[str] = Field(description="Which categories failed")
    root_cause: str = Field(description="Root cause analysis")
    fix_strategy: str = Field(description="How to fix (replan, refine_implementation, etc.)")


# ============================================================================
# Judge/Critic
# ============================================================================


class EvaluationResult(BaseModel):
    """Result of evaluation.

    Converted from dataclass to Pydantic for validation and serialization.
    """

    success: bool = Field(description="Whether evaluation succeeded")
    evaluation: Evaluation | None = Field(default=None, description="Evaluation if successful")
    failure_analysis: FailureAnalysis | None = Field(
        default=None, description="Failure analysis if unsuccessful"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    tokens_used: int = Field(ge=0, description="Number of tokens used")

    model_config = ConfigDict(
        frozen=False,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


class JudgeCritic:
    """Evaluates plan and implementation quality using LLM.

    Responsibilities:
    1. Build evaluation prompt with rubric
    2. Call LLM for assessment
    3. Parse scores and feedback
    4. Calculate overall score
    5. Identify failure reasons (if <pass_threshold)
    6. Generate actionable feedback

    Example:
        judge = JudgeCritic(
            job_config=job_config,
            openai_client=openai_client
        )

        result = judge.evaluate(
            plan=plan,
            implementation=implementation,
            song_features=song_features
        )

        if result.success:
            if result.evaluation.pass_threshold:
                print("PASSED")
            else:
                print("FAILED")
                print(result.failure_analysis.fix_strategy)
    """

    def __init__(self, job_config: JobConfig, openai_client: OpenAIClient) -> None:
        """Initialize judge/critic.

        Args:
            job_config: Job configuration
            openai_client: OpenAI API client
        """
        self.job_config = job_config
        self.openai_client = openai_client
        self.context_shaper = ContextShaper(job_config=job_config)

        # Get agent config
        self.agent_config = job_config.agent

        # Pass threshold
        self.pass_threshold = self.agent_config.success_threshold

        logger.debug(f"JudgeCritic initialized (pass threshold: {self.pass_threshold})")

    def evaluate(
        self,
        plan: AgentPlan,
        implementation: AgentImplementation,
        song_features: dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate plan and implementation quality.

        Args:
            plan: Generated plan
            implementation: Expanded implementation
            song_features: Audio features

        Returns:
            EvaluationResult with scores and feedback
        """
        logger.info("Evaluating plan and implementation...")

        # Shape context for judge stage
        shaped_context = self.context_shaper.shape_for_stage(
            stage=Stage.JUDGE, song_features=song_features, plan=plan.model_dump()
        )

        logger.info(
            f"Context shaped: {shaped_context.token_estimate} tokens "
            f"(reduced {shaped_context.reduction_pct:.1f}%)"
        )

        # Build prompt
        prompt = self._build_prompt(plan, implementation, shaped_context.data)

        # Call LLM
        try:
            logger.debug("Calling LLM for evaluation")

            # Build messages list for OpenAI API
            messages: list[dict[str, str]] = [
                {"role": "developer", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt},
            ]

            # gpt-5-mini only supports temperature=1.0, other models can use custom temperature
            model = self.agent_config.judge_agent.model
            temperature = 1.0 if "mini" in model.lower() else 0.4

            response = self.openai_client.generate_json(
                messages=messages,
                model=model,
                temperature=temperature,
                verbosity=Verbosity.MEDIUM,
            )

            tokens_used = self.openai_client.get_total_token_usage().total_tokens
            prompt_tokens = self.openai_client.get_total_token_usage().prompt_tokens
            response_tokens = self.openai_client.get_total_token_usage().completion_tokens

            logger.info(f"Prompt tokens: {prompt_tokens}")
            logger.info(f"Response tokens: {response_tokens}")
            logger.info(f"Evaluation: {json.dumps(response, indent=2)}")

            # Parse evaluation
            evaluation = self._parse_evaluation(json.dumps(response))

            # Calculate pass/fail
            evaluation.pass_threshold = evaluation.overall_score >= self.pass_threshold

            # If failed, analyze failure
            failure_analysis = None
            if not evaluation.pass_threshold:
                failure_analysis = self._analyze_failure(evaluation, plan, implementation)

            logger.info(
                f"Evaluation complete: score={evaluation.overall_score:.1f}, "
                f"{'PASS' if evaluation.pass_threshold else 'FAIL'}"
            )

            return EvaluationResult(
                success=True,
                evaluation=evaluation,
                failure_analysis=failure_analysis,
                error=None,
                tokens_used=tokens_used,
            )

        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Evaluation parsing/validation failed: {e}")
            return EvaluationResult(
                success=False,
                evaluation=None,
                failure_analysis=None,
                error=f"Failed to parse/validate evaluation: {e}",
                tokens_used=tokens_used,
            )
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return EvaluationResult(
                success=False,
                evaluation=None,
                failure_analysis=None,
                error=str(e),
                tokens_used=0,
            )

    # ========================================================================
    # Private Methods - Prompt Building
    # ========================================================================

    def _get_system_prompt(self) -> str:
        """Load system prompt from file using version resolution and format with pass_threshold."""
        from pathlib import Path

        from blinkb0t.core.config.models import SequencingVersionConfig

        # Get version config for prompt version
        version_config = SequencingVersionConfig()

        # Extract major version (e.g., "1.0.0" -> "v1")
        major_version = version_config.prompt.split(".")[0]
        version_dir = f"v{major_version}"

        # Build path relative to this file
        prompt_path = Path(__file__).parent / "prompts" / version_dir / "judge_system.txt"
        prompt_template = prompt_path.read_text()
        return prompt_template.format(pass_threshold=self.pass_threshold)

    def _build_prompt(
        self,
        plan: AgentPlan,
        implementation: AgentImplementation,
        shaped_context: dict[str, Any],
    ) -> str:
        """Build evaluation prompt.

        Args:
            plan: Plan to evaluate
            implementation: Implementation to evaluate
            shaped_context: Shaped context from ContextShaper

        Returns:
            Formatted prompt string
        """
        from pathlib import Path

        from blinkb0t.core.agents.schema_utils import get_json_schema_example
        from blinkb0t.core.config.models import SequencingVersionConfig

        # Load user prompt template
        version_config = SequencingVersionConfig()
        major_version = version_config.prompt.split(".")[0]
        version_dir = f"v{major_version}"
        prompt_path = Path(__file__).parent / "prompts" / version_dir / "judge_user.txt"
        prompt_template = prompt_path.read_text()

        audio_summary = shaped_context.get("audio_summary", {})

        # Generate JSON schema from Pydantic model
        json_schema = get_json_schema_example(Evaluation)

        # Format prompt with parameters
        return prompt_template.format(
            duration_s=audio_summary.get("duration_s"),
            tempo_bpm=audio_summary.get("tempo_bpm"),
            time_signature=audio_summary.get("time_signature"),
            bar_count=audio_summary.get("bar_count"),
            overall_strategy=plan.overall_strategy,
            section_count=len(plan.sections),
            plan_sections=self._format_plan_sections(plan),
            template_variety_score=plan.template_variety_score,
            energy_alignment_score=plan.energy_alignment_score,
            total_duration_bars=implementation.total_duration_bars,
            quantization_applied=implementation.quantization_applied,
            timing_precision=implementation.timing_precision,
            impl_section_count=len(implementation.sections),
            implementation_sections=self._format_implementation_sections(implementation),
            pass_threshold=self.pass_threshold,
            json_schema=json_schema,
        )

    def _format_plan_sections(self, plan: AgentPlan) -> str:
        """Format plan sections for prompt."""
        lines = []
        for section in plan.sections:
            templates_str = ", ".join(section.templates)
            lines.append(
                f"- {section.name}: bars {section.start_bar}-{section.end_bar}, "
                f"templates=[{templates_str}] ({section.section_role}, "
                f"energy={section.energy_level})"
            )
        return "\n".join(lines)

    def _format_implementation_sections(self, implementation: AgentImplementation) -> str:
        """Format implementation sections for prompt."""
        lines = []
        for section in implementation.sections:
            duration_s = (section.end_bar - section.start_bar) / 1000.0
            lines.append(
                f"- {section.name}: {section.start_bar}ms-{section.end_bar}ms "
                f"({duration_s:.1f}s), {section.template_id}, "
                f"targets={section.targets}"
            )
        return "\n".join(lines)

    # ========================================================================
    # Private Methods - Parsing & Analysis
    # ========================================================================

    def _parse_evaluation(self, response_content: str) -> Evaluation:
        """Parse LLM response into Evaluation object.

        Args:
            response_content: JSON string from LLM

        Returns:
            Validated Evaluation object

        Raises:
            json.JSONDecodeError: If invalid JSON
            ValidationError: If validation fails
        """
        # Parse JSON
        eval_json = json.loads(response_content)

        # Validate with Pydantic
        evaluation = Evaluation.model_validate(eval_json)

        logger.debug(
            f"Evaluation parsed: overall={evaluation.overall_score:.1f}, "
            f"categories={len(evaluation.category_scores)}"
        )

        return evaluation

    def _analyze_failure(
        self,
        evaluation: Evaluation,
        plan: AgentPlan,
        implementation: AgentImplementation,
    ) -> FailureAnalysis:
        """Analyze why evaluation failed.

        Determines whether failure is due to plan or implementation,
        and suggests fix strategy.

        Args:
            evaluation: Failed evaluation
            plan: Original plan
            implementation: Implementation

        Returns:
            FailureAnalysis with fix strategy
        """
        # Find failing categories (score < 60)
        failing_categories = [
            score.category for score in evaluation.category_scores if score.score < 60
        ]

        # Determine primary issue
        plan_related = {"Template Variety", "Energy Matching"}
        impl_related = {"Musical Alignment", "Timing Coverage", "Transition Quality"}

        plan_failures = len([c for c in failing_categories if c in plan_related])
        impl_failures = len([c for c in failing_categories if c in impl_related])

        if plan_failures > impl_failures:
            primary_issue = "plan"
            fix_strategy = "replan"
            root_cause = "Template selection or energy matching issues"
        elif impl_failures > plan_failures:
            primary_issue = "implementation"
            fix_strategy = "refine_implementation"
            root_cause = "Timing, coverage, or transition issues"
        else:
            primary_issue = "both"
            fix_strategy = "replan"  # Safer to replan
            root_cause = "Issues in both planning and implementation"

        return FailureAnalysis(
            primary_issue=primary_issue,
            failure_categories=failing_categories,
            root_cause=root_cause,
            fix_strategy=fix_strategy,
        )
