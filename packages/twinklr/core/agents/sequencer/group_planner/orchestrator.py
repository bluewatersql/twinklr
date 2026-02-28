"""Orchestrator for GroupPlanner with section-level iteration.

Coordinates GroupPlanner agent with heuristic validation and section-level
judge evaluation using the StandardIterationController.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from difflib import get_close_matches
from typing import Any

from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.sequencer.group_planner.context import SectionPlanningContext
from twinklr.core.agents.sequencer.group_planner.specs import (
    get_planner_spec,
    get_section_judge_spec,
)
from twinklr.core.agents.sequencer.group_planner.validators import (
    SectionPlanValidator,
    ValidationSeverity,
)
from twinklr.core.agents.shared.judge.controller import (
    IterationConfig,
    IterationContext,
    IterationResult,
    StandardIterationController,
)
from twinklr.core.agents.shared.judge.feedback import FeedbackManager
from twinklr.core.agents.shared.judge.models import IterationState
from twinklr.core.agents.spec import AgentSpec
from twinklr.core.sequencer.planning import SectionCoordinationPlan
from twinklr.core.sequencer.vocabulary import CoordinationMode, EffectDuration, LaneKind

logger = logging.getLogger(__name__)


class GroupPlannerOrchestrator:
    """Orchestrates GroupPlanner with section-level iteration.

    Provides high-level interface for running the GroupPlanner with:
    - Heuristic validation (fast, deterministic quality checks)
    - Section-level judge evaluation (LLM-driven quality assessment)
    - Iterative refinement with feedback

    This orchestrator handles ONE SECTION at a time. For full song processing,
    use GroupPlannerStage with FAN_OUT pattern in the pipeline.

    Attributes:
        planner_spec: Planner agent specification
        section_judge_spec: Section judge agent specification
        provider: LLM provider
        llm_logger: LLM call logger
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        planner_spec: AgentSpec | None = None,
        section_judge_spec: AgentSpec | None = None,
        max_iterations: int = 3,
        min_pass_score: float = 7.0,
        token_budget: int | None = None,
        llm_logger: LLMCallLogger | None = None,
    ):
        """Initialize GroupPlanner orchestrator.

        Args:
            provider: LLM provider for agent execution
            planner_spec: Optional planner spec (uses default if None)
            section_judge_spec: Optional section judge spec (uses default if None)
            max_iterations: Maximum refinement iterations per section (default: 3)
            min_pass_score: Minimum score for section approval (default: 7.0)
            token_budget: Optional token budget limit per section
            llm_logger: Optional LLM call logger (uses NullLLMCallLogger if None)
        """
        self.planner_spec = planner_spec or get_planner_spec()
        self.section_judge_spec = section_judge_spec or get_section_judge_spec()
        self.provider = provider
        self.llm_logger = llm_logger or NullLLMCallLogger()

        # Create iteration config
        self.config = IterationConfig(
            max_iterations=max_iterations,
            approval_score_threshold=min_pass_score,
            token_budget=token_budget,
        )

        logger.debug(
            f"GroupPlannerOrchestrator initialized "
            f"(max_iterations={max_iterations}, min_pass_score={min_pass_score})"
        )

    async def get_cache_key(self, section_context: SectionPlanningContext) -> str:
        """Generate cache key for deterministic caching.

        Cache key includes all inputs that affect section plan output:
        - Section planning context (macro section plan, display graph, templates, layer intents)
        - Max iterations
        - Min pass score
        - Model configuration

        Note: timing_context is excluded from cache key because it contains
        song-level data (all bars, all section bounds) that would cause cache
        invalidation when any section changes. The planner prompt doesn't use
        timing_context directly, and the validator uses it at runtime.

        Args:
            section_context: Section planning context for this run

        Returns:
            SHA256 hash of canonical inputs
        """
        # Create filtered section context for cache key
        section_context_dict = section_context.model_dump()

        # Filter timing_context to only section-relevant data
        # This prevents song-level data from leaking into cache keys
        timing_context = section_context_dict.get("timing_context", {})
        filtered_timing = self._filter_timing_for_cache(
            timing_context,
            section_context.section_id,
            section_context.start_ms,
            section_context.end_ms,
        )
        section_context_dict["timing_context"] = filtered_timing

        key_data = {
            "section_context": section_context_dict,
            "max_iterations": self.config.max_iterations,
            "min_pass_score": self.config.approval_score_threshold,
            "planner_model": self.planner_spec.model,
            "judge_model": self.section_judge_spec.model,
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

    def _filter_timing_for_cache(
        self,
        timing_context: dict[str, Any],
        section_id: str,
        start_ms: int,
        end_ms: int,
    ) -> dict[str, Any]:
        """Filter timing_context to only section-relevant data for cache key.

        Excludes song-level data that shouldn't affect cache keys:
        - song_duration_ms: Not needed for section planning
        - bar_map: Filtered to only bars overlapping this section
        - section_bounds: Filtered to only this section

        Args:
            timing_context: Full timing context dict
            section_id: Current section ID
            start_ms: Section start in milliseconds
            end_ms: Section end in milliseconds

        Returns:
            Filtered timing context with only section-relevant data
        """
        # Only include bars that overlap with this section
        bar_map = timing_context.get("bar_map", {})
        filtered_bars: dict[str, Any] = {}
        for bar_key, bar_info in bar_map.items():
            if isinstance(bar_info, dict):
                bar_start = bar_info.get("start_ms", 0)
                bar_duration = bar_info.get("duration_ms", 0)
                bar_end = bar_start + bar_duration
                # Include bar if it overlaps with section
                if bar_start < end_ms and bar_end > start_ms:
                    filtered_bars[bar_key] = bar_info

        # Only include bounds for current section
        section_bounds = timing_context.get("section_bounds", {})
        filtered_bounds: dict[str, Any] = {}
        if section_id in section_bounds:
            filtered_bounds[section_id] = section_bounds[section_id]

        return {
            "beats_per_bar": timing_context.get("beats_per_bar", 4),
            "bar_map": filtered_bars,
            "section_bounds": filtered_bounds,
            # Intentionally exclude song_duration_ms (song-level data)
        }

    def _is_ultra_short_section(self, section_context: SectionPlanningContext) -> bool:
        """Check if section is too short for meaningful judge evaluation.

        Sections shorter than ~1 bar are pickups/transitions where the LLM
        judge can't meaningfully assess "quality" — heuristic validation is
        sufficient for correctness.

        Args:
            section_context: Section planning context

        Returns:
            True if section is < 1 bar (based on timing context)
        """
        duration_ms = section_context.duration_ms
        timing_ctx = section_context.timing_context
        if timing_ctx.bar_map:
            first_bar = next(iter(timing_ctx.bar_map.values()))
            bar_duration_ms = first_bar.duration_ms
            return duration_ms < bar_duration_ms
        # Fallback: < 1 second is definitely ultra-short
        return duration_ms < 1000

    async def run(
        self,
        section_context: SectionPlanningContext,
        *,
        run_id: str | None = None,
    ) -> IterationResult[SectionCoordinationPlan]:
        """Run GroupPlanner for a single section with iterative refinement.

        Executes the complete GroupPlanner workflow for one section:
        1. Generate initial section plan (planner agent)
        2. Validate plan (heuristic validator)
        3. Evaluate plan (section judge agent) — skipped for ultra-short sections
        4. Refine if needed (repeat with feedback)
        5. Return final plan or best attempt

        For ultra-short sections (< 1 bar), heuristic-only validation is used.
        The LLM judge can't meaningfully evaluate a 400ms pickup, so if the
        heuristic passes, the plan is auto-approved.

        Args:
            section_context: Complete section planning context

        Returns:
            IterationResult containing the final SectionCoordinationPlan

        Raises:
            ValueError: If section context is invalid
        """
        if not section_context.primary_focus_targets:
            raise ValueError("Section must have at least one primary_focus_target")

        logger.debug(
            f"Starting GroupPlanner orchestration for section: {section_context.section_id}"
        )

        # For ultra-short sections (< 1 bar), skip the LLM judge entirely.
        # A 400ms pickup can't be meaningfully "judged" for quality — heuristic
        # validation is sufficient. This saves tokens and avoids false rejections.
        if self._is_ultra_short_section(section_context):
            logger.info(
                f"⚡ Section {section_context.section_id} is ultra-short "
                f"({section_context.duration_ms}ms) — using heuristic-only approval"
            )
            result = await self._run_heuristic_only(section_context, run_id=run_id)
        else:
            result = await self._run_full_iteration(section_context, run_id=run_id)

        if result.success:
            logger.debug(
                f"✅ Section {section_context.section_id} succeeded: "
                f"{result.context.current_iteration} iterations, "
                f"score {result.context.final_verdict.score:.1f}"
                if result.context.final_verdict
                else f"✅ Section {section_context.section_id} succeeded"
            )
        else:
            logger.warning(
                f"⚠️ Section {section_context.section_id} completed without approval: "
                f"{result.context.current_iteration} iterations, "
                f"termination: {result.context.termination_reason}"
            )

        return result

    async def _run_full_iteration(
        self,
        section_context: SectionPlanningContext,
        *,
        run_id: str | None = None,
    ) -> IterationResult[SectionCoordinationPlan]:
        """Run full planner → heuristic → judge iteration loop.

        Args:
            section_context: Section planning context

        Returns:
            IterationResult with final plan
        """
        feedback_manager = FeedbackManager()
        controller = StandardIterationController[SectionCoordinationPlan](
            config=self.config,
            feedback_manager=feedback_manager,
        )
        initial_variables = self._build_planner_variables(section_context, run_id=run_id)
        validator = self._build_validator(section_context)

        return await controller.run(
            planner_spec=self.planner_spec,
            judge_spec=self.section_judge_spec,
            initial_variables=initial_variables,
            validator=validator,
            provider=self.provider,
            llm_logger=self.llm_logger,
        )

    async def _run_heuristic_only(
        self,
        section_context: SectionPlanningContext,
        *,
        run_id: str | None = None,
    ) -> IterationResult[SectionCoordinationPlan]:
        """Run planner with heuristic-only validation (no LLM judge).

        Used for ultra-short sections (< 1 bar) where LLM judge evaluation
        is not meaningful. If the heuristic validator passes, the plan is
        auto-approved.

        Args:
            section_context: Section planning context

        Returns:
            IterationResult with final plan
        """
        from pathlib import Path
        from typing import cast

        from twinklr.core.agents._paths import AGENTS_BASE_PATH
        from twinklr.core.agents.async_runner import AsyncAgentRunner
        from twinklr.core.agents.state import AgentState

        runner = AsyncAgentRunner(
            provider=self.provider,
            prompt_base_path=Path(AGENTS_BASE_PATH),
            llm_logger=self.llm_logger,
        )

        initial_variables = self._build_planner_variables(section_context, run_id=run_id)
        validator = self._build_validator(section_context)
        context = IterationContext()

        planner_state: AgentState | None = None
        if self.planner_spec.mode.value == "conversational":
            planner_state = AgentState(name=self.planner_spec.name)

        context.update_state(IterationState.PLANNING)
        context.increment_iteration()

        # Generate plan
        plan_result = await runner.run(
            spec=self.planner_spec, variables=initial_variables, state=planner_state
        )
        context.add_tokens(plan_result.tokens_used or 0)

        if not plan_result.success:
            context.update_state(IterationState.FAILED)
            context.termination_reason = f"Planner failed: {plan_result.error_message}"
            return IterationResult(
                success=False,
                plan=None,
                context=context,
                error_message=context.termination_reason,
            )

        plan = cast(SectionCoordinationPlan, plan_result.data)

        # Heuristic validation only
        context.update_state(IterationState.VALIDATING)
        validation_errors = validator(plan)

        if validation_errors:
            context.update_state(IterationState.VALIDATION_FAILED)
            logger.warning(
                f"Heuristic validation failed for ultra-short section "
                f"{section_context.section_id}: {len(validation_errors)} error(s)"
            )
            for i, err in enumerate(validation_errors[:5], 1):
                logger.warning(f"  [{i}] {err}")
            # For ultra-short sections, accept plan despite heuristic errors
            # (better to have an imperfect pickup than a pipeline failure)
            logger.info(
                f"⚡ Accepting ultra-short section {section_context.section_id} "
                f"despite {len(validation_errors)} heuristic error(s)"
            )

        # Auto-approve: heuristic pass (or accepted despite errors for pickup)
        context.update_state(IterationState.COMPLETE)
        return IterationResult(
            success=True,
            plan=plan,
            context=context,
        )

    def _build_planner_variables(
        self,
        section_context: SectionPlanningContext,
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Build variables for planner prompt.

        Args:
            section_context: Section planning context

        Returns:
            Variables dict for planner
        """
        from twinklr.core.agents.sequencer.group_planner.context_shaping import (
            shape_planner_context,
        )

        # Get shaped context (filtered/simplified for tokens)
        # Note: Taxonomy enums are injected automatically by async_runner via taxonomy_utils
        variables = shape_planner_context(section_context)
        if run_id:
            variables["run_id"] = run_id

        return variables

    def _build_validator(
        self,
        section_context: SectionPlanningContext,
    ) -> Callable[[SectionCoordinationPlan], list[str]]:
        """Build validator function for section plans.

        Args:
            section_context: Section planning context

        Returns:
            Validator function that returns list of error messages
        """
        # Create deterministic validator
        validator = SectionPlanValidator(
            choreo_graph=section_context.choreo_graph,
            template_catalog=section_context.template_catalog,
            timing_context=section_context.timing_context,
            recipe_catalog=section_context.recipe_catalog,
        )

        def validate(plan: SectionCoordinationPlan) -> list[str]:
            """Validate plan and return list of error messages."""
            # Deterministic ID normalization to recover common alias drift
            # (e.g., MATRICES -> MATRIX) without spending an iteration.
            self._normalize_group_target_ids(plan, section_context)

            # Snap all timing to section bounds: drop out-of-range placements
            # and clamp window ends.  Prevents PLACEMENT_OUTSIDE_SECTION and
            # TIMING_START_OUT_OF_BOUNDS without burning an iteration.
            self._snap_to_section_bounds(plan, section_context)

            # Drop coordination plans that have no usable content (empty
            # UNIFIED plans, plans left empty after other sanitizers, etc.).
            self._drop_empty_coordination_plans(plan, section_context)

            # Drop placements that duplicate targets already covered by a
            # SEQUENCED window in the same lane (prevents TARGET_SELF_OVERLAP).
            self._drop_sequenced_window_conflicts(plan, section_context)

            # Deterministic safety pass to reduce avoidable first-iteration failures.
            # This removes same-target placements that are too tightly packed for
            # categorical duration expansion, which commonly causes overlap errors.
            self._sanitize_same_target_spacing(plan, section_context)
            result = validator.validate(plan)

            # Return only ERROR severity issues as strings
            errors = [
                f"{issue.code}: {issue.message}"
                for issue in result.errors
                if issue.severity == ValidationSeverity.ERROR
            ]
            return errors

        return validate

    def _normalize_group_target_ids(
        self,
        plan: SectionCoordinationPlan,
        section_context: SectionPlanningContext,
    ) -> None:
        """Normalize near-miss group IDs to valid concrete display IDs.

        This is intentionally conservative and only applies when there is a
        single high-confidence match in the current choreography graph.
        """
        from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
        from twinklr.core.sequencer.vocabulary import TargetType

        valid_ids = {g.id for g in section_context.choreo_graph.groups}
        if not valid_ids:
            return

        def canonicalize(raw_id: str) -> str:
            token = raw_id.strip().upper()
            if token == "MATRICES" and "MATRIX" in valid_ids:
                return "MATRIX"
            if token == "WREATH" and "WREATHS" in valid_ids:
                return "WREATHS"
            if token == "ICICLE" and "ICICLES" in valid_ids:
                return "ICICLES"
            if token == "SNOWFLAKE" and "SNOWFLAKES" in valid_ids:
                return "SNOWFLAKES"
            if token in valid_ids:
                return token
            close = get_close_matches(token, sorted(valid_ids), n=1, cutoff=0.84)
            return close[0] if close else token

        for lane_plan in plan.lane_plans:
            for coord_plan in lane_plan.coordination_plans:
                # Normalize coordination targets
                normalized_targets: list[PlanTarget] = []
                for target in coord_plan.targets:
                    if target.type != TargetType.GROUP:
                        normalized_targets.append(target)
                        continue
                    normalized_id = canonicalize(target.id)
                    if normalized_id != target.id:
                        logger.warning(
                            "Normalized group target id in %s/%s: %s -> %s",
                            section_context.section_id,
                            lane_plan.lane.value,
                            target.id,
                            normalized_id,
                        )
                    normalized_targets.append(target.model_copy(update={"id": normalized_id}))
                coord_plan.targets = normalized_targets

                # Normalize placement targets
                normalized_placements = []
                for placement in coord_plan.placements:
                    ptarget = placement.target
                    if ptarget.type != TargetType.GROUP:
                        normalized_placements.append(placement)
                        continue
                    normalized_id = canonicalize(ptarget.id)
                    new_target = (
                        ptarget
                        if normalized_id == ptarget.id
                        else ptarget.model_copy(update={"id": normalized_id})
                    )
                    normalized_placements.append(
                        placement.model_copy(update={"target": new_target})
                    )
                coord_plan.placements = normalized_placements

    def _sanitize_same_target_spacing(
        self,
        plan: SectionCoordinationPlan,
        section_context: SectionPlanningContext,
    ) -> None:
        """Drop same-target placements that are too close to safely coexist.

        This is intentionally conservative and deterministic:
        - BASE/RHYTHM same-target starts must be >= 1 beat apart.
        - ACCENT same-target starts must be >= 2 beats apart.
        - If either placement is BURST, same-target starts must be >= 1 bar apart.
        """
        beats_per_bar = max(1, section_context.timing_context.beats_per_bar)

        for lane_plan in plan.lane_plans:
            # Track last kept start+duration per target across entire lane.
            last_kept: dict[str, tuple[int, EffectDuration]] = {}

            for coordination_plan in lane_plan.coordination_plans:
                if not coordination_plan.placements:
                    continue

                placements_sorted = sorted(
                    coordination_plan.placements,
                    key=lambda p: (p.start.bar, p.start.beat, p.placement_id),
                )
                kept = []
                for placement in placements_sorted:
                    target_key = f"{placement.target.type.value}:{placement.target.id}"
                    start_beat = (placement.start.bar - 1) * beats_per_bar + placement.start.beat

                    prev = last_kept.get(target_key)
                    keep = True
                    if prev is not None:
                        prev_start, prev_duration = prev
                        min_gap = beats_per_bar if lane_plan.lane == LaneKind.ACCENT else 1
                        if (
                            prev_duration == EffectDuration.BURST
                            or placement.duration == EffectDuration.BURST
                        ):
                            min_gap = beats_per_bar
                        if start_beat - prev_start < min_gap:
                            keep = False

                    if keep:
                        kept.append(placement)
                        last_kept[target_key] = (start_beat, placement.duration)

                coordination_plan.placements = kept

    def _drop_empty_coordination_plans(
        self,
        plan: SectionCoordinationPlan,
        section_context: SectionPlanningContext,
    ) -> None:
        """Drop coordination plans that have no usable content.

        A UNIFIED/COMPLEMENTARY plan with no placements does nothing.
        A SEQUENCED/CALL_RESPONSE/RIPPLE plan with no window does nothing.
        Leaving them in causes the judge to flag UNIFIED_EMPTY_PLACEMENTS
        errors that the LLM fails to self-correct.
        """
        for lane_plan in plan.lane_plans:
            original_count = len(lane_plan.coordination_plans)
            kept = []
            for coord_plan in lane_plan.coordination_plans:
                has_placements = bool(coord_plan.placements)
                has_window = coord_plan.window is not None
                if has_placements or has_window:
                    kept.append(coord_plan)
            lane_plan.coordination_plans = kept
            dropped = original_count - len(kept)
            if dropped:
                logger.debug(
                    "Dropped %d empty coordination plan(s) in %s/%s",
                    dropped,
                    section_context.section_id,
                    lane_plan.lane.value,
                )

    def _drop_sequenced_window_conflicts(
        self,
        plan: SectionCoordinationPlan,
        section_context: SectionPlanningContext,
    ) -> None:
        """Drop placements on targets already covered by a SEQUENCED window.

        A SEQUENCED window occupies ALL its targets for the full window
        duration.  A separate placement on the same target in the same
        lane causes TARGET_SELF_OVERLAP.  Rather than burning an
        iteration, remove the redundant placement deterministically.
        """
        for lane_plan in plan.lane_plans:
            # Collect target IDs covered by any SEQUENCED/CALL_RESPONSE/RIPPLE window
            window_target_ids: set[str] = set()
            for coord_plan in lane_plan.coordination_plans:
                if coord_plan.window is not None and coord_plan.coordination_mode in (
                    CoordinationMode.SEQUENCED,
                    CoordinationMode.CALL_RESPONSE,
                    CoordinationMode.RIPPLE,
                ):
                    for target in coord_plan.targets:
                        window_target_ids.add(f"{target.type.value}:{target.id}")

            if not window_target_ids:
                continue

            # Remove conflicting placements from ALL coord plans in this lane
            for coord_plan in lane_plan.coordination_plans:
                if not coord_plan.placements:
                    continue
                original_count = len(coord_plan.placements)
                coord_plan.placements = [
                    p
                    for p in coord_plan.placements
                    if f"{p.target.type.value}:{p.target.id}" not in window_target_ids
                ]
                dropped = original_count - len(coord_plan.placements)
                if dropped:
                    logger.debug(
                        "Dropped %d SEQUENCED-window conflict(s) in %s/%s "
                        "(targets already in window: %s)",
                        dropped,
                        section_context.section_id,
                        lane_plan.lane.value,
                        window_target_ids,
                    )

    def _compute_max_valid_bar(
        self,
        section_context: SectionPlanningContext,
    ) -> int:
        """Compute the last bar whose start falls within section bounds."""
        timing_ctx = section_context.timing_context
        section_end_ms = section_context.end_ms
        return max(
            (bar for bar, info in timing_ctx.bar_map.items() if info.start_ms < section_end_ms),
            default=max(timing_ctx.bar_map.keys()),
        )

    def _snap_to_section_bounds(
        self,
        plan: SectionCoordinationPlan,
        section_context: SectionPlanningContext,
    ) -> None:
        """Snap all timing references to valid section bounds.

        Handles two recurring LLM planning errors deterministically:
        1. Placements whose resolved start_ms >= section_end_ms → dropped
        2. SEQUENCED window ends past section end → clamped

        Uses millisecond resolution (not just bar numbers) to catch
        beat-level overflows where bar N is valid but beat 2+ of bar N
        resolves past section_end_ms.
        """
        from twinklr.core.sequencer.vocabulary.planning import PlanningTimeRef

        timing_ctx = section_context.timing_context
        section_end_ms = section_context.end_ms
        max_valid_bar = self._compute_max_valid_bar(section_context)

        for lane_plan in plan.lane_plans:
            for coord_plan in lane_plan.coordination_plans:
                # 1. Drop placements whose resolved start_ms is out of bounds
                if coord_plan.placements:
                    original_count = len(coord_plan.placements)
                    kept: list[Any] = []
                    for p in coord_plan.placements:
                        try:
                            start_ms = timing_ctx.resolve_planning_time_ref(p.start)
                        except (ValueError, KeyError):
                            kept.append(p)
                            continue
                        if start_ms < section_end_ms:
                            kept.append(p)
                    coord_plan.placements = kept
                    dropped = original_count - len(kept)
                    if dropped:
                        logger.debug(
                            "Dropped %d out-of-bounds placement(s) in %s/%s (section_end=%dms)",
                            dropped,
                            section_context.section_id,
                            lane_plan.lane.value,
                            section_end_ms,
                        )

                # 2. Clamp window end to max_valid_bar
                if coord_plan.window and coord_plan.window.end.bar > max_valid_bar:
                    old_end = coord_plan.window.end.bar
                    clamped_end = PlanningTimeRef(bar=max_valid_bar, beat=1)
                    coord_plan.window = coord_plan.window.model_copy(update={"end": clamped_end})
                    logger.debug(
                        "Clamped window end bar %d→%d in %s/%s",
                        old_end,
                        max_valid_bar,
                        section_context.section_id,
                        lane_plan.lane.value,
                    )
