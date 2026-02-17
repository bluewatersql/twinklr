"""GroupPlanner pipeline stage.

Wraps GroupPlannerOrchestrator for pipeline execution with FAN_OUT pattern.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from twinklr.core.agents.sequencer.group_planner.context import (
    SectionPlanningContext,
)
from twinklr.core.agents.sequencer.group_planner.orchestrator import (
    GroupPlannerOrchestrator,
)
from twinklr.core.pipeline.result import failure_result, success_result
from twinklr.core.sequencer.planning import GroupPlanSet, SectionCoordinationPlan
from twinklr.core.sequencer.planning.group_plan import NarrativeAssetDirective

if TYPE_CHECKING:
    from twinklr.core.agents.audio.lyrics.models import (
        KeyPhrase,
        LyricContextModel,
        StoryBeat,
    )
    from twinklr.core.agents.sequencer.group_planner.timing import TimingContext
    from twinklr.core.agents.shared.judge.controller import IterationResult
    from twinklr.core.audio.models.song_bundle import SongBundle
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult
    from twinklr.core.sequencer.planning import MacroSectionPlan
    from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
    from twinklr.core.sequencer.templates.group.models.display import DisplayGraph

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
        display_graph: DisplayGraph,
        template_catalog: TemplateCatalog,
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

            def extract_plan(
                r: IterationResult[SectionCoordinationPlan],
            ) -> SectionCoordinationPlan:
                """Extract plan from result (guaranteed non-None by execute_step).

                When deserialized from cache, IterationResult is loaded without
                the generic type parameter, so plan may be a raw dict instead
                of a SectionCoordinationPlan. Validate explicitly.
                """
                if r.plan is None:
                    raise ValueError("IterationResult.plan is None")
                if isinstance(r.plan, dict):
                    return SectionCoordinationPlan.model_validate(r.plan)
                return r.plan

            return await execute_step(
                stage_name=f"{self.name}_{section_id}",
                context=context,
                compute=lambda: orchestrator.run(section_context),
                result_extractor=extract_plan,
                result_type=IterationResult,
                cache_key_fn=lambda: orchestrator.get_cache_key(section_context),
                cache_version="1",
                cache_domain=self.name,  # Group all sections under "group_planner"
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
        lyric_context_model = context.get_state("lyric_context")

        if audio_bundle is None:
            raise ValueError("Missing 'audio_bundle' in context.state")

        # Build timing context from audio bundle with section bounds
        timing_context = self._build_timing_context(
            audio_bundle,
            section_id=input.section.section_id,
            section_start_ms=input.section.start_ms,
            section_end_ms=input.section.end_ms,
        )

        # Extract layer intents from macro plan
        layer_intents = self._extract_layer_intents(macro_plan)

        # Build section-scoped lyric context
        section_lyric_context = self._build_section_lyric_context(
            lyric_context_model,
            section_id=input.section.section_id,
            start_ms=input.section.start_ms,
            end_ms=input.section.end_ms,
        )

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
            theme=input.theme,
            motif_ids=input.motif_ids,
            palette=input.palette.model_dump() if input.palette else None,
            lyric_context=section_lyric_context,
        )

    def _build_timing_context(
        self,
        audio_bundle: SongBundle,
        *,
        section_id: str,
        section_start_ms: int,
        section_end_ms: int,
    ) -> TimingContext:
        """Build timing context from audio bundle with section bounds.

        Args:
            audio_bundle: SongBundle from audio analysis
            section_id: Current section identifier
            section_start_ms: Section start time in milliseconds
            section_end_ms: Section end time in milliseconds

        Returns:
            TimingContext with bar map and section bounds
        """
        from twinklr.core.agents.sequencer.group_planner.timing import (
            BarInfo,
            SectionBounds,
            TimingContext,
        )
        from twinklr.core.sequencer.templates.group.models import TimeRef, TimeRefKind

        timing_info = audio_bundle.timing
        tempo_bpm = audio_bundle.features.get("tempo_bpm", 120.0)
        beat_duration_ms = 60000.0 / tempo_bpm
        beats_per_bar_raw = audio_bundle.features.get("assumptions", {}).get("beats_per_bar")
        beats_per_bar: int
        if isinstance(beats_per_bar_raw, int) and beats_per_bar_raw > 0:
            beats_per_bar = beats_per_bar_raw
        else:
            logger.warning(
                "Derived timing meter missing for section '%s'; falling back to 4/4",
                section_id,
            )
            beats_per_bar = 4
        bar_duration_ms = beat_duration_ms * beats_per_bar

        # Build SECTION-RELATIVE bar_map
        # Bar 1 = section start, not song start
        # This matches LLM expectations (bar 1 is always section start)
        bar_map: dict[int, BarInfo] = {}
        current_ms = float(section_start_ms)  # Start from section start
        bar_num = 1
        while current_ms < section_end_ms:
            bar_map[bar_num] = BarInfo(
                bar=bar_num,
                start_ms=int(current_ms),
                duration_ms=int(bar_duration_ms),
            )
            current_ms += bar_duration_ms
            bar_num += 1

        # Build section bounds using MS TimeRefs (exact millisecond values)
        section_bounds = {
            section_id: SectionBounds(
                section_id=section_id,
                start=TimeRef(kind=TimeRefKind.MS, offset_ms=section_start_ms),
                end=TimeRef(kind=TimeRefKind.MS, offset_ms=section_end_ms),
            )
        }

        return TimingContext(
            song_duration_ms=int(timing_info.duration_ms),
            beats_per_bar=beats_per_bar,
            bar_map=bar_map,
            section_bounds=section_bounds,
        )

    def _build_section_lyric_context(
        self,
        lyric_context_model: LyricContextModel | None,
        *,
        section_id: str,
        start_ms: int,
        end_ms: int,
    ) -> dict[str, Any] | None:
        """Build section-scoped lyric context for narrative asset directives.

        Extracts story beats, key phrases, characters, and themes relevant
        to the current section from the full LyricContextModel.

        Uses a two-pass matching strategy:
        1. Primary: match by section_id (fast, exact)
        2. Fallback: match by timestamp overlap (resilient to ID mismatches)

        Args:
            lyric_context_model: LyricContextModel from lyrics analysis (or None)
            section_id: Current section identifier
            start_ms: Section start time in milliseconds
            end_ms: Section end time in milliseconds

        Returns:
            Section-scoped lyric context dict, or None if no lyrics available
        """
        if lyric_context_model is None:
            return None

        if not getattr(lyric_context_model, "has_lyrics", False):
            return None

        # Filter story beats to this section (by ID, then timestamp fallback)
        section_beats = []
        if lyric_context_model.story_beats:
            for beat in lyric_context_model.story_beats:
                if self._beat_matches_section(beat, section_id, start_ms, end_ms):
                    section_beats.append(
                        {
                            "beat_type": beat.beat_type,
                            "description": beat.description,
                            "visual_opportunity": beat.visual_opportunity,
                        }
                    )

        # Filter key phrases to this section (by ID, then timestamp fallback)
        section_phrases = []
        if lyric_context_model.key_phrases:
            for phrase in lyric_context_model.key_phrases:
                if self._phrase_matches_section(phrase, section_id, start_ms, end_ms):
                    section_phrases.append(
                        {
                            "text": phrase.text,
                            "visual_hint": phrase.visual_hint,
                            "emphasis": phrase.emphasis,
                        }
                    )

        # Skip if no section-specific content
        if not section_beats and not section_phrases:
            return None

        return {
            "has_narrative": lyric_context_model.has_narrative,
            "characters": lyric_context_model.characters or [],
            "themes": lyric_context_model.themes or [],
            "mood_arc": lyric_context_model.mood_arc or "",
            "story_beats": section_beats,
            "key_phrases": section_phrases,
        }

    @staticmethod
    def _beat_matches_section(
        beat: StoryBeat,
        section_id: str,
        start_ms: int,
        end_ms: int,
    ) -> bool:
        """Check if a story beat belongs to a section.

        Primary match: exact section_id match.
        Fallback: timestamp_range overlaps the section time window.

        Args:
            beat: StoryBeat with section_id and timestamp_range
            section_id: Target section identifier
            start_ms: Section start in milliseconds
            end_ms: Section end in milliseconds

        Returns:
            True if the beat matches this section
        """
        if beat.section_id == section_id:
            return True

        # Timestamp fallback — beat's timestamp_range overlaps section
        beat_start, beat_end = beat.timestamp_range
        return bool(beat_start < end_ms and beat_end > start_ms)

    @staticmethod
    def _phrase_matches_section(
        phrase: KeyPhrase,
        section_id: str,
        start_ms: int,
        end_ms: int,
    ) -> bool:
        """Check if a key phrase belongs to a section.

        Primary match: exact section_id match.
        Fallback: timestamp_ms falls within the section time window.

        Args:
            phrase: KeyPhrase with section_id and timestamp_ms
            section_id: Target section identifier
            start_ms: Section start in milliseconds
            end_ms: Section end in milliseconds

        Returns:
            True if the phrase matches this section
        """
        if phrase.section_id == section_id:
            return True

        # Timestamp fallback — phrase timestamp is within section bounds
        return bool(start_ms <= phrase.timestamp_ms < end_ms)

    def _extract_layer_intents(self, macro_plan: MacroSectionPlan | None) -> list[dict[str, Any]]:
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
        input: list[SectionCoordinationPlan],
        context: PipelineContext,
    ) -> StageResult[GroupPlanSet]:
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

            # Aggregate + deduplicate narrative directives across sections
            aggregated_narratives = self._aggregate_narrative_directives(input)

            # Create GroupPlanSet from section plans
            group_plan_set = GroupPlanSet(
                plan_set_id=self.plan_set_id,
                section_plans=input,
                narrative_assets=aggregated_narratives,
            )

            logger.debug(
                f"GroupPlanSet created: {len(group_plan_set.section_plans)} sections, "
                f"{len(aggregated_narratives)} narrative directives"
            )

            # Track metrics
            context.add_metric("group_plan_sections", len(group_plan_set.section_plans))
            context.add_metric("narrative_directives", len(aggregated_narratives))

            return success_result(group_plan_set, stage_name=self.name)

        except Exception as e:
            logger.exception("Aggregation failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    @staticmethod
    def _aggregate_narrative_directives(
        section_plans: list[SectionCoordinationPlan],
    ) -> list[NarrativeAssetDirective]:
        """Collect and deduplicate narrative directives across sections.

        Deduplicates by directive_id. When duplicates exist, the first occurrence
        is kept and section_ids are merged.

        Args:
            section_plans: List of SectionCoordinationPlan objects

        Returns:
            List of NarrativeAssetDirective with section_ids populated
        """

        # Collect directives by ID, tracking which sections reference each
        directives_by_id: dict[str, NarrativeAssetDirective] = {}
        section_map: dict[str, list[str]] = {}

        for plan in section_plans:
            # Handle both Pydantic model and dict (cache deserialization)
            if isinstance(plan, dict):
                section_id = plan.get("section_id", "unknown")
                raw_assets = plan.get("narrative_assets", [])
            else:
                section_id = getattr(plan, "section_id", "unknown")
                raw_assets = getattr(plan, "narrative_assets", [])

            for raw_directive in raw_assets:
                # Normalize to NarrativeAssetDirective if dict
                if isinstance(raw_directive, dict):
                    directive = NarrativeAssetDirective.model_validate(raw_directive)
                else:
                    directive = raw_directive

                did = directive.directive_id
                if did not in directives_by_id:
                    directives_by_id[did] = directive
                    section_map[did] = []
                section_map[did].append(section_id)

        # Build aggregated directives with section_ids populated
        aggregated = [
            d.model_copy(update={"section_ids": section_map[d.directive_id]})
            for d in directives_by_id.values()
        ]

        if aggregated:
            logger.debug(
                f"Aggregated {len(aggregated)} unique narrative directives "
                f"from {len(section_plans)} sections"
            )

        return aggregated
