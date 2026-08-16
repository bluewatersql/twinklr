"""Moving head planner pipeline stage.

Wraps MovingHeadPlannerOrchestrator for pipeline execution.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult

logger = logging.getLogger(__name__)

# T4 canonicalizes section identities and binds lyric cues to the authoritative
# BeatGrid before validation/judging. Version 1 plans were cached before that seam.
MOVING_HEAD_CACHE_VERSION = "2"


class MovingHeadStage:
    """Pipeline stage for moving head choreography planning.

    Generates choreography using the MovingHead planner agent with V2 orchestrator.
    Takes audio bundle, audio profile, macro plan, and optional lyrics context to create
    a choreography plan that coordinates with the overall show strategy.

    Input: dict with keys:
        - "audio": SongBundle (from AudioAnalysisStage, for BeatGrid)
        - "profile": AudioProfileModel (from AudioProfileStage)
        - "lyrics": LyricContextModel | None (from LyricsStage, optional)
        - "macro": list[MacroSection] (from MacroPlannerStage; full plan is in state)
    Output: ChoreographyPlan

    State stored:
        - "choreography_plan": ChoreographyPlan (for downstream rendering)
        - "beat_grid": BeatGrid (for downstream rendering)
        - "mh_planning_context": MovingHeadPlanningContext (for debugging)

    Example:
        >>> stage = MovingHeadStage(
        ...     fixture_count=4,
        ...     available_templates=["sweep_lr_fan_pulse", "circle_fan_hold"],
        ... )
        >>> input = {
        ...     "audio": song_bundle,  # from AudioAnalysisStage
        ...     "profile": audio_profile,
        ...     "lyrics": lyric_context,  # optional, may be None
        ...     "macro": macro_sections,  # fan-out payload from MacroPlannerStage
        ... }
        >>> result = await stage.execute(input, context)
        >>> if result.success:
        ...     plan = result.output  # ChoreographyPlan
    """

    def __init__(
        self,
        fixture_count: int,
        available_templates: list[str],
        fixture_groups: list[dict[str, Any]] | None = None,
        max_iterations: int = 3,
        min_pass_score: float = 7.0,
        include_template_metadata: bool = True,
        section_id: str | None = None,
        regeneration_nonce: str | None = None,
        macro_planning_enabled: bool = True,
    ) -> None:
        """Initialize moving head planner stage.

        Args:
            fixture_count: Number of moving head fixtures
            available_templates: List of valid template IDs
            fixture_groups: Optional fixture group configurations
            max_iterations: Maximum refinement iterations (default: 3)
            min_pass_score: Minimum score for approval (default: 7.0)
            include_template_metadata: Load template descriptions from registry (default: True)
        """
        self.fixture_count = fixture_count
        self.available_templates = available_templates
        self.fixture_groups = fixture_groups or []
        self.max_iterations = max_iterations
        self.min_pass_score = min_pass_score
        self.include_template_metadata = include_template_metadata
        self.section_id = section_id
        self.regeneration_nonce = regeneration_nonce
        self.macro_planning_enabled = macro_planning_enabled

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "moving_head_planner"

    async def execute(
        self,
        input: dict[str, Any],
        context: PipelineContext,
    ) -> StageResult[ChoreographyPlan]:
        """Generate choreography plan for moving heads.

        Args:
            input: Dict with keys:
                - "audio": SongBundle (from AudioAnalysisStage)
                - "profile": AudioProfileModel (from AudioProfileStage)
                - "lyrics": LyricContextModel | None (from LyricsStage, optional)
                - "macro": list[MacroSection] | None (from MacroPlannerStage)
            context: Pipeline context with provider and config

        Returns:
            StageResult containing ChoreographyPlan

        Side Effects:
            - Stores "choreography_plan" in context.state
            - Stores "beat_grid" in context.state (for downstream rendering)
            - Stores "mh_planning_context" in context.state
            - Adds "mh_iterations" to context.metrics
            - Adds "mh_tokens" to context.metrics
            - Adds "mh_score" to context.metrics (if available)
            - Adds "mh_from_cache" to context.metrics
            - Adds "mh_section_count" to context.metrics
        """
        from twinklr.core.agents.sequencer.moving_heads.context import (
            FixtureContext,
            MovingHeadPlanningContext,
        )
        from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
        from twinklr.core.agents.sequencer.moving_heads.orchestrator import (
            MovingHeadPlannerOrchestrator,
        )
        from twinklr.core.agents.sequencer.moving_heads.specs import (
            get_judge_spec,
            get_planner_spec,
        )
        from twinklr.core.agents.shared.judge.controller import IterationResult
        from twinklr.core.pipeline.execution import execute_step
        from twinklr.core.pipeline.result import failure_result

        try:
            # Extract inputs per pipeline stage contract
            # inputs=["audio", "profile", "lyrics", "macro"]
            audio_bundle = input["audio"]  # SongBundle from AudioAnalysisStage
            audio_profile = input["profile"]
            lyric_context = input.get("lyrics")  # May be None (conditional stage)
            from twinklr.core.sequencer.planning import MacroPlan

            macro_state = context.get_state("macro_plan")
            macro_plan = (
                MacroPlan.model_validate(
                    macro_state.model_dump() if hasattr(macro_state, "model_dump") else macro_state
                )
                if macro_state is not None
                else None
            )
            if self.section_id is not None:
                audio_profile, lyric_context, _ = self._select_section_inputs(
                    audio_profile, lyric_context, input.get("macro"), self.section_id
                )

            # Build BeatGrid from audio bundle for downstream rendering
            from twinklr.core.sequencer.timing.beat_grid import BeatGrid

            beat_grid = context.get_state("beat_grid")
            if beat_grid is None:
                beat_grid = BeatGrid.from_song_features(
                    audio_bundle.features,
                    duration_ms=getattr(getattr(audio_bundle, "timing", None), "duration_ms", None),
                )
                context.set_state("beat_grid", beat_grid)
            logger.debug(
                f"Built beat_grid: tempo={beat_grid.tempo_bpm} BPM, "
                f"total_bars={beat_grid.total_bars}"
            )

            # Build fixture context
            fixture_context = FixtureContext(
                count=self.fixture_count,
                groups=self.fixture_groups,
            )

            # Build template descriptions from registry metadata
            template_descriptions = (
                self._build_template_descriptions() if self.include_template_metadata else None
            )

            # Build planning context with macro plan coordination
            planning_context = MovingHeadPlanningContext(
                audio_profile=audio_profile,
                lyric_context=lyric_context,
                fixtures=fixture_context,
                # Same grid the renderer places effects on, so the bar numbers the
                # planner produces name the instants the renderer will use.
                beat_grid=beat_grid,
                available_templates=self.available_templates,
                macro_plan=macro_plan,
                macro_planning_enabled=self.macro_planning_enabled,
                template_descriptions=template_descriptions,
            )

            # Store planning context for debugging
            context.set_state("mh_planning_context", planning_context)

            # Get max_iterations from job config if available
            max_iterations = self.max_iterations
            if hasattr(context, "job_config") and context.job_config:
                max_iterations = getattr(
                    context.job_config.agent, "max_iterations", self.max_iterations
                )

            # Create orchestrator with pipeline context dependencies
            orchestrator = MovingHeadPlannerOrchestrator(
                provider=context.provider,
                planner_spec=get_planner_spec(config=context.job_config.agent.plan_agent),
                judge_spec=get_judge_spec(config=context.job_config.agent.judge_agent),
                max_iterations=max_iterations,
                min_pass_score=self.min_pass_score,
                llm_logger=context.llm_logger,
            )

            def extract_plan(r: Any) -> ChoreographyPlan:
                """Extract choreography plan from IterationResult."""
                from twinklr.core.agents.shared.judge.controller import IterationResult

                normalized_result = IterationResult.model_validate(r) if isinstance(r, dict) else r
                plan = normalized_result.plan
                if plan is None:
                    raise ValueError("IterationResult.plan is None")

                return ChoreographyPlan.model_validate(plan)

            # Execute with caching and automatic metrics/state handling
            return await execute_step(
                stage_name=self.name,
                context=context,
                compute=lambda: orchestrator.run(planning_context),
                result_extractor=extract_plan,
                result_type=IterationResult,
                cache_key_fn=lambda: self._cache_key(orchestrator, planning_context),
                cache_version=MOVING_HEAD_CACHE_VERSION,
                state_handler=self._handle_state,
                metrics_handler=self._handle_metrics,
            )

        except KeyError as e:
            logger.error(f"Missing required input: {e}")
            return failure_result(f"Missing required input: {e}", stage_name=self.name)
        except Exception as e:
            logger.exception("Moving head planning failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    async def _cache_key(self, orchestrator: Any, planning_context: Any) -> str:
        base = cast("str", await orchestrator.get_cache_key(planning_context))
        if self.regeneration_nonce is None:
            return base
        return hashlib.sha256(f"{base}:{self.regeneration_nonce}".encode()).hexdigest()

    @staticmethod
    def _select_section_inputs(
        audio_profile: Any,
        lyric_context: Any,
        macro_plan: Any,
        section_id: str,
    ) -> tuple[Any, Any, Any]:
        """Restrict only the planning input; deterministic audio/BeatGrid stay whole."""
        matches = [
            section
            for section in audio_profile.structure.sections
            if section.section_id == section_id
        ]
        if not matches:
            raise ValueError(f"Unknown section_id {section_id!r}; use the canonical unique ID")
        section = matches[0]
        structure = audio_profile.structure.model_copy(update={"sections": [section]})
        energy_profile = audio_profile.energy_profile.model_copy(
            update={
                "section_profiles": [
                    profile
                    for profile in audio_profile.energy_profile.section_profiles
                    if profile.section_id == section_id
                ]
            }
        )
        selected_profile = audio_profile.model_copy(
            update={"structure": structure, "energy_profile": energy_profile}
        )
        selected_macro = (
            [item for item in macro_plan if item.section.section_id == section_id]
            if macro_plan is not None
            else None
        )
        if lyric_context is None:
            return selected_profile, None, selected_macro

        def in_section(item: Any) -> bool:
            item_section_id = getattr(item, "section_id", None)
            if item_section_id is not None:
                return bool(item_section_id == section_id)
            timestamp = getattr(item, "timestamp_ms", None)
            return timestamp is None or section.start_ms <= timestamp <= section.end_ms

        selected_lyrics = lyric_context.model_copy(
            update={
                "story_beats": (
                    [item for item in lyric_context.story_beats if in_section(item)]
                    if lyric_context.story_beats is not None
                    else None
                ),
                "key_phrases": [item for item in lyric_context.key_phrases if in_section(item)],
                "moment_cues": (
                    [item for item in lyric_context.moment_cues if in_section(item)]
                    if lyric_context.moment_cues is not None
                    else None
                ),
            }
        )
        return selected_profile, selected_lyrics, selected_macro

    def _build_template_descriptions(self) -> list[Any] | None:
        """Load template metadata from the registry for prompt enrichment.

        Returns:
            List of TemplateDescription objects, or None if registry not available.
        """
        from twinklr.core.agents.sequencer.moving_heads.context import TemplateDescription

        try:
            from twinklr.core.sequencer.moving_heads.templates.library import REGISTRY

            descriptions: list[TemplateDescription] = []
            for tid in self.available_templates:
                try:
                    doc = REGISTRY.get(tid, deep_copy=False)
                    tmpl = doc.template
                    meta = tmpl.metadata

                    descriptions.append(
                        TemplateDescription(
                            template_id=tid,
                            name=tmpl.name,
                            description=meta.description if meta else None,
                            tags=list(meta.tags) if meta and meta.tags else [],
                            energy_range=meta.energy_range if meta else None,
                            recommended_sections=list(meta.recommended_sections)
                            if meta and meta.recommended_sections
                            else [],
                        )
                    )
                except Exception:
                    descriptions.append(TemplateDescription(template_id=tid, name=tid))

            return descriptions if descriptions else None
        except Exception:
            logger.debug("Template registry not available for metadata extraction")
            return None

    def _handle_state(self, result: Any, context: PipelineContext) -> None:
        """Store choreography plan in state for downstream stages."""
        from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan

        plan = result.get("plan") if isinstance(result, dict) else getattr(result, "plan", None)
        if plan:
            validated_plan = ChoreographyPlan.model_validate(plan)
            context.set_state("choreography_plan", validated_plan)
            self._write_checkpoint(validated_plan, context)

    def _write_checkpoint(self, plan: ChoreographyPlan, context: PipelineContext) -> None:
        """Serialize today's plan for `twinklr eval-report` (P1P-T10).

        Historical checkpoints used a `templates:[...]` list shape that today's
        `PlanSection` model no longer has; this writes `plan.model_dump()` directly,
        which is exactly what `collect.extract_plan` already validates against.
        """
        if not context.job_config.write_checkpoint or context.output_dir is None:
            return
        checkpoint_path = context.output_dir / "checkpoints" / "plans" / "final.json"
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_data = {
            "run_id": context.session.session_id,
            "plan": plan.model_dump(mode="json"),
        }
        checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2), encoding="utf-8")

    def _handle_metrics(self, result: Any, context: PipelineContext) -> None:
        """Track iteration metrics (extends defaults from execute_step)."""
        from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan

        if isinstance(result, dict):
            plan = result.get("plan")
            ctx = result.get("context", {})
        else:
            plan = getattr(result, "plan", None)
            ctx = getattr(result, "context", None)

        # Track section count
        if plan:
            sections = ChoreographyPlan.model_validate(plan).sections
            context.add_metric("mh_section_count", len(sections))

        # Track iteration details
        if ctx:
            if isinstance(ctx, dict):
                iterations = ctx.get("current_iteration", 0)
                tokens = ctx.get("total_tokens_used", 0)
                final_verdict = ctx.get("final_verdict")
            else:
                iterations = getattr(ctx, "current_iteration", 0)
                tokens = getattr(ctx, "total_tokens_used", 0)
                final_verdict = getattr(ctx, "final_verdict", None)

            context.add_metric("mh_iterations", iterations)
            context.add_metric("mh_tokens", tokens)

            # Track final score if available
            if final_verdict:
                if isinstance(final_verdict, dict):
                    score = final_verdict.get("score")
                else:
                    score = getattr(final_verdict, "score", None)
                if score is not None:
                    context.add_metric("mh_score", score)
