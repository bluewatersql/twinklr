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
from twinklr.core.agents.prompts import spec_prompt_hash
from twinklr.core.agents.prompts.sanitize import sanitize_metadata_field
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.sequencer.moving_heads.context import MovingHeadPlanningContext
from twinklr.core.agents.sequencer.moving_heads.heuristic_validator import (
    create_validator_function,
)
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.agents.sequencer.moving_heads.moment_cues import (
    bind_lyric_moment_cues,
    unanswered_high_cues,
)
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
from twinklr.core.agents.sequencer.moving_heads.specs import (
    get_judge_spec,
    get_planner_spec,
)
from twinklr.core.agents.shared.judge.controller import (
    IterationConfig,
    IterationContext,
    IterationResult,
    StandardIterationController,
)
from twinklr.core.agents.shared.judge.feedback import FeedbackManager
from twinklr.core.agents.spec import AgentSpec

logger = logging.getLogger(__name__)


def cue_positions(context: MovingHeadPlanningContext) -> dict[str, str]:
    """Each lyric moment cue's nearest beat as `bar N beat B` on the bar grid
    (`BeatGrid.bar_and_beat`, the numbering the cue binder and the renderer use), by cue
    id; empty without a grid or cues."""
    grid, lyrics = context.beat_grid, context.lyric_context
    if grid is None or lyrics is None or not lyrics.moment_cues:
        return {}
    positions = {}
    for cue in lyrics.moment_cues:
        index = grid.nearest_beat_index(float(cue.timestamp_ms))
        position = None if index is None else grid.bar_and_beat(index)
        if position is not None:
            positions[cue.cue_id] = f"bar {position[0]} beat {position[1]}"
    return positions


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
        "song_title": sanitize_metadata_field(context.song_title),
        "song_artist": sanitize_metadata_field(context.song_artist),
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
        # Template descriptions (enriched metadata for informed selection)
        "template_descriptions": prompt_context.get("template_descriptions"),
        # Sections (with bar positions)
        "sections": prompt_context["song_structure"]["sections"],
        # The song's tail the beat grid does not reach, when it does not reach the end
        "beyond_grid": prompt_context["song_structure"]["beyond_grid"],
        # Audio profile (for initial iteration)
        "audio_profile": context.audio_profile if iteration == 0 else None,
        # Lyric context (for initial iteration), each cue's bar and beat on the bar grid
        "lyric_context": context.lyric_context if iteration == 0 else None,
        "cue_positions": cue_positions(context),
        # Macro plan guidance (always include for coordination)
        "macro_plan": prompt_context["macro_plan"],
        "macro_palette_arc": prompt_context["macro_palette_arc"],
        "macro_motif_continuity": prompt_context["macro_motif_continuity"],
        "macro_focal_arc": prompt_context["macro_focal_arc"],
        # How the show render adjusts intensity by the heads' focal role (show only)
        "head_focal_roles": prompt_context["head_focal_roles"],
        # What the rig can show of the song intent
        "rig_offer": prompt_context["rig_offer"],
        # Feedback (for refinement iterations)
        "feedback": feedback,
        "revision_focus": revision_focus,
    }

    return variables


def build_judge_variables(
    context: MovingHeadPlanningContext,
    plan: ChoreographyPlan,
    iteration: int,
    iteration_context: IterationContext,
) -> dict[str, Any]:
    """Build variables for judge prompt template.

    Args:
        context: MovingHead planning context
        plan: Choreography plan to judge
        iteration: Current iteration number
        iteration_context: Same-run verdict and revision history

    Returns:
        Dict of variables for judge prompt template
    """
    prompt_context = context.for_prompt()

    variables: dict[str, Any] = {
        # Plan to judge
        "plan": plan.model_dump(mode="json"),
        # Song structure
        "sections": prompt_context["song_structure"]["sections"],
        "beyond_grid": prompt_context["song_structure"]["beyond_grid"],
        "total_bars": context.total_bars,
        "tempo": context.tempo,
        "time_signature": context.time_signature,
        # Templates
        "available_templates": context.available_templates,
        # Iteration context
        "iteration": iteration,
        # Audio profile (for context, including planner_hints)
        "audio_profile": context.audio_profile,
        # Lyric moment cues, so the judge can see which the plan answers
        "lyric_context": context.lyric_context,
        "cue_positions": cue_positions(context),
        # Macro plan guidance (enriched with palette/motifs for alignment validation)
        "macro_plan": prompt_context["macro_plan"],
        "macro_palette_arc": prompt_context["macro_palette_arc"],
        "macro_motif_continuity": prompt_context["macro_motif_continuity"],
        "macro_focal_arc": prompt_context["macro_focal_arc"],
    }
    variables.update(iteration_context.judge_prompt_history())

    return variables


def normalize_plan(plan: ChoreographyPlan, context: MovingHeadPlanningContext) -> ChoreographyPlan:
    """What runs on every planner response before validation: canonical section ids, the
    lyric cues bound to their beats and single items the song cannot hold repaired
    (`bind_lyric_moment_cues`), then the colours and gobos the rig cannot show repaired
    (`repair_rig_intent`, when the run has the gate's offer)."""
    plan = bind_lyric_moment_cues(plan, context.lyric_context, context.beat_grid, context.sections)
    if context.rig_offer is None:
        return plan
    return repair_rig_intent(plan, context.rig_offer, context.palettes, context.beat_grid)


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
        - Model configuration
        - Planner and judge prompt-pack content

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
            "macro_plan": context.macro_plan.model_dump() if context.macro_plan else None,
            "fixtures": {
                "count": context.fixtures.count,
                "groups": context.fixtures.groups,
            },
            # These are prompt/validation inputs, not merely registry diagnostics.
            # Hash both the admitted IDs and the exact metadata snapshot so a
            # metadata-only library revision cannot reuse an older plan.
            "available_templates": context.available_templates,
            "template_descriptions": (
                [item.model_dump(mode="json") for item in context.template_descriptions]
                if context.template_descriptions is not None
                else None
            ),
            # The stops each section's palette roles resolve to: the macro plan names a
            # palette by id, and an edit of its stops changes the prompt and the repairs.
            "palettes": {
                section_id: palette.model_dump(mode="json")
                for section_id, palette in sorted(context.palettes.items())
            },
            # What the planner is told the rig can show, and what repair keeps.
            "rig_offer": (context.rig_offer.model_dump(mode="json") if context.rig_offer else None),
            # The show render adjusts intensity by these, and the prompt says so.
            "head_focal_roles": context.head_focal_roles,
            # Bar numbers in the plan name positions on this authoritative grid.
            "beat_grid": (context.beat_grid.model_dump(mode="json") if context.beat_grid else None),
            # None is also a valid macro result, so the experiment ablation must
            # remain distinguishable from a macro-enabled run that produced none.
            "macro_planning_enabled": context.macro_planning_enabled,
            "max_iterations": self.controller.config.max_iterations,
            "min_pass_score": self.controller.config.approval_score_threshold,
            "planner_model": self.planner_spec.model,
            "planner_reasoning_effort": self.planner_spec.reasoning_effort,
            "planner_temperature": self.planner_spec.temperature,
            "judge_model": self.judge_spec.model,
            "judge_reasoning_effort": self.judge_spec.reasoning_effort,
            "judge_temperature": self.judge_spec.temperature,
            "prompt_packs": spec_prompt_hash(
                self.prompt_base_path, self.planner_spec, self.judge_spec
            ),
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
        2. Normalise it: canonical section ids, repair of single items the song or the
           rig cannot hold, lyric cues bound to their beats (`normalize_plan`)
        3. Validate plan (heuristic validator)
        4. Evaluate plan (judge agent)
        5. Refine if needed (repeat with feedback, including what was repaired); a valid
           plan that leaves a HIGH lyric cue without an event is sent back before judging,
           at most once per run and only while iterations remain
        6. Return final plan or best attempt

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
        # Sections beyond the beat grid are not planned, so their cues are not advised.
        beyond_grid = context.song_structure()["beyond_grid"]
        unplannable = () if beyond_grid is None else tuple(beyond_grid["section_ids"])

        # Run iteration loop
        result = await self.controller.run(
            planner_spec=self.planner_spec,
            judge_spec=self.judge_spec,
            initial_variables=initial_variables,
            validator=validator,
            provider=self.provider,
            llm_logger=self.llm_logger,
            prompt_base_path=self.prompt_base_path,
            judge_context_builder=lambda plan, iteration, iteration_context: build_judge_variables(
                context, plan, iteration, iteration_context
            ),
            plan_normalizer=lambda plan: normalize_plan(plan, context),
            plan_repairs=lambda plan: [repair.describe() for repair in plan.repairs],
            plan_advisories=lambda plan: unanswered_high_cues(
                plan, context.lyric_context, context.sections, unplannable=unplannable
            ),
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
