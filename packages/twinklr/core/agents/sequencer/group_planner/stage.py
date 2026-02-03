"""GroupPlanner pipeline stage.

Wraps GroupPlannerOrchestrator for pipeline execution with FAN_OUT pattern.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from twinklr.core.agents.sequencer.group_planner.context import (
    SectionPlanningContext,
)
from twinklr.core.agents.sequencer.group_planner.models import GroupPlanSet
from twinklr.core.agents.sequencer.group_planner.orchestrator import (
    GroupPlannerOrchestrator,
)
from twinklr.core.pipeline.result import failure_result, success_result

if TYPE_CHECKING:
    from twinklr.core.agents.sequencer.group_planner.models import SectionCoordinationPlan
    from twinklr.core.agents.sequencer.macro_planner.models import MacroSectionPlan
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult

logger = logging.getLogger(__name__)


class GroupPlannerStage:
    """Pipeline stage for group planning (per-section).

    Designed for FAN_OUT execution pattern. Each invocation processes
    one MacroSectionPlan, builds its own SectionPlanningContext independently,
    and returns one SectionCoordinationPlan.

    Constructor args (configuration):
        - display_graph: DisplayGraph
        - template_catalog: TemplateCatalog

    State retrieved from PipelineContext (set by upstream stages):
        - audio_bundle: SongBundle (for building timing_context)
        - audio_profile: AudioProfileModel (optional, for enhanced context)
        - lyric_context: LyricContextModel (optional, for narrative context)
        - macro_plan: MacroPlan (for global_story, layering_plan)

    Usage with FAN_OUT:
        StageDefinition(
            id="groups",
            stage=GroupPlannerStage(
                display_graph=display_graph,
                template_catalog=template_catalog,
            ),
            pattern=ExecutionPattern.FAN_OUT,
            inputs=["sections"],  # List[MacroSectionPlan]
        )

    The pipeline executor will:
    1. Receive list of MacroSectionPlan from upstream
    2. Execute this stage once per section (in parallel)
    3. Each invocation builds its context independently (precisely scoped)
    4. Collect results into list of SectionCoordinationPlan

    Input: MacroSectionPlan (single section from MacroPlan)
    Output: SectionCoordinationPlan
    """

    def __init__(
        self,
        display_graph: Any,  # DisplayGraph - using Any to avoid circular import
        template_catalog: Any,  # TemplateCatalog
        max_iterations: int = 3,
        min_pass_score: float = 7.0,
    ) -> None:
        """Initialize group planner stage.

        Args:
            display_graph: Display group configuration
            template_catalog: Available templates for coordination
            max_iterations: Max refinement iterations per section (default: 3)
            min_pass_score: Min score for section approval (default: 7.0)
        """
        self.display_graph = display_graph
        self.template_catalog = template_catalog
        self.max_iterations = max_iterations
        self.min_pass_score = min_pass_score

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "group_planner"

    async def execute(
        self,
        input: MacroSectionPlan,
        context: PipelineContext,
    ) -> StageResult[SectionCoordinationPlan]:
        """Generate section coordination plan.

        Builds SectionPlanningContext from the MacroSectionPlan and
        shared context in PipelineContext.state, then runs the orchestrator.

        Args:
            input: MacroSectionPlan for one section
            context: Pipeline context with provider, config, and shared state

        Returns:
            StageResult containing SectionCoordinationPlan

        Side Effects:
            - Adds "group_planner_iterations_{section_id}" to context.metrics
            - Adds "group_planner_tokens_{section_id}" to context.metrics
        """
        from twinklr.core.agents.shared.judge.controller import IterationResult
        from twinklr.core.pipeline.execution import execute_step

        section_id = input.section.section_id

        try:
            logger.debug(f"Generating coordination plan for section: {section_id}")

            # Build section context (validates state presence)
            section_context = self._build_section_context(input, context)

            # Create orchestrator with pipeline context dependencies
            orchestrator = GroupPlannerOrchestrator(
                provider=context.provider,
                max_iterations=self.max_iterations,
                min_pass_score=self.min_pass_score,
                llm_logger=context.llm_logger,
            )

            def extract_plan(r: Any) -> SectionCoordinationPlan:
                """Extract plan from result (guaranteed non-None by execute_step)."""
                if r.plan is None:
                    raise ValueError("IterationResult.plan is None")
                result_plan: SectionCoordinationPlan = r.plan
                return result_plan

            return await execute_step(
                stage_name=f"{self.name}_{section_id}",
                context=context,
                compute=lambda: orchestrator.run(section_context),
                result_extractor=extract_plan,
                result_type=IterationResult,
                cache_key_fn=lambda: orchestrator.get_cache_key(section_context),
                cache_version="1",
            )

        except ValueError as e:
            logger.error(f"Invalid section context for {section_id}: {e}")
            return failure_result(f"Invalid section context: {e}", stage_name=self.name)
        except Exception as e:
            logger.exception(f"Section {section_id} planning failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    def _build_section_context(
        self, input: MacroSectionPlan, context: PipelineContext
    ) -> SectionPlanningContext:
        """Build section planning context from input and pipeline state.

        Args:
            input: MacroSectionPlan for this section
            context: Pipeline context with shared state

        Returns:
            SectionPlanningContext for orchestrator

        Raises:
            ValueError: If required state is missing
        """
        # Retrieve shared context from pipeline state
        audio_bundle = context.get_state("audio_bundle")
        macro_plan = context.get_state("macro_plan")

        if audio_bundle is None:
            raise ValueError("Missing 'audio_bundle' in context.state")

        # Build timing context from audio bundle
        timing_context = self._build_timing_context(audio_bundle)

        # Extract layer intents from macro plan
        layer_intents = self._extract_layer_intents(macro_plan)

        # Build SectionPlanningContext from MacroSectionPlan + constructor args
        return SectionPlanningContext(
            section_id=input.section.section_id,
            section_name=input.section.name,
            start_ms=input.section.start_ms,
            end_ms=input.section.end_ms,
            energy_target=input.energy_target.value,
            motion_density=input.motion_density.value,
            choreography_style=input.choreography_style.value,
            primary_focus_targets=input.primary_focus_targets,
            secondary_targets=input.secondary_targets,
            notes=input.notes,
            display_graph=self.display_graph,
            template_catalog=self.template_catalog,
            timing_context=timing_context,
            layer_intents=layer_intents,
        )

    def _build_timing_context(self, audio_bundle: Any) -> Any:
        """Build timing context from audio bundle.

        Args:
            audio_bundle: SongBundle from audio analysis

        Returns:
            TimingContext with bar map
        """
        from twinklr.core.agents.sequencer.group_planner.timing import (
            BarInfo,
            TimingContext,
        )

        timing_info = audio_bundle.timing
        tempo_bpm = audio_bundle.features.get("tempo_bpm", 120.0)
        beat_duration_ms = 60000.0 / tempo_bpm
        bar_duration_ms = beat_duration_ms * 4  # Assuming 4/4 time

        bar_map: dict[int, BarInfo] = {}
        current_ms = 0.0
        bar_num = 1
        while current_ms < timing_info.duration_ms:
            bar_map[bar_num] = BarInfo(
                bar=bar_num,
                start_ms=int(current_ms),
                duration_ms=int(bar_duration_ms),
            )
            current_ms += bar_duration_ms
            bar_num += 1

        return TimingContext(
            song_duration_ms=int(timing_info.duration_ms),
            beats_per_bar=4,
            bar_map=bar_map,
            section_bounds={},
        )

    def _extract_layer_intents(self, macro_plan: Any) -> list[dict[str, Any]]:
        """Extract layer intents from macro plan.

        Args:
            macro_plan: MacroPlan with optional layering_plan

        Returns:
            List of layer intent dicts (empty if no layering plan)
        """
        layer_intents: list[dict[str, Any]] = []
        if macro_plan and hasattr(macro_plan, "layering_plan") and macro_plan.layering_plan:
            layer_intents = [layer.model_dump() for layer in macro_plan.layering_plan.layers]
        return layer_intents


class GroupPlanAggregatorStage:
    """Pipeline stage that aggregates section plans into GroupPlanSet.

    Takes list of SectionCoordinationPlan (from FAN_OUT) and produces
    a single GroupPlanSet for holistic evaluation.

    Input: list[SectionCoordinationPlan] (from FAN_OUT results)
    Output: GroupPlanSet

    Example:
        StageDefinition(
            id="aggregate",
            stage=GroupPlanAggregatorStage(),
            inputs=["groups"],  # Output from FAN_OUT stage
        )
    """

    def __init__(self, plan_set_id: str = "default") -> None:
        """Initialize aggregator stage.

        Args:
            plan_set_id: ID for the resulting GroupPlanSet
        """
        self.plan_set_id = plan_set_id

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "group_plan_aggregator"

    async def execute(
        self,
        input: list[Any],  # list[SectionCoordinationPlan]
        context: PipelineContext,
    ) -> StageResult[Any]:  # StageResult[GroupPlanSet]
        """Aggregate section plans into GroupPlanSet.

        Args:
            input: List of SectionCoordinationPlan from FAN_OUT
            context: Pipeline context

        Returns:
            StageResult containing GroupPlanSet
        """
        try:
            if not input:
                return failure_result("No section plans to aggregate", stage_name=self.name)

            logger.debug(f"Aggregating {len(input)} section plans")

            # Create GroupPlanSet from section plans
            group_plan_set = GroupPlanSet(
                plan_set_id=self.plan_set_id,
                section_plans=input,
            )

            logger.debug(f"GroupPlanSet created: {len(group_plan_set.section_plans)} sections")

            # Track metrics
            context.add_metric("group_plan_sections", len(group_plan_set.section_plans))

            return success_result(group_plan_set, stage_name=self.name)

        except Exception as e:
            logger.exception("Aggregation failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)
