"""Orchestrator for GroupPlanner with judge-based iteration.

This module provides orchestration for GroupPlanner agent, coordinating planner execution,
heuristic validation, and judge-based refinement using StandardIterationController.

For v1: Sequential execution (one group at a time).
For v2+: Parallel fan-out pattern (documented in changes/vnext/todo/).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.issues import IssueSeverity
from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.sequencer.group_planner.context import GroupPlanningContext
from twinklr.core.agents.sequencer.group_planner.heuristics import (
    GroupPlanHeuristicValidator,
)
from twinklr.core.agents.sequencer.group_planner.models import GroupPlan, GroupPlanSet
from twinklr.core.agents.sequencer.group_planner.specs import (
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
from twinklr.core.sequencer.templates.group_templates.library import (
    list_templates as list_group_templates,
)
from twinklr.core.sequencer.templates.models import template_ref_from_info

logger = logging.getLogger(__name__)


class GroupPlannerOrchestrator:
    """Orchestrator for GroupPlanner with iterative refinement.

    Coordinates GroupPlanner agent with heuristic validation and judge-based refinement.

    For v1: Sequential execution (one group at a time).
    For v2: Parallel fan-out with holistic judge evaluation.
    """

    def __init__(
        self,
        provider: LLMProvider,
        max_iterations: int = 3,
        min_pass_score: float = 7.0,
        planner_spec: AgentSpec | None = None,
        judge_spec: AgentSpec | None = None,
        llm_logger: LLMCallLogger | None = None,
    ):
        """Initialize GroupPlanner orchestrator.

        Args:
            provider: LLM provider for agent execution
            max_iterations: Maximum refinement iterations
            min_pass_score: Minimum judge score for approval (0-10)
            planner_spec: Optional custom planner spec
            judge_spec: Optional custom judge spec
            llm_logger: Optional LLM call logger
        """
        self.provider = provider
        self.planner_spec = planner_spec or get_planner_spec()
        self.judge_spec = judge_spec or get_judge_spec()
        self.llm_logger = llm_logger or NullLLMCallLogger()

        # Create iteration controller
        config = IterationConfig(
            max_iterations=max_iterations,
            approval_score_threshold=min_pass_score,
        )

        self.controller: StandardIterationController[GroupPlan] = StandardIterationController(
            config=config,
            feedback_manager=FeedbackManager(),
        )

        self.heuristic_validator: GroupPlanHeuristicValidator | None = None

    async def run_single_group(
        self,
        planning_context: GroupPlanningContext,
    ) -> IterationResult[GroupPlan]:
        """Run GroupPlanner for a single display group.

        Args:
            planning_context: Complete planning context for this group

        Returns:
            IterationResult containing the final GroupPlan and metadata

        Raises:
            ValueError: If inputs are invalid
        """
        audio_profile = planning_context.audio_profile

        if not audio_profile.structure.sections:
            raise ValueError("AudioProfile must have at least one section")

        logger.debug(
            f"Starting GroupPlanner for group '{planning_context.group_id}' "
            f"({planning_context.group_type})"
        )

        # Create validator with available template IDs
        template_ids = {t.template_id for t in planning_context.available_templates}
        self.heuristic_validator = GroupPlanHeuristicValidator(
            available_templates=template_ids
        )

        # Prepare initial variables for planner
        initial_variables: dict[str, Any] = {
            "audio_profile": audio_profile,
            "macro_plan": planning_context.macro_plan,
            "display_group": planning_context.display_group,
            "available_templates": planning_context.available_templates,
        }

        # Add lyric context if available
        if planning_context.lyric_context:
            initial_variables["lyric_context"] = planning_context.lyric_context

        # Define validator function
        def validator(plan: GroupPlan) -> list[str]:
            """Validate plan and return list of error messages."""
            if self.heuristic_validator is None:
                return []

            issues = self.heuristic_validator.validate(
                plan, audio_profile, max_layers=planning_context.max_layers
            )

            # Return only ERROR severity issues as strings
            errors = [
                f"{issue.issue_id}: {issue.message}"
                for issue in issues
                if issue.severity == IssueSeverity.ERROR
            ]
            return errors

        # Run iteration loop
        result = await self.controller.run(
            planner_spec=self.planner_spec,
            judge_spec=self.judge_spec,
            initial_variables=initial_variables,
            validator=validator,
            provider=self.provider,
            llm_logger=self.llm_logger,
            prompt_base_path=Path("packages/twinklr/core/agents/sequencer/group_planner/prompts"),
        )

        if result.success:
            logger.debug(
                f"✅ GroupPlanner succeeded for '{planning_context.group_id}': "
                f"{result.context.current_iteration} iterations, "
                f"score {result.context.final_verdict.score:.1f}"
                if result.context.final_verdict
                else f"✅ GroupPlanner succeeded: {result.context.current_iteration} iterations"
            )
        else:
            logger.warning(
                f"⚠️ GroupPlanner completed without approval for '{planning_context.group_id}': "
                f"{result.context.current_iteration} iterations, "
                f"termination: {result.context.termination_reason}"
            )

        return result

    async def run_all_groups(
        self,
        audio_profile: AudioProfileModel,
        lyric_context: Any | None,
        macro_plan: Any,
        display_groups: list[dict[str, Any]],
        available_templates: list[str] | None = None,
        max_layers: int = 3,
        max_effects_per_section: int = 8,
        allow_assets: bool = True,
    ) -> GroupPlanSet:
        """Run GroupPlanner for all display groups (sequential).

        Args:
            audio_profile: Audio profile from Phase 1
            lyric_context: Optional lyric context from Phase 1
            macro_plan: Macro plan from MacroPlanner
            display_groups: List of display groups to plan for
            available_templates: Available template IDs (if None, loads all from registry)
            max_layers: Max layers per section
            max_effects_per_section: Max effects per section
            allow_assets: Whether to allow asset requests

        Returns:
            GroupPlanSet with plans for all groups

        Raises:
            ValueError: If no display groups provided
        """
        if not display_groups:
            raise ValueError("At least one display group required")

        # Build template ref list from registry if not provided

        # Import bootstrap to ensure templates are registered
        from twinklr.core.sequencer.templates.group_templates import (
            bootstrap_traditional,  # noqa: F401
        )

        if available_templates is None:
            # Load all templates from registry
            template_refs = [
                template_ref_from_info(info) for info in list_group_templates()
            ]
        else:
            # Filter to specified template IDs
            all_templates = {
                info.template_id: info for info in list_group_templates()
            }
            template_refs = [
                template_ref_from_info(all_templates[tid])
                for tid in available_templates
                if tid in all_templates
            ]

        logger.debug(
            f"Starting GroupPlanner orchestration for {len(display_groups)} groups (sequential)"
        )

        group_plans: list[GroupPlan] = []

        # Sequential execution (v1)
        for group_dict in display_groups:
            from twinklr.core.agents.sequencer.group_planner.context import DisplayGroupRef

            display_group = DisplayGroupRef(
                group_id=group_dict.get("group_id", group_dict.get("role_key", "unknown")),
                name=group_dict.get("name", group_dict.get("role_key", "Unknown")),
                group_type=group_dict.get("group_type", "CUSTOM"),
                model_count=group_dict.get("model_count"),
                tags=group_dict.get("tags", []),
            )

            planning_context = GroupPlanningContext(
                audio_profile=audio_profile,
                lyric_context=lyric_context,
                macro_plan=macro_plan,
                display_group=display_group,
                available_templates=template_refs,
                max_layers=max_layers,
                max_effects_per_section=max_effects_per_section,
                allow_assets=allow_assets,
            )

            result = await self.run_single_group(planning_context)

            if result.plan:
                group_plans.append(result.plan)

        logger.debug(
            f"✅ GroupPlanner orchestration complete: {len(group_plans)} group plans generated"
        )

        # Aggregate into GroupPlanSet
        plan_set = GroupPlanSet(
            set_id=f"group_plan_set_{audio_profile.song_identity.title or 'unknown'}",
            group_plans=group_plans,
        )

        return plan_set
