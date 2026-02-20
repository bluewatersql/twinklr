"""Orchestrator for MacroPlanner with judge-based iteration.

This module provides a high-level orchestrator that coordinates the MacroPlanner
agent with heuristic validation and judge-based refinement using the
StandardIterationController.
"""

from __future__ import annotations

import hashlib
import json
import logging

from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.sequencer.macro_planner.context import PlanningContext
from twinklr.core.agents.sequencer.macro_planner.heuristics import (
    MacroPlanHeuristicValidator,
)
from twinklr.core.agents.sequencer.macro_planner.specs import (
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
from twinklr.core.agents.taxonomy_utils import get_theming_catalog_dict, get_theming_ids
from twinklr.core.sequencer.planning import MacroPlan

logger = logging.getLogger(__name__)


class MacroPlannerOrchestrator:
    """Orchestrates MacroPlanner with judge-based iteration.

    Provides a high-level interface for running the MacroPlanner with:
    - Heuristic validation (fast, deterministic quality checks)
    - Judge-based evaluation (LLM-driven quality assessment)
    - Iterative refinement with feedback

    Attributes:
        planner_spec: Planner agent specification
        judge_spec: Judge agent specification
        heuristic_validator: Heuristic validator instance
        controller: StandardIterationController instance
        provider: LLM provider
        llm_logger: LLM call logger
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        planner_spec: AgentSpec | None = None,
        judge_spec: AgentSpec | None = None,
        heuristic_validator: MacroPlanHeuristicValidator | None = None,
        max_iterations: int = 3,
        min_pass_score: float = 7.0,
        token_budget: int | None = None,
        llm_logger: LLMCallLogger | None = None,
    ):
        """Initialize MacroPlanner orchestrator.

        Args:
            provider: LLM provider for agent execution
            planner_spec: Optional planner spec (uses default if None)
            judge_spec: Optional judge spec (uses default if None)
            heuristic_validator: Optional validator (creates default if None)
            max_iterations: Maximum refinement iterations (default: 3)
            min_pass_score: Minimum score for approval (default: 7.0)
            token_budget: Optional token budget limit
            llm_logger: Optional LLM call logger (uses NullLLMCallLogger if None)
        """
        self.planner_spec = planner_spec or get_planner_spec()
        self.judge_spec = judge_spec or get_judge_spec()
        self.heuristic_validator = heuristic_validator or MacroPlanHeuristicValidator()
        self.provider = provider
        self.llm_logger = llm_logger or NullLLMCallLogger()

        # Create iteration config
        config = IterationConfig(
            max_iterations=max_iterations,
            approval_score_threshold=min_pass_score,
            token_budget=token_budget,
        )

        # Create feedback manager
        feedback_manager = FeedbackManager()

        # Create controller
        self.controller = StandardIterationController[MacroPlan](
            config=config,
            feedback_manager=feedback_manager,
        )

        logger.debug(
            f"MacroPlannerOrchestrator initialized "
            f"(max_iterations={max_iterations}, min_pass_score={min_pass_score})"
        )

    async def get_cache_key(self, planning_context: PlanningContext) -> str:
        """Generate cache key for deterministic caching.

        Cache key includes all inputs that affect macro plan output:
        - Audio profile (musical analysis)
        - Lyric context (narrative/themes, if present)
        - Display groups (available fixtures)
        - Max iterations
        - Min pass score
        - Model configuration

        Args:
            planning_context: Planning context for this run

        Returns:
            SHA256 hash of canonical inputs
        """
        key_data = {
            "audio_profile": planning_context.audio_profile.model_dump(),
            "lyric_context": (
                planning_context.lyric_context.model_dump()
                if planning_context.lyric_context
                else None
            ),
            "display_groups": planning_context.display_groups,
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
        planning_context: PlanningContext,
    ) -> IterationResult[MacroPlan]:
        """Run MacroPlanner with iterative refinement.

        Executes the complete MacroPlanner workflow:
        1. Generate initial plan (planner agent)
        2. Validate plan (heuristic validator)
        3. Evaluate plan (judge agent)
        4. Refine if needed (repeat with feedback)
        5. Return final plan or best attempt

        Args:
            planning_context: Complete planning context containing:
                - audio_profile: Musical analysis and creative guidance
                - lyric_context: Narrative and thematic analysis (optional)
                - display_groups: Available display groups with concrete IDs

        Returns:
            IterationResult containing the final MacroPlan and metadata

        Raises:
            ValueError: If inputs are invalid
        """
        audio_profile = planning_context.audio_profile

        if not audio_profile.structure.sections:
            raise ValueError("AudioProfile must have at least one section")

        if not planning_context.display_groups:
            raise ValueError("At least one display group must be provided")

        missing_group_ids = [
            idx
            for idx, group in enumerate(planning_context.display_groups)
            if not str(group.get("id") or "").strip()
        ]
        if missing_group_ids:
            raise ValueError(
                "Display metadata missing concrete group id(s) at index(es): "
                f"{missing_group_ids}. Macro planner requires group['id'] for all groups."
            )

        logger.debug(
            f"Starting MacroPlanner orchestration: "
            f"{audio_profile.song_identity.title} by {audio_profile.song_identity.artist}"
        )
        if planning_context.has_lyrics:
            logger.debug("  ✅ Lyric context available (narrative + thematic analysis)")
        else:
            logger.debug("  ⏭️  No lyric context (musical analysis only)")

        # Prepare initial variables for planner
        # Get theming catalog for theme/palette/tag/motif selection
        theming_catalog = get_theming_catalog_dict()
        theming_ids = get_theming_ids()

        initial_variables = {
            "audio_profile": audio_profile,
            "display_groups": planning_context.display_groups,
            # Theme catalog: theme_id + title for selection
            "theme_catalog": [
                {"theme_id": t["id"], "title": t["title"]} for t in theming_catalog["themes"]
            ],
            # Palette catalog: for palette override validation
            "palette_catalog": theming_catalog["palettes"],
            # Tag catalog: for valid tag selection
            "tag_catalog": theming_catalog["tags"],
            # Motif catalog: for motif selection and energy matching
            "motif_catalog": theming_catalog["motifs"],
            # ID lists for validation
            "theming_ids": theming_ids,
        }

        # Derive typed targeting catalogs for macro section intent (group/zone/split)
        available_group_ids: list[str] = []
        available_zones: set[str] = set()
        available_splits: set[str] = set()
        for group in planning_context.display_groups:
            gid = str(group.get("id") or "").strip()
            if gid:
                available_group_ids.append(gid)

            zone = group.get("zone")
            if zone:
                available_zones.add(str(zone))
            tags = group.get("tags") or group.get("zones") or []
            if isinstance(tags, list):
                available_zones.update(str(tag) for tag in tags if tag)

            splits = group.get("split_membership") or group.get("splits") or []
            if isinstance(splits, list):
                available_splits.update(str(split) for split in splits if split)

        initial_variables["available_group_ids"] = available_group_ids
        initial_variables["available_zone_ids"] = sorted(available_zones)
        initial_variables["available_split_ids"] = sorted(available_splits)

        # Add lyric context if available
        if planning_context.lyric_context:
            initial_variables["lyric_context"] = planning_context.lyric_context

        # Define validator function (converts heuristic validator to callable)
        def validator(plan: MacroPlan) -> list[str]:
            """Validate plan and return list of error messages."""
            # Deterministic repair: canonicalize section ids by audio timing so
            # generic labels like "verse"/"chorus" don't cause avoidable failures.
            self._canonicalize_section_ids(plan, audio_profile)
            issues = self.heuristic_validator.validate(
                plan,
                audio_profile,
                display_groups=planning_context.display_groups,
            )

            # Return only ERROR severity issues as strings
            errors = [
                f"{issue.category.value}: {issue.message}"
                for issue in issues
                if issue.severity.name == "ERROR"
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
        )

        if result.success:
            logger.debug(
                f"✅ MacroPlanner succeeded: {result.context.current_iteration} iterations, "
                f"score {result.context.final_verdict.score:.1f}"
                if result.context.final_verdict
                else f"✅ MacroPlanner succeeded: {result.context.current_iteration} iterations"
            )
        else:
            logger.warning(
                f"⚠️ MacroPlanner completed without approval: "
                f"{result.context.current_iteration} iterations, "
                f"termination: {result.context.termination_reason}"
            )

        return result

    def _canonicalize_section_ids(self, plan: MacroPlan, audio_profile: object) -> None:
        """Normalize MacroPlan section ids to canonical audio structure ids.

        Uses exact timing bounds first, then ordered fallback when counts match.
        """
        sections = getattr(getattr(audio_profile, "structure", None), "sections", None)
        if not sections:
            return

        expected = list(sections)
        by_bounds = {(int(s.start_ms), int(s.end_ms)): s for s in expected}

        # Pass 1: exact timing match
        for section_plan in plan.section_plans:
            key = (int(section_plan.section.start_ms), int(section_plan.section.end_ms))
            match = by_bounds.get(key)
            if match is not None:
                section_plan.section = section_plan.section.model_copy(
                    update={"section_id": str(match.section_id), "name": str(match.name)}
                )

        # Pass 2: ordered fallback when section count matches
        if len(plan.section_plans) != len(expected):
            return

        sorted_plan = sorted(
            plan.section_plans, key=lambda sp: (sp.section.start_ms, sp.section.end_ms)
        )
        sorted_expected = sorted(expected, key=lambda s: (s.start_ms, s.end_ms))
        for plan_section, expected_section in zip(sorted_plan, sorted_expected, strict=False):
            if (
                abs(int(plan_section.section.start_ms) - int(expected_section.start_ms)) <= 1
                and abs(int(plan_section.section.end_ms) - int(expected_section.end_ms)) <= 1
            ):
                plan_section.section = plan_section.section.model_copy(
                    update={
                        "section_id": str(expected_section.section_id),
                        "name": str(expected_section.name),
                    }
                )
